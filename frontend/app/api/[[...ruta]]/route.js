/** Reenvía el contrato de FastAPI desde el mismo origen, incluidos adjuntos en flujo. */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CABECERAS_CONEXION = [
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "proxy-connection", "te", "trailer", "transfer-encoding", "upgrade",
];

function sinCabecerasDeConexion(originales) {
  const cabeceras = new Headers(originales);
  for (const clave of (cabeceras.get("connection") || "").split(",")) {
    if (clave.trim()) cabeceras.delete(clave.trim());
  }
  for (const clave of CABECERAS_CONEXION) cabeceras.delete(clave);
  return cabeceras;
}

async function reenviar(solicitud) {
  const entrada = new URL(solicitud.url);
  const destino = new URL(process.env.CONFORME_API_URL || "http://127.0.0.1:8000");
  destino.pathname = entrada.pathname;
  destino.search = entrada.search;

  const cabeceras = sinCabecerasDeConexion(solicitud.headers);
  cabeceras.delete("host");
  cabeceras.set("accept-encoding", "identity");
  cabeceras.set("x-forwarded-host", solicitud.headers.get("host") || entrada.host);
  const https = entrada.protocol === "https:" || cabeceras.get("x-forwarded-proto") === "https";
  cabeceras.set("x-forwarded-proto", https ? "https" : "http");

  try {
    const respuesta = await fetch(destino, {
      method: solicitud.method,
      headers: cabeceras,
      body: solicitud.body,
      duplex: "half",
      cache: "no-store",
      redirect: "manual",
      signal: solicitud.signal,
    });
    const salida = sinCabecerasDeConexion(respuesta.headers);
    if (salida.has("content-encoding")) {
      salida.delete("content-encoding");
      salida.delete("content-length");
    }
    const cookies = respuesta.headers.getSetCookie();
    if (cookies.length) {
      salida.delete("set-cookie");
      for (const cookie of cookies) salida.append("set-cookie", cookie);
    }
    return new Response(respuesta.body, { status: respuesta.status, headers: salida });
  } catch (error) {
    if (!solicitud.signal.aborted) console.error("Error al conectar con FastAPI", error);
    return Response.json({ detail: "La API de Conforme no está disponible." }, { status: 502 });
  }
}

export {
  reenviar as GET, reenviar as HEAD, reenviar as POST, reenviar as PUT,
  reenviar as PATCH, reenviar as DELETE, reenviar as OPTIONS,
};
