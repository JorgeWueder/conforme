import streamlit as st

from conforme import auth, db

st.title("Conforme")
st.caption("Alerta temprana y trazabilidad de la conformidad de bienes y servicios.")

with st.form("login"):
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    enviar = st.form_submit_button("Ingresar", type="primary")

if enviar:
    with db.sesion() as s:
        actor = auth.autenticar(s, username, password)
    if actor is None:
        st.error("Usuario o contraseña incorrectos.")
    else:
        st.session_state["actor"] = actor
        st.rerun()

st.info(
    "Usuarios de demostración: `inf1` (área usuaria), `tes1` (tesorería), "
    "`oci1` (auditoría). La contraseña la entrega el equipo.",
    icon=":material/info:",
)
