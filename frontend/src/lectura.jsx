import { useState } from "react";
import { Download, FileText, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useNavegar } from "./navegacion";
import { useParams } from "next/navigation";
import { useConsulta } from "./navegacion";
import { api, useAccion, useDatos } from "./api";
import { useSesion } from "./sesion";
import { capitalizar, fechaHora, rutaExpediente } from "./dominio";
import { Aviso, AvisoNavegacion, Campo, Carga, Encabezado, EstadoAccion, Indicador, Volver } from "./ui";

const ORIGENES = { modelo: "Extracción con IA", respaldo: "Ejemplo guardado" };
const ESTADOS_LECTURA = { propuesta: "Pendiente", aprobada: "Aprobada", rechazada: "Rechazada" };

function OrigenLectura({ origen }) {
  return <Indicador tono={origen === "respaldo" ? "ambar" : "neutro"}>{ORIGENES[origen] ?? origen}</Indicador>;
}

function Propuesta({ pendiente, expediente, recargar }) {
  const [filas, setFilas] = useState(() => pendiente.resultado.entregables.map((item, id) => ({ id, descripcion: item.descripcion })));
  const [confirmado, setConfirmado] = useState(false);
  const accion = useAccion();
  const navegar = useNavegar();
  const { resultado, avisos_coherencia: avisos } = pendiente;
  const discrepancia = avisos.some(([nivel]) => nivel === "error");

  function aprobar(evento) {
    evento.preventDefault();
    if (discrepancia && !confirmado) return;
    accion.ejecutar(async () => {
      const { agregados } = await api(`/lecturas/${pendiente.id}/aprobar`, {
        method: "POST", data: { descripciones: filas.map((fila) => fila.descripcion) },
      });
      navegar(rutaExpediente(expediente.id), { state: { aviso: `Propuesta aprobada. Entregables añadidos: ${agregados}.` } });
    });
  }

  function rechazar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    accion.ejecutar(async () => {
      await api(`/lecturas/${pendiente.id}/rechazar`, { method: "POST", data: datos });
      recargar();
    });
  }

  return (
    <section className="seccion">
      <div className="fila-titulo">
        <h2>Revisar propuesta</h2>
        <OrigenLectura origen={pendiente.origen} />
      </div>
      <p className="secundario">Documento «{pendiente.archivo_nombre}» · {fechaHora(pendiente.creado_en)}</p>
      {pendiente.origen === "respaldo"
        ? <Aviso tipo="advertencia">La extracción con IA no estuvo disponible. La propuesta corresponde al PDF de ejemplo.</Aviso>
        : <Aviso>Contrasta los entregables propuestos con el PDF antes de aprobarlos.</Aviso>}
      {resultado.objeto && <div className="panel ficha">
        <p><strong>Objeto del documento</strong> · {resultado.objeto}</p>
        <p><strong>Objeto del expediente</strong> · {expediente.descripcion}</p>
      </div>}
      {resultado.advertencias?.map((aviso, i) => <Aviso tipo="advertencia" key={i}>{aviso}</Aviso>)}
      {avisos.map(([nivel, aviso], i) => <Aviso tipo={nivel === "error" ? "error" : "advertencia"} key={i}>{aviso}</Aviso>)}
      <EstadoAccion accion={accion} />
      <form className="panel formulario" onSubmit={aprobar}>
        <h3>Entregables propuestos</h3>
        <small>Se añadirán a los entregables existentes con numeración correlativa. Si ya registraste todos,
          quita las filas y aprueba solo el análisis del TDR.</small>
        {filas.map((fila, i) => (
          <div className="fila-editor fila-editor-ia" key={fila.id}>
            <Campo titulo={`Entregable ${i + 1}`}>
              <input value={fila.descripcion} onChange={(e) => setFilas(filas.map((f) =>
                f.id === fila.id ? { ...f, descripcion: e.target.value } : f))} />
            </Campo>
            <button type="button" className="icono-boton" aria-label={`Quitar entregable ${i + 1}`}
              onClick={() => setFilas(filas.filter((f) => f.id !== fila.id))}><Trash2 size={17} /></button>
          </div>
        ))}
        <div><button type="button" onClick={() => setFilas([...filas, { id: Math.max(-1, ...filas.map((f) => f.id)) + 1, descripcion: "" }])}>
          <Plus size={16} /> Añadir fila</button></div>
        {(resultado.plazo_dias || resultado.penalidades?.length > 0) && <div className="ficha documento">
          <h3>Otros datos del documento (informativos)</h3>
          {resultado.plazo_dias && <p>Plazo según el documento: {resultado.plazo_dias} días calendario. El expediente tiene {expediente.plazo_dias}.</p>}
          {resultado.penalidades?.length > 0 && <ul>{resultado.penalidades.map((texto, i) => <li key={i}>{texto}</li>)}</ul>}
        </div>}
        {discrepancia && <label className="casilla"><input type="checkbox" checked={confirmado}
          onChange={(e) => setConfirmado(e.target.checked)} /> He revisado la discrepancia y quiero añadir estos entregables.</label>}
        <div><button className="primario" disabled={accion.pendiente || (discrepancia && !confirmado)}>Aprobar y añadir al expediente</button></div>
      </form>
      <form className="panel formulario" onSubmit={rechazar}>
        <Campo titulo="Motivo del rechazo (opcional)"><input name="motivo" /></Campo>
        <div><button disabled={accion.pendiente}>Rechazar propuesta</button></div>
      </form>
    </section>
  );
}

