import { useState } from "react";
import {
  Bell, ClipboardCheck, Download, FileText, Image, QrCode, RefreshCw, ScanSearch, Stamp, Wallet,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, useAccion, useDatos } from "./api";
import {
  ACCIONES, ESTADOS, ESTADOS_FLUJO, SEVERIDADES, alertaPendiente, capitalizar, fecha, fechaHora, hoy, nombreAlerta,
  observacionesDeEntrega, rutaAlerta, rutaExpediente, soles, tieneOrden,
} from "./dominio";
import {
  Aviso, AvisoNavegacion, Campo, Carga, DatosClave, Encabezado, EstadoAccion,
  EstadoEntregable, Indicador, InsigniaIA, ProximoPaso, ReferenciaRegla, Semaforo, Volver,
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

function RegistrarObservacion({ expediente, entregables, recargar }) {
  const accion = useAccion();
  function registrar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = Object.fromEntries(new FormData(form));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/observaciones-entrega`, { method: "POST", data: datos });
      form.reset();
      recargar();
      return "Observación registrada.";
    });
  }
  return (
    <details className="panel desplegable">
      <summary>Registrar observación</summary>
      <form className="formulario" onSubmit={registrar}>
        <Campo titulo="Entregable"><select name="entregable_id" defaultValue="" required>
          <option value="" disabled>Selecciona el entregable</option>
          {entregables.map((item) => <option key={item.id} value={item.id}>{item.numero}. {item.descripcion}</option>)}
        </select></Campo>
        <Campo titulo="Observación" ayuda="Indica qué falta o qué debe corregirse.">
          <textarea name="texto" maxLength={1000} required />
        </Campo>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>Guardar observación</button></div>
      </form>
    </details>
  );
}

function ComunicarObservacion({ expediente, observaciones, recargar }) {
  const accion = useAccion();
  const porComunicar = [...observaciones.values()].filter((registro) => !registro.comunicacion);
  if (!porComunicar.length) return null;
  function enviar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = Object.fromEntries(new FormData(form));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/comunicaciones`, {
        method: "POST", data: { ...datos, entregable_id: Number(datos.entregable_id), plazo_dias: Number(datos.plazo_dias) },
      });
      form.reset();
      recargar();
      return "Comunicación registrada.";
    });
  }
  return (
    <details className="panel desplegable" open>
      <summary>Comunicar observación al proveedor ({porComunicar.length})</summary>
      <form className="formulario" onSubmit={enviar}>
        <Aviso>La comunicación es simulada: el sistema registra el canal y el plazo, no envía nada.</Aviso>
        <Campo titulo="Observación"><select name="entregable_id" required defaultValue="">
          <option value="" disabled>Selecciona la observación</option>
          {porComunicar.map((r) => <option key={r.id} value={r.detalle.entregable_id}>Entregable {r.detalle.numero}: {r.detalle.resumen.slice(0, 70)}</option>)}
        </select></Campo>
        <Campo titulo="Canal"><input name="canal" defaultValue="Correo institucional (simulado)" maxLength={120} required /></Campo>
        <Campo titulo="Referencia (opcional)"><input name="referencia" maxLength={120} placeholder="SIM-COM-001" /></Campo>
        <Campo titulo="Plazo para subsanar (días calendario)"><input name="plazo_dias" type="number" min="1" max="30" defaultValue="3" required /></Campo>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>Registrar comunicación</button></div>
      </form>
    </details>
  );
}

