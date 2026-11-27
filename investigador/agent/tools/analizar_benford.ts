import { defineTool } from "eve/tools";
import { z } from "zod";

const ESPERADO: Record<number, number> = {
  1: 0.30103,
  2: 0.17609,
  3: 0.12494,
  4: 0.09691,
  5: 0.07918,
  6: 0.06695,
  7: 0.05799,
  8: 0.05115,
  9: 0.04576,
};

function primerDigito(valor: number): number | null {
  const n = Math.abs(valor);
  if (!Number.isFinite(n) || n <= 0) return null;
  const texto = n.toExponential().replace(/^0+\.?/, "");
  const d = Number(texto[0]);
  return d >= 1 && d <= 9 ? d : null;
}

export default defineTool({
  description:
    "Calcula la distribución de primeros dígitos (Ley de Benford), la desviación media absoluta (MAD) y detecta dígitos sospechosos en una lista de montos o precios unitarios.",
  inputSchema: z.object({
    montos: z.array(z.number()).min(1).describe("Lista de montos positivos a analizar."),
    minimo_muestra: z.number().int().min(10).default(30).optional(),
  }),
  async execute({ montos, minimo_muestra = 30 }) {
    const validos = montos.filter((m) => Number.isFinite(m) && m > 0);
    const conteo: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0 };
    for (const m of validos) {
      const d = primerDigito(m);
      if (d) conteo[d] += 1;
    }
    const total = validos.length;
    const minimo = total ? Math.min(...validos) : 0;
    const maximo = total ? Math.max(...validos) : 0;
    const ordenes = minimo > 0 ? Math.log10(maximo / minimo) : 0;
    const muestra_suficiente = total >= minimo_muestra && ordenes >= 1;

    const distribucion = Array.from({ length: 9 }, (_, i) => {
      const digito = i + 1;
      const observado = total ? conteo[digito] / total : 0;
      const esperado = ESPERADO[digito];
      const diferencia = Number((observado - esperado).toFixed(4));
      return {
        digito,
        conteo: conteo[digito],
        observado: Number(observado.toFixed(4)),
        esperado: Number(esperado.toFixed(4)),
        diferencia,
      };
    });

    const mad = Number(
      (distribucion.reduce((s, x) => s + Math.abs(x.diferencia), 0) / 9).toFixed(4),
    );
    const nivel = !muestra_suficiente
      ? "insuficiente"
      : mad >= 0.015
        ? "alta"
        : mad >= 0.012
          ? "moderada"
          : "normal";
    const digitos_sospechosos = distribucion
      .filter((x) => Math.abs(x.diferencia) >= 0.05)
      .map((x) => x.digito);

    return {
      total_montos: total,
      muestra_suficiente,
      nivel_anomalia: nivel,
      mad,
      digitos_sospechosos,
      distribucion,
    };
  },
});
