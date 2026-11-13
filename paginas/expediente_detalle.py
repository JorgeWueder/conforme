from datetime import date

import streamlit as st

from conforme import db, normativa, repositorio, sello
from conforme.errores import ErrorValidacion
from conforme.interfaz import (
    AVISO_NO_BLOQUEA, ETIQUETAS_ACCION, ETIQUETAS_ESTADO, ETIQUETAS_SEMAFORO,
    ETIQUETAS_SEVERIDAD, actor_actual, fecha, fecha_hora, mostrar_aviso_pendiente, soles,
)
from conforme.modelos import ESTADO_CERRADA, ROL_AREA_USUARIA, ROL_AUDITOR, ROL_TESORERIA
from conforme.permisos import PermisoDenegado

actor = actor_actual()
expediente_id = st.session_state.get("expediente_id")

if expediente_id is None:
    st.title("Detalle de expediente")
    st.info("Elige un expediente en la lista para ver su detalle.")
    st.page_link("paginas/expedientes.py", label="Ir a Expedientes", icon=":material/folder_open:")
    st.stop()

with db.sesion() as s:
    exp = repositorio.obtener_expediente(s, actor, expediente_id)
    if exp:
        eventos = repositorio.linea_de_tiempo(s, actor, expediente_id)
        entregables = repositorio.listar_entregables(s, actor, expediente_id)
        conformidad = repositorio.obtener_conformidad(s, actor, expediente_id)
        alertas = repositorio.listar_alertas(s, actor, expediente_id=expediente_id)
        pagos = repositorio.listar_pagos(s, actor, expediente_id)

if exp is None:
    st.error("El expediente no existe o está fuera de tu alcance.")
    st.stop()

st.page_link("paginas/expedientes.py", label="Volver a Expedientes", icon=":material/arrow_back:")
st.title(f"{exp['codigo']} · {ETIQUETAS_SEMAFORO[exp['semaforo']]}")
st.subheader(exp["descripcion"])
mostrar_aviso_pendiente()

limite = normativa.fecha_limite(exp["fecha_orden"], exp["plazo_dias"])  # POR VERIFICAR

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

# --- Resumen de estado ---------------------------------------------------------
cumplidos = [e for e in entregables if e["cumplido"]]
cumplidos_sin_evidencia = [e for e in cumplidos if not e["evidencias"]]
alertas_sin_cerrar = [a for a in alertas if a["estado"] != ESTADO_CERRADA]


def _estado_entregable(e: dict) -> tuple[str, str]:
    """Texto y color del estado de un entregable."""
    if e["cumplido"] is None:
        return "Sin conformidad", "gray"
    if not e["cumplido"]:
        return "No cumplido", "red"
    if not e["evidencias"]:
        return "Cumplido · SIN evidencia", "orange"
    return "Cumplido · con evidencia", "green"


with st.container(border=True):
    st.markdown("**Resumen**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Conformidad", "Registrada" if conformidad else "Pendiente")
    c2.metric("Cumplidos con evidencia",
              f"{len(cumplidos) - len(cumplidos_sin_evidencia)} de {len(cumplidos)}"
              if conformidad else "—",
              help="Entregables dados por cumplidos que tienen al menos un archivo adjunto.")
    c3.metric("Alertas sin cerrar", len(alertas_sin_cerrar))
    c4.metric("Pagos", len(pagos))
    if cumplidos_sin_evidencia:
        numeros = ", ".join(str(e["numero"]) for e in cumplidos_sin_evidencia)
        st.warning(
            f"Faltan evidencias: los entregables n.º {numeros} se dieron por cumplidos "
            "sin ningún archivo adjunto.", icon=":material/warning:")

# --- Alertas -------------------------------------------------------------------
st.divider()
st.subheader("Alertas")
st.caption(AVISO_NO_BLOQUEA)
if not alertas:
    st.write("Este expediente no tiene alertas.")
