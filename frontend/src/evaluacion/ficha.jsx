"use client";

import { useState } from "react";
import Link from "next/link";
import {
  CircleCheck, CircleX, ClipboardList, FileSearch, Layers, Plus, RefreshCw, Scale, Send, ShieldCheck, Trash2,
} from "lucide-react";
import { api, useAccion, useDatos } from "../api";
import { ESTADOS_FLUJO, fecha, fechaHora, rutaExpediente, soles } from "../dominio";
import { Aviso, Campo, Carga, DatosClave, Encabezado, EstadoAccion, Indicador, ProximoPaso, Volver } from "../ui";

const ESTADOS = {
  limpio: ["Limpio", "verde"],
  revisar: ["Revisar", "ambar"],
  alerta: ["Alerta", "rojo"],
};
const VEREDICTO_TONO = { apto: "verde", apto_con_observaciones: "ambar", no_recomendado: "rojo" };
const ESTADO_POSTOR = {
  seleccionado: ["Seleccionado", "verde"],
  descartado: ["Descartado", "neutro"],
};

function porcentaje(variacion) {
  if (variacion == null) return "";
  const valor = Math.round(Math.abs(variacion) * 100);
  if (valor === 0) return "igual al estimado";
  return `${valor} % ${variacion > 0 ? "sobre" : "bajo"} el estimado`;
}

function Punto({ estado }) {
  return <span className={`punto-dimension punto-${estado}`} aria-hidden="true" />;
}

/* --- Pasos del proceso ------------------------------------------------------------------ */

function pasosDe(datos) {
  const { postores, evaluacion, expediente } = datos;
  const analizados = postores.length > 0 && postores.every((p) => p.analisis_completo);
  const consolidados = postores.length > 0 && postores.every((p) => p.consolidado);
  const enviada = ["pendiente_revision_independiente", "seleccion_aprobada"].includes(expediente.estado_flujo)
    || evaluacion?.estado_revision === "aprobada";
  const aprobada = evaluacion?.estado_revision === "aprobada";
  return [
    { titulo: "Analizar", detalle: "6 dimensiones por proveedor", hecho: analizados },
    { titulo: "Consolidar", detalle: "Veredicto y riesgos combinados", hecho: consolidados },
    { titulo: "Seleccionar y sustentar", detalle: "Elección, descartes y declaración", hecho: enviada },
    { titulo: "Revisión independiente", detalle: "Otro especialista revisa", hecho: aprobada },
  ];
}

function Pasos({ pasos }) {
  const actual = pasos.findIndex((p) => !p.hecho);
  return <ol className="etapas pasos-evaluacion" aria-label="Pasos de la evaluación">
    {pasos.map((paso, i) => (
      <li key={paso.titulo} data-estado={paso.hecho ? "registrada" : i === actual ? "actual" : "pendiente"}
        aria-current={i === actual ? "step" : undefined}>
        <span className="etapa-punto" aria-hidden="true" />
        <strong>{i + 1}. {paso.titulo}</strong>
        <span>{paso.detalle}</span>
        <small>{paso.hecho ? "Hecho" : i === actual ? "Ahora" : "Pendiente"}</small>
      </li>
    ))}
  </ol>;
}

/* --- Una dimensión: resumen en una línea, detalle al abrir ----------------------------- */

