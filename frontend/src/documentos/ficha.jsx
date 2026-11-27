"use client";

import { useState } from "react";
import Link from "next/link";
import { Download, FileSearch, FileText, ScanSearch, Trash2, Upload } from "lucide-react";
import { api, useAccion, useDatos } from "../api";
import { fechaHora, rutaExpediente } from "../dominio";
import { Aviso, Campo, Carga, DatosClave, Encabezado, EstadoAccion, Indicador, ProximoPaso, Volver } from "../ui";
import { ResultadoBenford } from "./benford";
import { VEREDICTOS_DOC } from "./bandeja";

const ESTADOS = { limpio: ["Sin observaciones", "verde"], revisar: ["Revisar", "ambar"], alerta: ["Alerta", "rojo"] };
const TDR = { acreditado: ["Acreditado", "verde", "✓"], incompleto: ["Incompleto o ambiguo", "ambar", "!"],
  no_cumple: ["No lo cubre", "rojo", "✕"] };

function Hallazgos({ hallazgos }) {
  if (!hallazgos.length) return <p className="secundario">No se encontró nada que revisar en este bloque.</p>;
  return <ul className="hallazgos">{hallazgos.map((h, i) => (
    <li key={i} className={`hallazgo hallazgo-${h.nivel}`}>
      <strong>{h.que}</strong>
      <p><span className="etiqueta-hallazgo">Por qué importa:</span> {h.por_que}</p>
      <p><span className="etiqueta-hallazgo">Qué hacer:</span> {h.accion}</p>
    </li>
  ))}</ul>;
}

function DetalleMontos({ detalle }) {
  return <>
    {detalle.documentos.map((d) => {
      const errores = d.partidas.filter((p) => !p.cuadra).length;
      return <details key={d.documento} className="cuadre">
        <summary><strong>{d.postor}</strong> · {d.documento} · {d.partidas.length} partida(s) ·{" "}
          {errores ? <Indicador tono="rojo">{errores} no cuadra{errores === 1 ? "" : "n"}</Indicador>
            : <Indicador tono="verde">Todo cuadra</Indicador>}</summary>
        {d.partidas.length > 0 && <div className="tabla-scroll tabla-comparativo"><table className="comparativo">
          <thead><tr><th scope="col">Partida</th><th scope="col" className="numero">Cant.</th>
            <th scope="col" className="numero">P. unitario</th><th scope="col" className="numero">Subtotal</th>
            <th scope="col">¿Cuadra?</th></tr></thead>
          <tbody>{d.partidas.map((p, i) => (
            <tr key={i}><th scope="row">{p.descripcion}</th><td className="numero">{p.cantidad}</td>
              <td className="numero">{Number(p.precio_unitario).toFixed(2)}</td><td className="numero">{Number(p.subtotal).toFixed(2)}</td>
              <td>{p.cuadra ? <Indicador tono="verde">Sí</Indicador>
                : <Indicador tono="rojo">No · debería ser {Number(p.esperado).toFixed(2)}</Indicador>}</td></tr>
          ))}</tbody>
        </table></div>}
        {d.totales.total && <small>Subtotal {d.totales.subtotal ?? "—"} · IGV {d.totales.igv ?? "—"} · Total {d.totales.total}
          {d.totales.letras && ` · En letras: «${d.totales.letras}»`}</small>}
      </details>;
    })}
    <ResultadoBenford resultado={detalle.benford} titulo="Primer dígito de las partidas" />
  </>;
}

function DetalleMetadatos({ detalle }) {
  return <div className="tabla-scroll tabla-comparativo"><table className="comparativo">
    <thead><tr><th scope="col">Documento</th><th scope="col">Autor</th><th scope="col">Programa</th>
      <th scope="col">Creado</th><th scope="col">Modificado</th></tr></thead>
    <tbody>{detalle.documentos.map((d, i) => (
      <tr key={i}><th scope="row">{d.documento}<small className="dato-tabla">{d.postor} · {d.tipo}</small></th>
        <td>{d.autor ?? "—"}</td><td>{d.programa ?? "—"}</td><td>{d.creado}</td><td>{d.modificado}</td></tr>
    ))}</tbody>
  </table></div>;
}

function DetalleSimilitud({ detalle }) {
  if (!detalle.pares.length) return null;
  return <ul className="lista-simple">{detalle.pares.map((p) => (
    <li key={p.postores.join()}>
      <strong>{p.postores.join(" y ")}</strong>: {Math.round(p.similitud * 100)} % de texto en común.
      {p.frases_identicas.length > 0 && <ul>{p.frases_identicas.map((f, i) => <li key={i}><q>{f}</q></li>)}</ul>}
    </li>
  ))}</ul>;
}