for a in alertas:
    with st.container(border=True):
        st.markdown(
            f"**{a['regla']} · {normativa.NOMBRE_REGLA[a['regla']]}** — "
            f"severidad {ETIQUETAS_SEVERIDAD[a['severidad']].lower()} · "
            f"{ETIQUETAS_ESTADO[a['estado']]}"
        )
        st.write(a["explicacion"])
        if a["implicado"]:
            st.caption(f"Persona implicada: {a['implicado']}")
        if st.button("Revisar en la bandeja", key=f"alerta_{a['id']}",
                     icon=":material/notification_important:"):
            st.session_state["alerta_id"] = a["id"]
            st.switch_page("paginas/alertas.py")

if actor.rol in (ROL_AREA_USUARIA, ROL_TESORERIA):
    if st.button("Reevaluar reglas", icon=":material/refresh:",
                 help="Vuelve a pasar las reglas R1–R5 por este expediente. No duplica alertas."):
        with db.sesion() as s:
            nuevas = repositorio.reevaluar(s, actor, expediente_id)
        st.session_state["aviso"] = (
            f"Reglas reevaluadas: {nuevas} alertas nuevas." if nuevas
            else "Reglas reevaluadas: no hay alertas nuevas.")
        st.rerun()

# --- Entregables y conformidad -------------------------------------------------
st.divider()
st.subheader("Entregables y conformidad")
if conformidad:
    st.markdown(
        f"**Conformidad registrada** por {conformidad['conformante']} · "
        f"fecha {fecha(conformidad['fecha_conformidad'])} · "
        f"penalidad aplicada {soles(conformidad['penalidad_aplicada'])}"
    )
    if conformidad["observaciones"]:
        st.caption(f"Observaciones: {conformidad['observaciones']}")
    if conformidad["codigo_sello"]:
        url_sello = sello.url_verificacion(conformidad["codigo_sello"])
        with st.expander("Sello de conformidad (QR)", icon=":material/qr_code_2:"):
            columna_qr, columna_datos = st.columns([1, 2])
            columna_qr.image(sello.png_qr(conformidad["codigo_sello"]), width=180)
            columna_datos.markdown(
                f"**Código:** `{conformidad['codigo_sello']}`  \n"
                f"**Registro de bitácora sellado:** n.º {conformidad['sello_bitacora_id']}  \n"
                f"**Hash:** `{conformidad['sello_hash'][:24]}…`  \n"
                f"**Verificación pública:** [{url_sello}]({url_sello})"
            )
            columna_datos.download_button(
                "Descargar sello (PNG)",
                sello.png_sello(conformidad["codigo_sello"], exp["codigo"],
                                conformidad["sello_hash"]),
                file_name=f"sello-{exp['codigo']}.png", mime="image/png",
                icon=":material/download:",
            )
elif not entregables:
    st.info("Este expediente no tiene entregables cargados.")
else:
    st.info("Conformidad pendiente.")
    if actor.rol == ROL_AREA_USUARIA:
        if st.button("Registrar conformidad", type="primary", icon=":material/task_alt:"):
            st.switch_page("paginas/conformidad.py")
        if st.button("Leer términos de referencia con IA", icon=":material/auto_awesome:"):
            st.switch_page("paginas/lectura_ia.py")

