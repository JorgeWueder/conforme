import streamlit as st

from conforme import db, repositorio
from conforme.errores import ErrorValidacion
from conforme.ia import extractor
from conforme.ia.extractor import PropuestaIA
from conforme.interfaz import actor_actual, fecha_hora, mostrar_aviso_pendiente
from conforme.modelos import ROL_AREA_USUARIA
from conforme.permisos import PermisoDenegado

actor = actor_actual()
st.title("Lectura con IA")

if actor.rol != ROL_AREA_USUARIA:
    st.error("Solo el área usuaria carga entregables.")
    st.stop()

st.caption(
    "Sube los términos de referencia en PDF (con texto, sin escaneos). La IA propone los "
    "entregables; **nada se guarda en el expediente hasta que tú lo apruebes**."
)
mostrar_aviso_pendiente()

with db.sesion() as s:
    elegibles = [e for e in repositorio.listar_expedientes(s, actor)
                 if not e["tiene_conformidad"]]

if not elegibles:
    st.info("No hay expedientes de tu área sin conformidad.")
    st.stop()

actual = st.session_state.get("expediente_id")
indice = next((i for i, e in enumerate(elegibles) if e["id"] == actual), 0)
exp = st.selectbox(
    "Expediente", elegibles, index=indice,
    format_func=lambda e: f"{e['codigo']} · {e['descripcion'][:70]}",
)

with db.sesion() as s:
    extracciones = repositorio.listar_extracciones(s, actor, exp["id"])
    existentes = repositorio.listar_entregables(s, actor, exp["id"])
pendiente = next((x for x in extracciones if x["estado"] == "propuesta"), None)

# --- Lo que ya tiene el expediente -------------------------------------------------
with st.container(border=True):
    st.markdown(f"**Expediente:** {exp['codigo']} · {exp['tipo'].capitalize()} · "
                f"plazo {exp['plazo_dias']} días")
    st.write(exp["descripcion"])
    st.caption("Entregables que ya tiene: " + (
        "; ".join(f"{e['numero']}. {e['descripcion']}" for e in existentes) or "ninguno"))

# --- Subir y leer --------------------------------------------------------------
with st.container(border=True):
    st.markdown("**1. Sube el documento**")
    if extractor.PDF_EJEMPLO.exists():
        st.download_button(
            "Descargar un PDF de ejemplo", extractor.PDF_EJEMPLO.read_bytes(),
            file_name="terminos_referencia_ejemplo.pdf", mime="application/pdf",
            icon=":material/download:",
        )
    archivo = st.file_uploader("Términos de referencia (PDF)", type=["pdf"])
    if st.button("Leer documento", type="primary", icon=":material/auto_awesome:",
                 disabled=archivo is None):
        try:
            with st.spinner("Leyendo el documento…"):
                resultado = extractor.extraer(
                    archivo.getvalue(),
                    expediente={"tipo": exp["tipo"], "descripcion": exp["descripcion"],
                                "plazo_dias": exp["plazo_dias"]})
            with db.sesion() as s:
                repositorio.registrar_propuesta_ia(
                    s, actor, exp["id"], archivo_nombre=archivo.name,
                    archivo_sha256=resultado.archivo_sha256, propuesta=resultado.propuesta,
                    origen=resultado.origen, aviso=resultado.aviso,
                )
        except (ErrorValidacion, PermisoDenegado) as error:
            st.error(str(error))
        else:
            st.session_state["expediente_id"] = exp["id"]
            st.rerun()