function Dimension({ clave, titulo, resultado, editable, reanalizar, pendiente }) {
  if (!resultado) {
    return <div className="dimension dimension-vacia"><Punto estado="vacio" /><strong>{titulo}</strong>
      <span className="dimension-resumen">Sin analizar</span></div>;
  }
  const [texto, tono] = ESTADOS[resultado.estado];
  return (
    <details className="dimension">
      <summary>
        <Punto estado={resultado.estado} />
        <strong>{titulo}</strong>
        <span className="dimension-resumen">{resultado.resumen}</span>
        <Indicador tono={tono}>{texto}</Indicador>
      </summary>
      <div className="dimension-detalle">
        {resultado.hallazgos.length > 0 ? <ul className="hallazgos">
          {resultado.hallazgos.map((h, i) => (
            <li key={i} className={`hallazgo hallazgo-${h.nivel}`}>
              <strong>{h.que}</strong>
              <p><span className="etiqueta-hallazgo">Por qué importa:</span> {h.por_que}</p>
              <p><span className="etiqueta-hallazgo">Qué hacer:</span> {h.accion}</p>
            </li>
          ))}
        </ul> : <p className="secundario">No se encontró nada que revisar en esta dimensión.</p>}
        {resultado.personas?.length > 0 && <div>
          <h4>Personas detrás de la empresa</h4>
          <ul className="lista-simple">{resultado.personas.map((p) => <li key={p.dni}>{p.nombre} · {p.rol}</li>)}</ul>
        </div>}
        <div>
          <h4>Fuentes consultadas</h4>
          <dl className="fuentes">{resultado.fuentes.map((f) => (
            <div key={f.nombre}><dt>{f.nombre}</dt><dd>{f.resultado}</dd></div>
          ))}</dl>
          <small>Fuente simulada · analizado {fechaHora(resultado.calculado_en)}</small>
        </div>
        {editable && <div><button type="button" className="boton-sutil" disabled={pendiente}
          onClick={() => reanalizar(clave)}><RefreshCw size={15} /> Volver a analizar esta dimensión</button></div>}
      </div>
    </details>
  );
}

function Notas({ expedienteId, postor, editable }) {
  const accion = useAccion();
  const [texto, setTexto] = useState(postor.notas ?? "");
  if (!editable) {
    return postor.notas ? <p className="nota-encargado"><strong>Nota del encargado:</strong> {postor.notas}</p> : null;
  }
  return (
    <details className="notas-postor desplegable" open={Boolean(postor.notas) || undefined}>
      <summary>{postor.notas ? "Notas del encargado" : "Agregar una nota"}</summary>
      <Campo titulo="Nota" ayuda="Queda en el expediente; úsala para tu sustento.">
        <textarea rows={2} maxLength={2000} value={texto} onChange={(e) => setTexto(e.target.value)} />
      </Campo>
      <div className="acciones">
        <button type="button" disabled={accion.pendiente || texto === (postor.notas ?? "")}
          onClick={() => accion.ejecutar(async () => {
            await api(`/expedientes/${expedienteId}/postores/${postor.id}/notas`, { method: "PUT", data: { notas: texto } });
            return "Nota guardada.";
          })}>Guardar nota</button>
        <EstadoAccion accion={accion} />
      </div>
    </details>
  );
}

function TarjetaPostor({ datos, postor, editable, accion, recargar }) {
  const id = datos.expediente.id;
  const dims = Object.entries(datos.dimensiones);
  const conteo = dims.reduce((acc, [clave]) => {
    const estado = postor.dimensiones[clave]?.estado;
    if (estado) acc[estado] += 1;
    return acc;
  }, { alerta: 0, revisar: 0, limpio: 0 });
  const estadoPostor = ESTADO_POSTOR[postor.estado];
  function analizar(dimension) {
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/evaluacion/analisis`, { method: "POST", data: { postor_id: postor.id, dimension } });
      recargar();
      return dimension ? `${datos.dimensiones[dimension]} actualizada para ${postor.razon_social}.`
        : `${postor.razon_social} analizado en las 6 dimensiones.`;
    });
  }
  function quitar() {
    if (!window.confirm(`¿Quitar a ${postor.razon_social} de los posibles proveedores?`)) return;
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/postores/${postor.id}`, { method: "DELETE" });
      recargar();
      return `${postor.razon_social} ya no figura entre los posibles proveedores.`;
    });
  }
  return (
    <article className={`panel postor postor-${postor.consolidado?.veredicto ?? "sin"}`} aria-labelledby={`postor-${postor.id}`}>
      <header className="postor-cabecera">
        <div>
          <h3 id={`postor-${postor.id}`}>{postor.razon_social}</h3>
          <small>RUC {postor.ruc}{postor.proforma_ref ? ` · Cotización ${postor.proforma_ref}` : ""}</small>
        </div>
        <div className="postor-cifras">
          <strong>{soles(postor.monto_cotizado)}</strong>
          <small>{porcentaje(postor.variacion)} · {postor.plazo_dias} días</small>
        </div>
      </header>
      <div className="postor-estado">
        {postor.consolidado
          ? <Indicador tono={VEREDICTO_TONO[postor.consolidado.veredicto]}>{postor.consolidado.titulo}</Indicador>
          : postor.analisis_completo ? <Indicador>Analizado · falta consolidar</Indicador>
            : postor.analizado_en ? <Indicador>Análisis incompleto</Indicador> : <Indicador>Sin analizar</Indicador>}
        {postor.analizado_en && <small>{conteo.alerta} en alerta · {conteo.revisar} por revisar · {conteo.limpio} limpias</small>}
        {estadoPostor && <Indicador tono={estadoPostor[1]}>{estadoPostor[0]}</Indicador>}
      </div>
      {postor.consolidado && <p className="postor-motivo">{postor.consolidado.motivo}</p>}
      {postor.motivo_descarte && <p className="secundario">Motivo de descarte: {postor.motivo_descarte}</p>}
      {postor.analizado_en ? <>
        <div className="dimensiones" role="list" aria-label={`Dimensiones de ${postor.razon_social}`}>
          {dims.map(([clave, titulo]) => (
            <div role="listitem" key={clave}>
              <Dimension clave={clave} titulo={titulo} resultado={postor.dimensiones[clave]} editable={editable}
                reanalizar={analizar} pendiente={accion.pendiente} />
            </div>
          ))}
        </div>
        <Notas expedienteId={id} postor={postor} editable={editable} />
      </> : <p className="secundario">Aún no se analiza. El análisis revisa sus 6 dimensiones en segundos.</p>}
      {editable && <div className="acciones postor-acciones">
        <button type="button" disabled={accion.pendiente} onClick={() => analizar(null)}>
          <FileSearch size={16} /> {postor.analizado_en ? "Volver a analizar" : "Analizar este proveedor"}</button>
        <button type="button" className="boton-sutil" disabled={accion.pendiente} onClick={quitar}>
          <Trash2 size={15} /> Quitar</button>
      </div>}
    </article>
  );
}

