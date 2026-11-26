"""Reporte de trazabilidad de un expediente en PDF.

Función pura: recibe los datos que ya devuelve el detalle del expediente (los que el actor
puede ver) y la comprobación de la bitácora, y devuelve los bytes del PDF.
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_LIMA = ZoneInfo("America/Lima")
_ESTILOS = getSampleStyleSheet()
_CUERPO = ParagraphStyle("cuerpo", parent=_ESTILOS["BodyText"], fontSize=9, leading=12)
_PEQUENO = ParagraphStyle("pequeno", parent=_CUERPO, fontSize=7.5, leading=9.5)
_H1 = ParagraphStyle("h1", parent=_ESTILOS["Title"], fontSize=16, alignment=0)
_H2 = ParagraphStyle("h2", parent=_ESTILOS["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)


def _p(texto, estilo=_CUERPO) -> Paragraph:
    return Paragraph(escape(str(texto if texto is not None else "—")), estilo)


def _fecha(valor) -> str:
    return valor.strftime("%d/%m/%Y") if isinstance(valor, (date, datetime)) else "—"


def _fecha_hora(valor) -> str:
    return valor.astimezone(_LIMA).strftime("%d/%m/%Y %H:%M") if isinstance(valor, datetime) else "—"


def _soles(valor) -> str:
    return f"S/ {Decimal(valor):,.2f}"


def _tabla(filas, anchos, cabecera=True) -> Table:
    tabla = Table(filas, colWidths=anchos, repeatRows=1 if cabecera else 0)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c0cc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if cabecera:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ebf2")))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _estado_entregable(item: dict) -> str:
    if item["cumplido"] is None:
        return "Sin conformidad"
    if not item["cumplido"]:
        return "No cumplido"
    return "Cumplido con evidencia" if item["evidencias"] else "Cumplido SIN evidencia"


def generar_pdf(datos: dict, *, actor: str, cadena_integra: bool, registros: int) -> bytes:
    e = datos["expediente"]
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"Reporte de trazabilidad {e['codigo']}", author="Conforme",
    )
    ancho = A4[0] - 3.6 * cm
    historia = [
        _p("Conforme · Reporte de trazabilidad", _H1),
        _p(f"{e['codigo']} · {e['numero_orden']} · {e['descripcion']}"),
        _p("Datos sintéticos. Este reporte alerta y deja rastro; no determina responsabilidades "
           "ni autoriza pagos.", _PEQUENO),
        _p(f"Generado el {_fecha_hora(datetime.now(_LIMA))} para {actor}. El contenido está limitado "
           "a lo que ese usuario puede ver.", _PEQUENO),
    ]

    historia.append(_p("1. Datos de la orden", _H2))
    historia.append(_tabla([
        [_p("Área usuaria"), _p(e["area"]), _p("Proveedor"), _p(f"{e['proveedor']} (RUC {e['proveedor_ruc']})")],
        [_p("Solicitante"), _p(e["solicitante"]), _p("Monto"), _p(_soles(e["monto"]))],
        [_p("Requerimiento"), _p(_fecha(e["fecha_requerimiento"])), _p("Orden emitida"), _p(_fecha(e["fecha_orden"]))],
        [_p("Inicio pactado"), _p(_fecha(e["fecha_inicio_prestacion"])), _p("Plazo"), _p(f"{e['plazo_dias']} días")],
        [_p("Fecha límite"), _p(_fecha(datos["fecha_limite"])), _p("Recepción real"), _p(_fecha(e["fecha_entrega_real"]))],
        [_p("Semáforo"), _p(e["semaforo"]), _p("Revisión de Abastecimiento"),
         _p({"conformidad.revisada": "Revisada: lista para derivar", "conformidad.devuelta": "Devuelta al área usuaria"}
            .get(e.get("revision_dec"), "Pendiente"))],
    ], [2.6 * cm, ancho / 2 - 2.6 * cm, 3.2 * cm, ancho / 2 - 3.2 * cm], cabecera=False))

    conformidad = datos["conformidad"]
    historia.append(_p("2. Conformidad y entregables", _H2))
    if conformidad:
        historia.append(_p(
            f"Conformidad del {_fecha(conformidad['fecha_conformidad'])} dada por {conformidad['conformante']}. "
            f"Penalidad aplicada: {_soles(conformidad['penalidad_aplicada'])}."))
        if conformidad.get("codigo_sello"):
            historia.append(_p(f"Sello: registro n.º {conformidad['sello_bitacora_id']} · huella "
                               f"{conformidad['sello_hash']}", _PEQUENO))
    else:
        historia.append(_p("Aún no hay conformidad registrada."))
    filas = [[_p("N.º"), _p("Entregable"), _p("Estado"), _p("Evidencias (SHA-256)")]]
    for item in datos["entregables"]:
        filas.append([
            _p(item["numero"]), _p(item["descripcion"]), _p(_estado_entregable(item)),
            _p("\n".join(f"{a['nombre_archivo']} · {a['sha256'][:16]}…" for a in item["evidencias"]) or "—", _PEQUENO),
        ])
    historia.append(_tabla(filas, [1 * cm, ancho * 0.45, 3.4 * cm, ancho - 4.4 * cm - ancho * 0.45]))

    historia.append(_p("3. Alertas", _H2))
    if datos["alertas"]:
        filas = [[_p("Regla"), _p("Severidad"), _p("Estado"), _p("Explicación")]]
        for a in datos["alertas"]:
            filas.append([_p(a["regla"]), _p(a["severidad"]), _p(a["estado"]), _p(a["explicacion"], _PEQUENO)])
        historia.append(_tabla(filas, [1.3 * cm, 1.8 * cm, 2.2 * cm, ancho - 5.3 * cm]))
    else:
        historia.append(_p("Sin alertas."))

    historia.append(_p("4. Pagos registrados", _H2))
    if datos["pagos"]:
        filas = [[_p("Fecha"), _p("Monto"), _p("Penalidad descontada"), _p("Referencia SIAF")]]
        for pago in datos["pagos"]:
            filas.append([_p(_fecha(pago["fecha_pago"])), _p(_soles(pago["monto"])),
                          _p(_soles(pago["penalidad_descontada"])), _p(pago.get("referencia_siaf"))])
        historia.append(_tabla(filas, [3 * cm, 4 * cm, 4 * cm, ancho - 11 * cm]))
    else:
        historia.append(_p("Sin pagos registrados."))

    historia.append(_p("5. Línea de tiempo", _H2))
    filas = [[_p("N.º"), _p("Fecha y hora"), _p("Acción y responsable"), _p("Huella del documento")]]
    for ev in datos["eventos"]:
        resumen = (ev.get("detalle") or {}).get("resumen")
        filas.append([
            _p(ev["id"], _PEQUENO), _p(_fecha_hora(ev["ts"]), _PEQUENO),
            _p(f"{ev['accion']} · {ev['actor'] or 'Sistema'}" + (f" — {resumen}" if resumen else ""), _PEQUENO),
            _p(ev["documento_sha256"][:16] + "…" if ev.get("documento_sha256") else "—", _PEQUENO),
        ])
    historia.append(_tabla(filas, [1.1 * cm, 2.6 * cm, ancho - 6.2 * cm, 2.5 * cm]))

    historia.append(Spacer(1, 8))
    historia.append(_p("6. Integridad", _H2))
    historia.append(_p(
        f"Bitácora encadenada por hash: {'íntegra' if cadena_integra else 'ALTERADA'} "
        f"({registros} registros verificados). La huella acredita que el rastro no cambió; no acredita "
        "que la evidencia sea auténtica ni suficiente."))
    documento.build(historia)
    return buffer.getvalue()
