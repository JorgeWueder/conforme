import { cloneElement, useId, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, CircleAlert, CircleCheck, Info } from "lucide-react";
import Link from "next/link";
import { useAvisoNavegacion } from "./navegacion";
import { REFERENCIAS_REGLAS, SEMAFOROS, estadoEntregable } from "./dominio";

export function Encabezado({ titulo, descripcion, acciones, children }) {
  return (
    <header className="encabezado">
      <div>{children}<h1>{titulo}</h1>{descripcion && <p>{descripcion}</p>}</div>
      {acciones && <div className="acciones">{acciones}</div>}
    </header>
  );
}

export function Volver({ to, children }) {
  return <Link href={to} className="volver"><ChevronLeft size={17} />{children}</Link>;
}

export function Aviso({ tipo = "info", children }) {
  if (!children) return null;
  const Icono = tipo === "exito" ? CircleCheck : tipo === "info" ? Info : CircleAlert;
  return (
    <div className={`aviso aviso-${tipo}`} role={tipo === "error" ? "alert" : "status"}>
      <Icono size={19} aria-hidden="true" /><div>{children}</div>
    </div>
  );
}

export function EstadoAccion({ accion }) {
  return <><Aviso tipo="error">{accion.error}</Aviso><Aviso tipo="exito">{accion.aviso}</Aviso></>;
}

export function AvisoNavegacion() {
  const aviso = useAvisoNavegacion();
  return <Aviso tipo="exito">{aviso}</Aviso>;
}

export function Indicador({ tono = "neutro", children }) {
  return <span className={`indicador indicador-${tono}`}>{children}</span>;
}

export function InsigniaIA() {
  return <>
    <span className="insignia-ia" title="Extracción de entregables con IA" aria-hidden="true">
      <svg width="19" height="19" viewBox="0 0 20 20" fill="currentColor">
        <path d="M7.5 1 Q8.7 7.3 15 8.5 Q8.7 9.7 7.5 16 Q6.3 9.7 0 8.5 Q6.3 7.3 7.5 1Z" />
        <path d="M15.8 10 Q16.4 13.6 20 14.2 Q16.4 14.8 15.8 18.4 Q15.2 14.8 11.6 14.2 Q15.2 13.6 15.8 10Z" />
      </svg>
    </span>
    <span className="solo-lector"> con IA</span>
  </>;
}

export function Semaforo({ color }) {
  return <Indicador tono={color}><span className="punto" />{SEMAFOROS[color]}</Indicador>;
}

export function ReferenciaRegla({ alerta }) {
  const referencia = alerta.vigente === false ? null : REFERENCIAS_REGLAS[alerta.regla];
  if (!referencia) return null;
  const [texto, url] = referencia;
  return <small className="referencia-regla"><a href={url} target="_blank" rel="noreferrer">{texto}</a></small>;
}

export function EstadoEntregable({ item }) {
  const [texto, tono] = estadoEntregable(item);
  return <Indicador tono={tono}>{texto}</Indicador>;
}

export function Carga({ recurso }) {
  if (recurso.error) return <Aviso tipo="error">{recurso.error}</Aviso>;
  return <p className="secundario" role="status">Cargando…</p>;
}

export function Campo({ titulo, ayuda, icono, children }) {
  const id = useId();
  const control = cloneElement(children, { id, "aria-describedby": ayuda ? `${id}-ayuda` : undefined });
  return (
    <div className="campo">
      <label htmlFor={id}>{titulo}</label>
      {icono ? <span className="control-icono">{icono}{control}</span> : control}
      {ayuda && <small id={`${id}-ayuda`}>{ayuda}</small>}
    </div>
  );
}

export function DatosClave({ valores }) {
  return (
    <dl className="datos-clave">
      {valores.map(([titulo, valor]) => <div key={titulo}><dt>{titulo}</dt><dd>{valor ?? "—"}</dd></div>)}
    </dl>
  );
}

/** Botones de resumen que también filtran: muestran un conteo y se activan al pulsarlos. */
export function Resumen({ opciones, activo, onChange }) {
  return (
    <div className="resumen" role="group" aria-label="Resumen y filtros rápidos">
      {opciones.map(({ clave, titulo, valor, tono = "neutro", ayuda }) => (
        <button key={clave} type="button" className={`resumen-boton resumen-${tono}`} aria-pressed={activo === clave}
          title={ayuda} onClick={() => onChange(activo === clave ? null : clave)}>
          <span className="resumen-valor">{valor}</span><span>{titulo}</span>
        </button>
      ))}
    </div>
  );
}

/** Siguiente paso recomendado para el rol actual. */
export function ProximoPaso({ titulo, children, acciones, tono = "info" }) {
  return (
    <section className={`proximo proximo-${tono}`} aria-label="Próximo paso">
      <div><strong>{titulo}</strong>{children && <p>{children}</p>}</div>
      {acciones && <div className="acciones">{acciones}</div>}
    </section>
  );
}

export function Tabla({ columnas, filas, etiqueta, vacio = "No hay resultados.", alElegir, elegida }) {
  const [orden, setOrden] = useState(null);
  if (!filas.length) return <p className="vacio">{vacio}</p>;
  const columna = columnas.find(({ titulo }) => titulo === orden?.titulo);
  const ordenadas = columna ? [...filas].sort((a, b) => {
    const valorA = columna.valor(a);
    const valorB = columna.valor(b);
    const diferencia = typeof valorA === "number" && typeof valorB === "number"
      ? valorA - valorB
      : String(valorA ?? "").localeCompare(String(valorB ?? ""), "es", { numeric: true });
    return diferencia * (orden.ascendente ? 1 : -1);
  }) : filas;
  return (
    <div className="tabla-scroll" tabIndex={0} role="region" aria-label={etiqueta}>
      <table>
        <thead><tr>{columnas.map(({ titulo, clase }) => {
          const activa = orden?.titulo === titulo;
          const Icono = activa ? (orden.ascendente ? ArrowUp : ArrowDown) : ArrowUpDown;
          return (
            <th key={titulo} className={clase} scope="col" aria-sort={activa ? (orden.ascendente ? "ascending" : "descending") : undefined}>
              <button type="button" onClick={() => setOrden({ titulo, ascendente: !activa || !orden.ascendente })}>
                {titulo}<Icono size={13} aria-hidden="true" />
              </button>
            </th>
          );
        })}</tr></thead>
        <tbody>{ordenadas.map((fila) => (
          // Toda la fila es clicable con el ratón; con teclado se usa el enlace de la primera columna.
          <tr key={fila.id ?? fila.numero} className={`${alElegir ? "clicable" : ""} ${elegida != null && elegida === fila.id ? "elegida" : ""}`}
            onClick={alElegir ? (evento) => { if (!evento.target.closest("a, button")) alElegir(fila); } : undefined}>
            {columnas.map(({ titulo, valor, render, clase }) => (
              <td key={titulo} className={clase}>{render ? render(fila) : (valor(fila) ?? "—")}</td>
            ))}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
