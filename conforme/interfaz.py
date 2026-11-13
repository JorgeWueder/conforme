"""Utilidades compartidas por las páginas de Streamlit."""
from datetime import timedelta, timezone
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


def mostrar_aviso_pendiente() -> None:
    """Muestra una sola vez el mensaje que dejó la acción anterior."""
    aviso = st.session_state.pop("aviso", None)
    if aviso:
        st.success(aviso, icon=":material/check_circle:")


def soles(monto: Decimal) -> str:
    return f"S/ {monto:,.2f}"


def fecha_hora(ts) -> str:
    return ts.astimezone(_HORA_PERU).strftime("%d/%m/%Y %H:%M")


def fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"
