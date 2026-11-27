import Link from "next/link";
import { useDatos } from "./api";
import { ESTADOS, SEMAFOROS, SEVERIDADES } from "./dominio";
import { useSesion } from "./sesion";
import { Carga, Encabezado, Indicador } from "./ui";

function Cifra({ titulo, valor, ayuda, to }) {
  const cuerpo = <><strong>{valor}</strong><span>{titulo}</span>{ayuda && <small>{ayuda}</small>}</>;
  return to ? <Link className="panel cifra" href={to}>{cuerpo}</Link> : <div className="panel cifra">{cuerpo}</div>;
}

function Barras({ titulo, datos, nombres = {}, tonos = {} }) {
  const total = Object.values(datos).reduce((suma, n) => suma + n, 0) || 1;
  return (
    <section className="panel">
      <h2>{titulo}</h2>
      {Object.keys(datos).length === 0 && <p className="secundario">Sin datos.</p>}
      <ul className="barras">
        {Object.entries(datos).map(([clave, n]) => (
          <li key={clave}>
            <span><Indicador tono={tonos[clave] ?? "neutro"}>{nombres[clave] ?? clave}</Indicador></span>
            <progress value={n} max={total} aria-label={`${nombres[clave] ?? clave}: ${n}`} />
            <strong>{n}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Indicadores() {
  const { actor } = useSesion();
  const recurso = useDatos("/indicadores");
  const integridad = useDatos(actor?.rol === "auditor" ? "/integridad" : null);
  const d = recurso.datos;
  if (!d) return <><Encabezado titulo="Indicadores" /><Carga recurso={recurso} /></>;
  return (
    <>
      <Encabezado titulo="Indicadores" descripcion="Cifras de los expedientes que puedes ver. Son señales de gestión, no dictámenes." />
      <div className="tarjetas">
        <Cifra titulo="Expedientes" valor={d.expedientes} to="/expedientes" />
        <Cifra titulo="Con conformidad" valor={d.con_conformidad} />
        <Cifra titulo="Sin conformidad" valor={d.sin_conformidad} />
        <Cifra titulo="Con observaciones pendientes" valor={d.con_observaciones_pendientes} to="/expedientes?ver=observadas" />
        <Cifra titulo="Observaciones sin comunicar" valor={d.observaciones_sin_comunicar} ayuda="Pendientes de Abastecimiento" />
        <Cifra titulo="Conformidades por revisar" valor={d.revision_pendiente} ayuda="Pendientes de Abastecimiento" />
        <Cifra titulo="Listas para derivar" valor={d.listos_para_derivar} />
        <Cifra titulo="Devueltas" valor={d.devueltos} />
        <Cifra titulo="Por pagar" valor={d.por_pagar} ayuda="Con conformidad y sin pago registrado" />
        <Cifra titulo="Alertas" valor={d.alertas} to="/alertas" />
        {integridad.datos && <>
          <Cifra titulo="Conflictos bloqueantes" valor={integridad.datos.conflictos_bloqueantes} to="/integridad" />
          <Cifra titulo="Revisiones independientes pendientes" valor={integridad.datos.revisiones_pendientes} to="/integridad" />
          <Cifra titulo="Seguimientos OCI abiertos" valor={integridad.datos.seguimiento_abierto} to="/integridad" />
        </>}
      </div>
      <div className="rejilla dos">
        <Barras titulo="Expedientes por semáforo" datos={d.por_semaforo} nombres={SEMAFOROS}
          tonos={{ rojo: "rojo", ambar: "ambar", verde: "verde" }} />
        <Barras titulo="Alertas por estado" datos={d.alertas_por_estado} nombres={ESTADOS} />
        <Barras titulo="Alertas por regla" datos={d.alertas_por_regla} />
        <Barras titulo="Alertas por severidad" datos={d.alertas_por_severidad} nombres={SEVERIDADES}
          tonos={{ alta: "rojo", media: "ambar" }} />
      </div>
    </>
  );
}