function DetalleTdr({ detalle }) {
  return <div className="checklist-tdr">{detalle.checklist.map((c) => (
    <div key={c.postor}>
      <h4>{c.postor}</h4>
      <ul className="lista-tdr">{c.items.map((i) => {
        const [texto, tono, simbolo] = TDR[i.estado];
        return <li key={i.entregable}><span className={`marca-tdr marca-${tono}`} aria-hidden="true">{simbolo}</span>
          <span>{i.entregable}</span><Indicador tono={tono}>{texto}</Indicador>
          {i.estado !== "acreditado" && i.faltan.length > 0 && <small>No menciona: {i.faltan.join(", ")}</small>}</li>;
      })}</ul>
    </div>
  ))}<small className="secundario">Lectura asistida (simulada): contrasta los términos de cada entregable con el texto de la propuesta.</small></div>;
}

function DetalleCoherencia({ detalle }) {
  return <details className="huellas"><summary>Huellas SHA-256 de los documentos</summary>
    <ul className="lista-simple">{detalle.huellas.map((h) => (
      <li key={h.documento + h.postor}>{h.postor} · {h.documento} · <code>{h.sha256.slice(0, 20)}…</code></li>))}</ul>
  </details>;
}

const DETALLES = { montos: DetalleMontos, metadatos: DetalleMetadatos, similitud: DetalleSimilitud, tdr: DetalleTdr,
  coherencia: DetalleCoherencia };

function Bloque({ bloque }) {
  const [texto, tono] = ESTADOS[bloque.estado];
  const Detalle = DETALLES[bloque.clave];
  return (
    <details className="dimension">
      <summary>
        <span className={`punto-dimension punto-${bloque.estado}`} aria-hidden="true" />
        <strong>{bloque.titulo}</strong>
        <span className="dimension-resumen">{bloque.resumen}</span>
        <Indicador tono={tono}>{texto}</Indicador>
      </summary>
      <div className="dimension-detalle">
        <Hallazgos hallazgos={bloque.hallazgos} />
        <Detalle detalle={bloque.detalle} />
      </div>
    </details>
  );
}

function SubirDocumento({ expedienteId, postor, tipos, recargar }) {
  const accion = useAccion();
  function enviar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const data = new FormData(form);
    accion.ejecutar(async () => {
      await api(`/expedientes/${expedienteId}/postores/${postor.id}/documentos`, { method: "POST", data });
      form.reset();
      recargar();
      return "Documento cargado. Vuelve a analizar para incluirlo.";
    });
  }
  return (
    <details className="desplegable subir-documento">
      <summary><Upload size={16} /> Cargar documento</summary>
      <form className="formulario" onSubmit={enviar}>
        <div className="rejilla dos">
          <Campo titulo="Tipo"><select name="tipo" required defaultValue="cotizacion">
            {Object.entries(tipos).map(([clave, texto]) => <option key={clave} value={clave}>{texto}</option>)}
          </select></Campo>
          <Campo titulo="Archivo" ayuda="PDF, Word, Excel, CSV o imagen; hasta 5 MB.">
            <input type="file" name="archivo" required accept=".pdf,.docx,.xlsx,.csv,.jpg,.jpeg,.png" /></Campo>
        </div>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>Cargar</button></div>
      </form>
    </details>
  );
}

function Documentos({ datos, recargar }) {
  const accion = useAccion();
  const id = datos.expediente.id;
  return (
    <section className="seccion" aria-labelledby="titulo-documentos">
      <h2 id="titulo-documentos"><FileText size={19} /> Documentos presentados</h2>
      <div className="postores">
        {datos.postores.map((p) => (
          <article key={p.id} className="panel documentos-postor">
            <div className="fila-titulo"><h3>{p.razon_social}</h3><small>RUC {p.ruc}</small></div>
            {p.documentos.length ? <ul className="lista-documentos">{p.documentos.map((d) => (
              <li key={d.id}>
                <span><strong>{datos.tipos[d.tipo]}</strong> · {d.nombre_archivo}
                  <small className="dato-tabla">{(d.tamano / 1024).toFixed(1)} KB · {fechaHora(d.subido_en)}</small></span>
                <span className="acciones">
                  <a className="boton boton-sutil" href={`/api/documentos/archivo/${d.id}`}><Download size={15} /> Descargar</a>
                  {datos.puede_subir && <button type="button" className="boton-sutil" disabled={accion.pendiente}
                    aria-label={`Quitar ${d.nombre_archivo}`} onClick={() => {
                      if (!window.confirm(`¿Quitar ${d.nombre_archivo}?`)) return;
                      accion.ejecutar(async () => {
                        await api(`/expedientes/${id}/documentos/${d.id}`, { method: "DELETE" });
                        recargar();
                        return "Documento quitado.";
                      });
                    }}><Trash2 size={15} /></button>}
                </span>
              </li>
            ))}</ul> : <p className="secundario">Sin documentos.</p>}
            {datos.puede_subir && <SubirDocumento expedienteId={id} postor={p} tipos={datos.tipos} recargar={recargar} />}
          </article>
        ))}
      </div>
      <EstadoAccion accion={accion} />
    </section>
  );
}

