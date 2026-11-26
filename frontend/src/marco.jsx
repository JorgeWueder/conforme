"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3, Bell, ClipboardCheck, Database, FileText, FlaskConical, FolderOpen,
  LogOut, Menu, Plus, QrCode, ScanSearch, ShieldCheck, X,
} from "lucide-react";
import { useState } from "react";
import { useAccion, useDatos } from "./api";
import { ROLES } from "./dominio";
import { EstadoAccion } from "./ui";
import { meToca } from "./auditoria";

export function Marca({ publica = false }) {
  return (
    <Link href="/" className={`marca ${publica ? "marca-publica" : ""}`}>
      <span className="marca-icono" aria-hidden="true"><ShieldCheck size={22} strokeWidth={1.8} /></span>
      <span className="marca-texto"><span className="marca-nombre">Conforme</span>
        {!publica && <span className="marca-subtitulo">Compras públicas</span>}
      </span>
    </Link>
  );
}

export function Marco({ actor, cerrarSesion, children }) {
  const ruta = usePathname();
  const accion = useAccion();
  const [menuEnRuta, setMenuEnRuta] = useState(null);
  const abierto = menuEnRuta === ruta;
  const rutaMenu = ruta.endsWith("/conformidad") ? "/conformidad" :
    ruta.endsWith("/tdr") ? "/lectura-ia" : ruta;
  const alertas = useDatos(actor && ruta ? `/alertas?panel=${encodeURIComponent(ruta)}` : null);
  const porAtender = alertas.datos?.alertas.filter((a) => a.tipo_prestacion === "servicio" && meToca(a, actor)).length ?? 0;
  const grupos = [
    ["Contratación", [
      ...(actor?.rol === "abastecimiento" ? [["/prevencion", "Revisión previa", ScanSearch]] : []),
      ["/expedientes", "Expedientes", FolderOpen],
      ...(actor?.rol === "area_usuaria" ? [
        ["/nuevo-expediente", "Registrar orden", Plus],
        ["/lectura-ia", "Revisar TDR", FileText],
        ["/conformidad", "Conformidades", ClipboardCheck],
      ] : []),
    ]],
    ["Seguimiento", [
      ["/indicadores", "Indicadores", BarChart3],
      ["/alertas", "Alertas", Bell],
      ...(actor?.rol === "auditor" ? [["/bitacora", "Bitácora", Database]] : []),
      ["/verificar", "Verificar sello", QrCode],
    ]],
  ];
  return (
    <div className={`marco ${actor ? "marco-privado" : "marco-publico"}`}>
      <a className="salto" href="#contenido">Saltar al contenido</a>
      {actor ? (
        <aside className={`lateral ${abierto ? "menu-abierto" : ""}`}>
          <div className="lateral-marca">
            <Marca />
            <button type="button" className="menu-movil" aria-controls="navegacion-conforme"
              aria-expanded={abierto} onClick={() => setMenuEnRuta(abierto ? null : ruta)}>
              {abierto ? <X size={20} /> : <Menu size={20} />} Menú
            </button>
          </div>
          <div className="lateral-interior" id="navegacion-conforme">
            <nav aria-label="Menú principal">
              {grupos.map(([grupo, enlaces]) => (
                <div key={grupo} className="menu-grupo" role="group" aria-label={grupo}>
                  <span className="menu-titulo" aria-hidden="true">{grupo}</span>
                  {enlaces.map(([destino, etiqueta, Icono]) => {
                    const activo = rutaMenu === destino || rutaMenu.startsWith(destino + "/");
                    return <Link key={destino} href={destino} className={activo ? "active" : ""}
                      aria-current={activo ? "page" : undefined} onClick={() => setMenuEnRuta(null)}>
                      <Icono size={18} strokeWidth={1.75} aria-hidden="true" />{etiqueta}
                      {destino === "/alertas" && porAtender > 0 &&
                        <span className="insignia" aria-label={`${porAtender} por atender`}>{porAtender}</span>}
                    </Link>;
                  })}
                </div>
              ))}
            </nav>
            <div className="perfil">
              <div className="perfil-identidad">
                <span className="perfil-inicial" aria-hidden="true">{actor.nombre.slice(0, 1)}</span>
                <span><strong>{actor.nombre}</strong><small>{ROLES[actor.rol]}</small></span>
              </div>
              <button className="boton-sesion" disabled={accion.pendiente}
                onClick={() => accion.ejecutar(cerrarSesion)}><LogOut size={17} />Cerrar sesión</button>
              <EstadoAccion accion={accion} />
            </div>
          </div>
        </aside>
      ) : (
        <header className="barra-publica">
          <div className="barra-publica-interior">
            <div className="barra-publica-identidad">
              <Marca publica /><span className="separador-institucional" aria-hidden="true" />
              <span className="institucion-nombre">Universidad Nacional de Trujillo</span>
            </div>
            <nav aria-label="Menú público"><Link href="/verificar">Verificar sello</Link><Link href="/login">Iniciar sesión</Link></nav>
          </div>
        </header>
      )}
      <div className="cuerpo">
        <header className="barra-institucional">
          <strong>Universidad Nacional de Trujillo</strong>
          <span className="marca-demo"><FlaskConical size={14} aria-hidden="true" /> Entorno de demostración</span>
        </header>
        <main className={`contenido ${actor ? "" : "contenido-publico"}`} id="contenido">{children}</main>
      </div>
    </div>
  );
}
