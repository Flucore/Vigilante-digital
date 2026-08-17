-- =============================================================================
-- Vigilante Digital v2.0 — Esquema de Base de Datos Forense
-- PostgreSQL 14+ recomendado · TimescaleDB opcional
-- =============================================================================
-- Uso:
--   psql -U postgres -d vigilante -f outputs/forensic_schema.sql
-- Con TimescaleDB:
--   descomentarizar la sección "TIMESCALEDB" al final del archivo.
-- =============================================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- =============================================================================
-- TABLA: cameras
-- Registro de todas las cámaras del sistema.
-- =============================================================================
CREATE TABLE IF NOT EXISTS cameras (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    zone            TEXT NOT NULL DEFAULT '',
    sector          TEXT NOT NULL DEFAULT '',
    client_id       TEXT NOT NULL DEFAULT 'UNKNOWN',
    location_meta   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE cameras IS 'Registro de cámaras configuradas en el sistema Vigilante Digital.';

-- =============================================================================
-- TABLA: detections
-- Metadatos de detección por frame (alimentada por MetadataIndexer).
-- Cada fila = un objeto detectado en un frame específico.
-- =============================================================================
CREATE TABLE IF NOT EXISTS detections (
    id              UUID         NOT NULL DEFAULT gen_random_uuid(),
    camera_id       TEXT         NOT NULL,
    timestamp       TIMESTAMPTZ  NOT NULL,
    frame_idx       INTEGER      NOT NULL,
    object_class    TEXT         NOT NULL,
    confidence      NUMERIC(6,4) NOT NULL DEFAULT 0,
    bbox_xmin       INTEGER      NOT NULL DEFAULT 0,
    bbox_ymin       INTEGER      NOT NULL DEFAULT 0,
    bbox_xmax       INTEGER      NOT NULL DEFAULT 0,
    bbox_ymax       INTEGER      NOT NULL DEFAULT 0,
    color_label     TEXT         NOT NULL DEFAULT 'unknown',
    track_id        INTEGER,
    schema_version  TEXT         NOT NULL DEFAULT '2.0',
    metadata        JSONB        NOT NULL DEFAULT '{}',
    PRIMARY KEY (id, timestamp)   -- compuesto para TimescaleDB
);

COMMENT ON TABLE detections IS
    'Índice de detecciones por frame. Base del módulo de Auditoría Forense. '
    'Alimentada por MetadataIndexer vía batch_processor.py o runner.py.';

-- Índices de búsqueda frecuente
CREATE INDEX IF NOT EXISTS idx_det_timestamp    ON detections (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_det_camera       ON detections (camera_id);
CREATE INDEX IF NOT EXISTS idx_det_class        ON detections (object_class);
CREATE INDEX IF NOT EXISTS idx_det_color        ON detections (color_label);
CREATE INDEX IF NOT EXISTS idx_det_camera_ts    ON detections (camera_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_det_class_color  ON detections (object_class, color_label);

-- =============================================================================
-- TABLA: events
-- Eventos confirmados (caída, intrusión, movimiento fuera de horario, etc.).
-- Alimentada por EventLogger vía runner.py y batch_processor.py.
-- =============================================================================
CREATE TABLE IF NOT EXISTS events (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    camera_id       TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ,
    duration_seconds NUMERIC(10,3),
    alert_level     INTEGER     NOT NULL DEFAULT 1  CHECK (alert_level BETWEEN 1 AND 3),
    photo_path      TEXT,
    pdf_path        TEXT,
    photo_hash      TEXT,      -- SHA-256 del archivo de evidencia
    acknowledged    BOOLEAN     NOT NULL DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    compliance      JSONB       NOT NULL DEFAULT '{}',
    schema_version  TEXT        NOT NULL DEFAULT '2.0',
    metadata        JSONB       NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE events IS
    'Eventos de seguridad confirmados. alert_level: 1=log, 2=notify, 3=critical(bocina). '
    'Cumple IEC 62676 y cadena de custodia ISO 27001.';

CREATE INDEX IF NOT EXISTS idx_evt_camera    ON events (camera_id);
CREATE INDEX IF NOT EXISTS idx_evt_type      ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_evt_start     ON events (start_time DESC);
CREATE INDEX IF NOT EXISTS idx_evt_level     ON events (alert_level);
CREATE INDEX IF NOT EXISTS idx_evt_acked     ON events (acknowledged);
CREATE INDEX IF NOT EXISTS idx_evt_camera_ts ON events (camera_id, start_time DESC);

-- =============================================================================
-- TABLA: audit_queries
-- Cadena de custodia: toda consulta a la UI queda registrada.
-- Requerido por ISO 27001 y Ley 21.459 (acceso a sistemas).
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_queries (
    id              UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         TEXT        NOT NULL DEFAULT 'anonymous',
    user_ip         TEXT,
    endpoint        TEXT        NOT NULL,
    query_text      TEXT,
    query_params    JSONB       NOT NULL DEFAULT '{}',
    result_count    INTEGER     NOT NULL DEFAULT 0,
    queried_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit_queries IS
    'Registro de todas las consultas realizadas al sistema forense. '
    'Cadena de custodia ISO 27001 / Ley 21.459.';

CREATE INDEX IF NOT EXISTS idx_aq_queried_at ON audit_queries (queried_at DESC);
CREATE INDEX IF NOT EXISTS idx_aq_user       ON audit_queries (user_id);

-- =============================================================================
-- VISTA: recent_events_summary
-- Vista de conveniencia para el panel de operador.
-- =============================================================================
CREATE OR REPLACE VIEW recent_events_summary AS
SELECT
    e.id,
    e.camera_id,
    c.name        AS camera_name,
    c.zone,
    c.sector,
    e.event_type,
    e.start_time,
    e.duration_seconds,
    e.alert_level,
    e.photo_path,
    e.acknowledged,
    e.schema_version
FROM events e
LEFT JOIN cameras c ON c.id = e.camera_id
ORDER BY e.start_time DESC;

COMMENT ON VIEW recent_events_summary IS
    'Vista de eventos recientes con información de cámara. Uso en API y panel de operador.';

-- =============================================================================
-- VISTA: detections_summary_by_class
-- Resumen de detecciones por clase y cámara (última hora).
-- =============================================================================
CREATE OR REPLACE VIEW detections_summary_by_class AS
SELECT
    camera_id,
    object_class,
    color_label,
    COUNT(*)                             AS total,
    ROUND(AVG(confidence)::NUMERIC, 3)  AS avg_confidence,
    MAX(timestamp)                       AS last_seen
FROM detections
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY camera_id, object_class, color_label
ORDER BY total DESC;

-- =============================================================================
-- FUNCIÓN: update_updated_at()
-- Trigger para actualizar updated_at automáticamente.
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_cameras_updated_at ON cameras;
CREATE TRIGGER trg_cameras_updated_at
    BEFORE UPDATE ON cameras
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- POLÍTICA DE RETENCIÓN (comentada — ejecutar manualmente según cliente)
-- Ley 19.628 / 21.663: retención máxima configurable.
-- =============================================================================
-- DELETE FROM detections WHERE timestamp < NOW() - INTERVAL '30 days';
-- DELETE FROM events     WHERE start_time < NOW() - INTERVAL '30 days';

-- =============================================================================
-- TIMESCALEDB (descomentarizar si está instalado)
-- Convierte 'detections' en hypertable para máximo rendimiento en series temporales.
-- =============================================================================
-- SELECT create_hypertable(
--     'detections', 'timestamp',
--     chunk_time_interval => INTERVAL '1 day',
--     if_not_exists => TRUE
-- );
-- SELECT add_compression_policy('detections', INTERVAL '7 days');
-- SELECT add_retention_policy('detections', INTERVAL '30 days');
