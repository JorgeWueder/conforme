"""Verificación PÚBLICA del sello de una conformidad (sin login, solo lectura)."""
import streamlit as st

from conforme import db, repositorio, sello
from conforme.interfaz import fecha, soles

con_sesion = st.session_state.get("actor") is not None

if not con_sesion:
    st.page_link("paginas/login.py", label="Ir a iniciar sesión", icon=":material/arrow_back:")

st.title("Verificar sello")
st.caption(
    "Comprueba que una conformidad existe y que su rastro (bitácora y evidencias) "
    "no fue alterado. Se consulta solo con el código del sello."
)

codigo = (st.query_params.get("c") or "").strip()
with st.form("buscar_sello", border=False):
    columna_texto, columna_boton = st.columns([4, 1], vertical_alignment="bottom")
    ingresado = columna_texto.text_input(
        "Código del sello", value=codigo, placeholder="Pégalo o escanea el QR")
    consultar = columna_boton.form_submit_button("Verificar", type="primary", width="stretch")
if consultar:
    codigo = ingresado.strip()
    if codigo:
        st.query_params["c"] = codigo
    elif "c" in st.query_params:
        del st.query_params["c"]

if not codigo:
    st.info("Escanea el QR del sello o pega aquí su código.", icon=":material/qr_code_scanner:")
    st.stop()

with st.spinner("Verificando la bitácora…"):
    with db.sesion() as s:
        resultado = repositorio.consultar_sello(s, codigo)

if resultado is None:
    st.error("No se encontró ninguna conformidad con ese código. Revisa que esté completo.",
             icon=":material/search_off:")
    st.stop()

if resultado["integra"]:
    st.success(
        f"**Íntegra.** Se verificaron {resultado['registros_verificados']} registros de la "
        "bitácora, el registro sellado y las huellas de las evidencias.",
        icon=":material/verified:",
    )
else:
    st.error("**Alterada.** El rastro de esta conformidad no coincide con el sello.",
             icon=":material/gpp_bad:")
    for problema in resultado["problemas"]:
        st.markdown(f"- {problema}")

st.header(resultado["expediente"], anchor=False)
st.write(resultado["descripcion"])
st.caption(
    f"{resultado['tipo'].capitalize()} · {resultado['area']} · Proveedor: "
    f"{resultado['proveedor']}"
)

with st.container(border=True):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monto", soles(resultado["monto"]))
    m2.metric("Entrega real", fecha(resultado["fecha_entrega_real"]))
    m3.metric("Conformidad", fecha(resultado["fecha_conformidad"]))
    m4.metric("Penalidad aplicada", soles(resultado["penalidad_aplicada"]))
    st.caption(
        f"Conformidad dada por **{resultado['conformante']}** "
        f"({resultado['conformante_cargo']})."
        + (f" Observaciones: {resultado['observaciones']}" if resultado["observaciones"] else "")
    )

st.subheader("Entregables y evidencias", anchor=False)
cumplidos_sin_evidencia = [e for e in resultado["entregables"]
                           if e["cumplido"] and not e["evidencias"]]
if cumplidos_sin_evidencia:
    st.warning(
        f"**{len(cumplidos_sin_evidencia)} de {len(resultado['entregables'])} entregables se "
        "dieron por cumplidos sin ninguna evidencia.** Que el rastro sea íntegro no significa "
        "que la conformidad esté respaldada.", icon=":material/warning:")
for e in resultado["entregables"]:
    sin_evidencia = not e["evidencias"]
    if not e["cumplido"]:
        estado, icono = ":red-badge[No cumplido]", ":material/cancel:"
    elif sin_evidencia:
        estado, icono = ":orange-badge[Cumplido · SIN evidencia]", ":material/warning:"
    else:
        estado, icono = ":green-badge[Cumplido · con evidencia]", ":material/check_circle:"
    if any(not ev["coincide"] for ev in e["evidencias"]):
        icono = ":material/gpp_bad:"
    with st.expander(f"{e['numero']}. {e['descripcion']} — {estado}", icon=icono,
                     expanded=not sin_evidencia):
        if e["observacion"]:
            st.caption(f"Observación: {e['observacion']}")
        if sin_evidencia:
            st.warning("Sin evidencia adjunta.", icon=":material/warning:")
        columnas = st.columns(3)
        for i, ev in enumerate(e["evidencias"]):
            with columnas[i % 3]:
                if ev["miniatura"]:
                    st.image(ev["miniatura"], width=sello.LADO_MINIATURA)
                if ev["coincide"]:
                    st.caption(f":material/verified: {ev['nombre_archivo']}")
                else:
                    st.caption(f":material/gpp_bad: {ev['nombre_archivo']} — no coincide "
                               "con su huella")
                st.caption(f"SHA-256 `{ev['sha256'][:16]}…`")

st.caption(
    "Datos sintéticos. Esta herramienta alerta y deja rastro: no determina responsabilidades."
)
