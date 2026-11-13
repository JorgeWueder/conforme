import streamlit as st

from conforme import db, repositorio
from conforme.interfaz import ETIQUETAS_ACCION, actor_actual, fecha_hora

actor = actor_actual()

st.title("Bitácora")
st.caption(
    "Cada registro guarda el hash del anterior. Si alguien modifica, borra o "
    "reordena un registro, la cadena deja de cuadrar."
)

if st.button("Verificar integridad", type="primary", icon=":material/fact_check:"):
    with db.sesion() as s:
        resultado = repositorio.verificar_integridad(s, actor)
    if resultado.integra:
        st.success(f"Cadena íntegra: {resultado.total} registros verificados.",
                   icon=":material/check_circle:")
    else:
        st.error(
            f"Cadena alterada en el registro n.º {resultado.id_roto} "
            f"(de {resultado.total}). {resultado.motivo}",
            icon=":material/error:",
        )

with db.sesion() as s:
    filas = repositorio.listar_bitacora(s, actor, limite=200)

st.caption(f"Últimos {len(filas)} registros.")
st.dataframe(
    [
        {
            "N.º": f["id"],
            "Fecha": fecha_hora(f["ts"]),
            "Quién": f["actor"] or "Sistema",
            "Acción": ETIQUETAS_ACCION.get(f["accion"], f["accion"]),
            "Expediente": f["expediente"],
            "Documento (SHA-256)": (f["documento_sha256"] or "")[:16],
            "Hash anterior": f["hash_anterior"][:16],
            "Hash": f["hash"][:16],
        }
        for f in filas
    ],
    hide_index=True,
)
