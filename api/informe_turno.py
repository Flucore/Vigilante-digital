"""Informe de turno en PDF para el panel de operador.

Lo genera /operator/api/shift/export.pdf con los eventos que el panel tiene
en memoria: período cubierto, resumen por cámara y una fila por evento con
la hora, el lugar, el estado del aviso por correo, la hora de atención y la
captura del momento de la caída.

No incluye rutas internas del equipo (captura, video, foto del runner) ni la
duración del episodio: hoy es la del fragmento y no la de la caída (D7).
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as _esc

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# Mismos nombres en español que la bitácora del panel.
_EVENT_LABELS = {
    "fall": "Caída",
    "caída": "Caída",
    "perimeter_breach": "Intrusión de perímetro",
    "after_hours_motion": "Movimiento fuera de horario",
    "zone_occupancy": "Ocupación de zona",
    "manual_alert": "Alerta manual",
}

_INK = colors.HexColor("#111827")
_MUTED = colors.HexColor("#5B6470")
_LINE = colors.HexColor("#D9DDE3")
_HEAD_BG = colors.HexColor("#F3F4F6")
_ALERT = colors.HexColor("#B42318")
_OK = colors.HexColor("#067647")

_THUMB_W = 34 * mm
_THUMB_H = 25.5 * mm


def _tz(tz_name: str):
    """Zona horaria del config; si no se puede cargar, la del equipo."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        return datetime.now().astimezone().tzinfo


