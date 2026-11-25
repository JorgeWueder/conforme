import { StrictMode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate,
} from "react-router";
import {
  Bell, ClipboardCheck, Database, Eye, EyeOff, FileText, FlaskConical,
  FolderOpen, LogOut, Plus, QrCode, ShieldCheck,
} from "lucide-react";
import { api, useAccion, useDatos } from "./api";
import { ROLES } from "./dominio";
import { Aviso, Encabezado, EstadoAccion } from "./ui";
import { Expedientes, NuevoExpediente } from "./expedientes";
import { Detalle } from "./detalle";
import { Conformidad } from "./conformidad";
import { Alertas, Bitacora, meToca } from "./auditoria";
import { LecturaIA, RevisarTdr } from "./lectura";
import { Verificar } from "./verificar";
import "./estilos.css";

const ROLES_DEMO = [
  { usuario: "inf1", rol: "Área usuaria" },
  { usuario: "tes1", rol: "Tesorería" },
  { usuario: "oci1", rol: "OCI" },
];

function Marca({ publica = false }) {
  return (
    <Link to="/" className={`marca ${publica ? "marca-publica" : ""}`}>
      <span className="marca-icono" aria-hidden="true"><ShieldCheck size={20} /></span>
      <span className="marca-texto">
        <span className="marca-nombre">Conforme</span>
        {!publica && <span className="marca-subtitulo">Conformidad de servicios</span>}
      </span>
    </Link>
  );
}

/** Cuántas alertas esperan una acción de la persona; se actualiza al cambiar de página. */
function usePorAtender(actor) {
  const { pathname } = useLocation();
  const recurso = useDatos(actor ? "/alertas" : null);
  const { recargar } = recurso;
  useEffect(() => {
    if (actor) recargar();
  }, [pathname]); // Solo al navegar: recargar cambia en cada render.
  return recurso.datos?.alertas.filter((alerta) => alerta.tipo_prestacion === "servicio" && meToca(alerta, actor)).length ?? 0;
}

