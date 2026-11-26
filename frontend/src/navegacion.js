"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const CLAVE_AVISO = "conforme:aviso";

export function useNavegar() {
  const router = useRouter();
  return (ruta, opciones) => {
    if (opciones?.state?.aviso) {
      sessionStorage.setItem(CLAVE_AVISO, JSON.stringify({ ruta, aviso: opciones.state.aviso }));
    }
    if (opciones?.replace) router.replace(ruta);
    else router.push(ruta);
  };
}

export function useAvisoNavegacion() {
  const ruta = usePathname();
  const [mensaje, setMensaje] = useState(null);
  useEffect(() => {
    const valor = JSON.parse(sessionStorage.getItem(CLAVE_AVISO) || "null");
    if (valor?.ruta !== ruta) return;
    setMensaje(valor);
    sessionStorage.removeItem(CLAVE_AVISO);
  }, [ruta]);
  return mensaje?.ruta === ruta ? mensaje.aviso : null;
}

export function useConsulta() {
  const consulta = useSearchParams();
  const cambiar = useCallback((valor, opciones) => {
    const actual = new URL(window.location.href);
    const params = typeof valor === "function" ? valor(actual.searchParams) : valor;
    actual.search = new URLSearchParams(params).toString();
    if (opciones?.replace) window.history.replaceState(null, "", actual);
    else window.history.pushState(null, "", actual);
  }, []);
  return [consulta, cambiar];
}
