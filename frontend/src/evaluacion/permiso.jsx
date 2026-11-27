"use client";

import { useSesion } from "../sesion";
import { Aviso } from "../ui";

const ROLES = ["abastecimiento", "tesoreria", "auditor"];

/** Abastecimiento evalúa; Tesorería y el OCI consultan en solo lectura. */
export function SoloEvaluacion({ children }) {
  const { actor } = useSesion();
  return ROLES.includes(actor?.rol) ? children :
    <Aviso tipo="error">Este módulo es de Abastecimiento, Tesorería y el OCI. Consulta el estado de tu requerimiento en el expediente.</Aviso>;
}