function LecturasDelExpediente({ id }) {
  const { actor } = useSesion();
  const recurso = useDatos(`/expedientes/${id}/lecturas`);
  const accion = useAccion();
  const [archivo, setArchivo] = useState(null);
  const [rechazada, setRechazada] = useState(false);
  if (!recurso.datos) return <Carga recurso={recurso} />;
  const { expediente, entregables, lecturas, observaciones, tdr, hay_ejemplo } = recurso.datos;
  const esArea = actor.rol === "area_usuaria";
  const esDec = actor.rol === "abastecimiento";
  const preOrden = ["requerimiento", "tdr_observado", "en_evaluacion_proveedores"].includes(expediente.estado_flujo);
  const pendiente = lecturas.find((lectura) => lectura.estado === "propuesta");
  const historial = lecturas.filter((lectura) => expediente.tiene_conformidad || lectura.estado !== "propuesta");

  function leer(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = new FormData(form);
    setRechazada(false);
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/lecturas`, { method: "POST", data: datos });
      form.reset();
      setArchivo(null);
      recurso.recargar();
    });
  }

  function observar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/tdr/observaciones`, {
        method: "POST", data: Object.fromEntries(new FormData(form)),
      });
      form.reset();
      recurso.recargar();
    });
  }

  function responder(evento, observacionId) {
    evento.preventDefault();
    const form = evento.currentTarget;
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/tdr/observaciones/${observacionId}/responder`, {
        method: "POST", data: Object.fromEntries(new FormData(form)),
      });
      recurso.recargar();
    });
  }

  function guardarCriterios(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    accion.ejecutar(async () => {
      await api(`/expedientes/${id}/criterios-evidencia`, { method: "POST",
        data: entregables.map((item) => ({ entregable_id: item.id,
          criterio_evidencia: new FormData(form).get(`criterio-${item.id}`) })) });
      recurso.recargar();
    });
  }

  return (
    <>
      <div className="panel ficha contexto-formulario">
        <Link href={rutaExpediente(id)}>{expediente.codigo} · {capitalizar(expediente.tipo)} · Plazo de {expediente.plazo_dias} días</Link>
        <p>{expediente.descripcion}</p>
        <small>Entregables existentes: {entregables.map((e) => `${e.numero}. ${e.descripcion}`).join("; ") || "ninguno"}.</small>
      </div>
      {preOrden && <div className="panel ficha">
        <h2>Estado del TDR</h2>
        <p>{tdr.analizado ? "Lectura con IA aprobada." : "Falta aprobar una lectura real del TDR con IA."}
          {tdr.pendientes ? ` ${tdr.pendientes} observación(es) pendiente(s).` : " Sin observaciones pendientes."}</p>
        {!tdr.analizado && lecturas.some((l) => l.origen === "respaldo") &&
          <Aviso tipo="advertencia">El ejemplo guardado sirve para probar la extracción, pero no acredita el análisis del TDR cargado.</Aviso>}
      </div>}
      {esArea && !expediente.fecha_orden && entregables.length > 0 && <form className="panel formulario" onSubmit={guardarCriterios}>
        <h2>Evidencia exigida por entregable</h2>
        <p className="secundario">Define el archivo o conjunto de archivos que permitirá comprobar cada entrega. Es obligatorio antes de registrar la orden.</p>
        {entregables.map((item) => <Campo key={item.id} titulo={`${item.numero}. ${item.descripcion}`}>
          <input name={`criterio-${item.id}`} defaultValue={item.criterio_evidencia ?? ""}
            placeholder="Ej. Informe técnico firmado y acta de recepción" minLength={15} maxLength={300} required />
        </Campo>)}
        <EstadoAccion accion={accion} />
        <div><button disabled={accion.pendiente}>Guardar evidencia exigida</button></div>
      </form>}
      {esDec && entregables.some((item) => item.criterio_evidencia) && <div className="panel ficha">
        <h2>Evidencia exigida</h2>
        <ul>{entregables.map((item) => <li key={item.id}>{item.numero}. {item.criterio_evidencia || "Sin definir"}</li>)}</ul>
      </div>}
      {observaciones.length > 0 && <section className="panel formulario">
        <h2>Observaciones técnicas ({observaciones.length})</h2>
        {observaciones.map((obs) => <div className="ficha" key={obs.id}>
          <p><Indicador tono={obs.estado === "pendiente" ? "ambar" : "verde"}>
            {obs.estado === "pendiente" ? "Pendiente" : obs.estado === "corregida" ? "Corregida" : "Justificada"}
          </Indicador> {obs.detalle}</p>
          <small>{obs.origen === "ia" ? "Hallazgo de IA" : "Observación de Abastecimiento"} · {fechaHora(obs.creado_en)}</small>
          {obs.respuesta_area && <p><strong>Respuesta del área:</strong> {obs.respuesta_area}</p>}
          {esArea && obs.estado === "pendiente" && <form className="formulario" onSubmit={(e) => responder(e, obs.id)}>
            <Campo titulo="Resultado"><select name="estado" defaultValue="corregida">
              <option value="corregida">Corregí el TDR</option><option value="justificada">Justifiqué el punto</option>
            </select></Campo>
            <Campo titulo="Explica la corrección o justificación"
              ayuda="Si corregiste el TDR, carga y aprueba primero la nueva versión con IA.">
              <textarea name="respuesta" maxLength={2000} required />
            </Campo>
            <div><button disabled={accion.pendiente}>Registrar respuesta</button></div>
          </form>}
        </div>)}
      </section>}
      {esDec && preOrden && <form className="panel formulario" onSubmit={observar}>
        <h2>Registrar observación técnica</h2>
        <Campo titulo="Observación"><textarea name="detalle" maxLength={2000} required /></Campo>
        <Campo titulo="Severidad"><select name="severidad" defaultValue="bloqueante">
          <option value="bloqueante">Bloqueante</option><option value="advertencia">Advertencia</option>
        </select></Campo>
        <EstadoAccion accion={accion} />
        <div><button disabled={accion.pendiente}>Registrar observación</button></div>
      </form>}
      {expediente.tiene_conformidad && !historial.length && <Aviso>Este expediente no tiene lecturas de TDR registradas.</Aviso>}
      {esArea && !expediente.fecha_orden && !expediente.tiene_conformidad && <form className="panel formulario" onSubmit={leer}>
        <div className="fila-titulo">
          <h2>Cargar TDR</h2>
          {hay_ejemplo && <a className="boton" href="/api/ia/ejemplo"><Download size={16} /> Descargar PDF de ejemplo</a>}
        </div>
        {pendiente && <Aviso>Hay una propuesta pendiente. Revísala antes de leer otro documento.</Aviso>}
        <Campo titulo="Términos de referencia" ayuda="Archivo PDF con texto seleccionable.">
          <input type="file" name="archivo" accept=".pdf,application/pdf" required disabled={accion.pendiente || Boolean(pendiente)}
            onChange={(e) => setArchivo(e.target.files[0] ?? null)} />
        </Campo>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={!archivo || Boolean(pendiente) || accion.pendiente}>
          <FileText size={17} />{accion.pendiente ? "Procesando los TDR…" : "Extraer entregables con IA"}</button></div>
      </form>}
      {rechazada && <Aviso tipo="exito">Propuesta rechazada. No se añadió ningún entregable.</Aviso>}
      {esArea && pendiente && !expediente.fecha_orden && !expediente.tiene_conformidad && <Propuesta key={pendiente.id} pendiente={pendiente} expediente={expediente} recargar={() => {
        setRechazada(true);
        recurso.recargar();
      }} />}
      {historial.length > 0 && <details className="panel desplegable" open={expediente.tiene_conformidad || undefined}>
        <summary>Historial de lecturas ({historial.length})</summary>
        <ul className="lista-simple">{historial.map((lectura) =>
          <li key={lectura.id}>{fechaHora(lectura.creado_en)} · «{lectura.archivo_nombre}» · <OrigenLectura origen={lectura.origen} />
            {" · "}<Indicador tono={lectura.estado === "aprobada" ? "verde" : "neutro"}>{ESTADOS_LECTURA[lectura.estado] ?? lectura.estado}</Indicador></li>)}</ul>
      </details>}
    </>
  );
}

export function RevisarTdr() {
  const { id } = useParams();
  return <>
    <Encabezado titulo="Términos de referencia" descripcion="El área usuaria analiza el TDR con IA y responde observaciones; Abastecimiento revisa el documento antes de evaluar proveedores.">
      <Volver to={rutaExpediente(id)}>Expediente</Volver>
    </Encabezado>
    <AvisoNavegacion />
    <LecturasDelExpediente key={id} id={id} />
  </>;
}

export function LecturaIA() {
  const recurso = useDatos("/expedientes");
  const [params, setParams] = useConsulta();
  const elegibles = recurso.datos?.filter((e) => !e.fecha_orden && !e.tiene_conformidad &&
    (e.tipo === "servicio" || String(e.id) === params.get("expediente")));
  const elegido = elegibles?.find((e) => String(e.id) === params.get("expediente")) ?? elegibles?.[0];
  return (
    <>
      <Encabezado titulo="Términos de referencia" descripcion="Selecciona un expediente para extraer entregables con IA o revisar una propuesta.">
        <Volver to={elegido ? rutaExpediente(elegido.id) : "/expedientes"}>{elegido ? "Volver al expediente" : "Expedientes"}</Volver>
      </Encabezado>
      <AvisoNavegacion />
      {elegibles ? elegido ? <>
        <div className="panel">
          <Campo titulo="Expediente">
            <select value={elegido.id} onChange={(e) => setParams({ expediente: e.target.value })}>
              {elegibles.map((e) => <option key={e.id} value={e.id}>{e.codigo} · {e.descripcion.slice(0, 85)}</option>)}
            </select>
          </Campo>
        </div>
        <LecturasDelExpediente key={elegido.id} id={elegido.id} />
      </> : <Aviso>No hay expedientes de tu área sin conformidad.</Aviso> : <Carga recurso={recurso} />}
    </>
  );
}
