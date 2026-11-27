"use client";

import { Alertas, Bitacora } from "./auditoria";
import { Conformidad } from "./conformidad";
import { Detalle } from "./detalle";
import { Expedientes, NuevoRequerimiento } from "./expedientes";
import { Indicadores } from "./indicadores";
import { LecturaIA, RevisarTdr } from "./lectura";
import { useSesion } from "./sesion";
import { Aviso } from "./ui";

function Rol({ nombre, children }) {
  const { actor } = useSesion();
  return actor?.rol === nombre ? children : <Aviso tipo="error">Tu rol no permite acceder a esta página.</Aviso>;
}

export function VistaExpedientes() {
  return <Expedientes actor={useSesion().actor} />;
}

export function VistaDetalle() {
  return <Detalle actor={useSesion().actor} />;
}

export function VistaAlertas() {
  return <Alertas actor={useSesion().actor} />;
}

export function VistaIndicadores() {
  return <Indicadores />;
}

export function VistaConformidades() {
  const { actor } = useSesion();
  return <Rol nombre="area_usuaria"><Expedientes actor={actor} soloPendientes /></Rol>;
}

export function VistaConformidad() {
  return <Rol nombre="area_usuaria"><Conformidad /></Rol>;
}

export function VistaRequerimiento() {
  return <Rol nombre="area_usuaria"><NuevoRequerimiento /></Rol>;
}

export function VistaLectura() {
  return <Rol nombre="area_usuaria"><LecturaIA /></Rol>;
}

export function VistaTdr() {
  return <Rol nombre="area_usuaria"><RevisarTdr /></Rol>;
}

export function VistaBitacora() {
  return <Rol nombre="auditor"><Bitacora /></Rol>;
}
