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
}


def actor_actual() -> Actor:
    actor = st.session_state.get("actor")
    if actor is None:
        st.stop()
    return actor


def soles(monto: Decimal) -> str:
    return f"S/ {monto:,.2f}"


def fecha_hora(ts) -> str:
    return ts.astimezone(_HORA_PERU).strftime("%d/%m/%Y %H:%M")


def fecha(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"
