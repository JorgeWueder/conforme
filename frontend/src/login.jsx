"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Eye, EyeOff, FlaskConical, QrCode } from "lucide-react";
import { api, useAccion } from "./api";
import { Aviso, EstadoAccion } from "./ui";
import { Marca } from "./marco";
import fotoCampus from "./assets/unt-ciudad-universitaria.webp";
import fotoPatio from "./assets/unt-patio-historico.webp";

const ROLES_DEMO = [
  { usuario: "dec1", rol: "Abastecimiento (Evaluación)" },
  { usuario: "dec2", rol: "Revisión independiente" },
  { usuario: "aud1", rol: "Auditoría e Integridad" },
];

export function Login({ ingresar, vencida }) {
  const accion = useAccion();
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
    });
  }

  return (
    <div className="login-pagina">
      <a className="salto" href="#contenido">Saltar al contenido</a>
      <header className="login-cabecera">
        <div className="login-identidad">
          <Marca publica />
          <span>Universidad Nacional de Trujillo</span>
        </div>
        <nav aria-label="Menú público">
          <Link href="/verificar" className="boton"><QrCode size={17} aria-hidden="true" />Verificar sello</Link>
        </nav>
      </header>
      <main id="contenido" className="login-contenido" tabIndex={-1}>
        <section className="login-panel" aria-labelledby="titulo-login">
          <form className="formulario login-form" onSubmit={enviar}>
            <div className="login-encabezado">
              <h1 id="titulo-login">Iniciar sesión</h1>
            </div>

            {vencida && <Aviso tipo="advertencia">Tu sesión venció. Vuelve a ingresar para continuar donde estabas.</Aviso>}

            <div className="campo">
              <label htmlFor="login-usuario">Usuario</label>
              <input id="login-usuario" name="username" autoComplete="username" required
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)} />
            </div>

            <div className="campo">
              <label htmlFor="login-password">Contraseña</label>
              <div className="control-clave">
                <input id="login-password" ref={claveRef} name="password"
                  type={mostrarClave ? "text" : "password"} autoComplete="current-password" required />
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
              <strong className="demo-titulo">Usuarios de demostración</strong>
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
        <aside className="login-visual" aria-label="Universidad Nacional de Trujillo">
          <figure className="login-foto login-foto-campus">
            <img src={fotoCampus.src} width="1600" height="1033" alt="Pabellón de Educación y Ciencias de la Comunicación" />
            <figcaption>Ciudad Universitaria, 2012</figcaption>
          </figure>
          <div className="login-contexto">
            <figure className="login-foto login-foto-patio">
              <img src={fotoPatio.src} width="799" height="450" alt="Patio con arcos y un busto en el centro" loading="lazy" />
              <figcaption>Sede histórica, 2006</figcaption>
            </figure>
            <div className="login-contexto-texto">
              <h2>Filtro preventivo antes de contratar</h2>
              <p>Análisis de proveedores en 6 dimensiones, auditoría documental (Benford y metadatos) y revisión independiente para la Unidad de Abastecimiento de la UNT.</p>
            </div>
          </div>
        </aside>
      </main>
      <footer className="login-pie">
        <p className="login-creditos">
          Fotos adaptadas de <a href="https://commons.wikimedia.org/wiki/File:Universidad_Nacional_de_Trujillo.JPG">Latimax</a>
          {" y "}<a href="https://commons.wikimedia.org/wiki/File:UNT_antigua.jpg">EACC</a>
          {" ("}<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>{")"}
        </p>
        <p className="marca-demo"><FlaskConical size={15} aria-hidden="true" /> Demostración con datos sintéticos</p>
      </footer>
    </div>
  );
}

