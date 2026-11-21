import { useState } from "react";
import {
  Bell, ClipboardCheck, Download, Image, QrCode, RefreshCw, Sparkles,
} from "lucide-react";
import { Link, useParams } from "react-router";
import { api, useAccion, useDatos } from "./api";
import {
  ACCIONES, AVISO_ALERTAS, ESTADOS, SEVERIDADES, capitalizar, fecha, fechaHora, hoy, rutaAlerta, rutaExpediente, soles,
} from "./dominio";
import {
  Aviso, AvisoNavegacion, Campo, Carga, DatosClave, Encabezado, EstadoAccion,
  EstadoEntregable, Indicador, Metricas, Semaforo, Volver,
} from "./ui";

function Sello({ conformidad, id }) {
  return (
    <details className="panel desplegable">
      <summary><QrCode size={19} /> Sello de conformidad (QR)</summary>
      <div className="sello">
        <img src={`/api/expedientes/${id}/sello`} alt="QR para verificar el sello" width="180" height="180" loading="lazy" />
        <div>
          <Aviso tipo="advertencia">{conformidad.aviso_url}</Aviso>
          <DatosClave valores={[
            ["Código", <code>{conformidad.codigo_sello}</code>],
            ["Registro sellado", `N.º ${conformidad.sello_bitacora_id}`],
            ["Hash", <code>{conformidad.sello_hash.slice(0, 24)}…</code>],
            ["Verificación pública", <a href={conformidad.url_sello}>{conformidad.url_sello}</a>],
          ]} />
          <a className="boton" href={`/api/expedientes/${id}/sello?descarga=true`}><Download size={16} />Descargar sello (PNG)</a>
        </div>
      </div>
    </details>
  );
}

