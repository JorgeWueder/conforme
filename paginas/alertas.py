import streamlit as st

from conforme import db, normativa, repositorio
from conforme.errores import ErrorValidacion
from conforme.interfaz import (
    AVISO_NO_BLOQUEA, ETIQUETAS_ESTADO, ETIQUETAS_REVISION, ETIQUETAS_SEVERIDAD,
    actor_actual, fecha_hora, md, mostrar_aviso_pendiente,
)
from conforme.modelos import ESTADO_CERRADA, ESTADO_ESCALADA, ROL_AUDITOR, ROL_TESORERIA
from conforme.permisos import PermisoDenegado

actor = actor_actual()

st.title("Alertas")
st.caption(AVISO_NO_BLOQUEA)
mostrar_aviso_pendiente()

with db.sesion() as s:
    todas = repositorio.listar_alertas(s, actor)

# Si se llega desde el detalle de un expediente, esa alerta queda elegida.
desde_detalle = st.session_state.pop("alerta_id", None)

izquierda, derecha = st.columns(2)
estados = izquierda.multiselect(
    "Estado", list(ETIQUETAS_ESTADO), default=[e for e in ETIQUETAS_ESTADO if e != ESTADO_CERRADA],
    format_func=ETIQUETAS_ESTADO.get,
)
reglas = derecha.multiselect(
    "Regla", list(normativa.NOMBRE_REGLA), placeholder="Todas",
    format_func=lambda r: f"{r} · {normativa.NOMBRE_REGLA[r]}",
)
# La alerta que se está revisando sigue en la lista aunque deje de cumplir el
# filtro (por ejemplo, al cerrarla).
en_revision = desde_detalle or st.session_state.get("alerta_elegida")
alertas = [
    a for a in todas
    if a["id"] == en_revision
    or (a["estado"] in estados and (not reglas or a["regla"] in reglas))
]

st.caption(f"{len(alertas)} alertas.")
st.dataframe(
    [
        {
            "N.º": a["id"],
            "Expediente": a["expediente"],
            "Área": a["area_sigla"],
            "Regla": f"{a['regla']} · {normativa.NOMBRE_REGLA[a['regla']]}",
            "Severidad": ETIQUETAS_SEVERIDAD[a["severidad"]],
            "Estado": ETIQUETAS_ESTADO[a["estado"]],
            "Persona implicada": a["implicado"],
            "Creada": fecha_hora(a["creada_en"]),
        }
        for a in alertas
    ],
    hide_index=True,
)

por_id = {a["id"]: a for a in alertas}
if desde_detalle in por_id:
    st.session_state["alerta_elegida"] = desde_detalle
elif st.session_state.get("alerta_elegida") not in por_id:
    st.session_state.pop("alerta_elegida", None)

elegida = st.selectbox(
    "Alerta a revisar", list(por_id), index=None, placeholder="Elige una alerta",
    format_func=lambda i: f"N.º {i} · {por_id[i]['expediente']} · {por_id[i]['regla']}",
    key="alerta_elegida",
)
if elegida is None:
    st.stop()

alerta = por_id[elegida]
with db.sesion() as s:
    revisiones = repositorio.revisiones_de_alerta(s, actor, alerta["id"])

st.divider()
st.subheader(f"{alerta['expediente']} · {alerta['regla']} · {normativa.NOMBRE_REGLA[alerta['regla']]}")
st.markdown(
    f"Severidad **{ETIQUETAS_SEVERIDAD[alerta['severidad']].lower()}** · "
    f"estado **{ETIQUETAS_ESTADO[alerta['estado']].lower()}** · "
    f"creada el {fecha_hora(alerta['creada_en'])}"
)
st.write(md(alerta["explicacion"]))
if alerta["implicado"]:
    st.caption(f"Persona implicada: {md(alerta['implicado'])}")
if st.button("Abrir el expediente", icon=":material/description:"):
    st.session_state["expediente_id"] = alerta["expediente_id"]
    st.switch_page("paginas/expediente_detalle.py")

st.markdown("**Historial de la alerta**")
if not revisiones:
    st.caption("Sin descargos ni revisiones todavía.")
for r in revisiones:
    with st.container(border=True):
        st.markdown(f"**{ETIQUETAS_REVISION[r['tipo']]}** · {fecha_hora(r['creado_en'])} · {md(r['autor'])}")
        st.write(md(r["texto"]))


def ejecutar(accion, texto: str, aviso: str) -> None:
    try:
        with db.sesion() as s:
            accion(s, actor, alerta["id"], texto)
    except (ErrorValidacion, PermisoDenegado) as error:
        st.error(str(error))
    else:
        st.session_state["aviso"] = aviso
        st.session_state["alerta_id"] = alerta["id"]
        st.rerun()


if alerta["estado"] == ESTADO_CERRADA:
    st.info("Alerta cerrada. Queda en el historial y en la bitácora.")
    st.stop()

puede_descargar = actor.persona_id in (alerta["persona_implicada_id"], alerta["conformante_id"])
if puede_descargar:
    with st.form("descargo", clear_on_submit=True):
        st.markdown("**Presentar descargo**")
        texto = st.text_area("Explica lo ocurrido", key="texto_descargo")
        if st.form_submit_button("Enviar descargo", type="primary"):
            ejecutar(repositorio.registrar_descargo, texto, "Descargo registrado.")

if actor.rol in (ROL_TESORERIA, ROL_AUDITOR):
    if alerta["persona_implicada_id"] == actor.persona_id:
        st.warning(
            "Figuras como persona implicada en esta alerta: no puedes cerrarla ni "
            "escalarla. Debe revisarla otra persona.",
            icon=":material/block:",
        )
    else:
        opciones = ["Cerrar"] if alerta["estado"] == ESTADO_ESCALADA else ["Cerrar", "Escalar"]
        with st.form("revision", clear_on_submit=True):
            st.markdown("**Cerrar o escalar**")
            decision = st.radio("Decisión", opciones, horizontal=True)
            motivo = st.text_area("Motivo (obligatorio)", key="texto_motivo")
            if st.form_submit_button("Registrar decisión", type="primary"):
                if decision == "Cerrar":
                    ejecutar(repositorio.cerrar_alerta, motivo, "Alerta cerrada.")
                else:
                    ejecutar(repositorio.escalar_alerta, motivo, "Alerta escalada.")
elif not puede_descargar:
    st.caption("Cierran o escalan alertas tesorería y auditoría.")
