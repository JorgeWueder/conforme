export const ROLES = {
  area_usuaria: "Área usuaria",
  tesoreria: "Tesorería",
  auditor: "Auditoría",
};
export const ESTADOS = {
  abierta: "Abierta",
  con_descargo: "Con descargo",
  escalada: "Escalada",
  cerrada: "Cerrada",
};
export const SEMAFOROS = { rojo: "Rojo", ambar: "Ámbar", verde: "Verde" };
export const SEVERIDADES = { alta: "Alta", media: "Media" };
export const REVISIONES = { descargo: "Descargo", cierre: "Cierre", escalamiento: "Escalamiento" };
export const ACCIONES = {
  "expediente.registrado": "Expediente registrado",
  "orden.emitida": "Orden emitida",
  "conformidad.registrada": "Conformidad registrada",
  "evidencia.adjuntada": "Evidencia adjuntada",
  "pago.registrado": "Pago registrado",
  "alerta.generada": "Alerta generada",
  "alerta.actualizada": "Alerta actualizada",
  "alerta.descargo": "Descargo presentado",
  "alerta.cerrada": "Alerta cerrada",
  "alerta.escalada": "Alerta escalada",
  "conformidad.sellada": "Conformidad sellada",
  "ia.propuesta": "Lectura con IA",
  "ia.aprobada": "Propuesta de IA aprobada",
  "ia.rechazada": "Propuesta de IA rechazada",
};
export const AVISO_ALERTAS = "Las alertas orientan la revisión. No bloquean pagos ni determinan responsabilidades.";

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
