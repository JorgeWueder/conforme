"use client";

import { useSesion } from "../sesion";
import { Aviso } from "../ui";

export function SoloAbastecimiento({ children }) {
  const { actor } = useSesion();
  return actor?.rol === "abastecimiento" ? children :
    <Aviso tipo="error">Esta página es para Abastecimiento.</Aviso>;
}
