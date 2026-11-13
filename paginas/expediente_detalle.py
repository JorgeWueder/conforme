from datetime import timedelta

import streamlit as st

from conforme import db, repositorio
from conforme.interfaz import ETIQUETAS_ACCION, actor_actual, fecha, fecha_hora, soles

actor = actor_actual()
expediente_id = st.session_state.get("expediente_id")

if expediente_id is None:
    st.title("Detalle de expediente")
    st.info("Elige un expediente en la lista para ver su detalle.")
    st.page_link("paginas/expedientes.py", label="Ir a Expedientes", icon=":material/folder_open:")
    st.stop()

with db.sesion() as s:
    exp = repositorio.obtener_expediente(s, actor, expediente_id)
    eventos = repositorio.linea_de_tiempo(s, actor, expediente_id) if exp else []

if exp is None:
    st.error("El expediente no existe o está fuera de tu alcance.")
    st.stop()

st.page_link("paginas/expedientes.py", label="Volver a Expedientes", icon=":material/arrow_back:")
st.title(exp["codigo"])
st.subheader(exp["descripcion"])

# Fecha límite = fecha de la orden + plazo (supuesto POR VERIFICAR, ver PLAN.md).
limite = exp["fecha_orden"] + timedelta(days=exp["plazo_dias"])

izquierda, derecha = st.columns(2)
izquierda.markdown(
    f"**Monto:** {soles(exp['monto'])}  \n"
    f"**Plazo:** {exp['plazo_dias']} días  \n"
    f"**Tipo:** {exp['tipo'].capitalize()}  \n"
    f"**Área usuaria:** {exp['area']}  \n"
    f"**Solicitante:** {exp['solicitante']}  \n"
    f"**Proveedor:** {exp['proveedor']} (RUC {exp['proveedor_ruc']})  \n"
    f"**Orden:** {exp['numero_orden']}"
)
derecha.markdown(
    f"**Requerimiento:** {fecha(exp['fecha_requerimiento'])}  \n"
    f"**Orden emitida:** {fecha(exp['fecha_orden'])}  \n"
    f"**Inicio de la prestación:** {fecha(exp['fecha_inicio_prestacion'])}  \n"
    f"**Fecha límite:** {fecha(limite)}  \n"
    f"**Entrega real:** {fecha(exp['fecha_entrega_real'])}"
)

st.divider()
st.subheader("Línea de tiempo")
st.caption("Quién hizo qué, cuándo y con qué documento. Proviene de la bitácora encadenada.")

for e in eventos:
    with st.container(border=True):
        st.markdown(
            f"**{ETIQUETAS_ACCION.get(e['accion'], e['accion'])}** · "
            f"{fecha_hora(e['ts'])} · {e['actor'] or 'Sistema'}"
        )
        if e["documento_sha256"]:
            documento = e["detalle"].get("documento", "documento")
            st.caption(f"Documento: {documento} · SHA-256 `{e['documento_sha256'][:16]}…`")
        st.caption(f"Registro de bitácora n.º {e['id']}")