function RevisionDec({ expediente, recargar }) {
  const accion = useAccion();
  const [favorable, setFavorable] = useState(true);
  if (expediente.revision_dec) {
    return <Aviso tipo={expediente.revision_dec === "conformidad.revisada" ? "info" : "advertencia"}>
      {expediente.revision_dec === "conformidad.revisada"
        ? "La conformidad fue revisada y quedó lista para derivar." : "La conformidad fue devuelta al área usuaria."}</Aviso>;
  }
  function enviar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/revision`, { method: "POST", data: { ...datos, favorable } });
      recargar();
      return favorable ? "Revisión registrada: lista para derivar." : "Conformidad devuelta.";
    });
  }
  return (
    <details className="panel desplegable" open>
      <summary>Revisar la conformidad emitida</summary>
      <form className="formulario" onSubmit={enviar}>
        <Aviso>La derivación es una referencia simulada. El devengado y el pago siguen fuera de Conforme.</Aviso>
        <Campo titulo="Resultado"><select value={favorable ? "si" : "no"} onChange={(e) => setFavorable(e.target.value === "si")}>
          <option value="si">Favorable: lista para derivar</option>
          <option value="no">Con discrepancia: devolver al área usuaria</option>
        </select></Campo>
        {favorable && <Campo titulo="Referencia de derivación (simulada)"><input name="referencia_derivacion" maxLength={120} placeholder="SIM-DER-001" required /></Campo>}
        <Campo titulo="Motivo"><textarea name="motivo" maxLength={1000} required /></Campo>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>{favorable ? "Registrar revisión" : "Devolver conformidad"}</button></div>
      </form>
    </details>
  );
}

function ConfirmarOrden({ expediente, seleccionado, recargar }) {
  const accion = useAccion();
  function enviar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/orden`, { method: "POST", data: {
        ...datos, fecha_inicio_prestacion: datos.fecha_inicio_prestacion || null } });
      recargar();
      return "Orden registrada. Ya puedes hacer seguimiento a los entregables.";
    });
  }
  return (
    <form className="formulario orden-confirmar panel" onSubmit={enviar}>
      <h3>Registrar la orden de servicio</h3>
      <p className="secundario">La orden se emite a favor de <strong>{seleccionado.razon_social}</strong> por{" "}
        {soles(seleccionado.monto_cotizado)} y {seleccionado.plazo_dias} días, como se aprobó. No puedes cambiar el proveedor.</p>
      <div className="rejilla tres">
        <Campo titulo="N.º de orden de servicio"><input name="numero_orden" placeholder="OS-2026-00301" maxLength={60} required /></Campo>
        <Campo titulo="Fecha de la orden"><input name="fecha_orden" type="date" defaultValue={hoy()} max={hoy()}
          min={expediente.fecha_requerimiento} required /></Campo>
        <Campo titulo="Inicio pactado (opcional)"><input name="fecha_inicio_prestacion" type="date" min={expediente.fecha_requerimiento} /></Campo>
      </div>
      <EstadoAccion accion={accion} />
      <div><button className="primario" disabled={accion.pendiente}><Stamp size={16} /> Registrar orden</button></div>
    </form>
  );
}

function SeleccionProveedor({ expediente, seleccion, actor, recargar }) {
  if (!seleccion) return null;
  const { seleccionado } = seleccion;
  const puedeVerEvaluacion = ["abastecimiento", "tesoreria", "auditor"].includes(actor.rol);
  const estado = expediente.estado_flujo;
  let resumen;
  if (estado === "en_evaluacion_proveedores") {
    resumen = seleccion.estado_revision === "observada"
      ? `La revisión independiente observó la selección: ${seleccion.comentario_revision}`
      : `Abastecimiento evalúa a ${seleccion.postores} posible(s) proveedor(es).`;
  } else if (estado === "pendiente_revision_independiente") {
    resumen = `${seleccion.evaluador} propone a ${seleccionado?.razon_social}. Espera la revisión independiente de otro especialista.`;
  } else if (seleccionado) {
    resumen = `${seleccionado.razon_social} (RUC ${seleccionado.ruc}) · ${soles(seleccionado.monto_cotizado)} · `
      + `${seleccionado.plazo_dias} días. Evaluó ${seleccion.evaluador}; revisión independiente de ${seleccion.revisor}.`;
  }
  return (
    <section className="seccion" id="seleccion">
      <div className="fila-titulo">
        <h2>Selección del proveedor</h2>
        {puedeVerEvaluacion && <Link className="volver" href={`/prevencion/${expediente.id}`}><ScanSearch size={16} /> Ver evaluación</Link>}
      </div>
      {resumen && <p>{resumen}</p>}
      {estado === "seleccion_aprobada" && actor.rol === "area_usuaria" && seleccionado &&
        <ConfirmarOrden expediente={expediente} seleccionado={seleccionado} recargar={recargar} />}
      {estado === "seleccion_aprobada" && actor.rol !== "area_usuaria" &&
        <Aviso>Selección aprobada. Falta que el área usuaria registre la orden.</Aviso>}
    </section>
  );
}

