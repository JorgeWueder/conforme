from datetime import date

import streamlit as st

from conforme import db, normativa, repositorio
from conforme.errores import ErrorValidacion
from conforme.interfaz import actor_actual, fecha, soles
from conforme.modelos import ROL_AREA_USUARIA
from conforme.permisos import PermisoDenegado

actor = actor_actual()
st.title("Registrar conformidad")

if actor.rol != ROL_AREA_USUARIA:
    st.error("Solo el área usuaria registra conformidades.")
    st.stop()

expediente_id = st.session_state.get("expediente_id")
if expediente_id is None:
    st.info("Elige primero un expediente en la lista y abre su detalle.")
    st.page_link("paginas/expedientes.py", label="Ir a Expedientes", icon=":material/folder_open:")
    st.stop()

with db.sesion() as s:
    exp = repositorio.obtener_expediente(s, actor, expediente_id)
    if exp:
        entregables = repositorio.listar_entregables(s, actor, expediente_id)

if exp is None:
    st.error("El expediente no existe o está fuera de tu alcance.")
    st.stop()

st.page_link("paginas/expediente_detalle.py", label="Volver al detalle",
             icon=":material/arrow_back:")
st.subheader(f"{exp['codigo']} · {exp['descripcion']}")
limite = normativa.fecha_limite(exp["fecha_orden"], exp["plazo_dias"])
st.caption(
    f"{exp['proveedor']} · {soles(exp['monto'])} · plazo {exp['plazo_dias']} días · "
    f"fecha límite {fecha(limite)}"
)

if exp["tiene_conformidad"]:
    st.info("Este expediente ya tiene una conformidad registrada.")
    st.stop()
if not entregables:
    st.warning("Este expediente no tiene entregables: no hay sobre qué dar conformidad.")
    st.stop()

with st.form("conformidad"):
    columnas = st.columns(3)
    if exp["fecha_entrega_real"]:
        columnas[0].markdown(f"**Entrega real**  \n{fecha(exp['fecha_entrega_real'])}")
        entrega = None
    else:
        entrega = columnas[0].date_input("Fecha de entrega real", value=date.today(),
                                         format="DD/MM/YYYY")
    fecha_conformidad = columnas[1].date_input("Fecha de la conformidad", value=date.today(),
                                               format="DD/MM/YYYY")
    penalidad = columnas[2].number_input("Penalidad aplicada (S/)", min_value=0.0, value=0.0,
                                         step=10.0, format="%.2f")

    st.markdown("**Entregables**")
    st.caption(
        "Adjunta evidencia de cada entregable (JPG, PNG o PDF, hasta 5 MB). Puedes guardar "
        "sin evidencia, pero el sistema generará una alerta."
    )
    items = []
    for e in entregables:
        with st.container(border=True):
            st.markdown(f"**{e['numero']}. {e['descripcion']}**")
            cumplido = st.checkbox("Cumplido", value=True, key=f"cumplido_{e['id']}")
            observacion = st.text_input("Observación (opcional)", key=f"observacion_{e['id']}")
            archivos = st.file_uploader(
                "Evidencia", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True,
                key=f"evidencia_{e['id']}",
            )
            items.append((e["id"], cumplido, observacion, archivos))

    observaciones = st.text_area("Observaciones generales (opcional)")
    guardar = st.form_submit_button("Guardar conformidad", type="primary",
                                    icon=":material/task_alt:")

if guardar:
    try:
        with db.sesion() as s:
            repositorio.registrar_conformidad(
                s, actor, expediente_id,
                fecha_conformidad=fecha_conformidad,
                fecha_entrega_real=entrega,
                penalidad_aplicada=f"{penalidad:.2f}",
                observaciones=observaciones,
                items=[
                    {
                        "entregable_id": entregable_id,
                        "cumplido": cumplido,
                        "observacion": observacion,
                        "evidencias": [
                            {"nombre_archivo": a.name, "mime": a.type, "contenido": a.getvalue()}
                            for a in archivos or []
                        ],
                    }
                    for entregable_id, cumplido, observacion, archivos in items
                ],
            )
            n_alertas = len(repositorio.listar_alertas(s, actor, expediente_id=expediente_id))
    except (ErrorValidacion, PermisoDenegado) as error:
        st.error(str(error))
    else:
        st.session_state["aviso"] = (
            f"Conformidad registrada. El expediente tiene {n_alertas} alertas."
            if n_alertas else "Conformidad registrada. No se generaron alertas."
        )
        st.switch_page("paginas/expediente_detalle.py")
