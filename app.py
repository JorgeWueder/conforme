"""Conforme — entrada de la aplicación.  Uso: streamlit run app.py"""
import streamlit as st

from conforme.interfaz import ETIQUETAS_ROL
from conforme.modelos import ROL_AUDITOR

st.set_page_config(page_title="Conforme", page_icon=":material/verified:", layout="wide")

st.warning(
    "**Datos sintéticos.** Demostración académica: las personas, proveedores, "
    "montos y documentos que aparecen son ficticios.",
    icon=":material/science:",
)

actor = st.session_state.get("actor")


def cerrar_sesion():
    st.session_state.clear()
    st.rerun()


# Pública: se registra también para visitantes sin sesión (la abre el QR en F3).
verificar = st.Page("paginas/verificar.py", title="Verificar sello",
                    url_path="verificar", icon=":material/qr_code_2:")

if actor is None:
    paginas = [
        st.Page("paginas/login.py", title="Ingresar", icon=":material/login:", default=True),
        verificar,
    ]
else:
    paginas = [
        st.Page("paginas/expedientes.py", title="Expedientes",
                icon=":material/folder_open:", default=True),
        st.Page("paginas/expediente_detalle.py", title="Detalle de expediente",
                icon=":material/description:"),
    ]
    if actor.rol == ROL_AUDITOR:
        paginas.append(st.Page("paginas/bitacora.py", title="Bitácora",
                               icon=":material/link:"))
    paginas += [
        verificar,
        st.Page(cerrar_sesion, title="Cerrar sesión", icon=":material/logout:"),
    ]
    st.sidebar.markdown(f"**{actor.nombre}**")
    st.sidebar.caption(f"{ETIQUETAS_ROL[actor.rol]} · usuario `{actor.username}`")

st.navigation(paginas).run()
