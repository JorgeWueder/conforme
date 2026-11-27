"use client";

import Link from "next/link";
import { useDatos } from "../api";
import { ESTADOS_FLUJO, fecha, soles } from "../dominio";
import { useConsulta, useNavegar } from "../navegacion";
import { useSesion } from "../sesion";
import { Carga, Encabezado, Indicador, Resumen, Tabla } from "../ui";

export const rutaEvaluacion = (id) => `/prevencion/${id}`;

const VISTAS = {
  atender: { titulo: "Por atender", ayuda: "Lo que te toca hacer hoy", tono: "neutro" },
  analizar: { titulo: "En evaluación", ayuda: "Proveedores por analizar, consolidar o seleccionar", tono: "neutro" },
  observadas: { titulo: "Observadas", ayuda: "La revisión independiente pidió cambios", tono: "ambar" },
  revision: { titulo: "En revisión independiente", ayuda: "Esperan la revisión de otro especialista", tono: "ambar" },
  aprobadas: { titulo: "Aprobadas", ayuda: "Selección aprobada", tono: "verde" },
};

function vistaDe(fila) {
  if (fila.estado_flujo === "pendiente_revision_independiente") return "revision";
  if (fila.estado_flujo === "en_evaluacion_proveedores") {
    return fila.estado_revision_independiente === "observada" ? "observadas" : "analizar";
  }
  return fila.estado_revision_independiente === "aprobada" ? "aprobadas" : "analizar";
}

function meToca(fila, actor) {
  if (actor.rol !== "abastecimiento") return false;
  if (fila.me_toca_revisar) return true;
  return fila.estado_flujo === "en_evaluacion_proveedores" && (fila.soy_evaluador || !fila.evaluador_id);
}

function Avance({ fila }) {
  if (!fila.postores) return <small>Sin posibles proveedores</small>;
  return <small>{fila.analizados} de {fila.postores} analizados</small>;
}

function QueSigue({ fila, actor }) {
  const [texto, , tono] = ESTADOS_FLUJO[fila.estado_flujo] ?? [fila.estado_flujo, "", "neutro"];
  let detalle = null;
  if (fila.me_toca_revisar) detalle = "Te toca revisarla";
  else if (fila.estado_flujo === "pendiente_revision_independiente") detalle = fila.soy_evaluador ? "La enviaste tú" : null;
  else if (fila.estado_revision_independiente === "observada") detalle = "Corrige lo observado";
  else if (fila.estado_flujo === "en_evaluacion_proveedores" && !fila.evaluador_id) detalle = "Nadie la ha iniciado";
  else if (fila.estado_flujo === "seleccion_aprobada") detalle = "Falta que el área confirme la orden";
  return <div className="celda-estado">
    <Indicador tono={fila.me_toca_revisar ? "ambar" : tono}>{texto}</Indicador>
    {detalle && actor.rol === "abastecimiento" && <small>{detalle}</small>}
  </div>;
}

export function BandejaEvaluaciones() {
  const { actor } = useSesion();
  const recurso = useDatos("/evaluaciones");
  const [params, setParams] = useConsulta();
  const navegar = useNavegar();
  const filas = recurso.datos;
  const esDec = actor.rol === "abastecimiento";
  const porVista = (clave) => filas?.filter((f) => clave === "atender" ? meToca(f, actor) : vistaDe(f) === clave) ?? [];
  const pedida = params.get("ver");
  const vista = pedida === "todas" ? null
    : VISTAS[pedida] && (esDec || pedida !== "atender") ? pedida : (esDec ? "atender" : null);
  const visibles = filas && (vista ? porVista(vista) : filas);
  const columnas = [
    { titulo: "Expediente", valor: (f) => f.codigo, render: (f) => <>
      <Link className="codigo-expediente" href={rutaEvaluacion(f.id)}>{f.codigo}</Link>
      <small className="dato-tabla">Requerido el {fecha(f.fecha_requerimiento)}</small>
    </> },
    { titulo: "Qué se compra", valor: (f) => f.descripcion, clase: "celda-texto prestacion", render: (f) => <>
      <span className="recorte" title={f.descripcion}>{f.descripcion}</span>
      <small className="dato-tabla">{f.area}</small>
    </> },
    { titulo: "Valor estimado", valor: (f) => Number(f.monto), render: (f) => soles(f.monto), clase: "numero columna-amplia" },
    { titulo: "Proveedores", valor: (f) => f.postores, render: (f) => <Avance fila={f} />, clase: "columna-amplia" },
    { titulo: "Estado", valor: (f) => f.estado_flujo, render: (f) => <QueSigue fila={f} actor={actor} /> },
    { titulo: "Responsable", valor: (f) => f.evaluador ?? "", clase: "columna-amplia", render: (f) => <>
      <span>{f.evaluador ?? "Sin asignar"}</span>
      {f.revisor && <small className="dato-tabla">Revisó: {f.revisor}</small>}
    </> },
  ];
  return (
    <>
      <Encabezado titulo="Análisis de proveedores"
        descripcion={esDec
          ? "Evalúa a los posibles proveedores de cada requerimiento, sustenta la selección y envíala a revisión independiente."
          : "Consulta en solo lectura las evaluaciones de proveedores y sus decisiones."} />
      <section className="registro-expedientes" aria-label="Bandeja de evaluaciones">
        <div className="registro-controles">
          <Resumen activo={vista ?? "todas"} onChange={(clave) => setParams((p) => {
            p.set("ver", clave ?? "todas");
            return p;
          }, { replace: true })} opciones={[
            ...(esDec ? [{ clave: "atender", ...VISTAS.atender, valor: filas ? porVista("atender").length : "…" }] : []),
            ...["analizar", "observadas", "revision", "aprobadas"].map((clave) => ({
              clave, ...VISTAS[clave], valor: filas ? porVista(clave).length : "…",
            })),
            { clave: "todas", titulo: "Todas", valor: filas?.length ?? "…" },
          ]} />
        </div>
        {visibles ? <>
          <Tabla columnas={columnas} filas={visibles} etiqueta="Evaluaciones de proveedores"
            alElegir={(fila) => navegar(rutaEvaluacion(fila.id))}
            vacio={vista === "atender" ? "No tienes evaluaciones pendientes. ¡Todo al día!" : "No hay evaluaciones en esta vista."} />
          <p className="registro-pie" aria-live="polite">{visibles.length} de {filas.length} evaluaciones</p>
        </> : <div className="registro-pie"><Carga recurso={recurso} /></div>}
      </section>
    </>
  );
}
