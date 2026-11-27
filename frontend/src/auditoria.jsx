import { useEffect, useRef, useState } from "react";
import { ExternalLink, Search, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useConsulta } from "./navegacion";
import { api, useAccion, useDatos } from "./api";
import { ACCIONES, AVISO_ALERTAS, ESTADOS, REVISIONES, SEVERIDADES, alertaPendiente, fechaHora, nombreAlerta, rutaExpediente } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Indicador, ReferenciaRegla, Resumen, Tabla } from "./ui";

const DECISIONES_AUDITORIA = [
  "Recomendar abstención o rotación",
  "Derivar a PAD / Tribunal de Contrataciones / DGA",
  "Solicitar descargos o ampliar indagación",
  "Archivar con sustento",
];

function RevisionAlerta({ alerta, reglas, actor, recargar }) {
  const recurso = useDatos(`/alertas/${alerta.id}/revisiones`);
  const accion = useAccion();
  const implicado = alerta.persona_implicada_id === actor.persona_id;
  const puedeDescargar = implicado || alerta.conformante_id === actor.persona_id;
  const puedeRevisar = alerta.puede_revisar;
  const esAuditor = actor.rol === "auditor";

  function revisar(evento, tipo) {
    evento.preventDefault();
    const form = evento.currentTarget;
    const datos = new FormData(form);
    const decision = tipo ?? evento.nativeEvent.submitter?.value;
    const medida = datos.get("medida");
    const baseTexto = String(datos.get("texto") || "").trim();
    const texto = medida && decision !== "descargo" ? `[${medida}] ${baseTexto}` : baseTexto;
    accion.ejecutar(async () => {
      await api(`/alertas/${alerta.id}/revisiones`, { method: "POST", data: { accion: decision, texto } });
      form.reset();
      recurso.recargar();
      recargar();
      return { descargo: "Descargo registrado.", cierre: "Decisión registrada y alerta cerrada.", escalamiento: "Alerta escalada." }[decision];
    });
  }

  const origenTexto = alerta.regla?.startsWith("I")
    ? "Acción interna en evaluación"
    : alerta.regla?.startsWith("D")
      ? "Revisión forense documental"
      : alerta.regla?.startsWith("P")
        ? "Evaluación de proveedores (6 dim.)"
        : "Control automático del sistema";
  const tieneDecision = alerta.estado === "cerrada" || (recurso.datos?.length ?? 0) > 0;
  const pasos = [
    { n: "1", titulo: "Detectada automáticamente", detalle: origenTexto, tono: "verde" },
    { n: "2", titulo: "Escalada a Auditoría e Integridad", detalle: "Sin edición por Abastecimiento", tono: alerta.ambito === "seguimiento_oci" || alerta.estado === "escalada" || alerta.estado === "cerrada" ? "verde" : "ambar" },
    { n: "3", titulo: "Decisión registrada", detalle: alerta.estado === "cerrada" ? "Cerrada con sustento en bitácora" : tieneDecision ? "En seguimiento documentado" : "Pendiente de resolución", tono: alerta.estado === "cerrada" ? "verde" : tieneDecision ? "ambar" : "neutro" },
  ];

  const destinoAlerta = (alerta.regla?.startsWith("P") || alerta.regla?.startsWith("I"))
    ? [`/prevencion/${alerta.expediente_id}`, "Ver evaluación de proveedores"]
    : alerta.regla?.startsWith("D")
      ? [`/documentos/${alerta.expediente_id}`, "Ver revisión documental"]
      : [rutaExpediente(alerta.expediente_id), "Abrir expediente"];

  return (
    <section className="seccion">
      <div className="fila-titulo">
        <h2>{alerta.expediente} · {nombreAlerta(alerta, reglas)}</h2>
        <Link className="boton" href={destinoAlerta[0]}><ExternalLink size={16} /> {destinoAlerta[1]}</Link>
      </div>
      <div className="tarjetas" aria-label="Recorrido de la alerta">
        {pasos.map((p) => (
          <div key={p.n} className="panel ficha">
            <div className="acciones">
              <Indicador tono={p.tono}>Paso {p.n}</Indicador>
              <strong>{p.titulo}</strong>
            </div>
            <small>{p.detalle}</small>
          </div>
        ))}
      </div>
      <article className="panel ficha">
        <div className="acciones">
          {alerta.vigente !== false && <Indicador tono={alerta.severidad === "alta" ? "rojo" : "ambar"}>{SEVERIDADES[alerta.severidad]}</Indicador>}
          {alerta.bloqueante && alertaPendiente(alerta) && <Indicador tono="rojo">Bloqueante</Indicador>}
          <Indicador>{AMBITOS[alerta.ambito]}</Indicador>
          <Indicador>{alerta.vigente === false ? "Criterio anterior" : ESTADOS[alerta.estado]}</Indicador>
          <small>Creada el {fechaHora(alerta.creada_en)}</small>
        </div>
        <p>{alerta.explicacion}</p>
        {alerta.implicado && <small>Persona implicada: {alerta.implicado}</small>}
        <ReferenciaRegla alerta={alerta} />
      </article>
      <h3>Historial de la alerta</h3>
      {recurso.datos ? recurso.datos.length ? (
        <div className="tarjetas">{recurso.datos.map((r) => (
          <article className="panel ficha" key={r.id}>
            <h3>{REVISIONES[r.tipo]}</h3>
            <small>{fechaHora(r.creado_en)} · {r.autor}</small>
            <p>{r.texto}</p>
          </article>
        ))}</div>
      ) : <p className="vacio">Sin descargos ni revisiones.</p> : <Carga recurso={recurso} />}
      <EstadoAccion accion={accion} />
      {alertaPendiente(alerta) && <>
        {puedeDescargar && <form className="panel formulario" onSubmit={(e) => revisar(e, "descargo")}>
          <h3>Presentar descargo</h3>
          <Campo titulo="Explica lo ocurrido"><textarea name="texto" required /></Campo>
          <div><button className="primario" disabled={accion.pendiente}>Enviar descargo</button></div>
        </form>}
        {puedeRevisar && <form className="panel formulario" onSubmit={(e) => revisar(e)}>
            <h3>{esAuditor ? "Registrar decisión de Auditoría e Integridad" : (alerta.estado === "escalada" ? "Cerrar alerta" : "Cerrar o escalar")}</h3>
            {esAuditor && <Campo titulo="Decisión recomendada">
              <select name="medida" defaultValue={DECISIONES_AUDITORIA[0]}>
                {DECISIONES_AUDITORIA.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </Campo>}
            <Campo titulo="Sustento de la decisión (obligatorio)"
              ayuda={esAuditor ? "Queda sellado en la bitácora inmutable (SHA-256) junto al expediente." : (alerta.estado === "escalada" ? undefined : "Cierra si la alerta quedó aclarada; escala si necesita revisión de una instancia superior.")}>
              <textarea name="texto" required /></Campo>
            <div className="acciones">
              <button className="primario" name="accion" value="cierre" disabled={accion.pendiente}>
                {esAuditor ? "Registrar decisión y cerrar" : "Cerrar alerta"}
              </button>
              {alerta.estado !== "escalada" && <button name="accion" value="escalamiento" disabled={accion.pendiente}>
                {esAuditor ? "Mantener escalada / derivar" : "Escalar"}
              </button>}
            </div>
          </form>}
        {!puedeRevisar && !puedeDescargar && <small>La revisión corresponde a {RESPONSABLES[alerta.ambito]}. Si figuras en esta alerta, debe actuar otra persona.</small>}
      </>}
    </section>
  );
}

/** Alertas en las que la persona puede actuar ahora: descargo (área usuaria) o cierre/escalamiento. */
export function meToca(alerta, actor) {
  if (!alertaPendiente(alerta)) return false;
  const implicado = alerta.persona_implicada_id === actor.persona_id;
  const puedePresentarDescargo = alerta.estado === "abierta"
    && (implicado || alerta.conformante_id === actor.persona_id);
  return puedePresentarDescargo || alerta.puede_revisar;
}

const AMBITOS = { preventiva_dec: "Proveedores y documentos", operativa_tesoreria: "Ejecución y pago",
  seguimiento_oci: "Auditoría e Integridad" };
const RESPONSABLES = { operativa_tesoreria: "Tesorería", preventiva_dec: "otro especialista DEC",
  seguimiento_oci: "Auditoría e Integridad" };

const VISTAS_ALERTA = {
  atender: { titulo: "Por atender", filtro: meToca },
  abierta: { titulo: "Abiertas", filtro: (a) => a.estado === "abierta" && alertaPendiente(a) },
  con_descargo: { titulo: "Con descargo", filtro: (a) => a.estado === "con_descargo" && alertaPendiente(a) },
  escalada: { titulo: "Escaladas", filtro: (a) => a.estado === "escalada" && alertaPendiente(a) },
  cerrada: { titulo: "Cerradas", filtro: (a) => a.estado === "cerrada" && a.vigente !== false },
  todas: { titulo: "Todas", filtro: () => true },
};
const AYUDA_ATENDER = {
  area_usuaria: "Alertas abiertas donde puedes presentar descargo",
  tesoreria: "Alertas operativas que puedes revisar",
  abastecimiento: "Alertas preventivas que puedes revisar",
  auditor: "Alertas de seguimiento que puedes revisar",
};
const prioridad = (a, b) => (a.severidad === b.severidad ? 0 : a.severidad === "alta" ? -1 : 1)
  || String(b.creada_en).localeCompare(String(a.creada_en));

export function Alertas({ actor }) {
  const recurso = useDatos("/alertas");
  const [params, setParams] = useConsulta();
  const seleccion = params.get("alerta") ?? "";
  const filtro = params.get("ver");
  const vista = filtro === null ? "atender" : Object.hasOwn(VISTAS_ALERTA, filtro) ? filtro : null;
  const regla = params.get("regla") ?? "";
  const panel = useRef(null);
  function cambiar(clave, valor) {
    setParams((actuales) => {
      if (valor === null || valor === "") actuales.delete(clave);
      else actuales.set(clave, valor);
      return actuales;
    }, { replace: clave !== "alerta" });
  }
  useEffect(() => {
    if (seleccion && panel.current) panel.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [seleccion, recurso.datos]);
  if (!recurso.datos) return <><Encabezado titulo="Bandeja de alertas" descripcion={AVISO_ALERTAS} /><Carga recurso={recurso} /></>;
  const { alertas, reglas } = recurso.datos;
  const opciones = Object.fromEntries(Object.entries(reglas).map(([clave, nombre]) => [clave, `${clave} · ${nombre}`]));
  const elegida = alertas.find((a) => String(a.id) === seleccion);
  const tipo = params.get("tipo") ?? "todos";
  const ambitoParam = params.get("ambito");
  const ambito = ambitoParam !== null ? ambitoParam : (actor.rol === "auditor" ? "seguimiento_oci" : (actor.rol === "abastecimiento" ? "preventiva_dec" : ""));
  const delTipo = alertas.filter((a) => (tipo === "todos" || a.tipo_prestacion === tipo)
    && (!ambito || a.ambito === ambito));
  const vistaEfectiva = vista === "atender" && actor.rol === "abastecimiento"
    && delTipo.filter((a) => meToca(a, actor)).length === 0
    && delTipo.some((a) => a.estado === "abierta" && alertaPendiente(a))
    ? "abierta" : vista;
  const filas = delTipo
    .filter((a) => (!vistaEfectiva || VISTAS_ALERTA[vistaEfectiva].filtro(a, actor)) && (!regla || a.regla === regla))
    .sort(prioridad);
  const columnas = [
    { titulo: "N.º", valor: (a) => a.id, render: (a) => <Link href={`?${new URLSearchParams({ ...Object.fromEntries(params), alerta: a.id })}`}>{a.id}</Link> },
    { titulo: "Severidad", valor: (a) => a.severidad, render: (a) => a.vigente === false ? "—"
      : <Indicador tono={a.severidad === "alta" ? "rojo" : "ambar"}>{SEVERIDADES[a.severidad]}</Indicador> },
    { titulo: "Señal detectada", valor: (a) => nombreAlerta(a, reglas), clase: "celda-texto" },
    { titulo: "Ámbito", valor: (a) => AMBITOS[a.ambito] },
    { titulo: "Efecto", valor: (a) => a.bloqueante && alertaPendiente(a) ? "Bloquea" : "Revisión",
      render: (a) => a.bloqueante && alertaPendiente(a)
        ? <Indicador tono="rojo">Bloquea</Indicador>
        : <span className="secundario">Revisión</span> },
    { titulo: "Expediente", valor: (a) => a.expediente },
    ...(actor.rol === "area_usuaria" ? [] : [{ titulo: "Área", valor: (a) => a.area_sigla }]),
    { titulo: "Estado", valor: (a) => a.vigente === false ? "Criterio anterior" : ESTADOS[a.estado] },
    { titulo: "Persona implicada", valor: (a) => a.implicado, clase: "celda-texto" },
    { titulo: "Creada", valor: (a) => a.creada_en, render: (a) => fechaHora(a.creada_en) },
  ];
  return (
    <>
      <Encabezado titulo="Bandeja de alertas" descripcion={AVISO_ALERTAS} />
      <Resumen activo={vistaEfectiva} onChange={(clave) => cambiar("ver", clave ?? "todas")}
        opciones={Object.entries(VISTAS_ALERTA).map(([clave, { titulo, filtro }]) => ({
          clave, titulo, valor: delTipo.filter((a) => filtro(a, actor)).length,
          tono: clave === "atender" ? "ambar" : "neutro", ayuda: clave === "atender" ? AYUDA_ATENDER[actor.rol] : undefined,
        }))} />
      <div className="barra-filtros">
        <Campo titulo="Tipo de prestación"><select value={tipo} onChange={(e) => cambiar("tipo", e.target.value)}>
          <option value="todos">Todos</option>
          <option value="servicio">Servicios</option><option value="bien">Bienes</option>
        </select></Campo>
        <Campo titulo="Ámbito"><select value={ambito} onChange={(e) => cambiar("ambito", e.target.value)}>
          <option value="">Todos los ámbitos</option>
          {Object.entries(AMBITOS).map(([clave, nombre]) => <option key={clave} value={clave}>{nombre}</option>)}
        </select></Campo>
        <Campo titulo="Regla"><select value={regla} onChange={(e) => cambiar("regla", e.target.value)}>
          <option value="">Todas las reglas</option>
          {Object.entries(opciones).map(([clave, nombre]) => <option key={clave} value={clave}>{nombre}</option>)}
        </select></Campo>
      </div>
      {seleccion && !elegida && <Aviso tipo="error">La alerta no existe o está fuera de tu alcance.</Aviso>}
      {elegida && <div ref={panel} className="panel-revision">
        <div className="fila-titulo">
          <span className="secundario">Alerta N.º {elegida.id}</span>
          <button type="button" onClick={() => cambiar("alerta", null)}><X size={16} /> Cerrar panel</button>
        </div>
        <RevisionAlerta key={elegida.id} alerta={elegida} reglas={reglas} actor={actor} recargar={recurso.recargar} />
      </div>}
      <p className="secundario">
        {filas.length} {filas.length === 1 ? "alerta" : "alertas"}{vista ? ` · ${VISTAS_ALERTA[vista].titulo.toLowerCase()}` : " en total"}.
      </p>
      <Tabla columnas={columnas} filas={filas} etiqueta="Bandeja de alertas" elegida={elegida?.id}
        alElegir={(fila) => cambiar("alerta", String(fila.id))}
        vacio={vista === "atender" ? "No tienes alertas pendientes de atender." : "No hay alertas con estos filtros."} />
    </>
  );
}

const huella = (texto) => texto && <code title={texto}>{texto.slice(0, 12)}…</code>;
const columnasBitacora = [
  { titulo: "N.º", valor: (f) => f.id },
  { titulo: "Fecha", valor: (f) => f.ts, render: (f) => fechaHora(f.ts) },
  { titulo: "Quién", valor: (f) => f.actor ?? "Sistema", clase: "celda-texto" },
  { titulo: "Acción", valor: (f) => ACCIONES[f.accion] ?? f.accion },
  { titulo: "Expediente", valor: (f) => f.expediente,
    render: (f) => f.expediente_id ? <Link href={rutaExpediente(f.expediente_id)}>{f.expediente}</Link> : "—" },
  { titulo: "Documento", valor: (f) => f.documento_sha256, render: (f) => huella(f.documento_sha256) ?? "—" },
  { titulo: "Huella (anterior → propia)", valor: (f) => f.hash,
    render: (f) => <span className="cadena">{huella(f.hash_anterior) ?? "inicio"} → {huella(f.hash)}</span> },
];
const textoBitacora = (f) => [f.id, f.actor ?? "Sistema", ACCIONES[f.accion] ?? f.accion, f.expediente].join(" ").toLowerCase();

export function Bitacora() {
  const recurso = useDatos("/bitacora");
  const accion = useAccion();
  const [integridad, setIntegridad] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const filas = recurso.datos?.filter((f) => textoBitacora(f).includes(busqueda.trim().toLowerCase()));
  function verificar() {
    setIntegridad(null);
    accion.ejecutar(async () => setIntegridad(await api("/bitacora/integridad")));
  }
  return (
    <>
      <Encabezado titulo="Bitácora" descripcion="Registro de actuaciones y verificación de integridad."
        acciones={<button className="primario" onClick={verificar} disabled={accion.pendiente}><ShieldCheck size={17} />
          {accion.pendiente ? "Verificando…" : "Verificar integridad"}</button>} />
      <EstadoAccion accion={accion} />
      {integridad && (integridad.integra
        ? <Aviso tipo="exito">Cadena íntegra. Registros verificados: {integridad.total}.</Aviso>
        : <Aviso tipo="error">Cadena alterada en el registro n.º {integridad.id_roto} de {integridad.total}. {integridad.motivo}</Aviso>)}
      {filas ? <>
        <div className="barra-filtros">
          <Campo titulo="Buscar" icono={<Search size={18} aria-hidden="true" />}>
            <input type="search" placeholder="Expediente, persona, acción o n.º" value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)} />
          </Campo>
        </div>
        <p className="secundario">{busqueda ? `${filas.length} de los últimos` : "Últimos"} {recurso.datos.length} registros.
          {" "}Pasa el cursor sobre una huella para verla completa.</p>
        <Tabla columnas={columnasBitacora} filas={filas} etiqueta="Registros de bitácora"
          vacio="Ningún registro coincide con la búsqueda." />
      </> : <Carga recurso={recurso} />}
    </>
  );
}
