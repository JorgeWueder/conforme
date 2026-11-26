"use client";

import Link from "next/link";
import {
  AlertTriangle, ArrowUpRight, Building2, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleAlert, ClipboardCheck, FileSearch, Info, Layers3, Loader2, OctagonAlert,
  Pencil, Play, RefreshCw, ShieldCheck, Square, Users, X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, apiStream, useAccion, useDatos } from "../api";
import { Aviso, Carga, EstadoAccion, Volver } from "../ui";
import { EstadoRevision } from "./lista";

const ESTADOS_REVISION = {
  aclarado: "Aclarado",
  descartado: "Descartado",
  derivado: "Derivado",
  pendiente: "Pendiente",
  verificado: "Verificado",
  no_aplica: "No aplica",
};

const PRIORIDADES = {
  verificar: "Verificar",
  aclarar: "Aclarar",
  contexto: "Contexto",
};

const ROLES_DIALOGO = {
  constancias: { titulo: "Registrar comprobación", opciones: ["verificado", "derivado", "no_aplica", "pendiente"] },
  hallazgos: { titulo: "Registrar actuación", opciones: ["aclarado", "descartado", "derivado", "pendiente"] },
  cierre: { titulo: "Cerrar revisión", opciones: [] },
};

function formatoImporte(importe, moneda) {
  return new Intl.NumberFormat("es-PE", { style: "currency", currency: moneda }).format(importe);
}

function fechaCorta(fecha) {
  return new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(fecha));
}

function FuenteEnlace({ href, children }) {
  return href && /^https:\/\//i.test(href)
    ? <a href={href} target="_blank" rel="noreferrer">{children}<ArrowUpRight size={13} aria-hidden="true" /></a>
    : <span>{children}</span>;
}

function IconoPaso({ estado }) {
  if (estado === "consultando") return <Loader2 size={15} className="prev-girar" aria-hidden="true" />;
  if (estado === "alerta") return <OctagonAlert size={15} aria-hidden="true" />;
  if (estado === "atencion") return <AlertTriangle size={15} aria-hidden="true" />;
  if (estado === "contexto") return <Info size={15} aria-hidden="true" />;
  return <CheckCircle2 size={15} aria-hidden="true" />;
}

function nivelDeHallazgos(hallazgos) {
  if (hallazgos.some((h) => h.prioridad === "verificar")) return "verificar";
  if (hallazgos.some((h) => h.prioridad === "aclarar")) return "aclarar";
  if (hallazgos.some((h) => h.prioridad === "contexto")) return "contexto";
  return "limpio";
}

function EstadoSujeto({ analizando, analizado, hallazgos, resoluciones }) {
  if (analizando) {
    return <span className="prev-chip chip-curso"><Loader2 size={12} className="prev-girar" aria-hidden="true" />Analizando</span>;
  }
  if (!analizado) {
    return <span className="prev-chip chip-pendiente">Sin analizar</span>;
  }
  const porVerificar = hallazgos.filter((h) => h.prioridad === "verificar" &&
    !["aclarado", "descartado", "derivado"].includes(resoluciones[h.id]?.resultado)).length;
  if (porVerificar > 0) {
    return <span className="prev-chip chip-alerta">{porVerificar} por verificar</span>;
  }
  const nivel = nivelDeHallazgos(hallazgos);
  if (nivel === "verificar") {
    return <span className="prev-chip chip-ok">Atendido</span>;
  }
  if (nivel === "aclarar") {
    const n = hallazgos.filter((h) => h.prioridad === "aclarar").length;
    return <span className="prev-chip chip-atencion">{n} por aclarar</span>;
  }
  if (nivel === "contexto") {
    const n = hallazgos.length;
    return <span className="prev-chip chip-contexto">{n} de contexto</span>;
  }
  return <span className="prev-chip chip-ok">Sin observaciones</span>;
}

function Evidencias({ evidencias }) {
  return <ul className="prev-evidencias">
    {evidencias.map((e, indice) => <li key={`${e.sha256 ?? e.fuente}:${e.fila ?? e.acto ?? indice}:${indice}`}>
      <div className="prev-evidencia-encabezado">
        <FuenteEnlace href={e.url_acto || e.url}>{e.fuente}</FuenteEnlace>
        <small>{[e.fecha && fechaCorta(e.fecha), e.fila && `Fila ${e.fila}`, e.acto].filter(Boolean).join(" · ")}</small>
      </div>
      {e.extracto && <p>{e.extracto}</p>}
      {e.alcance && <small>{e.alcance}</small>}
    </li>)}
  </ul>;
}

