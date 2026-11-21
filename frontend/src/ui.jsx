import { cloneElement, useId, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, CircleAlert, CircleCheck, Info } from "lucide-react";
import { Link, useLocation } from "react-router";
import { SEMAFOROS, estadoEntregable } from "./dominio";

export function Encabezado({ titulo, descripcion, acciones, children }) {
  return (
    <header className="encabezado">
      <div>{children}<h1>{titulo}</h1>{descripcion && <p>{descripcion}</p>}</div>
      {acciones && <div className="acciones">{acciones}</div>}
    </header>
  );
}

export function Volver({ to, children }) {
  return <Link to={to} className="volver"><ChevronLeft size={17} />{children}</Link>;
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
  const { state } = useLocation();
  return <Aviso tipo="exito">{state?.aviso}</Aviso>;
}

export function Indicador({ tono = "neutro", children }) {
  return <span className={`indicador indicador-${tono}`}>{children}</span>;
}

export function Semaforo({ color }) {
  return <Indicador tono={color}><span className="punto" />{SEMAFOROS[color]}</Indicador>;
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

export function Metricas({ valores }) {
  return (
    <dl className="metricas">
      {valores.map(([titulo, valor]) => <div key={titulo}><dt>{titulo}</dt><dd>{valor}</dd></div>)}
    </dl>
  );
}

export function DatosClave({ valores }) {
  return (
    <dl className="datos-clave">
      {valores.map(([titulo, valor]) => <div key={titulo}><dt>{titulo}</dt><dd>{valor ?? "—"}</dd></div>)}
    </dl>
  );
}

export function Filtros({ titulo, opciones, valores, onChange }) {
  const id = useId();
  return (
    <fieldset className="filtros">
      <legend>{titulo}</legend>
      {Object.entries(opciones).map(([valor, etiqueta]) => (
        <label key={valor} className="filtro" htmlFor={`${id}-${valor}`}>
          <input
            id={`${id}-${valor}`} type="checkbox" checked={valores.includes(valor)}
            onChange={(e) => onChange(e.target.checked ? [...valores, valor] : valores.filter((v) => v !== valor))}
          />
          {etiqueta}
        </label>
      ))}
    </fieldset>
  );
}

export function Tabla({ columnas, filas, etiqueta, vacio = "No hay resultados." }) {
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
        <thead><tr>{columnas.map(({ titulo }) => {
          const activa = orden?.titulo === titulo;
          const Icono = activa ? (orden.ascendente ? ArrowUp : ArrowDown) : ArrowUpDown;
          return (
            <th key={titulo} scope="col" aria-sort={activa ? (orden.ascendente ? "ascending" : "descending") : undefined}>
              <button type="button" onClick={() => setOrden({ titulo, ascendente: !activa || !orden.ascendente })}>
                {titulo}<Icono size={13} aria-hidden="true" />
              </button>
            </th>
          );
        })}</tr></thead>
        <tbody>{ordenadas.map((fila) => (
          <tr key={fila.id ?? fila.numero}>
            {columnas.map(({ titulo, valor, render }) => <td key={titulo}>{render ? render(fila) : (valor(fila) ?? "—")}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