function AgregarPostor({ expedienteId, recargar }) {
  const accion = useAccion();
  function enviar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = Object.fromEntries(new FormData(form));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expedienteId}/postores`, { method: "POST", data: { ...datos, plazo_dias: Number(datos.plazo_dias) } });
      form.reset();
      recargar();
      return `${datos.razon_social} agregado. Analízalo para incluirlo en la comparación.`;
    });
  }
  return (
    <details className="panel desplegable">
      <summary><Plus size={17} /> Agregar posible proveedor</summary>
      <form className="formulario" onSubmit={enviar}>
        <div className="rejilla dos">
          <Campo titulo="RUC" ayuda="11 dígitos; se valida el dígito verificador.">
            <input name="ruc" inputMode="numeric" pattern="\d{11}" maxLength={11} required /></Campo>
          <Campo titulo="Razón social"><input name="razon_social" maxLength={200} required /></Campo>
          <Campo titulo="Monto cotizado (S/)"><input name="monto_cotizado" type="number" min="0.01" step="0.01" required /></Campo>
          <Campo titulo="Plazo ofrecido (días)"><input name="plazo_dias" type="number" min="1" required /></Campo>
          <Campo titulo="Teléfono de contacto (opcional)"><input name="contacto_telefono" maxLength={40} /></Campo>
          <Campo titulo="Correo de contacto (opcional)"><input name="contacto_correo" type="email" maxLength={120} /></Campo>
          <Campo titulo="Dirección (opcional)"><input name="direccion" maxLength={200} /></Campo>
          <Campo titulo="Referencia de la cotización (opcional)"><input name="proforma_ref" maxLength={120} /></Campo>
        </div>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>Agregar</button></div>
      </form>
    </details>
  );
}

/* --- Consolidado: comparación entre postores -------------------------------------------- */

function Comparativo({ datos }) {
  const consolidados = datos.postores.filter((p) => p.consolidado);
  if (!consolidados.length) return null;
  const seleccionado = datos.evaluacion?.seleccionado_ruc;
  return (
    <section className="seccion" id="consolidado" aria-labelledby="titulo-consolidado">
      <h2 id="titulo-consolidado"><Layers size={19} /> Informe consolidado</h2>
      <p className="secundario">Cruza las seis dimensiones de cada postor y detecta riesgos que solo aparecen al combinarlas.</p>
      <div className="tabla-scroll tabla-comparativo" tabIndex={0} role="region" aria-label="Comparación de postores">
        <table className="comparativo">
          <thead><tr><th scope="col">Postor</th><th scope="col" className="numero">Cotización</th>
            <th scope="col">Plazo</th><th scope="col">Veredicto</th><th scope="col">Riesgos combinados</th></tr></thead>
          <tbody>{consolidados.map((p) => (
            <tr key={p.id} className={p.ruc === seleccionado ? "elegida" : undefined}>
              <th scope="row">{p.razon_social}{p.ruc === seleccionado && <small className="dato-tabla">Seleccionado</small>}</th>
              <td className="numero">{soles(p.monto_cotizado)}<small className="dato-tabla">{porcentaje(p.variacion)}</small></td>
              <td>{p.plazo_dias} días</td>
              <td><Indicador tono={VEREDICTO_TONO[p.consolidado.veredicto]}>{p.consolidado.titulo}</Indicador>
                <small className="dato-tabla">{p.consolidado.motivo}</small></td>
              <td>{p.consolidado.riesgos_combinados.length
                ? <ul className="lista-simple">{p.consolidado.riesgos_combinados.map((r) => (
                  <li key={r.titulo} title={r.detalle}><strong>{r.titulo}.</strong> {r.detalle}</li>))}</ul>
                : <span className="secundario">Ninguno</span>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

/* --- Selección sustentada ----------------------------------------------------------------- */

function Seleccion({ datos, recargar, accion }) {
  const postores = datos.postores;
  const aptos = postores.filter((p) => p.consolidado?.veredicto !== "no_recomendado");
  const [elegido, setElegido] = useState(aptos.length === 1 ? aptos[0].id : null);
  const [descartes, setDescartes] = useState(() => Object.fromEntries(postores
    .filter((p) => p.consolidado?.veredicto === "no_recomendado")
    .map((p) => [p.id, `No recomendado: ${p.consolidado.motivo}`])));
  const [sustento, setSustento] = useState("");
  const [declaro, setDeclaro] = useState(false);
  const elegidoDatos = postores.find((p) => p.id === elegido);
  const otros = postores.filter((p) => p.id !== elegido);
  const masBaratos = elegidoDatos ? otros.filter((p) => Number(p.monto_cotizado) < Number(elegidoDatos.monto_cotizado)) : [];
  const faltan = [
    !elegido && "elige al proveedor",
    otros.some((p) => !(descartes[p.id] ?? "").trim()) && "explica cada descarte",
    sustento.trim().length < 20 && "escribe el sustento",
    !declaro && "marca la declaración",
  ].filter(Boolean);
  function enviar(evento) {
    evento.preventDefault();
    accion.ejecutar(async () => {
      await api(`/expedientes/${datos.expediente.id}/evaluacion/seleccion`, { method: "POST", data: {
        seleccionado_id: elegido, sustento, declaro_sin_conflicto: declaro,
        descartes: Object.fromEntries(otros.map((p) => [p.id, descartes[p.id] ?? ""])),
      } });
      recargar();
      window.scrollTo({ top: 0, behavior: "smooth" });
      return "Selección enviada a revisión independiente. Otro especialista de Abastecimiento debe revisarla.";
    });
  }
  return (
    <section className="seccion" id="seleccion" aria-labelledby="titulo-seleccion">
      <h2 id="titulo-seleccion"><Scale size={19} /> Selección sustentada</h2>
      {datos.evaluacion?.estado_revision === "observada" && <Aviso tipo="advertencia">
        <strong>La revisión independiente observó la selección anterior:</strong> {datos.evaluacion.comentario_revision}
        {" "}({datos.evaluacion.revisor}).</Aviso>}
      <form className="formulario" onSubmit={enviar}>
        <fieldset className="opciones-postor">
          <legend>1. ¿A quién seleccionas?</legend>
          {postores.map((p) => {
            const bloqueado = p.consolidado?.veredicto === "no_recomendado";
            return <label key={p.id} className={`opcion-postor ${bloqueado ? "opcion-bloqueada" : ""}`}>
              <input type="radio" name="seleccionado" value={p.id} checked={elegido === p.id} disabled={bloqueado}
                onChange={() => setElegido(p.id)} />
              <span><strong>{p.razon_social}</strong> · {soles(p.monto_cotizado)} · {p.plazo_dias} días
                <small className="dato-tabla">{bloqueado ? `No seleccionable: ${p.consolidado.motivo}` : p.consolidado?.titulo}</small></span>
            </label>;
          })}
        </fieldset>
        {elegido && otros.length > 0 && <fieldset>
          <legend>2. ¿Por qué descartas a los demás?</legend>
          {masBaratos.length > 0 && <Aviso tipo="advertencia">
            {masBaratos.map((p) => p.razon_social).join(", ")} {masBaratos.length === 1 ? "cotiza" : "cotizan"} menos
            que tu elección: explica con claridad por qué no {masBaratos.length === 1 ? "conviene" : "convienen"}.</Aviso>}
          {otros.map((p) => (
            <Campo key={p.id} titulo={`${p.razon_social} (${soles(p.monto_cotizado)})`}>
              <textarea rows={2} maxLength={1000} value={descartes[p.id] ?? ""}
                onChange={(e) => setDescartes({ ...descartes, [p.id]: e.target.value })} />
            </Campo>
          ))}
        </fieldset>}
        <Campo titulo={`${otros.length ? 3 : 2}. Sustento de la selección`}
          ayuda="Por qué esta es la mejor opción y cómo se atendieron sus observaciones (mínimo 20 caracteres).">
          <textarea rows={3} maxLength={3000} value={sustento} onChange={(e) => setSustento(e.target.value)} />
        </Campo>
        <label className="casilla declaracion">
          <input type="checkbox" checked={declaro} onChange={(e) => setDeclaro(e.target.checked)} />
          <span>Declaro que no tengo parentesco, relación comercial ni interés personal con ninguno de los postores
            de este expediente. Si lo tuviera, me abstengo y otro especialista asume la evaluación.</span>
        </label>
        {accion.error && <Aviso tipo="error">{accion.error}</Aviso>}
        <div className="acciones">
          <button className="primario" disabled={accion.pendiente || faltan.length > 0}>
            <Send size={16} /> Enviar a revisión independiente</button>
          {faltan.length > 0 && <small>Para enviar: {faltan.join(", ")}.</small>}
        </div>
      </form>
    </section>
  );
}

function SeleccionPropuesta({ datos }) {
  const ev = datos.evaluacion;
  const elegido = datos.postores.find((p) => p.ruc === ev?.seleccionado_ruc);
  if (!ev?.enviado_en || !elegido || datos.puede_editar) return null;
  const descartados = datos.postores.filter((p) => p.estado === "descartado");
  const declaracion = datos.declaraciones.filter((d) => d.tipo === "declaracion_negativa").at(-1);
  const vinculos = datos.declaraciones.filter((d) => d.tipo === "vinculo_detectado");
  return (
    <section className="seccion" id="seleccion" aria-labelledby="titulo-propuesta">
      <h2 id="titulo-propuesta"><Scale size={19} /> Selección propuesta</h2>
      <DatosClave valores={[
        ["Proveedor seleccionado", `${elegido.razon_social} (RUC ${elegido.ruc})`],
        ["Cotización", `${soles(elegido.monto_cotizado)} · ${elegido.plazo_dias} días`],
        ["Evaluó", `${ev.evaluador} · enviada el ${fechaHora(ev.enviado_en)}`],
      ]} />
      <p><strong>Sustento:</strong> {ev.sustento}</p>
      {descartados.length > 0 && <div><strong>Descartes</strong>
        <ul className="lista-simple">{descartados.map((p) => <li key={p.id}>{p.razon_social}: {p.motivo_descarte}</li>)}</ul></div>}
      {declaracion && <p className="secundario"><ShieldCheck size={15} /> {declaracion.descripcion}</p>}
      {vinculos.length > 0 && <Aviso tipo="advertencia">
        <strong>Vínculos detectados y registrados para el OCI:</strong>
        <ul>{vinculos.map((v) => <li key={v.id}>{v.descripcion}</li>)}</ul></Aviso>}
    </section>
  );
}

function RevisionIndependiente({ datos, recargar, accion }) {
  const [comentario, setComentario] = useState("");
  const ev = datos.evaluacion;
  if (ev?.estado_revision === "aprobada") {
    return <Aviso tipo="exito"><strong>Revisión independiente aprobada</strong> por {ev.revisor} el {fechaHora(ev.revisado_en)}.
      {ev.comentario_revision && ` «${ev.comentario_revision}».`} El área usuaria ya puede confirmar la orden.</Aviso>;
  }
  if (!datos.puede_revisar) return null;
  function decidir(aprobar) {
    accion.ejecutar(async () => {
      await api(`/expedientes/${datos.expediente.id}/evaluacion/revision-independiente`, {
        method: "POST", data: { aprobar, comentario } });
      recargar();
      return aprobar ? "Revisión aprobada: el área usuaria ya puede confirmar la orden."
        : "Evaluación observada: vuelve al especialista que la hizo.";
    }).then(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  }
  return (
    <section className="panel-revision" id="revision" aria-labelledby="titulo-revision">
      <h2 id="titulo-revision"><ClipboardList size={19} /> Tu revisión independiente</h2>
      <p>Revisa el análisis, el consolidado y el sustento de {ev.evaluador}. Si todo es coherente, apruébala;
        si algo no cuadra, obsérvala explicando qué debe corregirse.</p>
      <Campo titulo="Comentario" ayuda="Obligatorio si observas la evaluación.">
        <textarea rows={3} maxLength={2000} value={comentario} onChange={(e) => setComentario(e.target.value)} />
      </Campo>
      {accion.error && <Aviso tipo="error">{accion.error}</Aviso>}
      <div className="acciones">
        <button className="primario" disabled={accion.pendiente} onClick={() => decidir(true)}>
          <CircleCheck size={16} /> Aprobar selección</button>
        <button disabled={accion.pendiente || !comentario.trim()} onClick={() => decidir(false)}>
          <CircleX size={16} /> Observar y devolver</button>
      </div>
    </section>
  );
}

/* --- Qué toca ahora ---------------------------------------------------------------------- */

function Siguiente({ datos, accion, recargar }) {
  const { postores, expediente, evaluacion, puede_editar: editable } = datos;
  const id = expediente.id;
  const analizarTodas = () => accion.ejecutar(async () => {
    const conteo = await api(`/expedientes/${id}/evaluacion/analisis`, { method: "POST", data: {} });
    recargar();
    return `Análisis listo: ${conteo.alerta} dimensiones en alerta, ${conteo.revisar} por revisar y ${conteo.limpio} limpias.`;
  });
  const consolidar = () => accion.ejecutar(async () => {
    await api(`/expedientes/${id}/evaluacion/consolidado`, { method: "POST" });
    recargar();
    return "Evaluación consolidada. Revisa la comparación y elige al proveedor.";
  });
  if (expediente.estado_flujo === "seleccion_aprobada") {
    return <ProximoPaso tono="info" titulo="Selección aprobada"
      acciones={<Link className="boton" href={rutaExpediente(id)}>Ver expediente</Link>}>
      Falta que el área usuaria confirme la orden a favor del proveedor aprobado.</ProximoPaso>;
  }
  if (expediente.estado_flujo === "pendiente_revision_independiente") {
    return datos.puede_revisar
      ? <ProximoPaso tono="advertencia" titulo="Te toca la revisión independiente"
        acciones={<a className="boton primario" href="#revision">Ir a la revisión</a>}>
        {evaluacion.evaluador} evaluó y propone una selección. Tú no participaste: revísala con ojos frescos.</ProximoPaso>
      : <ProximoPaso titulo="Esperando la revisión independiente">
        Otro especialista de Abastecimiento debe aprobar u observar la selección.</ProximoPaso>;
  }
  if (!editable) return null;
  if (!postores.length) {
    return <ProximoPaso titulo="Agrega a los posibles proveedores">
      Registra las cotizaciones recibidas para poder analizarlas.</ProximoPaso>;
  }
  if (!postores.every((p) => p.analisis_completo)) {
    return <ProximoPaso titulo={`Analiza a ${postores.length === 1 ? "el posible proveedor" : `los ${postores.length} posibles proveedores`}`}
      acciones={<button className="primario" disabled={accion.pendiente} onClick={analizarTodas}>
        <FileSearch size={16} /> {accion.pendiente ? "Analizando…" : "Analizar todas"}</button>}>
      Se revisan 6 dimensiones por cada uno: antecedentes, empresa, personas, colusión, precio y desempeño.</ProximoPaso>;
  }
  if (!postores.every((p) => p.consolidado)) {
    return <ProximoPaso titulo="Consolida la evaluación"
      acciones={<button className="primario" disabled={accion.pendiente} onClick={consolidar}>
        <Layers size={16} /> Consolidar evaluación</button>}>
      Cruza las 6 dimensiones, detecta riesgos combinados y da un veredicto por postor.</ProximoPaso>;
  }
  return <ProximoPaso titulo="Elige al proveedor y sustenta la decisión"
    acciones={<a className="boton primario" href="#seleccion"><Scale size={16} /> Ir a la selección</a>}>
    Explica por qué descartas a los demás y envía la evaluación a revisión independiente.</ProximoPaso>;
}

export function FichaEvaluacion({ id }) {
  const recurso = useDatos(`/expedientes/${id}/evaluacion`);
  const accion = useAccion();
  if (!recurso.datos) return <><Volver to="/prevencion">Análisis de proveedores</Volver><Carga recurso={recurso} /></>;
  const datos = recurso.datos;
  const { expediente, postores, puede_editar: editable } = datos;
  const [estado] = ESTADOS_FLUJO[expediente.estado_flujo] ?? [expediente.estado_flujo];
  const consolidadoListo = postores.length > 0 && postores.every((p) => p.consolidado);
  return (
    <>
      <Volver to="/prevencion">Análisis de proveedores</Volver>
      <div className="caratula">
        <Encabezado titulo={expediente.descripcion} descripcion={expediente.area}
          acciones={<Indicador>{estado}</Indicador>}>
          <div className="caratula-codigo">{expediente.codigo} <span>Valor estimado {soles(expediente.monto)} · {expediente.plazo_dias} días</span></div>
        </Encabezado>
        <Pasos pasos={pasosDe(datos)} />
      </div>
      {datos.bloqueo && <Aviso>{datos.bloqueo}</Aviso>}
      <Siguiente datos={datos} accion={accion} recargar={recurso.recargar} />
      <EstadoAccion accion={accion} />
      <section className="seccion" aria-labelledby="titulo-postores">
        <div className="fila-titulo">
          <h2 id="titulo-postores">Posibles proveedores ({postores.length})</h2>
          <span className="acciones">
            <Link className="volver" href={`/documentos/${expediente.id}`}>Revisión documental</Link>
            <Link className="volver" href={rutaExpediente(expediente.id)}>Ver expediente completo</Link>
          </span>
        </div>
        <p className="secundario">Cada fila es una dimensión: <Punto estado="limpio" /> limpio, <Punto estado="revisar" /> revisar,{" "}
          <Punto estado="alerta" /> alerta. Ábrela para ver qué se encontró, por qué importa y qué hacer.
          Las fuentes externas están simuladas.</p>
        {postores.length === 0 && <p className="vacio">Todavía no hay posibles proveedores registrados.</p>}
        <div className="postores">
          {postores.map((p) => <TarjetaPostor key={p.id} datos={datos} postor={p} editable={editable}
            accion={accion} recargar={recurso.recargar} />)}
        </div>
        {editable && <AgregarPostor expedienteId={expediente.id} recargar={recurso.recargar} />}
      </section>
      <Comparativo datos={datos} />
      {editable && consolidadoListo && <Seleccion key={postores.map((p) => p.consolidado_en).join()} datos={datos}
        recargar={recurso.recargar} accion={accion} />}
      {editable && !consolidadoListo && datos.evaluacion?.estado_revision === "observada" && <Aviso tipo="advertencia">
        <strong>Observación de la revisión independiente:</strong> {datos.evaluacion.comentario_revision}</Aviso>}
      <SeleccionPropuesta datos={datos} />
      <RevisionIndependiente datos={datos} recargar={recurso.recargar} accion={accion} />
      {datos.evaluacion && <p className="registro-pie">Evaluación iniciada por {datos.evaluacion.evaluador} el {fecha(datos.evaluacion.iniciada_en?.slice(0, 10))}.</p>}
    </>
  );
}