function Marco({ actor, cerrarSesion }) {
  const accion = useAccion();
  const porAtender = usePorAtender(actor);
  const grupos = [
    ["Trámite", [
      ["/expedientes", "Expedientes", FolderOpen],
      ...(actor?.rol === "area_usuaria" ? [
        ["/nuevo-expediente", "Registrar orden", Plus],
        ["/lectura-ia", "Revisar TDR", FileText],
        ["/conformidad", "Conformidades", ClipboardCheck],
      ] : []),
    ]],
    ["Control", [
      ["/alertas", "Alertas", Bell],
      ...(actor?.rol === "auditor" ? [["/bitacora", "Bitácora", Database]] : []),
      ["/verificar", "Verificar sello", QrCode],
    ]],
  ];
  return (
    <div className={`marco ${actor ? "marco-privado" : "marco-publico"}`}>
      <a className="salto" href="#contenido">Saltar al contenido</a>
      {actor ? (
        <aside className="lateral">
          <Marca />
          <nav aria-label="Menú principal">
            {grupos.map(([grupo, enlaces]) => (
              <div key={grupo} className="menu-grupo" role="group" aria-label={grupo}>
                <span className="menu-titulo" aria-hidden="true">{grupo}</span>
                {enlaces.map(([ruta, etiqueta, Icono]) => (
                  <NavLink key={ruta} to={ruta}><Icono size={18} aria-hidden="true" />{etiqueta}
                    {ruta === "/alertas" && porAtender > 0 && <span className="insignia" title="Alertas por atender">
                      {porAtender}<span className="solo-lector"> por atender</span></span>}
                  </NavLink>
                ))}
              </div>
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
        <header className="barra-publica">
          <div className="barra-publica-interior">
            <div className="barra-publica-identidad">
              <Marca publica />
              <span className="separador-institucional" aria-hidden="true" />
              <span className="institucion-nombre">Universidad Nacional de Trujillo</span>
            </div>
            <nav aria-label="Menú público">
              <NavLink to="/verificar">Verificar sello</NavLink>
              <NavLink to="/login">Iniciar sesión</NavLink>
            </nav>
          </div>
        </header>
      )}
      <div className="cuerpo">
        {actor ? <header className="barra-institucional">
          <strong>Universidad Nacional de Trujillo</strong>
          <span className="marca-demo"><FlaskConical size={14} aria-hidden="true" /> Datos sintéticos</span>
        </header> : <div className="sinteticos">
          <div className="sinteticos-interior">
            <FlaskConical size={14} aria-hidden="true" />
            <span>Demostración con datos sintéticos</span>
          </div>
        </div>}
        <main className={`contenido ${actor ? "" : "contenido-publico"}`} id="contenido"><Outlet /></main>
        {!actor && (
          <footer className="pie-publico">
            <div className="pie-publico-interior">
              <span>Conforme para la Universidad Nacional de Trujillo</span>
              <span>Entorno de demostración</span>
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}

function Login({ ingresar, vencida }) {
  const accion = useAccion();
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const [usuario, setUsuario] = useState("");
  const [mostrarClave, setMostrarClave] = useState(false);
  const claveRef = useRef(null);

  function elegirDemo(username) {
    setUsuario(username);
    claveRef.current?.focus();
  }

  function enviar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    accion.ejecutar(async () => {
      ingresar(await api("/sesion", { method: "POST", data: datos }));
      navegar(ubicacion.state?.volver ?? "/expedientes", { replace: true });
    });
  }

  return (
    <div className="login-contenedor">
      <div className="login-marco">
        <aside className="login-lado" aria-label="Contexto institucional">
          <div className="login-lado-cuerpo">
            <div className="login-marca-unt">
              <span className="login-barra-oro" aria-hidden="true" />
              <span>Universidad Nacional de Trujillo</span>
            </div>
            <h1>Conformidad de servicios</h1>
            <p className="login-descripcion">
              Expedientes, evidencias y alertas antes del pago.
            </p>
          </div>

          <div className="login-lado-pie">
            <div className="login-verificar-bloque">
              <Link to="/verificar" className="login-verificar-enlace">
                <QrCode size={16} aria-hidden="true" />
                Verificar sello de conformidad
              </Link>
            </div>
          </div>
        </aside>

        <section className="login-panel" aria-labelledby="titulo-login">
          <form className="formulario login-form" onSubmit={enviar}>
            <div className="login-encabezado">
              <h2 id="titulo-login">Iniciar sesión</h2>
              <p className="secundario">Usa una cuenta de demostración.</p>
            </div>

            {vencida && <Aviso tipo="advertencia">Tu sesión venció. Vuelve a ingresar para continuar donde estabas.</Aviso>}

            <div className="campo">
              <label htmlFor="login-usuario">Usuario</label>
              <input id="login-usuario" name="username" autoComplete="username" required
                placeholder="inf1, tes1 u oci1" value={usuario}
                onChange={(e) => setUsuario(e.target.value)} />
            </div>

            <div className="campo">
              <label htmlFor="login-password">Contraseña</label>
              <div className="control-clave">
                <input id="login-password" ref={claveRef} name="password"
                  type={mostrarClave ? "text" : "password"} autoComplete="current-password"
                  placeholder="Ingresa tu contraseña" required />
                <button type="button" className="boton-ojo"
                  aria-label={mostrarClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                  onClick={() => setMostrarClave((v) => !v)}>
                  {mostrarClave ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <EstadoAccion accion={accion} />

            <button className="primario boton-ancho" disabled={accion.pendiente}>
              {accion.pendiente ? "Ingresando…" : "Ingresar"}
            </button>

            <div className="demo-bloque">
              <div className="demo-titulo">
                <span>Usuarios de demostración</span>
              </div>
              <div className="demo-chips" role="group" aria-label="Elegir usuario de demostración">
                {ROLES_DEMO.map((item) => (
                  <button key={item.usuario} type="button"
                    className={`demo-chip ${usuario === item.usuario ? "activo" : ""}`}
                    onClick={() => elegirDemo(item.usuario)}>
                    <code>{item.usuario}</code>
                    <span>{item.rol}</span>
                  </button>
                ))}
              </div>
              <small>Solicita la contraseña al equipo de la demo.</small>
            </div>
          </form>
        </section>
      </div>
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
  const [vencida, setVencida] = useState(false);
  const actor = sesion === undefined ? inicial.datos : sesion;
  const navegacion = useLocation();
  useEffect(() => {
    const vencer = () => {
      setSesion(null);
      setVencida(true);
    };
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
        <Route path="login" element={actor ? <Navigate to="/expedientes" replace /> : <Login vencida={vencida} ingresar={(actor) => {
          setVencida(false);
          setSesion(actor);
        }} />} />
        <Route path="verificar" element={<Verificar />} />
        <Route element={<Protegida actor={actor} />}>
          <Route path="expedientes" element={<Expedientes actor={actor} />} />
          <Route path="expedientes/:id" element={<Detalle actor={actor} />} />
          <Route path="alertas" element={<Alertas actor={actor} />} />
          <Route element={<Protegida actor={actor} rol="area_usuaria" />}>
            <Route path="nuevo-expediente" element={<NuevoExpediente />} />
            <Route path="lectura-ia" element={<LecturaIA />} />
            <Route path="expedientes/:id/tdr" element={<RevisarTdr />} />
            <Route path="conformidad" element={<Expedientes actor={actor} soloPendientes />} />
            <Route path="expedientes/:id/conformidad" element={<Conformidad />} />
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
