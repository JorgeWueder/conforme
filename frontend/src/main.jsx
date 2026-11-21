import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate,
} from "react-router";
import {
  BadgeCheck, Bell, ClipboardCheck, Database, FlaskConical, FolderOpen, LogOut, Plus, QrCode, ShieldCheck, Sparkles,
} from "lucide-react";
import { api, useAccion, useDatos } from "./api";
import { ROLES } from "./dominio";
import { Aviso, Campo, Encabezado, EstadoAccion } from "./ui";
import { Expedientes, ElegirConformidad, NuevoExpediente } from "./expedientes";
import { Detalle } from "./detalle";
import { Conformidad } from "./conformidad";
import { Alertas, Bitacora } from "./auditoria";
import { LecturaIA } from "./lectura";
import { Verificar } from "./verificar";
import "./estilos.css";

function Marca() {
  return (
    <Link to="/" className="marca">
      <span className="marca-icono"><ShieldCheck size={24} /></span><span>Conforme</span>
    </Link>
  );
}

function Marco({ actor, cerrarSesion }) {
  const accion = useAccion();
  const enlaces = [
    ["/expedientes", "Expedientes", FolderOpen],
    ...(actor?.rol === "area_usuaria" ? [
      ["/nuevo-expediente", "Nuevo expediente", Plus],
      ["/lectura-ia", "Lectura con IA", Sparkles],
      ["/conformidad", "Registrar conformidad", ClipboardCheck],
    ] : []),
    ["/alertas", "Alertas", Bell],
    ...(actor?.rol === "auditor" ? [["/bitacora", "Bitácora", Database]] : []),
    ["/verificar", "Verificar sello", QrCode],
  ];
  return (
    <div className={`marco ${actor ? "marco-privado" : ""}`}>
      <a className="salto" href="#contenido">Saltar al contenido</a>
      {actor ? (
        <aside className="lateral">
          <Marca />
          <nav aria-label="Menú principal">
            {enlaces.map(([ruta, etiqueta, Icono]) => (
              <NavLink key={ruta} to={ruta}><Icono size={18} />{etiqueta}</NavLink>
            ))}
          </nav>
          <div className="perfil">
            <strong>{actor.nombre}</strong>
            <small>{ROLES[actor.rol]} · {actor.username}</small>
            <button className="boton-sesion" disabled={accion.pendiente}
              onClick={() => accion.ejecutar(cerrarSesion)}>
              <LogOut size={17} /> Cerrar sesión
            </button>
            <EstadoAccion accion={accion} />
          </div>
        </aside>
      ) : (
        <div className="barra-publica">
          <Marca />
          <nav aria-label="Menú público">
            <NavLink to="/verificar"><QrCode size={17} /> Verificar sello</NavLink>
            <NavLink to="/login">Ingresar</NavLink>
          </nav>
        </div>
      )}
      <div className="cuerpo">
        <div className="sinteticos">
          <FlaskConical size={16} aria-hidden="true" />
          <span><strong>Datos sintéticos</strong> · Demostración académica con datos y documentos ficticios.</span>
        </div>
        <main className="contenido" id="contenido"><Outlet /></main>
      </div>
    </div>
  );
}

function Login({ ingresar }) {
  const accion = useAccion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  function enviar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    accion.ejecutar(async () => {
      ingresar(await api("/sesion", { method: "POST", data: datos }));
      navegar(ubicacion.state?.volver ?? "/expedientes", { replace: true });
    });
  }
  return (
    <div className="login">
      <div className="login-contexto">
        <span className="login-icono"><BadgeCheck size={32} /></span>
        <Encabezado titulo="Conforme" descripcion="Alerta temprana y trazabilidad de la conformidad de bienes y servicios." />
      </div>
      <form className="panel formulario" onSubmit={enviar}>
        <h2>Ingresar</h2>
        <Campo titulo="Usuario"><input name="username" autoComplete="username" required placeholder="inf1, tes1 u oci1" /></Campo>
        <Campo titulo="Contraseña"><input name="password" type="password" autoComplete="current-password" required /></Campo>
        <EstadoAccion accion={accion} />
        <button className="primario" disabled={accion.pendiente}>{accion.pendiente ? "Ingresando…" : "Ingresar"}</button>
        <small>Usuarios de demostración: <b>inf1</b> (área usuaria), <b>tes1</b> (tesorería) y <b>oci1</b> (auditoría). La contraseña la entrega el equipo.</small>
      </form>
      <Link to="/verificar" className="volver"><QrCode size={18} />Verificar un sello sin ingresar</Link>
    </div>
  );
}

function Protegida({ actor, rol }) {
  const ubicacion = useLocation();
  if (!actor) {
    return <Navigate to="/login" replace state={{ volver: ubicacion.pathname + ubicacion.search }} />;
  }
  if (rol && actor.rol !== rol) return <Aviso tipo="error">Tu rol no permite acceder a esta página.</Aviso>;
  return <Outlet />;
}

function App() {
  const inicial = useDatos("/sesion");
  const [sesion, setSesion] = useState(undefined);
  const actor = sesion === undefined ? inicial.datos : sesion;
  const navegacion = useLocation();
  useEffect(() => {
    const vencer = () => setSesion(null);
    window.addEventListener("sesion-vencida", vencer);
    return () => window.removeEventListener("sesion-vencida", vencer);
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [navegacion.pathname]);

  async function cerrarSesion() {
    await api("/sesion", { method: "DELETE" });
    setSesion(null);
  }

  if (inicial.pendiente && sesion === undefined) {
    return <div className="inicio" role="status">Cargando Conforme…</div>;
  }
  return (
    <Routes>
      <Route element={<Marco actor={actor} cerrarSesion={cerrarSesion} />}>
        <Route index element={<Navigate to={actor ? "/expedientes" : "/login"} replace />} />
        <Route path="login" element={actor ? <Navigate to="/expedientes" replace /> : <Login ingresar={setSesion} />} />
        <Route path="verificar" element={<Verificar />} />
        <Route element={<Protegida actor={actor} />}>
          <Route path="expedientes" element={<Expedientes actor={actor} />} />
          <Route path="expedientes/:id" element={<Detalle actor={actor} />} />
          <Route path="alertas" element={<Alertas actor={actor} />} />
          <Route element={<Protegida actor={actor} rol="area_usuaria" />}>
            <Route path="nuevo-expediente" element={<NuevoExpediente />} />
            <Route path="lectura-ia" element={<LecturaIA />} />
            <Route path="conformidad" element={<ElegirConformidad />} />
            <Route path="expedientes/:id/conformidad" element={<Conformidad actor={actor} />} />
          </Route>
          <Route element={<Protegida actor={actor} rol="auditor" />}>
            <Route path="bitacora" element={<Bitacora />} />
          </Route>
        </Route>
        <Route path="*" element={<><Encabezado titulo="Página no encontrada" /><Link to="/">Volver al inicio</Link></>} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")).render(<StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>);
