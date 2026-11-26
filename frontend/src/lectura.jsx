import { useState } from "react";
import { Download, FileText, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useNavegar } from "./navegacion";
import { useParams } from "next/navigation";
import { useConsulta } from "./navegacion";
import { api, useAccion, useDatos } from "./api";
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
        <small>Se añadirán a los entregables existentes con numeración correlativa.</small>
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
  const recurso = useDatos(`/expedientes/${id}/lecturas`);
  const accion = useAccion();
  const [archivo, setArchivo] = useState(null);
  const [rechazada, setRechazada] = useState(false);
  if (!recurso.datos) return <Carga recurso={recurso} />;
  const { expediente, entregables, lecturas, hay_ejemplo } = recurso.datos;
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

  return (
    <>
      <div className="panel ficha contexto-formulario">
        <Link href={rutaExpediente(id)}>{expediente.codigo} · {capitalizar(expediente.tipo)} · Plazo de {expediente.plazo_dias} días</Link>
        <p>{expediente.descripcion}</p>
        <small>Entregables existentes: {entregables.map((e) => `${e.numero}. ${e.descripcion}`).join("; ") || "ninguno"}.</small>
      </div>
      {expediente.tiene_conformidad && !historial.length && <Aviso>Este expediente no tiene lecturas de TDR registradas.</Aviso>}
      {!expediente.tiene_conformidad && <form className="panel formulario" onSubmit={leer}>
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
      {pendiente && !expediente.tiene_conformidad && <Propuesta key={pendiente.id} pendiente={pendiente} expediente={expediente} recargar={() => {
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
    <Encabezado titulo="Términos de referencia" descripcion="La IA propone entregables del PDF. El área usuaria revisa y aprueba cuáles se incorporan al expediente.">
      <Volver to={rutaExpediente(id)}>Expediente</Volver>
    </Encabezado>
    <AvisoNavegacion />
    <LecturasDelExpediente key={id} id={id} />
  </>;
}

export function LecturaIA() {
  const recurso = useDatos("/expedientes");
  const [params, setParams] = useConsulta();
  const elegibles = recurso.datos?.filter((e) => !e.tiene_conformidad && (e.tipo === "servicio" || String(e.id) === params.get("expediente")));
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
