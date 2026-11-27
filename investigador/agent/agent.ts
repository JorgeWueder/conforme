import { defineAgent } from "eve";
import { chatgpt, openai } from "eve/models/openai";
import { anthropic } from "eve/models/anthropic";

const modelo = process.env.CONFORME_EVE_MODELO;
function resolverModelo() {
  if (modelo === "chatgpt" || modelo?.startsWith("chatgpt/")) {
    return chatgpt(modelo?.split("/")[1]);
  }
  if (process.env.OPENAI_API_KEY && (!modelo || modelo.startsWith("openai/"))) {
    return openai(modelo?.split("/")[1] || "gpt-5-mini");
  }
  if (process.env.ANTHROPIC_API_KEY && (!modelo || modelo.startsWith("anthropic/"))) {
    return modelo ? anthropic(modelo.split("/")[1]) : anthropic();
  }
  return modelo || chatgpt();
}

export default defineAgent({
  description: "Analiza proveedores, revisa TDR y documentación forense (Benford) y contrasta evidencias de conformidad.",
  defaultTools: false,
  model: resolverModelo(),
});
