"use client";

import Link from "next/link";
import { Search, Wallet } from "lucide-react";
import { useState } from "react";
import { useDatos } from "./api";
import { fecha, rutaExpediente, soles } from "./dominio";
import { useConsulta, useNavegar } from "./navegacion";
import { useSesion } from "./sesion";
import { Aviso, Campo, Carga, Encabezado, Indicador, Resumen, Tabla } from "./ui";

const VISTAS = {
  listo: { titulo: "Listos para pagar", ayuda: "Cumplen los 6 controles obligatorios", tono: "verde" },
  bloqueado: { titulo: "Con bloqueo activo", ayuda: "Les falta uno o más controles obligatorios", tono: "rojo" },
  pagado: { titulo: "Pagados", ayuda: "Pago registrado con verificación previa", tono: "neutro" },
};

const ESTADO_TONO = {
  listo: ["Listo para pagar", "verde"],
  bloqueado: ["Bloqueado", "rojo"],
  pagado: ["Pagado", "neutro"],
};

export function BandejaPagos() {
  const { actor } = useSesion();
  const recurso = useDatos("/pagos/bandeja");
  const [params, setParams] = useConsulta();
  const [busqueda, setBusqueda] = useState("");
  const navegar = useNavegar();

  if (actor && !["tesoreria", "abastecimiento", "auditor"].includes(actor.rol)) {
    return <Aviso tipo="error">La verificación de pagos no corresponde al Área usuaria.</Aviso>;
  }

  const filas = recurso.datos;
  const hayListos = filas?.some((f) => f.estado_pago === "listo");
  const pedida = params.get("ver");
  const vista = pedida === "todos" ? null
    : VISTAS[pedida] ? pedida : (filas ? (hayListos ? "listo" : "bloqueado") : "listo");
  const texto = busqueda.trim().toLowerCase();
  const filtradas = filas?.filter((f) => {
    if (vista && f.estado_pago !== vista) return false;
    if (!texto) return true;
    return [f.codigo, f.numero_orden, f.descripcion, f.proveedor, f.area]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(texto);
  });

  const contar = (clave) => filas?.filter((f) => f.estado_pago === clave).length ?? "…";

  const columnas = [
    {
      titulo: "Expediente",
      valor: (f) => f.codigo,
      render: (f) => <>
        <Link className="codigo-expediente" href={`${rutaExpediente(f.id)}#pagos`}>{f.codigo}</Link>
        <small className="dato-tabla">{f.numero_orden} · {fecha(f.fecha_orden)}</small>
      </>,
    },
    {
      titulo: "Prestación y proveedor",
      valor: (f) => f.descripcion,
      clase: "celda-texto prestacion",
      render: (f) => <>
        <span className="recorte" title={f.descripcion}>{f.descripcion}</span>
        <small className="dato-tabla">{f.proveedor} · {f.area}</small>
      </>,
    },
    {
      titulo: "Monto",
      valor: (f) => Number(f.monto),
      render: (f) => soles(f.monto),
      clase: "numero columna-amplia",
    },
    {
      titulo: "Controles",
      valor: (f) => f.controles_ok,
      render: (f) => {
        const [etiqueta, tono] = ESTADO_TONO[f.estado_pago];
        return (
          <div className="celda-estado">
            <Indicador tono={tono}>{etiqueta}</Indicador>
            <small>{f.controles_ok} de {f.controles_total} conformes</small>
          </div>
        );
      },
    },
    {
      titulo: "Qué falta",
      valor: (f) => f.bloqueos.length,
      clase: "celda-texto",
      render: (f) => {
        if (f.estado_pago === "pagado") return <span className="secundario">Pago registrado</span>;
        if (f.estado_pago === "listo") {
          return <Link className="boton primario" href={`${rutaExpediente(f.id)}#pagos`}>
            <Wallet size={15} /> {actor?.rol === "tesoreria" ? "Registrar pago" : "Ver verificación"}
          </Link>;
        }
        const primero = f.bloqueos[0];
        const extras = f.bloqueos.length - 1;
        return <>
          <span>{primero.nombre}{extras > 0 ? ` (+${extras} más)` : ""}</span>
          <small className="dato-tabla">Le toca: {f.responsables.join(", ")}</small>
        </>;
      },
    },
  ];

  return (
    <>
      <Encabezado
        titulo="Verificación y pagos"
        descripcion={actor?.rol === "tesoreria"
          ? "Comprueba los seis controles obligatorios antes de registrar un pago. Si falla alguno, el pago queda bloqueado."
          : "Consulta en solo lectura el estado de verificación previa al pago de cada orden."}
      />
      <section className="registro-expedientes" aria-label="Bandeja de verificación y pagos">
        <div className="registro-controles">
          <div className="barra-filtros">
            <Campo titulo="Buscar orden o proveedor" icono={<Search size={17} aria-hidden="true" />}>
              <input
                type="search"
                placeholder="Expediente, orden, proveedor o área"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
              />
            </Campo>
          </div>
          <Resumen
            activo={vista ?? "todos"}
            onChange={(clave) => setParams((p) => {
              p.set("ver", clave ?? "todos");
              return p;
            }, { replace: true })}
            opciones={[
              { clave: "listo", ...VISTAS.listo, valor: contar("listo") },
              { clave: "bloqueado", ...VISTAS.bloqueado, valor: contar("bloqueado") },
              { clave: "pagado", ...VISTAS.pagado, valor: contar("pagado") },
              { clave: "todos", titulo: "Todos", valor: filas?.length ?? "…" },
            ]}
          />
        </div>
        {filtradas ? <>
          <Tabla
            columnas={columnas}
            filas={filtradas}
            etiqueta="Órdenes para verificación de pago"
            alElegir={(fila) => navegar(`${rutaExpediente(fila.id)}#pagos`)}
            vacio={vista === "listo"
              ? "No hay órdenes listas para pagar en este momento."
              : "No hay órdenes en esta vista."}
          />
          <p className="registro-pie" aria-live="polite">
            {filtradas.length} de {filas.length} órdenes con verificación
          </p>
        </> : <div className="registro-pie"><Carga recurso={recurso} /></div>}
      </section>
    </>
  );
}