function Entregables({ expediente, conformidad, entregables, actor }) {
  const [mostrar, setMostrar] = useState(false);
  const ruta = rutaExpediente(expediente.id);
  return (
    <section className="seccion">
      <h2>Entregables y conformidad</h2>
      {conformidad ? <>
        <p>Conformidad registrada por <strong>{conformidad.conformante}</strong> el {fecha(conformidad.fecha_conformidad)}
          {" · "}Penalidad aplicada de {soles(conformidad.penalidad_aplicada)}</p>
        {conformidad.observaciones && <p className="secundario">Observaciones: {conformidad.observaciones}</p>}
        {conformidad.codigo_sello && <Sello conformidad={conformidad} id={expediente.id} />}
      </> : <>
        <Aviso>{entregables.length ? "Conformidad pendiente." : "Este expediente no tiene entregables cargados."}</Aviso>
        {actor.rol === "area_usuaria" && <div className="acciones">
          {entregables.length > 0 && <Link className="boton primario" to={`${ruta}/conformidad`}><ClipboardCheck size={17} /> Registrar conformidad</Link>}
          <Link className="boton" to={`/lectura-ia?expediente=${expediente.id}`}><Sparkles size={16} /> Leer términos de referencia con IA</Link>
        </div>}
      </>}
      {entregables.some((item) => item.evidencias.length > 0) && (
        <label className="casilla"><input type="checkbox" checked={mostrar} onChange={(e) => setMostrar(e.target.checked)} /> Mostrar evidencias</label>
      )}
      <div className="tarjetas">
        {entregables.map((item) => (
          <article className="panel ficha" key={item.id}>
            <div className="fila-titulo"><h3>{item.numero}. {item.descripcion}</h3><EstadoEntregable item={item} /></div>
            {item.observacion && <p className="secundario">Observación: {item.observacion}</p>}
            {item.cumplido != null && !item.evidencias.length && <small>Sin archivos adjuntos.</small>}
            {item.evidencias.map((archivo) => (
              <div key={archivo.id} className="archivo">
                <small><Image size={15} /> {archivo.nombre_archivo} · {(archivo.tamano / 1024).toFixed(1)} KB · SHA-256 <code>{archivo.sha256.slice(0, 16)}…</code></small>
                {mostrar && <>
                  {archivo.mime.startsWith("image/") && <img loading="lazy" src={`/api/evidencias/${archivo.id}`}
                    alt={archivo.nombre_archivo} className="miniatura" />}
                  <a className="boton" href={`/api/evidencias/${archivo.id}?descarga=true`}><Download size={16} /> Descargar {archivo.nombre_archivo}</a>
                </>}
              </div>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}

function AlertasDelExpediente({ expediente, alertas, reglas, actor, recargar }) {
  const accion = useAccion();
  return (
    <section className="seccion">
      <div className="fila-titulo">
        <div><h2>Alertas</h2><p className="secundario">{AVISO_ALERTAS}</p></div>
        {actor.rol !== "auditor" && (
          <button disabled={accion.pendiente} onClick={() => accion.ejecutar(async () => {
            const { nuevas } = await api(`/expedientes/${expediente.id}/reevaluar`, { method: "POST" });
            recargar();
            return nuevas ? `Reglas reevaluadas. Alertas nuevas: ${nuevas}.` : "Reglas reevaluadas. No hay alertas nuevas.";
          })}><RefreshCw size={16} /> Reevaluar reglas</button>
        )}
      </div>
      <EstadoAccion accion={accion} />
      {!alertas.length && <p className="vacio">Este expediente no tiene alertas.</p>}
      <div className="tarjetas">
        {alertas.map((a) => (
          <article className="panel ficha" key={a.id}>
            <div className="fila-titulo"><h3>{a.regla} · {reglas[a.regla]}</h3>
              <div className="acciones"><Indicador tono={a.severidad === "alta" ? "rojo" : "ambar"}>{SEVERIDADES[a.severidad]}</Indicador>
                <Indicador>{ESTADOS[a.estado]}</Indicador></div>
            </div>
            <p>{a.explicacion}</p>
            {a.implicado && <small>Persona implicada: {a.implicado}</small>}
            <Link className="volver" to={rutaAlerta(a.id)}><Bell size={16} /> Revisar en la bandeja</Link>
          </article>
        ))}
      </div>
    </section>
  );
}

function Pagos({ expediente, conformidad, abiertas, pagos, actor, recargar }) {
  const accion = useAccion();
  function registrar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = Object.fromEntries(new FormData(form));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/pagos`, { method: "POST", data: datos });
      form.reset();
      recargar();
      return "Pago registrado. Se reevaluaron las reglas.";
    });
  }
  return (
    <section className="seccion">
      <h2>Pagos</h2>
      {pagos.length ? <>
        {abiertas > 0 && <Aviso tipo="advertencia">El expediente tiene {abiertas} alertas sin cerrar y ya registra pagos. Revisa las alertas.</Aviso>}
        <ul className="lista-simple">{pagos.map((p) => <li key={p.id}>
          <strong>{soles(p.monto)}</strong> · {fecha(p.fecha_pago)} · Penalidad descontada de {soles(p.penalidad_descontada)} · {p.registrado_por}
        </li>)}</ul>
      </> : <p className="vacio">Sin pagos registrados.</p>}
      {actor.rol === "tesoreria" && (
        <details className="panel desplegable">
          <summary>Registrar pago</summary>
          <form className="formulario" onSubmit={registrar}>
            {abiertas > 0 && <Aviso tipo="advertencia">Este expediente tiene {abiertas} alertas sin cerrar. El sistema no bloquea el pago.</Aviso>}
            {!conformidad && <Aviso tipo="advertencia">El expediente no tiene conformidad registrada.</Aviso>}
            <div className="rejilla tres">
              <Campo titulo="Fecha de pago"><input name="fecha_pago" type="date" defaultValue={hoy()} required /></Campo>
              <Campo titulo="Monto pagado (S/)"><input name="monto" type="number" min="0.01" step="0.01" defaultValue={expediente.monto} required /></Campo>
              <Campo titulo="Penalidad descontada (S/)"><input name="penalidad_descontada" type="number" min="0" step="0.01" defaultValue="0" required /></Campo>
            </div>
            <EstadoAccion accion={accion} />
            <div><button className="primario" disabled={accion.pendiente}>Registrar pago</button></div>
          </form>
        </details>
      )}
    </section>
  );
}

function LineaDeTiempo({ eventos }) {
  return (
    <section className="seccion">
      <h2>Línea de tiempo</h2>
      <p className="secundario">Actividad registrada en la bitácora encadenada.</p>
      {!eventos.length && <p className="vacio">Sin movimientos registrados.</p>}
      <ol className="linea-tiempo">
        {eventos.map((evento) => (
          <li key={evento.id} data-tipo={evento.accion.split(".")[0]}>
            <time dateTime={evento.ts}>{fechaHora(evento.ts)}</time>
            <div className="evento">
              <h3>{ACCIONES[evento.accion] ?? evento.accion}</h3>
              <small>{evento.actor ?? "Sistema"} · Registro n.º {evento.id}</small>
              {evento.detalle?.resumen && <p>{evento.detalle.resumen}</p>}
              {evento.documento_sha256 && <small>{evento.detalle?.documento ?? "Documento"} · SHA-256 <code>{evento.documento_sha256.slice(0, 16)}…</code></small>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Detalle({ actor }) {
  const { id } = useParams();
  const recurso = useDatos(`/expedientes/${id}`);
  if (!recurso.datos) return <><Volver to="/expedientes">Expedientes</Volver><Carga recurso={recurso} /></>;
  const { expediente, conformidad, fecha_limite, entregables, alertas, reglas, pagos, eventos } = recurso.datos;
  const cumplidos = entregables.filter((item) => item.cumplido);
  const sinEvidencia = cumplidos.filter((item) => !item.evidencias.length);
  const abiertas = alertas.filter((a) => a.estado !== "cerrada").length;
  return (
    <>
      <Encabezado titulo={expediente.codigo} descripcion={expediente.descripcion}
        acciones={<Semaforo color={expediente.semaforo} />}>
        <Volver to="/expedientes">Expedientes</Volver>
      </Encabezado>
      <AvisoNavegacion />
      <Metricas valores={[
        ["Conformidad", conformidad ? "Registrada" : "Pendiente"],
        ["Cumplidos con evidencia", conformidad ? `${cumplidos.length - sinEvidencia.length} de ${cumplidos.length}` : "—"],
        ["Alertas sin cerrar", abiertas], ["Pagos", pagos.length],
      ]} />
      {sinEvidencia.length > 0 && <Aviso tipo="advertencia">Entregables dados por cumplidos sin evidencia: {sinEvidencia.map((e) => e.numero).join(", ")}.</Aviso>}
      <section className="panel">
        <h2>Datos del expediente</h2>
        <div className="rejilla dos">
          <DatosClave valores={[
            ["Monto", soles(expediente.monto)], ["Tipo", capitalizar(expediente.tipo)],
            ["Área usuaria", expediente.area], ["Solicitante", expediente.solicitante],
            ["Proveedor", `${expediente.proveedor} (RUC ${expediente.proveedor_ruc})`], ["Orden", expediente.numero_orden],
          ]} />
          <DatosClave valores={[
            ["Requerimiento", fecha(expediente.fecha_requerimiento)], ["Orden emitida", fecha(expediente.fecha_orden)],
            ["Inicio de la prestación", fecha(expediente.fecha_inicio_prestacion)], ["Plazo", `${expediente.plazo_dias} días`],
            ["Fecha límite", fecha(fecha_limite)], ["Entrega real", fecha(expediente.fecha_entrega_real)],
          ]} />
        </div>
      </section>
      <AlertasDelExpediente expediente={expediente} alertas={alertas} reglas={reglas} actor={actor} recargar={recurso.recargar} />
      <Entregables expediente={expediente} conformidad={conformidad} entregables={entregables} actor={actor} />
      <Pagos expediente={expediente} conformidad={conformidad} abiertas={abiertas} pagos={pagos} actor={actor} recargar={recurso.recargar} />
      <LineaDeTiempo eventos={eventos} />
    </>
  );
}
