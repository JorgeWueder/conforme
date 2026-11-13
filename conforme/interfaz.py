"""Utilidades compartidas por las páginas de Streamlit."""
import html
import re
from datetime import timedelta, timezone
from urllib.parse import urlsplit
from decimal import Decimal

import streamlit as st

from conforme.permisos import Actor

_HORA_PERU = timezone(timedelta(hours=-5))

ETIQUETAS_ROL = {
    "area_usuaria": "Área usuaria",
    "tesoreria": "Tesorería",
    "auditor": "Auditoría",
}

ETIQUETAS_ACCION = {
    "expediente.registrado": "Expediente registrado",
    "orden.emitida": "Orden emitida",
    "conformidad.registrada": "Conformidad registrada",
    "evidencia.adjuntada": "Evidencia adjuntada",
    "pago.registrado": "Pago registrado",
    "alerta.generada": "Alerta generada",
    "alerta.actualizada": "Alerta actualizada",
    "alerta.descargo": "Descargo presentado",
    "alerta.cerrada": "Alerta cerrada",
    "alerta.escalada": "Alerta escalada",
    "conformidad.sellada": "Conformidad sellada",
    "ia.propuesta": "Lectura con IA",
    "ia.aprobada": "Propuesta de IA aprobada",
    "ia.rechazada": "Propuesta de IA rechazada",
}

ETIQUETAS_SEMAFORO = {"rojo": "🔴 Rojo", "ambar": "🟡 Ámbar", "verde": "🟢 Verde"}
ETIQUETAS_SEVERIDAD = {"alta": "Alta", "media": "Media"}
ETIQUETAS_ESTADO = {
    "abierta": "Abierta",
    "con_descargo": "Con descargo",
    "escalada": "Escalada",
    "cerrada": "Cerrada",
}
ETIQUETAS_REVISION = {
    "descargo": "Descargo",
    "cierre": "Cierre",
    "escalamiento": "Escalamiento",
}

AVISO_NO_BLOQUEA = (
    "Las alertas son señales para revisar. No bloquean pagos ni determinan "
    "responsabilidades: una persona decide."
)


def actor_actual() -> Actor:
    actor = st.session_state.get("actor")
    if actor is None:
        st.stop()
    return actor


def origen_actual() -> str | None:
    """Esquema y servidor desde los que el navegador está viendo la app (o None)."""
    try:
        partes = urlsplit(st.context.url or "")
    except Exception:
        return None
    return f"{partes.scheme}://{partes.netloc}" if partes.scheme and partes.netloc else None


def mostrar_aviso_pendiente() -> None:
    """Muestra una sola vez el mensaje que dejó la acción anterior."""
    aviso = st.session_state.pop("aviso", None)
    if aviso:
        st.success(aviso, icon=":material/check_circle:")


_ESPECIALES_MD = re.compile(r"([\\`*_{}\[\]()<>#+!|~$:&])")


def md(texto) -> str:
    """Escapa texto escrito por personas (o leído de un PDF) antes de mostrarlo como markdown.

    Sin esto, una observación como «[clic](http://…)» o «![x](http://…)» se convertiría en un
    enlace o en una imagen externa, también en la página pública. Colapsa los saltos de línea
    para que no formen listas, citas ni bloques.
    """
    plano = " ".join(str(texto if texto is not None else "").split())
    return _ESPECIALES_MD.sub(r"\\\1", plano)


def soles(monto: Decimal) -> str:
    return f"S/ {monto:,.2f}"


def fecha_hora(ts) -> str:
    return ts.astimezone(_HORA_PERU).strftime("%d/%m/%Y %H:%M")


def fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


COLOR_ACCION = {
    "expediente.registrado": "#64748b",
    "orden.emitida": "#3b82f6",
    "conformidad.registrada": "#22c55e",
    "conformidad.sellada": "#15803d",
    "evidencia.adjuntada": "#06b6d4",
    "pago.registrado": "#a855f7",
    "alerta.generada": "#f97316",
    "alerta.actualizada": "#fb923c",
    "alerta.descargo": "#eab308",
    "alerta.cerrada": "#22c55e",
    "alerta.escalada": "#ef4444",
    "ia.propuesta": "#8b5cf6",
    "ia.aprobada": "#8b5cf6",
    "ia.rechazada": "#8b5cf6",
}
COLOR_ACCION_DEFECTO = "#94a3b8"


def html_linea_de_tiempo(eventos: list[dict]) -> str:
    """Línea de tiempo vertical (fecha | línea con puntos de color | detalle) en HTML.

    Todo dato dinámico se escapa con html.escape: el resultado es seguro para
    `st.markdown(..., unsafe_allow_html=True)`. Sin saltos de línea ni sangrías, para que el
    markdown no lo interprete como bloques de código.
    """
    e_ = html.escape
    partes = ['<div style="margin:4px 0 8px 0">']
    for i, e in enumerate(eventos):
        titulo = ETIQUETAS_ACCION.get(e["accion"], e["accion"])
        color = COLOR_ACCION.get(e["accion"], COLOR_ACCION_DEFECTO)
        dia, hora = fecha_hora(e["ts"]).split(" ")
        es_ultimo = i == len(eventos) - 1
        linea = "transparent" if es_ultimo else "rgba(128,128,128,0.45)"
        detalle = []
        resumen = (e.get("detalle") or {}).get("resumen")
        if resumen:
            detalle.append(f'<div style="margin-top:2px">{e_(str(resumen))}</div>')
        if e.get("documento_sha256"):
            documento = (e.get("detalle") or {}).get("documento", "documento")
            detalle.append(
                '<div style="margin-top:4px;font-size:0.8rem;opacity:0.75">'
                f'&#128206; {e_(str(documento))} &middot; SHA-256 '
                f'<code>{e_(e["documento_sha256"][:16])}&hellip;</code></div>')
        partes.append(
            '<div style="display:flex;gap:14px">'
            '<div style="flex:0 0 78px;text-align:right;font-size:0.8rem;line-height:1.35;'
            f'opacity:0.75;padding-top:1px"><b>{e_(dia)}</b><br>{e_(hora)}</div>'
            f'<div style="position:relative;flex:1;border-left:2px solid {linea};'
            'padding:0 0 18px 20px;min-width:0">'
            f'<span style="position:absolute;left:-8px;top:3px;width:14px;height:14px;'
            f'border-radius:50%;background:{color};box-shadow:0 0 0 4px rgba(128,128,128,0.15)">'
            '</span>'
            f'<div style="font-weight:600;line-height:1.3">{e_(titulo)}</div>'
            f'<div style="font-size:0.85rem;opacity:0.75">{e_(e.get("actor") or "Sistema")}'
            f' &middot; registro n.&ordm; {e_(str(e["id"]))}</div>'
            + "".join(detalle) + "</div></div>")
    partes.append("</div>")
    return "".join(partes)
