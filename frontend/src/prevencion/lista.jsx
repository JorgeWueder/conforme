"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUpRight, FileSearch, FlaskConical, Plus } from "lucide-react";
import { useState } from "react";
import { api, useAccion, useDatos } from "../api";
import { Aviso, Carga, EstadoAccion } from "../ui";

const fechaCorta = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric", timeZone: "America/Lima" });

export function EstadoRevision({ estado }) {
  return <span className={`estado-revision estado-${estado}`}><span aria-hidden="true" />
    {estado === "cerrada" ? "Cerrada" : "En revisión"}
  </span>;
}

export function ListaPrevencion() {
  const router = useRouter();
  const recurso = useDatos("/prevencion");
  const accion = useAccion();
  const [paginas, setPaginas] = useState([]);
  const revisiones = [...(recurso.datos?.revisiones ?? []), ...paginas.flatMap((p) => p.revisiones)];
  const siguiente = (paginas.at(-1) || recurso.datos)?.siguiente;

  function abrirDemo() {
    accion.ejecutar(async () => {
      const revision = await api("/prevencion/demo", { method: "POST" });
      router.push(`/prevencion/${revision.id}`);
    });
  }

  return <div className="prevencion">
    <header className="prev-cabecera">
      <div className="prev-cabecera-cuerpo">
        <p className="prev-area">Abastecimiento</p>
        <h1>Revisión previa</h1>
        <p>Contrasta a los candidatos y documenta las comprobaciones antes de emitir la orden.</p>
        <div className="prev-acciones">
          <Link className="boton prev-boton-dorado" href="/prevencion/nueva"><Plus size={18} />Nueva revisión</Link>
          {recurso.datos?.demo_disponible && <button className="prev-boton-secundario" onClick={abrirDemo}
            disabled={accion.pendiente}><FlaskConical size={17} />Abrir caso de ejemplo</button>}
        </div>
      </div>
      <div className="prev-cabecera-marca" aria-hidden="true"><FileSearch size={106} strokeWidth={.8} /></div>
    </header>
    <EstadoAccion accion={accion} />
    <section className="prev-bandeja" aria-labelledby="revisiones-titulo">
      <div className="prev-seccion-cabecera"><h2 id="revisiones-titulo">Mis revisiones</h2></div>
      {!recurso.datos ? <Carga recurso={recurso} /> : revisiones.length === 0 ? (
        <div className="prev-vacio">
          <FileSearch size={30} strokeWidth={1.65} />
          <h3>Aún no tienes revisiones</h3>
          <p>Crea una revisión cuando tengas el requerimiento y al menos un candidato.</p>
        </div>
      ) : (
        <>
          <ul className="prev-lista" aria-label="Revisiones asignadas">
            {revisiones.map((r) => (
              <li key={r.id}>
                <Link href={`/prevencion/${r.id}`}>
                  <span className="prev-lista-icono"><FileSearch size={21} strokeWidth={1.6} /></span>
                  <span className="prev-lista-titulo"><small>{r.requerimiento}{r.demo ? " · Ejemplo" : ""}</small><strong>{r.objeto}</strong></span>
                  <span className="prev-lista-metadatos">{r.candidatos} {r.candidatos === 1 ? "candidato" : "candidatos"}
                    <small>{fechaCorta.format(new Date(r.actualizado_en))}</small>
                  </span>
                  <EstadoRevision estado={r.estado} />
                  <ArrowUpRight size={18} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
          {siguiente && <div className="prev-lista-pie"><button disabled={accion.pendiente}
            onClick={() => accion.ejecutar(async () => {
              const pagina = await api(`/prevencion?antes_de=${siguiente}`);
              setPaginas((actual) => [...actual, pagina]);
            })}><ArrowDown size={16} />Cargar más revisiones</button></div>}
        </>
      )}
    </section>
    {recurso.datos && recurso.error && <Aviso tipo="error">{recurso.error}</Aviso>}
  </div>;
}
