import streamlit as st

from conforme import auth, db

_, centro, _ = st.columns([1, 2, 1])

with centro:
    st.title("Conforme")
    st.caption("Alerta temprana y trazabilidad de la conformidad de bienes y servicios.")

    with st.container(border=True):
        st.subheader("Ingresar", anchor=False)
        with st.form("login", border=False):
            username = st.text_input("Usuario", placeholder="inf1, tes1 u oci1")
            password = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Ingresar", type="primary", width="stretch")

    if enviar:
        with db.sesion() as s:
            actor = auth.autenticar(s, username, password)
        if actor is None:
            st.error("Usuario o contraseña incorrectos.")
        else:
            st.session_state["actor"] = actor
            st.rerun()

    st.caption(
        "Usuarios de demostración: `inf1` (área usuaria), `tes1` (tesorería), "
        "`oci1` (auditoría). La contraseña la entrega el equipo."
    )

    st.divider()
    st.markdown("**¿Tienes el código o el QR de un sello de conformidad?**")
    st.caption("Cualquier persona puede comprobarlo, sin cuenta.")
    st.page_link("paginas/verificar.py", label="Verificar un sello",
                 icon=":material/qr_code_2:")
