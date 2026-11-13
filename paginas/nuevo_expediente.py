from datetime import date

import streamlit as st

from conforme import db, entregables as validacion, repositorio
from conforme.errores import ErrorValidacion
from conforme.interfaz import actor_actual
from conforme.modelos import ROL_AREA_USUARIA
from conforme.permisos import PermisoDenegado

actor = actor_actual()
st.title("Nuevo expediente")

if actor.rol != ROL_AREA_USUARIA:
    st.error("Solo el área usuaria registra expedientes.")
    st.stop()

st.caption("El expediente queda en tu área y tú figuras como solicitante.")

with db.sesion() as s:
    proveedores = repositorio.listar_proveedores(s, actor)

tipo = st.radio("Tipo", ["servicio", "bien"], format_func=str.capitalize, horizontal=True)
descripcion = st.text_area("Descripción del bien o servicio")
proveedor = st.selectbox(
    "Proveedor", proveedores, index=None, placeholder="Elige un proveedor",
    format_func=lambda p: f"{p['razon_social']} (RUC {p['ruc']})",
)
izquierda, centro, derecha = st.columns(3)
numero_orden = izquierda.text_input("Número de la orden", placeholder="OS-2026-00301")
plazo_dias = centro.number_input("Plazo (días calendario)", min_value=1, value=30, step=1)
monto = derecha.number_input("Monto (S/)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
izquierda, centro, derecha = st.columns(3)
fecha_requerimiento = izquierda.date_input("Fecha del requerimiento", value=date.today(),
                                           format="DD/MM/YYYY")
fecha_orden = centro.date_input("Fecha de la orden", value=date.today(), format="DD/MM/YYYY")
fecha_inicio = derecha.date_input("Inicio de la prestación", value=date.today(),
                                  format="DD/MM/YYYY")

st.subheader("Entregables")
modo = st.radio("Cómo cargarlos", ["A mano", "Desde un archivo CSV"], horizontal=True)
entregables, errores = [], []
if modo == "A mano":
    st.caption("Añade una fila por entregable.")
    filas = st.data_editor(
        [{"numero": 1, "descripcion": ""}],
        num_rows="dynamic",
        column_config={
            "numero": st.column_config.NumberColumn("N.º", min_value=1, step=1, format="%d"),
            "descripcion": st.column_config.TextColumn("Descripción", width="large"),
        },
        key="editor_entregables",
    )
    if hasattr(filas, "to_dict"):
        filas = filas.to_dict("records")
    for f in filas:
        numero, texto = f.get("numero"), f.get("descripcion")
        numero = None if numero is None or numero != numero else int(numero)  # NaN = vacío
        texto = texto if isinstance(texto, str) else ""
        if numero is None and not texto.strip():
            continue  # fila vacía
        entregables.append({"numero": numero if numero is not None else "", "descripcion": texto})
    origen = "manual"
else:
    st.caption("Archivo con encabezado `numero,descripcion` y una fila por entregable.")
    archivo = st.file_uploader("Archivo CSV", type=["csv"])
    if archivo:
        entregables, errores = validacion.leer_csv(archivo.getvalue())
        if errores:
            st.error("No se puede usar el archivo:\n\n" + "\n".join(f"- {e}" for e in errores))
        else:
            st.success(f"{len(entregables)} entregables leídos del archivo.")
            st.dataframe(
                [{"N.º": e["numero"], "Descripción": e["descripcion"]} for e in entregables],
                hide_index=True,
            )
    origen = "csv"

if st.button("Registrar expediente", type="primary", icon=":material/note_add:",
             disabled=bool(errores)):
    try:
        if proveedor is None:
            raise ErrorValidacion("Elige un proveedor.")
        with db.sesion() as s:
            nuevo_id = repositorio.crear_expediente(
                s, actor, tipo=tipo, descripcion=descripcion, proveedor_id=proveedor["id"],
                numero_orden=numero_orden, fecha_requerimiento=fecha_requerimiento,
                fecha_orden=fecha_orden, fecha_inicio_prestacion=fecha_inicio,
                plazo_dias=int(plazo_dias), monto=f"{monto:.2f}",
                entregables=entregables, origen_entregables=origen,
            )
    except (ErrorValidacion, PermisoDenegado) as error:
        st.error(str(error))
    else:
        st.session_state["expediente_id"] = nuevo_id
        st.session_state["aviso"] = "Expediente registrado."
        st.switch_page("paginas/expediente_detalle.py")
