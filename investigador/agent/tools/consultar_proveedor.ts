import { defineTool } from "eve/tools";
import { z } from "zod";

const REGISTRO_SIMULADO: Record<string, object> = {
  "20601122333": {
    razon_social: "TECNOLAB SERVICIOS INTEGRALES S.A.C.",
    estado: "ACTIVO",
    condicion: "HABIDO",
    inicio_actividades: "2014-03-10",
    ciiu: "3312",
    actividad: "Reparación y mantenimiento de maquinaria y equipo",
    domicilio: "Av. América Sur 1450, Trujillo",
    trabajadores: 18,
    sanciones: [],
    vinculados: [
      { nombre: "Carlos Augusto Ríos Benites", rol: "representante_legal" },
      { nombre: "Lucía Fernanda Ríos Benites", rol: "socio" },
    ],
  },
  "20614988771": {
    razon_social: "INVERSIONES KALLPA ANDINA E.I.R.L.",
    estado: "ACTIVO",
    condicion: "HABIDO",
    inicio_actividades: "2026-07-02",
    ciiu: "4690",
    actividad: "Venta al por mayor no especializada",
    domicilio: "Jr. Bolívar 812, Of. 3, Trujillo",
    trabajadores: 1,
    sanciones: [],
    vinculados: [
      { nombre: "Rosa Elena Paredes Gil", rol: "socio" },
      { nombre: "Jorge Luis Paredes Vela", rol: "representante_legal" },
    ],
  },
  "20605544119": {
    razon_social: "GRUPO SERVIMAX DEL NORTE S.A.C.",
    estado: "ACTIVO",
    condicion: "HABIDO",
    inicio_actividades: "2019-11-15",
    ciiu: "3312",
    actividad: "Reparación y mantenimiento de maquinaria y equipo",
    domicilio: "Jr. Bolívar 812, Of. 5, Trujillo",
    trabajadores: 6,
    sanciones: [
      {
        tipo: "inhabilitacion",
        resolucion: "Res. N.º 0412-2026-TCP-S2 (simulada)",
        desde: "2026-05-20",
        hasta: "2027-05-19",
        motivo: "Presentó documentación falsa en un procedimiento anterior",
      },
    ],
    vinculados: [
      { nombre: "Jorge Luis Paredes Vela", rol: "apoderado" },
      { nombre: "Mario César Gutiérrez Lau", rol: "representante_legal" },
    ],
  },
};

export default defineTool({
  description:
    "Consulta el adaptador de fuentes públicas (modo simulado) por RUC para obtener padrón SUNAT, sanciones vigentes y personas vinculadas (representantes, socios, apoderados).",
  inputSchema: z.object({
    ruc: z.string().regex(/^\d{11}$/).describe("RUC de 11 dígitos del proveedor."),
  }),
  async execute({ ruc }) {
    const ficha = REGISTRO_SIMULADO[ruc];
    if (ficha) {
      return { encontrado: true, modo: "simulado", ruc, ...ficha };
    }
    return {
      encontrado: false,
      modo: "simulado",
      ruc,
      estado: "ACTIVO",
      condicion: "HABIDO",
      sanciones: [],
      vinculados: [],
      nota: "Sin observaciones registradas en el padrón simulado.",
    };
  },
});