function Resultado({ resultado }) {
  if (!resultado) return null;
  return <div className="prev-actuacion">
    <Check size={15} aria-hidden="true" />
    <div>
      <strong>{ESTADOS_REVISION[resultado.resultado]}</strong>
      <p>{resultado.nota}</p>
      <small>{resultado.referencia}{resultado.fecha_hecho ? ` · ${fechaCorta(resultado.fecha_hecho)}` : ""}</small>
    </div>
  </div>;
}

function ConsolaAnalisis({ flujo, abierta, alternar, detener }) {
  const listaRef = useRef(null);
  useEffect(() => {
    if (abierta && listaRef.current) {
      listaRef.current.scrollTop = listaRef.current.scrollHeight;
    }
  }, [flujo.eventos.length, abierta]);

  if (!flujo.activo && flujo.eventos.length === 0) return null;

  const porcentaje = flujo.totalPasos > 0
    ? Math.min(100, Math.round((flujo.progreso / flujo.totalPasos) * 100))
    : 0;

  if (!flujo.activo && !abierta) {
    return <section className={`prev-stream-resumen ${flujo.detenido ? "detenido" : ""}`} aria-label="Resumen del último análisis">
      <div className="prev-stream-resumen-texto">
        {flujo.detenido ? <AlertTriangle size={17} aria-hidden="true" /> : <CheckCircle2 size={17} aria-hidden="true" />}
        <span>
          <strong>{flujo.detenido ? "Análisis detenido" : "Análisis completado"}</strong>
          {" · "}
          {flujo.progreso}{flujo.detenido && flujo.totalPasos ? ` de ${flujo.totalPasos}` : ""} verificaciones en fuentes simuladas
          {flujo.hallazgosDetectados > 0
            ? ` · ${flujo.hallazgosDetectados} ${flujo.hallazgosDetectados === 1 ? "hallazgo detectado" : "hallazgos detectados"}`
            : " · sin hallazgos"}
        </span>
      </div>
      <button type="button" className="prev-texto-boton" onClick={alternar}>
        Ver bitácora <ChevronDown size={15} aria-hidden="true" />
      </button>
    </section>;
  }

  return <section className={`prev-stream ${flujo.activo ? "prev-stream-vivo" : ""}`} aria-label="Análisis en tiempo real" aria-live="polite">
    <header className="prev-stream-cabecera">
      <div className="prev-stream-estado">
        <span className={`prev-pulso ${flujo.activo ? "activo" : "listo"}`} aria-hidden="true" />
        <div>
          <strong>{flujo.activo ? flujo.tituloActual : "Bitácora del último análisis"}</strong>
          <small>
            {flujo.activo
              ? `${flujo.progreso} de ${flujo.totalPasos || "…"} verificaciones`
              : `${flujo.progreso} verificaciones completadas · fuentes simuladas`}
          </small>
        </div>
      </div>
      <div className="prev-stream-acciones">
        <span className="prev-stream-porcentaje">{porcentaje}%</span>
        {flujo.activo ? (
          <button type="button" className="prev-boton-compacto" onClick={detener}>
            <Square size={13} aria-hidden="true" />Detener
          </button>
        ) : (
          <button type="button" className="prev-texto-boton" onClick={alternar}>
            Ocultar
          </button>
        )}
      </div>
    </header>
    <div className="prev-progreso" role="progressbar" aria-valuenow={porcentaje} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${porcentaje}%` }} />
    </div>
    <ol className="prev-stream-lista" ref={listaRef}>
      {flujo.eventos.map((item) => <li key={item.id} className={`prev-stream-item estado-${item.estado}`}>
        <span className="prev-stream-icono"><IconoPaso estado={item.estado} /></span>
        <div className="prev-stream-cuerpo">
          <div className="prev-stream-linea">
            <strong>{item.sujeto}</strong>
            <span className="prev-stream-fuente">{item.fuente}</span>
            {item.hallazgo && (
              <span className={`prev-chip chip-${item.hallazgo.prioridad === "verificar" ? "alerta" : item.hallazgo.prioridad === "aclarar" ? "atencion" : "contexto"}`}>
                {PRIORIDADES[item.hallazgo.prioridad]}
              </span>
            )}
          </div>
          <p>{item.mensaje}</p>
        </div>
      </li>)}
    </ol>
  </section>;
}

function ComprobacionesCompactas({ revision, ruc, dialogo }) {
  const [verOpcionales, setVerOpcionales] = useState(false);
  const controles = revision.controles.filter((c) => c.ruc === ruc);
  const obligatorios = controles.filter((c) => c.obligatorio);
  const opcionales = controles.filter((c) => !c.obligatorio);
  const hechosObligatorios = obligatorios.filter((c) =>
    ["verificado", "no_aplica", "derivado"].includes(revision.constancias[c.id]?.resultado),
  ).length;
  const visibles = verOpcionales ? controles : obligatorios;

  return <details className="prev-bloque-plegable">
    <summary>
      <ClipboardCheck size={16} aria-hidden="true" />
      <span>Comprobaciones de control</span>
      <span className={`prev-chip ${hechosObligatorios === obligatorios.length ? "chip-ok" : "chip-pendiente"}`}>
        {hechosObligatorios} / {obligatorios.length} obligatorias
      </span>
      <ChevronRight size={16} className="prev-plegable-flecha" aria-hidden="true" />
    </summary>
    <div className="prev-controles-cuerpo">
      <ul className="prev-controles-lista">
        {visibles.map((control) => {
          const resultado = revision.constancias[control.id];
          const cumplido = ["verificado", "no_aplica", "derivado"].includes(resultado?.resultado);
          return <li key={control.id} className="prev-control-fila">
            <div className="prev-control-info">
              <div className="prev-control-titulo">
                <span className={`prev-control-punto ${cumplido ? "hecho" : ""}`} aria-hidden="true" />
                <strong>{control.titulo}</strong>
                {control.obligatorio && <span className="prev-etiqueta">Obligatoria</span>}
                {resultado && <span className="prev-chip chip-ok">{ESTADOS_REVISION[resultado.resultado]}</span>}
              </div>
              <p>{control.instruccion}</p>
              <div className="prev-control-meta">
                <FuenteEnlace href={control.url}>Fuente oficial</FuenteEnlace>
                {resultado && <small>Ref. {resultado.referencia}</small>}
              </div>
            </div>
            {revision.estado === "abierta" && (
              <button type="button" className="prev-boton-compacto"
                onClick={() => dialogo({ tipo: "constancias", item: control, anterior: resultado })}>
                {resultado ? "Editar" : "Registrar"}
              </button>
            )}
          </li>;
        })}
      </ul>
      {opcionales.length > 0 && (
        <button type="button" className="prev-texto-boton" onClick={() => setVerOpcionales((v) => !v)}>
          {verOpcionales ? "Ocultar comprobaciones complementarias" : `Ver ${opcionales.length} comprobaciones complementarias`}
        </button>
      )}
    </div>
  </details>;
}

function Actuacion({ datos, cerrar, ejecutar, accion }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current.open) ref.current.showModal();
  }, []);
  const { titulo, opciones } = ROLES_DIALOGO[datos.tipo];

  function enviar(evento) {
    evento.preventDefault();
    const valores = Object.fromEntries(new FormData(evento.currentTarget));
    if (datos.tipo === "hallazgos") valores.hallazgo = datos.item.id;
    if (datos.tipo === "constancias") {
      valores.control = datos.item.id;
      valores.fecha_hecho ||= null;
    }
    ejecutar(datos.tipo, valores, cerrar);
  }

  return <dialog className="prev-dialogo" ref={ref} onClose={cerrar}>
    <form onSubmit={enviar}>
      <div className="prev-dialogo-cabecera">
        <h2>{titulo}</h2>
        <button type="button" className="prev-cerrar-dialogo" onClick={cerrar} aria-label="Cerrar formulario">
          <X size={20} />
        </button>
      </div>
      {datos.item && <p className="secundario">{datos.item.titulo}</p>}
      {opciones.length > 0 && <>
        <label>Resultado<select name="resultado" defaultValue={datos.anterior?.resultado ?? ""} autoFocus required>
          <option value="" disabled>Selecciona un resultado</option>
          {opciones.map((opcion) => <option key={opcion} value={opcion}>{ESTADOS_REVISION[opcion]}</option>)}
        </select></label>
        <label>Referencia o constancia<input name="referencia" maxLength={200} defaultValue={datos.anterior?.referencia} required /></label>
      </>}
      {datos.tipo === "constancias" && <label>Fecha de comprobación <span>Opcional</span>
        <input type="date" name="fecha_hecho" defaultValue={datos.anterior?.fecha_hecho} /></label>}
      <label>{datos.tipo === "cierre" ? "Sustento del cierre" : "Nota"}
        <textarea name="nota" rows={3} minLength={5} maxLength={1800} defaultValue={datos.anterior?.nota} required />
      </label>
      <EstadoAccion accion={accion} />
      <div className="prev-dialogo-pie">
        <button type="button" onClick={cerrar} disabled={accion.pendiente}>Cancelar</button>
        <button className="primario" disabled={accion.pendiente}>{accion.pendiente ? "Guardando…" : titulo}</button>
      </div>
    </form>
  </dialog>;
}

function Ficha({ revision, actualizar, recargar }) {
  const { compra } = revision;
  const [seleccion, setSeleccion] = useState(() => compra.candidatos[0]?.ruc ?? null);
  const [dialogo, setDialogo] = useState(null);
  const [bitacoraAbierta, setBitacoraAbierta] = useState(false);
  const [errorFlujo, setErrorFlujo] = useState(null);
  const [flujo, setFlujo] = useState({
    activo: false,
    detenido: false,
    alcance: null,
    rucActivo: null,
    tituloActual: "",
    progreso: 0,
    totalPasos: 0,
    hallazgosDetectados: 0,
    eventos: [],
    verificacionesVivas: {},
    hallazgosVivos: {},
  });
  const abortarRef = useRef(null);
  const accion = useAccion();
  const accionDialogo = useAccion();

  useEffect(() => () => abortarRef.current?.abort(), []);

  const abierta = revision.estado === "abierta";
  const analisisGuardado = revision.analisis || {};
  const candidato = compra.candidatos.find((c) => c.ruc === seleccion) ?? null;
  const ruc = candidato?.ruc ?? null;
  const claveSujeto = ruc ?? "__compra__";

  // Combina resultados ya persistidos con hallazgos/verificaciones que van llegando en vivo.
  function hallazgosDe(sujetoRuc) {
    const clave = sujetoRuc ?? "__compra__";
    if (flujo.activo && flujo.hallazgosVivos[clave]) {
      return flujo.hallazgosVivos[clave];
    }
    return revision.hallazgos.filter((h) => h.ruc === sujetoRuc);
  }

  function verificacionesDe(sujetoRuc) {
    const clave = sujetoRuc ?? "__compra__";
    if (flujo.verificacionesVivas[clave]?.length) {
      return flujo.verificacionesVivas[clave];
    }
    return analisisGuardado[clave]?.verificaciones ?? [];
  }

  function estaAnalizado(sujetoRuc) {
    const clave = sujetoRuc ?? "__compra__";
    if (flujo.verificacionesVivas[clave]?.length) return true;
    if (analisisGuardado[clave]?.estado === "analizado") return true;
    return revision.fuentes.length > 0;
  }

  const obligatorios = revision.controles.filter((c) => c.obligatorio);
  const comprobados = obligatorios.filter((c) =>
    ["verificado", "no_aplica", "derivado"].includes(revision.constancias[c.id]?.resultado),
  ).length;
  const pendientes = revision.hallazgos.filter((h) => h.prioridad === "verificar" &&
    !["aclarado", "descartado", "derivado"].includes(revision.resoluciones[h.id]?.resultado));
  const porVerificar = pendientes.length;

  const hallazgosActuales = hallazgosDe(ruc);
  const verificacionesActuales = verificacionesDe(ruc);
  const investigacionesActuales = revision.investigaciones.filter((i) => (ruc ? i.ruc === ruc : true));
  const analizadoActual = estaAnalizado(ruc);
  const analizandoActual = flujo.activo && (flujo.rucActivo === ruc || (flujo.rucActivo === "__compra__" && ruc === null));
  const yaAnalizadoAlguno = revision.fuentes.length > 0 || Object.keys(analisisGuardado).length > 0;

  function ejecutar(operacion, datos, despues) {
    const estadoAccion = despues ? accionDialogo : accion;
    estadoAccion.ejecutar(async () => {
      const nueva = await api(`/prevencion/${revision.id}/${operacion}`, {
        method: "POST", data: { version: revision.version, ...datos },
      });
      actualizar(nueva);
      despues?.();
    });
  }

  function detenerAnalisis() {
    abortarRef.current?.abort();
    abortarRef.current = null;
    setFlujo((actual) => ({ ...actual, activo: false, detenido: true, rucActivo: null }));
    setBitacoraAbierta(false);
  }

  async function iniciarAnalisis(objetivoRuc = null) {
    if (flujo.activo) return;
    if (objetivoRuc) setSeleccion(objetivoRuc);
    setErrorFlujo(null);
    setBitacoraAbierta(true);

    const control = new AbortController();
    abortarRef.current = control;

    setFlujo({
      activo: true,
      detenido: false,
      alcance: objetivoRuc ?? "todos",
      rucActivo: objetivoRuc,
      tituloActual: objetivoRuc
        ? `Iniciando análisis de ${compra.candidatos.find((c) => c.ruc === objetivoRuc)?.nombre ?? objetivoRuc}…`
        : `Iniciando análisis de ${compra.candidatos.length} proveedores…`,
      progreso: 0,
      totalPasos: 0,
      hallazgosDetectados: 0,
      eventos: [],
      verificacionesVivas: objetivoRuc ? { [objetivoRuc]: [] } : {},
      hallazgosVivos: objetivoRuc ? { [objetivoRuc]: [] } : {},
    });

    try {
      await apiStream(`/prevencion/${revision.id}/analizar`, {
        data: { version: revision.version, ruc: objetivoRuc, simular: true },
        signal: control.signal,
        onEvento: (ev) => {
          if (ev.tipo === "inicio") {
            setFlujo((prev) => ({
              ...prev,
              totalPasos: ev.total_pasos,
              tituloActual: objetivoRuc
                ? `Analizando ${ev.proveedores[0]?.nombre ?? objetivoRuc}…`
                : `Analizando ${ev.proveedores.length} proveedores registrados…`,
            }));
            return;
          }
          if (ev.tipo === "proveedor_inicio") {
            setFlujo((prev) => ({
              ...prev,
              rucActivo: ev.ruc,
              tituloActual: `Analizando proveedor ${ev.indice} de ${ev.total}: ${ev.nombre}`,
              verificacionesVivas: { ...prev.verificacionesVivas, [ev.ruc]: [] },
              hallazgosVivos: { ...prev.hallazgosVivos, [ev.ruc]: [] },
            }));
            return;
          }
          if (ev.tipo === "compra_inicio") {
            setFlujo((prev) => ({
              ...prev,
              rucActivo: "__compra__",
              tituloActual: "Analizando alcance general de la compra y cotizaciones…",
              verificacionesVivas: { ...prev.verificacionesVivas, __compra__: [] },
              hallazgosVivos: { ...prev.hallazgosVivos, __compra__: [] },
            }));
            return;
          }
          if (ev.tipo === "paso") {
            const idPaso = `${ev.ruc ?? "compra"}:${ev.fuente_id}`;
            const clave = ev.ruc ?? "__compra__";
            setFlujo((prev) => {
              const lista = prev.verificacionesVivas[clave] ?? [];
              const sinDuplicar = lista.filter((v) => v.fuente_id !== ev.fuente_id);
              return {
                ...prev,
                eventos: [
                  ...prev.eventos.filter((item) => item.id !== idPaso),
                  {
                    id: idPaso,
                    sujeto: ev.nombre,
                    fuente: ev.fuente,
                    estado: "consultando",
                    mensaje: ev.mensaje,
                    hallazgo: null,
                  },
                ],
                verificacionesVivas: {
                  ...prev.verificacionesVivas,
                  [clave]: [...sinDuplicar, { fuente_id: ev.fuente_id, fuente: ev.fuente, frente: ev.frente, estado: "consultando", mensaje: ev.mensaje }],
                },
              };
            });
            return;
          }
          if (ev.tipo === "paso_resultado") {
            const idPaso = `${ev.ruc ?? "compra"}:${ev.fuente_id}`;
            const clave = ev.ruc ?? "__compra__";
            setFlujo((prev) => {
              const listaVerif = (prev.verificacionesVivas[clave] ?? []).filter((v) => v.fuente_id !== ev.fuente_id);
              const nuevaVerif = {
                fuente_id: ev.fuente_id,
                fuente: ev.fuente,
                frente: ev.frente,
                estado: ev.estado,
                mensaje: ev.mensaje,
              };
              const listaHallazgos = prev.hallazgosVivos[clave] ?? [];
              const siguientesHallazgos = ev.hallazgo
                ? [...listaHallazgos.filter((h) => h.id !== ev.hallazgo.id), ev.hallazgo]
                : listaHallazgos;
              return {
                ...prev,
                progreso: ev.progreso,
                totalPasos: ev.total_pasos,
                hallazgosDetectados: prev.hallazgosDetectados + (ev.hallazgo ? 1 : 0),
                eventos: prev.eventos.map((item) => item.id === idPaso
                  ? { ...item, estado: ev.estado, mensaje: ev.mensaje, hallazgo: ev.hallazgo }
                  : item),
                verificacionesVivas: { ...prev.verificacionesVivas, [clave]: [...listaVerif, nuevaVerif] },
                hallazgosVivos: { ...prev.hallazgosVivos, [clave]: siguientesHallazgos },
              };
            });
            return;
          }
          if (ev.tipo === "error") {
            setErrorFlujo(ev.detail || "No se pudo completar el análisis.");
            setFlujo((prev) => ({ ...prev, activo: false, rucActivo: null }));
            return;
          }
          if (ev.tipo === "completado") {
            actualizar(ev.revision);
            setFlujo((prev) => ({
              ...prev,
              activo: false,
              rucActivo: null,
              progreso: prev.totalPasos || prev.progreso,
              verificacionesVivas: {},
              hallazgosVivos: {},
            }));
            setBitacoraAbierta(false);
          }
        },
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        setErrorFlujo(error.message || "Se interrumpió la conexión durante el análisis.");
      }
      setFlujo((prev) => ({ ...prev, activo: false, rucActivo: null }));
    } finally {
      abortarRef.current = null;
    }
  }

  return <div className="prevencion prev-ficha-pagina">
    <Volver to="/prevencion">Mis revisiones</Volver>

    <header className="prev-ficha-encabezado">
      <div className="prev-ficha-titulo">
        <h1>{compra.objeto}</h1>
        <div className="prev-ficha-detalles">
          <code>{compra.requerimiento}</code>
          <span>{compra.unidad}</span>
          <span>{compra.modalidad}</span>
          <strong className="prev-cifra">{formatoImporte(compra.importe, compra.moneda)}</strong>
          <span>{fechaCorta(compra.fecha)}</span>
          <EstadoRevision estado={revision.estado} />
          <span className="prev-etiqueta">{revision.demo ? "Caso de ejemplo" : "Simulación de fuentes"}</span>
        </div>
      </div>

      {abierta && <div className="prev-acciones">
        {!revision.demo && (
          <Link className="boton" href={`/prevencion/${revision.id}/editar`}>
            <Pencil size={15} aria-hidden="true" />Editar
          </Link>
        )}
        {flujo.activo ? (
          <button type="button" onClick={detenerAnalisis}>
            <Square size={15} aria-hidden="true" />Detener análisis
          </button>
        ) : (
          <button type="button" className="primario" disabled={accion.pendiente} onClick={() => iniciarAnalisis(null)}>
            {yaAnalizadoAlguno ? <RefreshCw size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {yaAnalizadoAlguno ? "Reanalizar proveedores" : "Analizar proveedores"}
          </button>
        )}
      </div>}
    </header>

    <EstadoAccion accion={accion} />
    {errorFlujo && <Aviso tipo="error">
      {errorFlujo}{" "}
      <button type="button" className="enlace" onClick={recargar}>Recargar ficha</button>
    </Aviso>}

    <ConsolaAnalisis
      flujo={flujo}
      abierta={bitacoraAbierta}
      alternar={() => setBitacoraAbierta((v) => !v)}
      detener={detenerAnalisis}
    />

    <div className="prev-espacio">
      <aside className="prev-proveedores" aria-label="Proveedores registrados en la compra">
        <div className="prev-proveedores-cabecera">
          <h2>Proveedores registrados</h2>
          <span className="prev-contador">{compra.candidatos.length}</span>
        </div>

        <ul className="prev-proveedores-lista">
          {compra.candidatos.map((c) => {
            const seleccionado = ruc === c.ruc;
            const analizandoProv = flujo.activo && flujo.rucActivo === c.ruc;
            const hallazgosProv = hallazgosDe(c.ruc);
            const analizadoProv = estaAnalizado(c.ruc);
            return <li key={c.ruc} className={`prev-prov-fila ${seleccionado ? "seleccionado" : ""} ${analizandoProv ? "en-curso" : ""}`}>
              <button type="button" className="prev-prov-seleccion" aria-pressed={seleccionado}
                onClick={() => setSeleccion(c.ruc)}>
                <span className="prev-prov-icono" aria-hidden="true">
                  {analizandoProv ? <Loader2 size={17} className="prev-girar" /> : <Building2 size={17} />}
                </span>
                <span className="prev-prov-datos">
                  <strong>{c.nombre}</strong>
                  <small>
                    <code>{c.ruc}</code>
                    {c.importe ? ` · ${formatoImporte(c.importe, compra.moneda)}` : ""}
                  </small>
                  <span className="prev-prov-estado">
                    <EstadoSujeto
                      analizando={analizandoProv}
                      analizado={analizadoProv}
                      hallazgos={hallazgosProv}
                      resoluciones={revision.resoluciones}
                    />
                  </span>
                </span>
              </button>
              {abierta && (
                <button
                  type="button"
                  className="prev-prov-analizar"
                  disabled={flujo.activo || accion.pendiente}
                  title={`Analizar a ${c.nombre}`}
                  aria-label={`Analizar a ${c.nombre}`}
                  onClick={() => iniciarAnalisis(c.ruc)}
                >
                  {analizadoProv ? <RefreshCw size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
                  <span>Analizar</span>
                </button>
              )}
            </li>;
          })}
        </ul>

        <div className="prev-alcance-general">
          <button type="button" className={`prev-prov-seleccion prev-general-boton ${ruc === null ? "seleccionado" : ""}`}
            aria-pressed={ruc === null} onClick={() => setSeleccion(null)}>
            <span className="prev-prov-icono" aria-hidden="true">
              {flujo.activo && flujo.rucActivo === "__compra__"
                ? <Loader2 size={17} className="prev-girar" />
                : <Layers3 size={17} />}
            </span>
            <span className="prev-prov-datos">
              <strong>Alcance general de la compra</strong>
              <small>
                {compra.intervinientes.length} {compra.intervinientes.length === 1 ? "interviniente" : "intervinientes"} · órdenes y cotizaciones
              </small>
              <span className="prev-prov-estado">
                <EstadoSujeto
                  analizando={flujo.activo && flujo.rucActivo === "__compra__"}
                  analizado={estaAnalizado(null)}
                  hallazgos={hallazgosDe(null)}
                  resoluciones={revision.resoluciones}
                />
              </span>
            </span>
          </button>
        </div>
      </aside>

      <section className="prev-detalle" aria-label="Resultado del análisis seleccionado">
        <header className="prev-detalle-cabecera">
          <div className="prev-detalle-identidad">
            <h2>{candidato ? candidato.nombre : "Alcance general de la compra"}</h2>
            <p>
              {candidato ? (
                <>
                  <code>RUC {candidato.ruc}</code>
                  {candidato.proforma && <span> · {candidato.proforma}</span>}
                  {candidato.importe && <span> · Cotización {formatoImporte(candidato.importe, compra.moneda)}</span>}
                </>
              ) : (
                <>Cruce de órdenes previas, cotizaciones comparables e intervinientes designados.</>
              )}
            </p>
          </div>
          {abierta && candidato && (
            <button type="button" className="prev-boton-compacto" disabled={flujo.activo || accion.pendiente}
              onClick={() => iniciarAnalisis(candidato.ruc)}>
              {analizadoActual ? <RefreshCw size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
              {analizadoActual ? "Reanalizar proveedor" : "Analizar proveedor"}
            </button>
          )}
        </header>

        {!candidato && compra.intervinientes.length > 0 && (
          <div className="prev-intervinientes-tira">
            <span className="prev-intervinientes-etiqueta"><Users size={14} aria-hidden="true" />Intervinientes</span>
            <ul>
              {compra.intervinientes.map((p, idx) => (
                <li key={idx}><strong>{p.rol}:</strong> {p.designacion} <small>({p.referencia})</small></li>
              ))}
            </ul>
          </div>
        )}

        {!analizadoActual && !analizandoActual ? (
          <div className="prev-vacio prev-vacio-detalle">
            <FileSearch size={28} strokeWidth={1.6} aria-hidden="true" />
            <h3>Listo para analizar</h3>
            <p>
              {candidato
                ? `Inicia el análisis para contrastar a ${candidato.nombre} en SUNAT, RNP, sanciones TCP, penalidades y vínculos en tiempo real.`
                : "Ejecuta el análisis de la compra para contrastar órdenes previas similares y cotizaciones."}
            </p>
            {abierta && (
              <button type="button" className="primario" disabled={flujo.activo}
                onClick={() => iniciarAnalisis(candidato?.ruc ?? null)}>
                <Play size={15} aria-hidden="true" />
                {candidato ? "Analizar este proveedor" : "Analizar compra y proveedores"}
              </button>
            )}
          </div>
        ) : (
          <div className="prev-detalle-cuerpo">
            {verificacionesActuales.length > 0 && (
              <section className="prev-bloque" aria-label="Fuentes verificadas">
                <div className="prev-bloque-cabecera">
                  <h3>Verificación de fuentes</h3>
                  <small>{verificacionesActuales.length} {verificacionesActuales.length === 1 ? "fuente" : "fuentes"}</small>
                </div>
                <ul className="prev-fuentes-rejilla">
                  {verificacionesActuales.map((v) => (
                    <li key={v.fuente_id} className={`prev-fuente-celda estado-${v.estado}`}>
                      <span className="prev-fuente-celda-icono"><IconoPaso estado={v.estado} /></span>
                      <div>
                        <strong>{v.fuente}</strong>
                        <p>{v.mensaje}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="prev-bloque" aria-label="Hallazgos encontrados">
              <div className="prev-bloque-cabecera">
                <h3>Hallazgos ({hallazgosActuales.length})</h3>
                {candidato && abierta && hallazgosActuales.length > 0 && (
                  <button type="button" className="prev-texto-boton" disabled={accion.pendiente || flujo.activo}
                    onClick={() => ejecutar("investigaciones", { ruc: candidato.ruc, acto: null })}>
                    <FileSearch size={14} aria-hidden="true" />Contraste documental
                  </button>
                )}
              </div>

              {hallazgosActuales.length === 0 ? (
                <div className="prev-limpio">
                  <ShieldCheck size={22} aria-hidden="true" />
                  <div>
                    <strong>Sin hallazgos relevantes</strong>
                    <p>Las fuentes simuladas no reportan impedimentos ni alertas para este alcance.</p>
                  </div>
                </div>
              ) : (
                <div className="prev-hallazgos-lista">
                  {hallazgosActuales.map((h) => {
                    const resultado = revision.resoluciones[h.id];
                    const actos = [...new Set(h.evidencias.map((e) => e.acto).filter(Boolean))];
                    return <article className={`prev-hallazgo prioridad-${h.prioridad}`} key={h.id}>
                      <header className="prev-hallazgo-cabecera">
                        <div className="prev-hallazgo-etiquetas">
                          <span className="prev-prioridad">
                            <CircleAlert size={13} aria-hidden="true" />{PRIORIDADES[h.prioridad]}
                          </span>
                          <span className="prev-etiqueta">{h.frente}</span>
                          {h.simulado && <span className="prev-etiqueta">Simulado</span>}
                        </div>
                        <h4>{h.titulo}</h4>
                        <p>{h.detalle}</p>
                      </header>
                      <details className="prev-evidencia">
                        <summary>
                          <ChevronRight size={15} aria-hidden="true" />
                          Ver evidencia <span>{h.evidencias.length}</span>
                        </summary>
                        <Evidencias evidencias={h.evidencias} />
                      </details>
                      <Resultado resultado={resultado} />
                      {abierta && !flujo.activo && (
                        <footer className="prev-hallazgo-pie">
                          <button type="button" className="prev-boton-compacto"
                            onClick={() => setDialogo({ tipo: "hallazgos", item: h, anterior: resultado })}>
                            {resultado ? "Editar actuación" : "Registrar actuación"}
                          </button>
                          {ruc && actos.length === 1 && (
                            <button type="button" className="prev-texto-boton" disabled={accion.pendiente}
                              onClick={() => ejecutar("investigaciones", { ruc, acto: actos[0] })}>
                              <FileSearch size={14} aria-hidden="true" />Investigar {actos[0]}
                            </button>
                          )}
                        </footer>
                      )}
                    </article>;
                  })}
                </div>
              )}
            </section>

            {investigacionesActuales.length > 0 && (
              <details className="prev-bloque-plegable" open>
                <summary>
                  <FileSearch size={16} aria-hidden="true" />
                  <span>Contraste documental ({investigacionesActuales.length})</span>
                  <ChevronRight size={16} className="prev-plegable-flecha" aria-hidden="true" />
                </summary>
                <div className="prev-investigaciones-cuerpo">
                  {investigacionesActuales.map((inv) => (
                    <article className="prev-investigacion-item" key={`${inv.ruc}:${inv.acto}`}>
                      <header>
                        <strong>{inv.acto || "Consulta documental del proveedor"}</strong>
                        <small>
                          {inv.modo === "eve" ? "Borrador de eve"
                            : inv.modo === "ejemplo" ? "Ejemplo documental"
                            : inv.modo === "simulacion" ? "Simulación documental"
                            : "Búsqueda documental"}
                        </small>
                      </header>
                      {inv.afirmaciones.map((a, idx) => (
                        <div className="prev-cita" key={idx}>
                          <p>{a.afirmacion}</p>
                          <blockquote>{a.extracto}</blockquote>
                          <small>
                            <FuenteEnlace href={a.url}>{a.titulo}</FuenteEnlace> · Página {a.pagina}
                            {a.estado === "por_verificar" ? " · Por verificar" : " · Identidad corroborada"}
                          </small>
                        </div>
                      ))}
                      {inv.pendientes.length > 0 && (
                        <ul className="prev-pendientes-lista">
                          {inv.pendientes.map((p, idx) => <li key={idx}>{p}</li>)}
                        </ul>
                      )}
                    </article>
                  ))}
                </div>
              </details>
            )}

            <ComprobacionesCompactas revision={revision} ruc={ruc} dialogo={setDialogo} />
          </div>
        )}
      </section>
    </div>

    <footer className="prev-ficha-pie">
      <div className="prev-ficha-pie-estado">
        <strong>{abierta ? "Cierre de revisión" : "Revisión cerrada"}</strong>
        <p>
          {abierta
            ? `Comprobaciones obligatorias: ${comprobados}/${obligatorios.length} · Hallazgos por verificar pendientes: ${porVerificar}.`
            : revision.cierre?.nota}
        </p>
        <small>Versión {revision.version}</small>
      </div>
      {abierta && (
        <button type="button" disabled={flujo.activo || !revision.fuentes.length || comprobados < obligatorios.length || porVerificar > 0}
          onClick={() => setDialogo({ tipo: "cierre" })}>
          <Check size={16} aria-hidden="true" />Cerrar revisión
        </button>
      )}
    </footer>

    {dialogo && (
      <Actuacion
        datos={dialogo}
        cerrar={() => setDialogo(null)}
        ejecutar={ejecutar}
        accion={accionDialogo}
      />
    )}
  </div>;
}

export function FichaPrevencion({ id }) {
  const recurso = useDatos(`/prevencion/${id}`);
  const [cambio, setCambio] = useState(null);
  const revision = cambio?.id === recurso.datos?.id && cambio?.version >= recurso.datos?.version ? cambio : recurso.datos;
  if (!revision) return <><Volver to="/prevencion">Mis revisiones</Volver><Carga recurso={recurso} /></>;
  return <>
    {recurso.error && <Aviso tipo="error">{recurso.error}</Aviso>}
    <Ficha key={revision.id} revision={revision} actualizar={setCambio} recargar={recurso.recargar} />
  </>;
}
