"use client";

import { createContext, useContext, useEffect, useState, useSyncExternalStore } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api, useDatos } from "./api";
import { Login } from "./login";
import { Marco } from "./marco";

const ContextoSesion = createContext(null);
const suscribirHidratacion = () => () => {};
const enNavegador = () => true;
const enServidor = () => false;

function useHidratado() {
  return useSyncExternalStore(suscribirHidratacion, enNavegador, enServidor);
}
const inicioDe = (actor) => actor?.rol === "abastecimiento" ? "/prevencion" : "/expedientes";

function rutaInterna(valor) {
  if (!valor?.startsWith("/")) return null;
  const base = "https://conforme.invalid";
  try {
    const url = new URL(valor, base);
    if (url.origin !== base || url.pathname.startsWith("/login")) return null;
    return url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

export function SesionProvider({ children }) {
  const inicial = useDatos("/sesion");
  const [sesion, setSesion] = useState(undefined);
  const [vencida, setVencida] = useState(false);
  const actor = sesion === undefined ? inicial.datos : sesion;
  useEffect(() => {
    function vencer() {
      setSesion(null);
      setVencida(true);
    }
    window.addEventListener("sesion-vencida", vencer);
    return () => window.removeEventListener("sesion-vencida", vencer);
  }, []);

  function ingresar(persona) {
    setVencida(false);
    setSesion(persona);
  }

  async function cerrarSesion() {
    await api("/sesion", { method: "DELETE" });
    setSesion(null);
  }

  return <ContextoSesion.Provider value={{
    actor, pendiente: inicial.pendiente && sesion === undefined, vencida, ingresar, cerrarSesion,
  }}>{children}</ContextoSesion.Provider>;
}

export function useSesion() {
  return useContext(ContextoSesion);
}

export function PantallaLogin() {
  const hidratado = useHidratado();
  const router = useRouter();
  const params = useSearchParams();
  const { actor, pendiente, vencida, ingresar } = useSesion();
  const volver = rutaInterna(params.get("volver"));
  const ruta = volver || inicioDe(actor);

  useEffect(() => {
    if (hidratado && actor) router.replace(ruta);
  }, [hidratado, actor, router, ruta]);
  if (!hidratado || pendiente || actor) return <InicioCargando />;
  return <Login ingresar={ingresar} vencida={vencida} />;
}

export function InicioCargando() {
  return <div className="inicio" role="status">Cargando Conforme…</div>;
}

export function Pantalla({ children, publica = false }) {
  const hidratado = useHidratado();
  const { actor, pendiente, cerrarSesion } = useSesion();
  const router = useRouter();
  const ruta = usePathname();
  useEffect(() => {
    if (hidratado && !publica && !pendiente && !actor) {
      router.replace("/login?" + new URLSearchParams({ volver: ruta + window.location.search }));
    }
  }, [hidratado, publica, pendiente, actor, router, ruta]);
  if (!hidratado || pendiente || (!publica && !actor)) return <InicioCargando />;
  return <Marco actor={actor} cerrarSesion={cerrarSesion}>{children}</Marco>;
}
