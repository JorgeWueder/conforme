import streamlit as st

from conforme import db, repositorio
from conforme.interfaz import ETIQUETAS_SEMAFORO, actor_actual, mostrar_aviso_pendiente

actor = actor_actual()

st.title("Expedientes")
mostrar_aviso_pendiente()

izquierda, derecha = st.columns([2, 1])
texto = izquierda.text_input("Buscar por código, descripción o proveedor")
colores = derecha.multiselect(
    "Semáforo", list(ETIQUETAS_SEMAFORO), format_func=ETIQUETAS_SEMAFORO.get,
    placeholder="Todos",
)

with db.sesion() as s:
    filas = repositorio.listar_expedientes(s, actor, texto=texto)
if colores:
    filas = [f for f in filas if f["semaforo"] in colores]

alcance = "de tu área" if actor.rol == "area_usuaria" else "de toda la entidad"
st.caption(
    f"{len(filas)} expedientes {alcance}. Selecciona una fila para ver su detalle. "
    "Semáforo: rojo = alguna alerta alta sin cerrar; ámbar = solo medias; verde = ninguna."
)

tabla = [
    {
        "Semáforo": ETIQUETAS_SEMAFORO[f["semaforo"]],
        "Código": f["codigo"],
        "Área": f["area_sigla"],
        "Tipo": f["tipo"].capitalize(),
        "Descripción": f["descripcion"],
        "Proveedor": f["proveedor"],
        "Orden": f["fecha_orden"],
        "Plazo (días)": f["plazo_dias"],
        "Monto (S/)": float(f["monto"]),
        "Conformidad": "Registrada" if f["tiene_conformidad"] else "Pendiente",
        "Alertas sin cerrar": f["alertas_altas"] + f["alertas_medias"],
    }
    for f in filas
]
evento = st.dataframe(
    tabla,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Orden": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Monto (S/)": st.column_config.NumberColumn(format="%.2f"),
    },
)
if evento.selection.rows:
    st.session_state["expediente_id"] = filas[evento.selection.rows[0]]["id"]
    st.switch_page("paginas/expediente_detalle.py")