function Observacion({ registro }) {
  const { subsanacion } = registro;
  return (
    <div className="observacion-entrega">
      <Indicador tono={subsanacion ? "verde" : "ambar"}>{subsanacion ? "Subsanado"
        : registro.comunicacion ? "Comunicada, en plazo de subsanación" : "Observación sin comunicar"}</Indicador>
      <p>{registro.detalle.resumen}</p>
      <small>{registro.actor} · {fechaHora(registro.ts)}</small>
      {registro.comunicacion && <div className="subsanacion-entrega">
        <strong>Comunicación al proveedor</strong>
        <p>{registro.comunicacion.detalle.resumen}</p>
        <small>{registro.comunicacion.actor} · {fechaHora(registro.comunicacion.ts)}</small>
      </div>}
      {subsanacion && <div className="subsanacion-entrega">
        <strong>Subsanación verificada</strong>
        <p>{subsanacion.detalle.resumen}</p>
        <small>{subsanacion.actor} · {fechaHora(subsanacion.ts)}</small>
      </div>}
    </div>
  );
}

function Entregables({ expediente, conformidad, entregables, observaciones, actor, recargar }) {
  const [mostrar, setMostrar] = useState(false);
  const porObservar = entregables.filter((item) => !observaciones.has(item.id));
  return (
    <section className="seccion" id="entregables">
      <h2>Entregables y conformidad</h2>
      {!tieneOrden(expediente) ? <Aviso>Estos son los entregables del requerimiento. La conformidad se registra después de la orden.</Aviso>
      : conformidad ? <>
        <p>Conformidad registrada por <strong>{conformidad.conformante}</strong> el {fecha(conformidad.fecha_conformidad)}
          {" · "}Penalidad aplicada de {soles(conformidad.penalidad_aplicada)}</p>
        {conformidad.observaciones && <p className="secundario">Observaciones: {conformidad.observaciones}</p>}
        {conformidad.codigo_sello && <Sello conformidad={conformidad} id={expediente.id} />}
        {actor.rol === "abastecimiento" && <RevisionDec expediente={expediente} recargar={recargar} />}
        {actor.rol === "area_usuaria" && <div className="acciones">
          <Link className="boton" href={`${rutaExpediente(expediente.id)}/tdr`}><FileText size={16} /> Historial de TDR</Link>
        </div>}
      </> : <>
        <Aviso>{entregables.length ? "Conformidad pendiente." : "Este expediente no tiene entregables cargados."}</Aviso>
        {actor.rol === "area_usuaria" && entregables.length > 0 && <div className="acciones">
          <Link className="boton" href={`${rutaExpediente(expediente.id)}/tdr`}><FileText size={16} /> Revisar TDR<InsigniaIA /></Link>
        </div>}
        {actor.rol === "abastecimiento" && <ComunicarObservacion expediente={expediente}
          observaciones={observaciones} recargar={recargar} />}
        {actor.rol === "area_usuaria" && porObservar.length > 0 && (
          <RegistrarObservacion expediente={expediente} entregables={porObservar} recargar={recargar} />
        )}
      </>}
      {entregables.some((item) => item.evidencias.length > 0) && (
        <label className="casilla"><input type="checkbox" checked={mostrar} onChange={(e) => setMostrar(e.target.checked)} /> Mostrar evidencias</label>
      )}
      <div className="tarjetas">
        {entregables.map((item) => (
          <article className="panel ficha" key={item.id}>
            <div className="fila-titulo"><h3>{item.numero}. {item.descripcion}</h3><EstadoEntregable item={item} /></div>
            {observaciones.has(item.id) && <Observacion registro={observaciones.get(item.id)} />}
            {item.observacion && !observaciones.get(item.id)?.subsanacion && <p className="secundario">Observación en la conformidad: {item.observacion}</p>}
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
    <section className="seccion" id="alertas">
      <div className="fila-titulo">
        <h2>Alertas del expediente</h2>
        {actor.rol !== "auditor" && (
          <button disabled={accion.pendiente} onClick={() => accion.ejecutar(async () => {
            const { nuevas } = await api(`/expedientes/${expediente.id}/reevaluar`, { method: "POST" });
            recargar();
            return nuevas ? `Alertas nuevas: ${nuevas}.` : "Sin alertas nuevas.";
          })}><RefreshCw size={16} /> Actualizar alertas</button>
        )}
      </div>
      <EstadoAccion accion={accion} />
      {!alertas.length && <p className="vacio">Este expediente no tiene alertas.</p>}
      <div className="tarjetas">
        {alertas.map((a) => (
          <article className="panel ficha" key={a.id}>
            <div className="fila-titulo"><h3>{a.regla} · {nombreAlerta(a, reglas)}</h3>
              {a.vigente === false ? <Indicador>Criterio anterior</Indicador> :
                <div className="acciones"><Indicador tono={a.severidad === "alta" ? "rojo" : "ambar"}>{SEVERIDADES[a.severidad]}</Indicador>
                  <Indicador>{ESTADOS[a.estado]}</Indicador></div>}
            </div>
            <p>{a.explicacion}</p>
            {a.implicado && <small>Persona implicada: {a.implicado}</small>}
            <ReferenciaRegla alerta={a} />
            <Link className="volver" href={rutaAlerta(a.id)}><Bell size={16} /> Revisar en la bandeja</Link>
          </article>
        ))}
      </div>
    </section>
  );
}

function Pagos({ expediente, conformidad, abiertas, pendientes, pagos, actor, recargar }) {
  const accion = useAccion();
  function registrar(evento) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = Object.fromEntries(new FormData(form));
    accion.ejecutar(async () => {
      await api(`/expedientes/${expediente.id}/pagos`, { method: "POST", data: datos });
      form.reset();
      recargar();
      return "Pago registrado.";
    });
  }
  return (
    <section className="seccion" id="pagos">
      <h2>Pagos</h2>
      {pagos.length ? <>
        {abiertas > 0 && <Aviso tipo="advertencia">El expediente tiene {abiertas} alertas sin cerrar y ya registra pagos. Revisa las alertas.</Aviso>}
        <ul className="lista-simple">{pagos.map((p) => <li key={p.id}>
          <strong>{soles(p.monto)}</strong> · {fecha(p.fecha_pago)} · Penalidad descontada de {soles(p.penalidad_descontada)} · {p.registrado_por}
          {p.referencia_siaf && <small className="dato-tabla">Referencia SIAF {p.referencia_siaf}</small>}
        </li>)}</ul>
      </> : <p className="vacio">Sin pagos registrados.</p>}
      {actor.rol === "tesoreria" && tieneOrden(expediente) && (
        <details className="panel desplegable" id="registrar-pago">
          <summary>Registrar pago efectuado</summary>
          <form className="formulario" onSubmit={registrar}>
            {abiertas > 0 && <Aviso tipo="advertencia">Hay {abiertas} alertas pendientes de revisión.</Aviso>}
            {pendientes > 0 && <Aviso tipo="advertencia">Hay observaciones pendientes en los entregables.</Aviso>}
            {!conformidad && <Aviso tipo="advertencia">Si registras este pago sin conformidad previa, se genera la alerta R5.</Aviso>}
            <div className="rejilla tres">
              <Campo titulo="Fecha de pago"><input name="fecha_pago" type="date" defaultValue={hoy()} required /></Campo>
              <Campo titulo="Monto pagado (S/)" ayuda={`Monto de la orden: ${soles(expediente.monto)}`}>
                <input name="monto" type="number" min="0.01" step="0.01" defaultValue={expediente.monto} required /></Campo>
              <Campo titulo="Penalidad descontada (S/)"
                ayuda={conformidad ? `Penalidad aplicada en la conformidad: ${soles(conformidad.penalidad_aplicada)}` : undefined}>
                <input name="penalidad_descontada" type="number" min="0" step="0.01"
                  defaultValue={conformidad?.penalidad_aplicada ?? "0"} required /></Campo>
              <Campo titulo="Referencia SIAF (opcional)">
                <input name="referencia_siaf" maxLength={60} /></Campo>
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
    <section className="seccion" id="linea-de-tiempo">
      <h2>Línea de tiempo</h2>
      {!eventos.length && <p className="vacio">Sin movimientos registrados.</p>}
      <ol className="linea-tiempo">
        {eventos.map((evento) => (
          <li key={evento.id} data-tipo={evento.accion.split(".")[0]}>
            <time dateTime={evento.ts}>{fechaHora(evento.ts)}</time>
            <div className="evento">
              <h3>{ACCIONES[evento.accion] ?? evento.accion}</h3>
              <small>{evento.actor ?? "Sistema"} · Registro n.º {evento.id}</small>
              {evento.detalle?.resumen && <p>{evento.detalle.resumen}</p>}
              {evento.accion.startsWith("entregable.") && <small>Entregable {evento.detalle.numero}</small>}
              {evento.detalle?.referencia_siaf && <small>Referencia SIAF {evento.detalle.referencia_siaf}</small>}
              {evento.documento_sha256 && <small>{evento.detalle?.documento ?? "Documento"} · SHA-256 <code>{evento.documento_sha256.slice(0, 16)}…</code></small>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function abrirRegistroPago() {
  const panel = document.getElementById("registrar-pago");
  if (!panel) return;
  panel.open = true;
  panel.querySelector("summary")?.focus({ preventScroll: true });
  panel.scrollIntoView({ block: "start" });
}

/** Qué le toca hacer a quien mira el expediente, según su rol y el estado. */
function Siguiente({ actor, expediente, conformidad, entregables, pendientes, alertas, pagos }) {
  const ruta = rutaExpediente(expediente.id);
  const sinCerrar = alertas.filter(alertaPendiente);
  const estado = expediente.estado_flujo;
  if (!tieneOrden(expediente)) {
    if (actor.rol === "area_usuaria") {
      return estado === "seleccion_aprobada"
        ? <ProximoPaso titulo="Registra la orden de servicio"
          acciones={<a className="boton primario" href="#seleccion"><Stamp size={16} /> Registrar orden</a>}>
          La selección del proveedor ya tiene revisión independiente aprobada.</ProximoPaso>
        : <ProximoPaso titulo="Abastecimiento está evaluando a los posibles proveedores">
          Te avisaremos aquí cuando la selección esté aprobada para que registres la orden.</ProximoPaso>;
    }
    if (actor.rol === "abastecimiento" && estado !== "seleccion_aprobada") {
      return <ProximoPaso titulo={estado === "pendiente_revision_independiente" ? "Selección en revisión independiente" : "Evalúa a los posibles proveedores"}
        acciones={<Link className="boton primario" href={`/prevencion/${expediente.id}`}><ScanSearch size={16} /> Ir a la evaluación</Link>}>
        El análisis por 6 dimensiones, el consolidado y la selección se hacen en Análisis de proveedores.</ProximoPaso>;
    }
    return null;
  }
  if (actor.rol === "area_usuaria") {
    if (!conformidad && !entregables.length) {
      return <ProximoPaso titulo="Faltan los entregables"
        acciones={<Link className="boton primario" href={`${ruta}/tdr`}><FileText size={16} /> Revisar TDR<InsigniaIA /></Link>} />;
    }
    if (!conformidad) {
      return <ProximoPaso tono={pendientes ? "advertencia" : "info"}
        titulo={pendientes ? "Hay entregables observados" : "Falta registrar la conformidad"}
        acciones={<>
          <a className="boton" href="#entregables">Revisar entregables</a>
          <Link className="boton primario" href={`${ruta}/conformidad`}><ClipboardCheck size={17} /> Registrar conformidad</Link>
        </>}>
        {pendientes ? "Adjunta la corrección y describe qué verificaste al registrar la conformidad."
          : "Verifica la prestación y adjunta la evidencia de cada entregable."}</ProximoPaso>;
    }
    const propias = sinCerrar.filter((a) => a.estado === "abierta"
      && [a.persona_implicada_id, a.conformante_id].includes(actor.persona_id));
    if (propias.length) {
      return <ProximoPaso tono="advertencia" titulo={`Puedes presentar descargo en ${propias.length === 1 ? "1 alerta" : `${propias.length} alertas`}`}
        acciones={<Link className="boton primario" href={rutaAlerta(propias[0].id)}><Bell size={16} /> Ir a la alerta</Link>}>
        El descargo quedará en el historial de la alerta.</ProximoPaso>;
    }
    return null;
  }
  if (actor.rol === "tesoreria" && !pagos.length) {
    if (!conformidad) {
      return <ProximoPaso tono="advertencia" titulo="Falta la conformidad del área usuaria"
        acciones={pendientes > 0 && <a className="boton" href="#entregables">Ver observaciones</a>}>
        Revisa el sustento antes de tramitar el pago.</ProximoPaso>;
    }
    return <ProximoPaso tono={sinCerrar.length || pendientes ? "advertencia" : "info"}
      titulo={pendientes ? "Hay observaciones pendientes"
        : sinCerrar.length ? `${sinCerrar.length} alertas pendientes de revisión` : "Conformidad registrada"}
      acciones={<>
        {pendientes > 0 && <a className="boton" href="#entregables">Ver observaciones</a>}
        {sinCerrar.length > 0 && <a className="boton" href="#alertas"><Bell size={16} /> Ver alertas</a>}
        <button className="primario" onClick={abrirRegistroPago}><Wallet size={16} /> Registrar pago efectuado</button>
      </>}>
      {sinCerrar.length || pendientes ? "Revisa el sustento antes del pago." : "Consulta el devengado en el SIAF."}
    </ProximoPaso>;
  }
  if (actor.rol !== "area_usuaria" && sinCerrar.length) {
    return <ProximoPaso tono="advertencia" titulo={`${sinCerrar.length === 1 ? "1 alerta" : `${sinCerrar.length} alertas`} por revisar`}
      acciones={<Link className="boton primario" href={rutaAlerta(sinCerrar[0].id)}><Bell size={16} /> Revisar en la bandeja</Link>} />;
  }
  return null;
}

function EstadoTramite({ expediente, conformidad, pagos }) {
  const ultimoPago = pagos.at(-1);
  const conOrden = tieneOrden(expediente);
  const evaluacion = conOrden || expediente.estado_flujo === "seleccion_aprobada" ? ["Aprobada", "registrada"]
    : expediente.estado_flujo === "pendiente_revision_independiente" ? ["En revisión independiente", "pendiente"]
      : ["En curso", "pendiente"];
  const etapas = [
    ["Evaluación de proveedores", "Abastecimiento", evaluacion[0], evaluacion[1]],
    [expediente.tipo === "servicio" ? "Orden de servicio" : "Orden de compra", "Área usuaria",
      conOrden ? fecha(expediente.fecha_orden) : "Pendiente", conOrden ? "registrada" : "pendiente"],
    ["Conformidad", "Área usuaria", conformidad ? fecha(conformidad.fecha_conformidad) : "Pendiente", conformidad ? "registrada" : "pendiente"],
    ["Devengado", "Contabilidad", "Consultar en SIAF", "externa"],
    ["Pago", "Tesorería", ultimoPago ? fecha(ultimoPago.fecha_pago) : "Sin registro", ultimoPago ? "registrada" : "pendiente"],
  ];
  return <ol className="etapas etapas-cinco" aria-label="Estado del trámite">
    {etapas.map(([titulo, dependencia, estado, clase]) => (
      <li key={titulo} data-estado={clase}>
        <span className="etapa-punto" aria-hidden="true" />
        <strong>{titulo}</strong>
        <span>{dependencia}</span>
        <small>{estado}</small>
      </li>
    ))}
  </ol>;
}

export function Detalle({ actor }) {
  const { id } = useParams();
  const recurso = useDatos(`/expedientes/${id}`);
  if (!recurso.datos) return <><Volver to="/expedientes">Expedientes</Volver><Carga recurso={recurso} /></>;
  const { expediente, conformidad, fecha_limite, plazo_maximo_conformidad, entregables, alertas, reglas, pagos, eventos,
    seleccion } = recurso.datos;
  const conOrden = tieneOrden(expediente);
  const [estadoTexto, estadoQuien, estadoTono] = ESTADOS_FLUJO[expediente.estado_flujo] ?? [expediente.estado_flujo, "", "neutro"];
  const cumplidos = entregables.filter((item) => item.cumplido);
  const sinEvidencia = cumplidos.filter((item) => !item.evidencias.length);
  const abiertas = alertas.filter(alertaPendiente).length;
  const observaciones = observacionesDeEntrega(eventos);
  const pendientes = [...observaciones.values()].filter((registro) => !registro.subsanacion).length;
  return (
    <>
      <Volver to={expediente.tipo === "bien" ? "/expedientes?tipo=bien" : "/expedientes"}>Expedientes</Volver>
      <div className="caratula">
        <Encabezado titulo={expediente.descripcion} descripcion={expediente.area}
          acciones={<div className="acciones">
            <Indicador tono={estadoTono}>{estadoTexto}</Indicador>
            {conOrden && <Semaforo color={expediente.semaforo} />}
          </div>}>
          <div className="caratula-codigo">{expediente.codigo} <span>{expediente.numero_orden ?? "Sin orden todavía"}</span>
            {estadoQuien && estadoQuien !== "—" && <span>Le toca: {estadoQuien}</span>}</div>
        </Encabezado>
        <EstadoTramite expediente={expediente} conformidad={conformidad} pagos={pagos} />
      </div>
      <AvisoNavegacion />
      <div className="acciones"><a className="boton" href={`/api/expedientes/${expediente.id}/reporte`}>
        <Download size={16} /> Reporte de trazabilidad (PDF)</a></div>
      <Siguiente actor={actor} expediente={expediente} conformidad={conformidad} entregables={entregables} pendientes={pendientes}
        alertas={alertas} pagos={pagos} />
      <SeleccionProveedor expediente={expediente} seleccion={seleccion} actor={actor} recargar={recurso.recargar} />
      <nav className="indice" aria-label="Secciones del expediente">
        <a href="#datos">{conOrden ? "Datos de la orden" : "Datos del requerimiento"}</a>
        {seleccion && <a href="#seleccion">Selección del proveedor</a>}
        <a href="#entregables">Entregables ({entregables.length})</a>
        <a href="#alertas">Alertas ({abiertas})</a>
        <a href="#pagos">Pagos ({pagos.length})</a>
        <a href="#linea-de-tiempo">Línea de tiempo</a>
      </nav>
      <section id="datos" className="panel datos-orden">
        <h2>{conOrden ? "Datos de la orden" : "Datos del requerimiento"}</h2>
        <div className="rejilla dos">
          <DatosClave valores={[
            [conOrden ? "Monto" : "Valor estimado", soles(expediente.monto)], ["Tipo", capitalizar(expediente.tipo)],
            ["Área usuaria", expediente.area], ["Solicitante", expediente.solicitante],
            ["Proveedor", conOrden ? `${expediente.proveedor} (RUC ${expediente.proveedor_ruc})` : "Por definir: en evaluación"],
            ...(expediente.proyecto_referencia ? [["Proyecto", expediente.proyecto_referencia]] : []),
          ]} />
          <DatosClave valores={[
            ["Requerimiento", fecha(expediente.fecha_requerimiento)], ["Orden emitida", fecha(expediente.fecha_orden)],
            ["Inicio pactado", fecha(expediente.fecha_inicio_prestacion)], ["Plazo de ejecución", `${expediente.plazo_dias} días`],
            [expediente.fecha_inicio_prestacion ? "Fecha límite" : "Fecha límite estimada", conOrden ? fecha(fecha_limite) : "Se calcula con la orden"],
            ["Recepción del entregable", fecha(expediente.fecha_entrega_real)],
            ["Plazo de conformidad", `${plazo_maximo_conformidad} días`],
          ]} />
        </div>
        {expediente.proyecto_referencia && <p className="secundario tramite-dine">
          Trámite por la Dirección de Investigación y Ética (DINE) para proyectos con fondos externos.{" "}
          <a href="https://din.unitru.edu.pe/ruta-de-procesos/" target="_blank" rel="noreferrer">Ruta de la UNT</a>
        </p>}
      </section>
      {sinEvidencia.length > 0 && <Aviso tipo="advertencia">Entregables dados por cumplidos sin evidencia: {sinEvidencia.map((e) => e.numero).join(", ")}.</Aviso>}
      <Entregables key={expediente.id} expediente={expediente} conformidad={conformidad} entregables={entregables}
        observaciones={observaciones} actor={actor} recargar={recurso.recargar} />
      <AlertasDelExpediente expediente={expediente} alertas={alertas} reglas={reglas} actor={actor} recargar={recurso.recargar} />
      <Pagos expediente={expediente} conformidad={conformidad} abiertas={abiertas} pendientes={pendientes}
        pagos={pagos} actor={actor} recargar={recurso.recargar} />
      <LineaDeTiempo eventos={eventos} />
    </>
  );
}