hay_evidencias = any(e["evidencias"] for e in entregables)
ver_evidencias = hay_evidencias and st.toggle("Mostrar evidencias")
for e in entregables:
    with st.container(border=True):
        texto_estado, color_estado = _estado_entregable(e)
        st.markdown(f"**{e['numero']}. {e['descripcion']}**")
        st.badge(texto_estado, color=color_estado)
        if e["observacion"]:
            st.caption(f"Observación: {e['observacion']}")
        if e["cumplido"] is not None:
            if not e["evidencias"]:
                st.caption(":material/warning: No hay ningún archivo adjunto.")
            for evidencia in e["evidencias"]:
                st.caption(
                    f"Evidencia: {evidencia['nombre_archivo']} · "
                    f"{evidencia['tamano'] / 1024:.1f} KB · SHA-256 `{evidencia['sha256'][:16]}…`"
                )
                if ver_evidencias:
                    with db.sesion() as s:
                        archivo = repositorio.obtener_evidencia(s, actor, evidencia["id"])
                    if archivo and archivo["mime"].startswith("image/"):
                        st.image(bytes(archivo["contenido"]), width=200)
                    elif archivo:
                        st.download_button(
                            f"Descargar {archivo['nombre_archivo']}",
                            bytes(archivo["contenido"]), file_name=archivo["nombre_archivo"],
                            mime=archivo["mime"], key=f"evidencia_{evidencia['id']}",
                        )

# --- Pagos ---------------------------------------------------------------------
st.divider()
st.subheader("Pagos")
if not pagos:
    st.write("Sin pagos registrados.")
elif alertas_sin_cerrar:
    st.warning(
        f"Este expediente tiene {len(alertas_sin_cerrar)} alertas sin cerrar y ya registra "
        "pagos. El sistema no bloquea el pago: es una señal para revisar.",
        icon=":material/warning:")
for p in pagos:
    st.markdown(
        f"- {fecha(p['fecha_pago'])} · {soles(p['monto'])} · penalidad descontada "
        f"{soles(p['penalidad_descontada'])} · registrado por {p['registrado_por']}"
    )

if actor.rol == ROL_TESORERIA:
    sin_cerrar = [a for a in alertas if a["estado"] != ESTADO_CERRADA]
    with st.expander("Registrar pago", icon=":material/payments:"):
        if sin_cerrar:
            st.warning(
                f"Este expediente tiene {len(sin_cerrar)} alertas sin cerrar. "
                "El sistema no bloquea el pago: la decisión es tuya.",
                icon=":material/warning:",
            )
        if not conformidad:
            st.warning("El expediente no tiene conformidad registrada.",
                       icon=":material/warning:")
        with st.form("pago"):
            fecha_pago = st.date_input("Fecha de pago", value=date.today(), format="DD/MM/YYYY")
            monto = st.number_input("Monto pagado (S/)", min_value=0.0,
                                    value=float(exp["monto"]), step=100.0, format="%.2f")
            descontada = st.number_input("Penalidad descontada (S/)", min_value=0.0,
                                         value=0.0, step=10.0, format="%.2f")
            if st.form_submit_button("Registrar pago", type="primary"):
                try:
                    with db.sesion() as s:
                        repositorio.registrar_pago(
                            s, actor, expediente_id, fecha_pago=fecha_pago,
                            monto=f"{monto:.2f}", penalidad_descontada=f"{descontada:.2f}")
                except (ErrorValidacion, PermisoDenegado) as error:
                    st.error(str(error))
                else:
                    st.session_state["aviso"] = "Pago registrado. Se reevaluaron las reglas."
                    st.rerun()
elif actor.rol == ROL_AUDITOR:
    st.caption("Auditoría: solo lectura.")

# --- Línea de tiempo -----------------------------------------------------------
st.divider()
st.subheader("Línea de tiempo")
st.caption("Quién hizo qué, cuándo y con qué documento. Proviene de la bitácora encadenada.")

for e in eventos:
    with st.container(border=True):
        st.markdown(
            f"**{ETIQUETAS_ACCION.get(e['accion'], e['accion'])}** · "
            f"{fecha_hora(e['ts'])} · {e['actor'] or 'Sistema'}"
        )
        if e["detalle"].get("resumen"):
            st.write(e["detalle"]["resumen"])
        if e["documento_sha256"]:
            documento = e["detalle"].get("documento", "documento")
            st.caption(f"Documento: {documento} · SHA-256 `{e['documento_sha256'][:16]}…`")
        st.caption(f"Registro de bitácora n.º {e['id']}")
