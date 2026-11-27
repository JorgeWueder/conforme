"use client";

import { useState } from "react";
import Link from "next/link";
import { useDatos } from "../api";
import { ESTADOS_FLUJO, fecha, fechaHora } from "../dominio";
import { useConsulta, useNavegar } from "../navegacion";
import { useSesion } from "../sesion";
import { Campo, Carga, Encabezado, Indicador, Resumen, Tabla } from "../ui";
import { ResultadoBenford } from "./benford";

export const rutaDocumentos = (id) => `/documentos/${id}`;
export const VEREDICTOS_DOC = {
  conforme: ["Documentación coherente", "verde"],
  revisar: ["Puntos por revisar", "ambar"],
  anomalia: ["Anomalías", "rojo"],
};

function PorExpediente() {
  const recurso = useDatos("/documentos");
  const navegar = useNavegar();
  const [vista, setVista] = useState(null);
  const filas = recurso.datos;
  const filtros = {
    sin_analizar: (f) => f.documentos > 0 && !f.veredicto,
    sin_documentos: (f) => f.documentos === 0,
    anomalia: (f) => f.veredicto === "anomalia",
  };
  const visibles = filas && (vista ? filas.filter(filtros[vista]) : filas);
  const contar = (clave) => filas ? filas.filter(filtros[clave]).length : "…";
  const columnas = [
    { titulo: "Expediente", valor: (f) => f.codigo, render: (f) => <>
      <Link className="codigo-expediente" href={rutaDocumentos(f.id)}>{f.codigo}</Link>
      <small className="dato-tabla">Requerido el {fecha(f.fecha_requerimiento)}</small>
    </> },
    { titulo: "Qué se compra", valor: (f) => f.descripcion, clase: "celda-texto prestacion", render: (f) => <>
      <span className="recorte" title={f.descripcion}>{f.descripcion}</span>
      <small className="dato-tabla">{f.area} · {ESTADOS_FLUJO[f.estado_flujo]?.[0]}</small>
    </> },
    { titulo: "Documentos", valor: (f) => f.documentos, clase: "columna-amplia",
      render: (f) => <span>{f.documentos} documento{f.documentos === 1 ? "" : "s"}
        <small className="dato-tabla">{f.postores} postor{f.postores === 1 ? "" : "es"}</small></span> },
    { titulo: "Resultado", valor: (f) => f.veredicto ?? "", render: (f) => {
      if (!f.documentos) return <small>Sin documentos cargados</small>;
      if (!f.veredicto) return <Indicador>Sin analizar</Indicador>;
      const [texto, tono] = VEREDICTOS_DOC[f.veredicto];
      return <div className="celda-estado"><Indicador tono={tono}>{texto}</Indicador>
        <small>{fechaHora(f.analizado_en)}</small></div>;
    } },
  ];
  return (
    <section className="registro-expedientes" aria-label="Expedientes con documentos de postores">
      <div className="registro-controles">
        <Resumen activo={vista ?? "todos"} onChange={(clave) => setVista(clave === "todos" ? null : clave)} opciones={[
          { clave: "todos", titulo: "Todos", valor: filas?.length ?? "…" },
          { clave: "sin_analizar", titulo: "Por analizar", valor: contar("sin_analizar"), ayuda: "Tienen documentos sin revisar" },
          { clave: "anomalia", titulo: "Con anomalías", valor: contar("anomalia"), tono: "rojo" },
          { clave: "sin_documentos", titulo: "Sin documentos", valor: contar("sin_documentos"), tono: "ambar" },
        ]} />
      </div>
      {visibles ? <>
        <Tabla columnas={columnas} filas={visibles} etiqueta="Revisión documental por expediente"
          alElegir={(fila) => navegar(rutaDocumentos(fila.id))} vacio="No hay expedientes en esta vista." />
        <p className="registro-pie">{visibles.length} de {filas.length} expedientes</p>
      </> : <div className="registro-pie"><Carga recurso={recurso} /></div>}
    </section>
  );
}

function MontosEntidad() {
  const [filtros, setFiltros] = useState({ fuente: "ordenes", area_id: "", ruc: "", desde: "", hasta: "" });
  const [rucTexto, setRucTexto] = useState("");
  const consulta = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v)).toString();
  const recurso = useDatos(`/documentos/benford?${consulta}`);
  const cambiar = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value });
  const datos = recurso.datos;
  return (
    <section className="seccion" aria-labelledby="titulo-transversal">
      <h2 id="titulo-transversal">Auditoría transversal de montos</h2>
      <p className="secundario">Aplica la Ley de Benford a los montos de las órdenes o de los pagos de la entidad.
        Filtra por área, proveedor o periodo para encontrar dónde se concentran los montos atípicos.</p>
      <div className="barra-filtros filtros-benford">
        <Campo titulo="Montos de"><select value={filtros.fuente} onChange={cambiar("fuente")}>
          <option value="ordenes">Órdenes emitidas</option><option value="pagos">Pagos registrados</option>
        </select></Campo>
        <Campo titulo="Área"><select value={filtros.area_id} onChange={cambiar("area_id")}>
          <option value="">Todas</option>
          {datos?.areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
        </select></Campo>
        <Campo titulo="RUC del proveedor (11 dígitos)"><input inputMode="numeric" maxLength={11} placeholder="Todos"
          value={rucTexto} onChange={(e) => {
            const valor = e.target.value.replace(/\D/g, "");
            setRucTexto(valor);
            if (valor.length === 11 || !valor) setFiltros({ ...filtros, ruc: valor });
          }} /></Campo>
        <Campo titulo="Desde"><input type="date" value={filtros.desde} onChange={cambiar("desde")} /></Campo>
        <Campo titulo="Hasta"><input type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></Campo>
      </div>
      {datos ? <div className="panel"><ResultadoBenford resultado={datos}
        titulo={`Primer dígito de los ${filtros.fuente === "pagos" ? "pagos" : "montos de las órdenes"}`} /></div>
        : <Carga recurso={recurso} />}
    </section>
  );
}

export function BandejaDocumentos() {
  const { actor } = useSesion();
  const [params, setParams] = useConsulta();
  const pestana = params.get("ver") === "montos" ? "montos" : "expedientes";
  const descripcion = {
    abastecimiento: "Revisa los documentos que presentan los postores: montos, metadatos, textos repetidos, cumplimiento del TDR y vigencias.",
    tesoreria: "Consulta las señales documentales y de Benford antes de registrar un pago.",
    auditor: "Audita la documentación de los postores y los montos de la entidad por proveedor, área o periodo.",
  }[actor.rol];
  return (
    <>
      <Encabezado titulo="Revisión documental" descripcion={descripcion} />
      <div className="pestanas" role="tablist" aria-label="Vistas de la revisión documental">
        {[["expedientes", "Por expediente"], ["montos", "Montos de la entidad (Benford)"]].map(([clave, texto]) => (
          <button key={clave} role="tab" aria-selected={pestana === clave} className={pestana === clave ? "activa" : ""}
            onClick={() => setParams((p) => { p.set("ver", clave); return p; }, { replace: true })}>{texto}</button>
        ))}
      </div>
      {pestana === "expedientes" ? <PorExpediente /> : <MontosEntidad />}
    </>
  );
}
