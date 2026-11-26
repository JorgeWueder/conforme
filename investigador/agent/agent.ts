import { defineAgent } from "eve";
import { openai } from "eve/models/openai";
import { anthropic } from "eve/models/anthropic";

const modelo = process.env.CONFORME_EVE_MODELO;
function resolverModelo() {
  if (process.env.OPENAI_API_KEY && (!modelo || modelo.startsWith("openai/"))) {
    return openai(modelo?.split("/")[1] || "gpt-5-mini");
  }
  if (process.env.ANTHROPIC_API_KEY && (!modelo || modelo.startsWith("anthropic/"))) {
    return modelo ? anthropic(modelo.split("/")[1]) : anthropic();
  }
  return modelo || "openai/gpt-5-mini";
}

export default defineAgent({
  description: "Contrasta evidencia oficial y cita las páginas que sustentan cada hallazgo.",
  defaultTools: false,
  tool: false,
  model: resolverModelo(),
});
