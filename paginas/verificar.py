"""Verificación PÚBLICA del sello de una conformidad (sin login, solo lectura)."""
import streamlit as st

from conforme import db, repositorio, sello
from conforme.interfaz import fecha, soles

st.title("Verificar sello")
st.caption(
    "Comprueba que una conformidad existe y que su rastro (bitácora y evidencias) "
    "no fue alterado. Se consulta solo con el código del sello."
)

codigo = (st.query_params.get("c") or "").strip()
if not codigo:
    codigo = st.text_input("Código del sello", placeholder="Pégalo o escanea el QR").strip()

if not codigo:
    st.stop()

with db.sesion() as s:
    resultado = repositorio.consultar_sello(s, codigo)

if resultado is None:
    st.error("No se encontró ninguna conformidad con ese código.", icon=":material/search_off:")
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

st.subheader(f"{resultado['expediente']} · {resultado['descripcion']}")
columnas = st.columns(2)
columnas[0].markdown(
    f"**Área usuaria:** {resultado['area']}  \n"
    f"**Proveedor:** {resultado['proveedor']}  \n"
    f"**Tipo:** {resultado['tipo'].capitalize()}  \n"
    f"**Monto:** {soles(resultado['monto'])}"
)
columnas[1].markdown(
    f"**Conformidad dada por:** {resultado['conformante']} ({resultado['conformante_cargo']})  \n"
    f"**Fecha de la conformidad:** {fecha(resultado['fecha_conformidad'])}  \n"
    f"**Entrega real:** {fecha(resultado['fecha_entrega_real'])}  \n"
    f"**Penalidad aplicada:** {soles(resultado['penalidad_aplicada'])}"
)
if resultado["observaciones"]:
    st.caption(f"Observaciones: {resultado['observaciones']}")

st.markdown("**Entregables y evidencias**")
for e in resultado["entregables"]:
    with st.container(border=True):
        st.markdown(
            f"**{e['numero']}. {e['descripcion']}** — "
            f"{'cumplido' if e['cumplido'] else 'no cumplido'}"
        )
        if e["observacion"]:
            st.caption(f"Observación: {e['observacion']}")
        if not e["evidencias"]:
            st.caption(":material/warning: Sin evidencia adjunta.")
        for ev in e["evidencias"]:
            marca = "coincide con su huella" if ev["coincide"] else "NO coincide con su huella"
            st.caption(f"{ev['nombre_archivo']} · SHA-256 `{ev['sha256'][:16]}…` · {marca}")
            if ev["miniatura"]:
                st.image(ev["miniatura"], width=sello.LADO_MINIATURA)

st.caption(
    "Datos sintéticos. Esta herramienta alerta y deja rastro: no determina responsabilidades."
)
