import { defineTool } from "eve/tools";
import { z } from "zod";

const MARCAS = /\b(hp|dell|lenovo|apple|cisco|mikrotik|epson|canon|sony|samsung|siemens|bosch|3m|adobe|microsoft|oracle|sap)\b/gi;
const EQUIVALENTE = /\b(o\s+equivalente|equivalente\s+o\s+superior|similar\s+o\s+superior)\b/i;
const VAGOS = [
  { patron: /a\s+entera\s+satisfacci[oó]n/i, detalle: "Criterio subjetivo («a entera satisfacción») sin parámetro verificable." },
  { patron: /seg[uú]n\s+coordinaci[oó]n\s+con\s+el\s+[aá]rea/i, detalle: "Alcance indefinido («según coordinación con el área») que dificulta verificar entregas." },
  { patron: /informe\s+general\s+del\s+servicio/i, detalle: "Entregable genérico («informe general») sin evidencia mínima exigida." },
];

export default defineTool({
  description:
    "Analiza texto de Términos de Referencia (TDR) con reglas deterministas para detectar posibles señales de direccionamiento: marcas sin «o equivalente», plazos irreales o entregables vagos.",
  inputSchema: z.object({
    texto_tdr: z.string().min(10).describe("Texto extraído del TDR."),
    plazo_dias: z.number().int().positive().optional().describe("Plazo de ejecución en días calendario."),
  }),
  async execute({ texto_tdr, plazo_dias }) {
    const senales: Array<{ tipo: string; severidad: "bloqueante" | "advertencia"; detalle: string }> = [];

    const marcasEncontradas = [...new Set((texto_tdr.match(MARCAS) || []).map((m) => m.toUpperCase()))];
    if (marcasEncontradas.length > 0 && !EQUIVALENTE.test(texto_tdr)) {
      senales.push({
        tipo: "marca_sin_equivalente",
        severidad: "bloqueante",
        detalle: `Menciona marca(s) específica(s) (${marcasEncontradas.join(", ")}) sin incluir la cláusula «o equivalente».`,
      });
    }

    if (plazo_dias !== undefined && plazo_dias <= 3) {
      senales.push({
        tipo: "plazo_irreal",
        severidad: "advertencia",
        detalle: `El plazo de ${plazo_dias} día(s) calendario es muy corto y puede restringir la competencia a un proveedor previamente avisado.`,
      });
    }

    for (const regla of VAGOS) {
      if (regla.patron.test(texto_tdr)) {
        senales.push({
          tipo: "entregable_vago",
          severidad: "advertencia",
          detalle: regla.detalle,
        });
      }
    }

    return {
      total_senales: senales.length,
      tiene_bloqueantes: senales.some((s) => s.severidad === "bloqueante"),
      senales,
    };
  },
});