def _fmt(ts: Optional[float], tz, pattern: str = "%H:%M:%S") -> str:
    """Epoch → texto en hora local, 24 h."""
    if ts is None:
        return "—"
    return datetime.fromtimestamp(float(ts), tz=tz).strftime(pattern)


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    mk = lambda name, **kw: ParagraphStyle(name, parent=base, alignment=TA_LEFT, **kw)
    return {
        "title": mk("title", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=_INK),
        "sub": mk("sub", fontSize=10.5, leading=14, textColor=_MUTED),
        "h2": mk("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                 textColor=_INK, spaceBefore=10, spaceAfter=4),
        "cell": mk("cell", fontSize=8.8, leading=11, textColor=_INK),
        "cell_muted": mk("cell_muted", fontSize=8.3, leading=10.5, textColor=_MUTED),
        "head": mk("head", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=_MUTED),
        "note": mk("note", fontSize=8, leading=10.5, textColor=_MUTED),
    }


def _thumb(path: Any) -> Any:
    """Miniatura de la captura (o un guion si no hay)."""
    if path and Path(str(path)).is_file():
        try:
            return Image(str(path), width=_THUMB_W, height=_THUMB_H, kind="proportional")
        except Exception:
            pass
    return "—"


def _table_style(header_rows: int = 1) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), _HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def build_shift_pdf(
    events: List[Dict[str, Any]],
    cameras: Dict[str, Dict[str, Any]],
    *,
    facility: str,
    tz_name: str,
    from_ts: float,
    to_ts: float,
    generated_ts: float,
) -> bytes:
    """Arma el PDF del turno y retorna sus bytes.

    events: eventos del panel en el período, del más antiguo al más reciente
    (timestamp epoch, camera_id, zone, event_type, correo, captura,
    acknowledged_at). cameras: estado del panel (name, zone por cámara).
    """
    tz = _tz(tz_name)
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title="Informe de turno — Vigía Digital", author="Vigía Digital",
    )
    width = doc.width
    story: List[Any] = []

    # Encabezado
    story.append(Paragraph("Vigía Digital · Informe de turno", st["title"]))
    if facility:
        story.append(Paragraph(_esc(facility), st["sub"]))
    story.append(Spacer(1, 3 * mm))
    period = Table([
        ["Período cubierto",
         f"Desde {_fmt(from_ts, tz, '%d-%m-%Y %H:%M:%S')} "
         f"hasta {_fmt(to_ts, tz, '%d-%m-%Y %H:%M:%S')}"],
        ["Generado", _fmt(generated_ts, tz, "%d-%m-%Y %H:%M:%S")],
        ["Zona horaria", tz_name],
    ], colWidths=[34 * mm, width - 34 * mm])
    period.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), _INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    story.append(period)

    # Resumen
    attended = sum(1 for e in events if e.get("acknowledged_at"))
    story.append(Paragraph("Resumen", st["h2"]))
    summary = Table(
        [["Eventos", "Atendidos", "Pendientes"],
         [str(len(events)), str(attended), str(len(events) - attended)]],
        colWidths=[width / 3] * 3,
    )
    summary.setStyle(_table_style())
    summary.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), _MUTED),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 15),
        ("LEADING", (0, 1), (-1, 1), 18),
        ("TEXTCOLOR", (2, 1), (2, 1), _ALERT if len(events) - attended else _INK),
    ]))
    story.append(summary)

    # Por cámara (todas las registradas, también las que no tuvieron eventos)
    story.append(Paragraph("Eventos por cámara", st["h2"]))
    rows = [[Paragraph("Cámara", st["head"]), Paragraph("Ubicación", st["head"]),
             Paragraph("Eventos", st["head"])]]
    for cam_id, cam in sorted(cameras.items(), key=lambda kv: kv[1].get("name") or kv[0]):
        n = sum(1 for e in events if e.get("camera_id") == cam_id)
        rows.append([Paragraph(_esc(str(cam.get("name") or cam_id)), st["cell"]),
                     Paragraph(_esc(str(cam.get("zone") or "—")), st["cell_muted"]),
                     str(n)])
    by_cam = Table(rows, colWidths=[width * 0.45, width * 0.40, width * 0.15], repeatRows=1)
    by_cam.setStyle(_table_style())
    by_cam.setStyle(TableStyle([("FONTSIZE", (2, 1), (2, -1), 9)]))
    story.append(by_cam)

    # Detalle
    story.append(Paragraph("Detalle de eventos", st["h2"]))
    if not events:
        story.append(Paragraph("Sin eventos en el período.", st["cell_muted"]))
    else:
        rows = [[Paragraph(h, st["head"]) for h in
                 ("N°", "Hora", "Lugar", "Evento", "Aviso por correo", "Atención", "Captura")]]
        for i, e in enumerate(events, 1):
            cam = cameras.get(e.get("camera_id"), {})
            place = str(cam.get("name") or e.get("camera_name") or e.get("camera_id") or "—")
            zone = e.get("zone") or cam.get("zone")
            ack = e.get("acknowledged_at")
            label = _EVENT_LABELS.get(str(e.get("event_type", "")).lower(), "Evento")
            rows.append([
                str(i),
                _fmt(e.get("timestamp"), tz),
                Paragraph(_esc(place) + (f"<br/><font color='#5B6470'>{_esc(str(zone))}</font>" if zone else ""),
                          st["cell"]),
                Paragraph(label, st["cell"]),
                Paragraph(_esc(str(e.get("correo") or "—")), st["cell_muted"]),
                Paragraph(f"<font color='#067647'><b>Atendida</b></font><br/>{_fmt(ack, tz)}"
                          if ack else "<font color='#B42318'><b>Pendiente</b></font>",
                          st["cell"]),
                _thumb(e.get("captura")),
            ])
        fixed = 8 * mm + 15 * mm + 20 * mm + 20 * mm + _THUMB_W + 10
        detail = Table(rows, repeatRows=1, colWidths=[
            8 * mm, 15 * mm, (width - fixed) * 0.55, 20 * mm,
            (width - fixed) * 0.45, 20 * mm, _THUMB_W + 10,
        ])
        detail.setStyle(_table_style())
        detail.setStyle(TableStyle([("FONTSIZE", (0, 1), (1, -1), 8.8)]))
        story.append(detail)

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Registro generado automáticamente por el panel de operador a partir de los eventos "
        "del turno. Horas en formato 24 h, zona horaria indicada arriba.", st["note"]))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTED)
        canvas.drawString(16 * mm, 10 * mm,
                          "Vigía Digital · prototipo académico, INACAP 2026")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
