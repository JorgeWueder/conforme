export const ROLES = {
  area_usuaria: "Área usuaria",
  tesoreria: "Tesorería",
  auditor: "Órgano de Control Institucional",
  abastecimiento: "Abastecimiento (DEC)",
};
export const ESTADOS = {
  abierta: "Abierta",
  con_descargo: "Con descargo",
  escalada: "Escalada",
  cerrada: "Cerrada",
};
export const SEMAFOROS = { rojo: "Alerta alta", ambar: "Alerta media", verde: "Sin alertas abiertas" };
export const SEVERIDADES = { alta: "Alta", media: "Media" };
export const REVISIONES = { descargo: "Descargo", cierre: "Cierre", escalamiento: "Escalamiento" };
export const ACCIONES = {
  "expediente.registrado": "Expediente registrado",
  "orden.emitida": "Orden emitida",
  "entregable.observado": "Observación registrada",
  "entregable.subsanado": "Subsanación verificada",
  "observacion.comunicada": "Observación comunicada al proveedor",
  "conformidad.revisada": "Conformidad revisada por Abastecimiento",
  "conformidad.devuelta": "Conformidad devuelta por Abastecimiento",
  "conformidad.registrada": "Conformidad registrada",
  "evidencia.adjuntada": "Evidencia adjuntada",
  "pago.registrado": "Pago registrado",
  "alerta.generada": "Alerta generada",
  "alerta.actualizada": "Alerta actualizada",
  "alerta.descargo": "Descargo presentado",
  "alerta.cerrada": "Alerta cerrada",
  "alerta.escalada": "Alerta escalada",
  "conformidad.sellada": "Conformidad sellada",
  "ia.propuesta": "TDR leído",
  "ia.aprobada": "Propuesta de entregables aprobada",
  "ia.rechazada": "Propuesta de entregables rechazada",
};
export const AVISO_ALERTAS = "Señales para revisión antes del pago.";

const REGLAMENTO = "https://cdn.www.gob.pe/uploads/document/file/9295551/6444155-ref-reglamento-de-la-ley-de-contrataciones-del-estado-con-modificaciones-posteriores-hasta-08-ene-2026-2-v2.pdf?v=1768513235";
const LEY_CONTRATACIONES = "https://www.congreso.gob.pe/Docs/DGP/DIDP/files/ley_32069.pdf";
export const REFERENCIAS_REGLAS = {
  R1: ["Reglamento de la Ley N.º 32069, art. 144", REGLAMENTO],
  R2: ["Reglamento de la Ley N.º 32069, arts. 119, 120 y 229", REGLAMENTO],
  R3: ["Reglamento de la Ley N.º 32069, art. 144.3", REGLAMENTO],
  R4: ["Normas de Control Interno, numeral 3.2", "https://apps.contraloria.gob.pe/wcm/control_interno/documentos/normativa/RC_320-2006-CG.pdf"],
  R5: ["Ley N.º 32069, art. 67", LEY_CONTRATACIONES],
};

export const alertaPendiente = (a) => a.vigente !== false && a.estado !== "cerrada";
export const nombreAlerta = (a, reglas) => a.vigente === false
  ? "Solicitante y conformante son la misma persona"
  : reglas[a.regla];

const formatoSoles = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const formatoFechaHora = new Intl.DateTimeFormat("es-PE", {
  timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const formatoHoy = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
});

export const soles = (valor) => `S/ ${formatoSoles.format(valor)}`;
export const fecha = (valor) => valor ? valor.split("-").reverse().join("/") : "—";
export const fechaHora = (valor) => valor ? formatoFechaHora.format(new Date(valor)) : "—";
export const hoy = () => formatoHoy.format(new Date());
export const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);
export const rutaExpediente = (id) => `/expedientes/${id}`;
export const rutaAlerta = (id) => `/alertas?alerta=${id}`;

export function estadoEntregable(item) {
  if (item.cumplido == null) return ["Sin conformidad", "neutro"];
  if (!item.cumplido) return ["No cumplido", "rojo"];
  if (!item.evidencias.length) return ["Cumplido · sin evidencia", "ambar"];
  return ["Cumplido · con evidencia", "verde"];
}

export function observacionesDeEntrega(eventos) {
  const subsanaciones = new Map(eventos.filter((e) => e.accion === "entregable.subsanado")
    .map((e) => [e.detalle.observacion_id, e]));
  const comunicaciones = new Map(eventos.filter((e) => e.accion === "observacion.comunicada")
    .map((e) => [e.detalle.observacion_id, e]));
  return new Map(eventos.filter((e) => e.accion === "entregable.observado")
    .map((e) => [e.detalle.entregable_id, {
      ...e, subsanacion: subsanaciones.get(e.id), comunicacion: comunicaciones.get(e.id),
    }]));
}
