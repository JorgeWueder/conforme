import { useEffect, useRef, useState } from "react";

export async function api(ruta, { method = "GET", data, signal } = {}) {
  const headers = {};
  let body = data;
  if (method !== "GET") headers["X-Conforme"] = "1";
  if (data !== undefined && !(data instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(data);
  }
  const respuesta = await fetch(`/api${ruta}`, { method, headers, body, signal });
  if (respuesta.status === 204) return null;
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    if (respuesta.status === 401 && ruta !== "/sesion") {
      window.dispatchEvent(new Event("sesion-vencida"));
    }
    const detalle = datos?.detail;
    const mensaje = typeof detalle === "string" ? detalle
      : respuesta.status === 422 ? "Revisa los campos del formulario."
      : "No se pudo completar la solicitud.";
    throw Object.assign(new Error(mensaje), { status: respuesta.status });
  }
  return datos;
}

export async function apiStream(ruta, { data, signal, onEvento } = {}) {
  const headers = { "X-Conforme": "1", "Content-Type": "application/json" };
  const respuesta = await fetch(`/api${ruta}`, {
    method: "POST",
    headers,
    body: JSON.stringify(data ?? {}),
    signal,
  });
  if (!respuesta.ok) {
    if (respuesta.status === 401 && ruta !== "/sesion") {
      window.dispatchEvent(new Event("sesion-vencida"));
    }
    const datos = await respuesta.json().catch(() => null);
    const detalle = datos?.detail;
    const mensaje = typeof detalle === "string" ? detalle
      : respuesta.status === 422 ? "Revisa los datos de la revisión."
      : "No se pudo iniciar el análisis.";
    throw Object.assign(new Error(mensaje), { status: respuesta.status });
  }
  if (!respuesta.body) {
    throw new Error("El navegador no permite lectura progresiva de la respuesta.");
  }
  const lector = respuesta.body.getReader();
  const decodificador = new TextDecoder("utf-8");
  let pendiente = "";
  try {
    while (true) {
      const { value, done } = await lector.read();
      if (done) break;
      pendiente += decodificador.decode(value, { stream: true });
      const lineas = pendiente.split("\n");
      pendiente = lineas.pop() ?? "";
      for (const linea of lineas) {
        const texto = linea.trim();
        if (!texto) continue;
        onEvento?.(JSON.parse(texto));
      }
    }
    const resto = (pendiente + decodificador.decode()).trim();
    if (resto) onEvento?.(JSON.parse(resto));
  } finally {
    lector.releaseLock();
  }
}

export function useDatos(ruta) {
  const [resultado, setResultado] = useState({});
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!ruta) return;
    const control = new AbortController();
    api(ruta, { signal: control.signal })
      .then((datos) => {
        if (!control.signal.aborted) setResultado({ ruta, version, datos });
      })
      .catch((error) => {
        if (!control.signal.aborted) setResultado({ ruta, version, error: error.message });
      });
    return () => control.abort();
  }, [ruta, version]);
  return {
    ...(resultado.ruta === ruta ? resultado : {}),
    pendiente: Boolean(ruta && (resultado.ruta !== ruta || resultado.version !== version)),
    recargar: () => setVersion((n) => n + 1),
  };
}

export function useAccion() {
  const [estado, setEstado] = useState({});
  const enCurso = useRef(false);
  async function ejecutar(accion) {
    if (enCurso.current) return;
    enCurso.current = true;
    setEstado({ pendiente: true });
    try {
      const aviso = await accion();
      setEstado({ aviso });
    } catch (error) {
      setEstado({ error: error.message });
    } finally {
      enCurso.current = false;
    }
  }
  return { ...estado, ejecutar, limpiar: () => setEstado({}) };
}
