import { cp } from "node:fs/promises";

await cp(new URL("./.next/static", import.meta.url),
         new URL("./.next/standalone/.next/static", import.meta.url), { recursive: true });
process.env.PORT ||= "8501";
process.env.HOSTNAME = process.env.CONFORME_HOST || "127.0.0.1";
await import("./.next/standalone/server.js");