export function FichaDocumentos({ id }) {
  const recurso = useDatos(`/expedientes/${id}/documentos`);
  const accion = useAccion();
  if (!recurso.datos) return <><Volver to="/documentos">Revisión documental</Volver><Carga recurso={recurso} /></>;
  const datos = recurso.datos;
  const { expediente, revision } = datos;
  const total = datos.postores.reduce((n, p) => n + p.documentos.length, 0);
  const analizar = () => accion.ejecutar(async () => {
    const r = await api(`/expedientes/${id}/documentos/analisis`, { method: "POST" });
    recurso.recargar();
    return `Análisis listo: ${r.titulo.toLowerCase()} (${r.conteo.alerta} bloque(s) en alerta, ${r.conteo.revisar} por revisar).`;
  });
  const [veredicto, tono] = revision ? VEREDICTOS_DOC[revision.veredicto] : [];
  return (
    <>
      <Volver to="/documentos">Revisión documental</Volver>
      <div className="caratula">
        <Encabezado titulo={expediente.descripcion} descripcion={expediente.area}
          acciones={revision && <Indicador tono={tono}>{veredicto}</Indicador>}>
          <div className="caratula-codigo">{expediente.codigo} <span>{total} documento(s) de {datos.postores.length} postor(es)</span></div>
        </Encabezado>
      </div>
      <div className="acciones">
        <Link className="boton" href={rutaExpediente(expediente.id)}>Ver expediente</Link>
        <Link className="boton" href={`/prevencion/${expediente.id}`}><ScanSearch size={16} /> Ver evaluación de proveedores</Link>
      </div>
      {datos.puede_analizar && (!revision || datos.documentos_cambiaron) && (total > 0
        ? <ProximoPaso tono={revision ? "advertencia" : "info"}
          titulo={revision ? "Los documentos cambiaron desde el último análisis" : "Analiza la documentación"}
          acciones={<button className="primario" disabled={accion.pendiente} onClick={analizar}>
            <FileSearch size={16} /> {accion.pendiente ? "Analizando…" : "Analizar documentación"}</button>}>
          Revisa en un solo paso: montos y Benford, metadatos, textos repetidos entre postores, cumplimiento del TDR y vigencias.
        </ProximoPaso>
        : <ProximoPaso titulo="Carga los documentos de los postores">Sube cotizaciones, presupuestos, declaraciones o certificados para analizarlos.</ProximoPaso>)}
      {!datos.puede_analizar && !revision && <Aviso>Este expediente aún no tiene revisión documental.</Aviso>}
      <EstadoAccion accion={accion} />
      {revision && <section className={`seccion veredicto-documental veredicto-${revision.veredicto}`} aria-labelledby="titulo-veredicto">
        <h2 id="titulo-veredicto">{veredicto}</h2>
        <p>{revision.resumen}</p>
        <DatosClave valores={[["Analizado", `${fechaHora(revision.creado_en)} por ${revision.creado_por}`],
          ["Documentos", `${revision.archivos.documentos.length}`]]} />
        {revision.archivos.documentos.some((d) => d.aviso) && <Aviso tipo="advertencia">
          Algunos archivos no se pudieron leer: {revision.archivos.documentos.filter((d) => d.aviso).map((d) => d.nombre).join(", ")}.
        </Aviso>}
        <div className="dimensiones" role="list" aria-label="Bloques del análisis documental">
          {Object.keys(datos.bloques).map((clave) => (
            <div role="listitem" key={clave}><Bloque bloque={revision.resultados[clave]} /></div>
          ))}
        </div>
        <small className="secundario">Ábrelo para ver el detalle. La lectura del TDR y el resumen son asistidos (simulados).</small>
      </section>}
      <Documentos datos={datos} recargar={recurso.recargar} />
    </>
  );
}