# --- Revisar la propuesta ------------------------------------------------------
if pendiente:
    st.subheader("2. Revisa la propuesta", anchor=False)
    st.caption(f"Documento «{pendiente['archivo_nombre']}» · {fecha_hora(pendiente['creado_en'])}")
    if pendiente["origen"] == "respaldo":
        st.warning(
            "**Resultado de respaldo.** No es una lectura de tu documento: es un ejemplo "
            f"guardado. {pendiente['aviso'] or ''}",
            icon=":material/inventory_2:",
        )
    else:
        st.info("Lectura hecha por el modelo. Puede equivocarse: revisa cada fila.",
                icon=":material/auto_awesome:")

    propuesta = pendiente["resultado"]
    lectura = PropuestaIA.model_validate(propuesta)
    if lectura.objeto:
        st.markdown(f"**Objeto del documento:** {lectura.objeto}")
        st.caption(f"Objeto del expediente: {exp['descripcion']}")
    avisos = extractor.avisos_de_coherencia(
        lectura, exp, pendiente["origen"], [e["descripcion"] for e in existentes])
    hay_discrepancia = any(nivel == "error" for nivel, _ in avisos)
    for nivel, texto in avisos:
        if nivel == "error":
            st.error(texto, icon=":material/error:")
        else:
            st.warning(texto, icon=":material/warning:")
    st.markdown("**Entregables propuestos** (puedes editar, borrar o añadir filas)")
    filas = st.data_editor(
        [{"descripcion": e["descripcion"]} for e in propuesta["entregables"]],
        num_rows="dynamic",
        column_config={"descripcion": st.column_config.TextColumn("Descripción", width="large")},
        key=f"editor_ia_{pendiente['id']}",
    )
    if hasattr(filas, "to_dict"):
        filas = filas.to_dict("records")
    descripciones = [f.get("descripcion") for f in filas if isinstance(f.get("descripcion"), str)]
    st.caption("Se añadirán a los entregables que el expediente ya tiene, con numeración "
               "correlativa.")

    plazo = propuesta.get("plazo_dias")
    if plazo or propuesta.get("penalidades"):
        with st.container(border=True):
            st.markdown("**Otros datos del documento** (solo informativos, no se guardan)")
            if plazo:
                st.write(f"Plazo según el documento: {plazo} días calendario "
                         f"(el expediente tiene {exp['plazo_dias']}).")
            for penalidad in propuesta.get("penalidades", []):
                st.write(f"- {penalidad}")

    confirmado = True
    if hay_discrepancia:
        confirmado = st.checkbox(
            "Entiendo que el documento no parece corresponder a este expediente y aun así "
            "quiero añadir estos entregables.", key=f"confirma_{pendiente['id']}")

    aprobar, rechazar = st.columns(2)
    if aprobar.button("Aprobar y añadir al expediente", type="primary", width="stretch",
                      icon=":material/check:", disabled=not confirmado):
        try:
            with db.sesion() as s:
                n = repositorio.aprobar_extraccion(s, actor, pendiente["id"], descripciones)
        except (ErrorValidacion, PermisoDenegado) as error:
            st.error(str(error))
        else:
            st.session_state["expediente_id"] = exp["id"]
            st.session_state["aviso"] = f"Propuesta aprobada: {n} entregables añadidos."
            st.switch_page("paginas/expediente_detalle.py")
    motivo = rechazar.text_input("Motivo del rechazo (opcional)", key=f"motivo_{pendiente['id']}")
    if rechazar.button("Rechazar propuesta", width="stretch", icon=":material/close:"):
        try:
            with db.sesion() as s:
                repositorio.rechazar_extraccion(s, actor, pendiente["id"], motivo)
        except (ErrorValidacion, PermisoDenegado) as error:
            st.error(str(error))
        else:
            st.session_state["aviso"] = "Propuesta rechazada. No se añadió ningún entregable."
            st.rerun()

# --- Historial -----------------------------------------------------------------
revisadas = [x for x in extracciones if x["estado"] != "propuesta"]
if revisadas:
    with st.expander(f"Historial de lecturas ({len(revisadas)})"):
        for x in revisadas:
            st.markdown(
                f"- {fecha_hora(x['creado_en'])} · «{x['archivo_nombre']}» · "
                f"{x['origen']} · **{x['estado']}**"
            )
