import streamlit as st

from conforme import db, repositorio
from conforme.interfaz import actor_actual

actor = actor_actual()

st.title("Expedientes")
texto = st.text_input("Buscar por código, descripción o proveedor")

with db.sesion() as s:
    filas = repositorio.listar_expedientes(s, actor, texto=texto)

alcance = "de tu área" if actor.rol == "area_usuaria" else "de toda la entidad"
st.caption(f"{len(filas)} expedientes {alcance}. Selecciona una fila para ver su detalle.")

tabla = [
    {
        "Código": f["codigo"],
        "Área": f["area_sigla"],
        "Tipo": f["tipo"].capitalize(),
        "Descripción": f["descripcion"],
        "Proveedor": f["proveedor"],
        "Orden": f["fecha_orden"],
        "Plazo (días)": f["plazo_dias"],
        "Monto (S/)": float(f["monto"]),
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
