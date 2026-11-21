import { useState } from "react";
import { RefreshCw, ScanLine } from "lucide-react";
import { useSearchParams } from "react-router";
import { useDatos } from "./api";
import { capitalizar, fecha, soles } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoEntregable, Metricas } from "./ui";

function Consulta({ codigo }) {
  const [forzar, setForzar] = useState(false);
  const recurso = useDatos(`/sellos/${encodeURIComponent(codigo)}?forzar=${forzar}`);
  const r = recurso.datos;
  if (!r) return <Carga recurso={recurso} />;
  const sinEvidencia = r.entregables.filter((item) => item.cumplido && !item.evidencias.length).length;
  return (
    <>
      {r.integra
        ? <Aviso tipo="exito"><strong>Íntegra.</strong> Registros verificados: {r.registros_verificados}. También se comprobó el registro sellado y las huellas de las evidencias.</Aviso>
        : <Aviso tipo="error"><strong>Alterada.</strong> El rastro de esta conformidad no coincide con el sello.
          <ul>{r.problemas.map((problema, i) => <li key={i}>{problema}</li>)}</ul>
        </Aviso>}
      <div className="fila-titulo">
        <small>{r.desde_cache ? `Bitácora verificada hace ${Math.round(r.verificado_hace)} s.` : "Bitácora recién verificada."}</small>
        <button disabled={recurso.pendiente} onClick={() => forzar ? recurso.recargar() : setForzar(true)}>
          <RefreshCw size={16} /> Verificar de nuevo
        </button>
      </div>
      <section className="seccion">
        <h2>{r.expediente}</h2>
        <p>{r.descripcion}</p>
        <p className="secundario">{capitalizar(r.tipo)} · {r.area} · Proveedor: {r.proveedor}</p>
        <Metricas valores={[
          ["Monto", soles(r.monto)], ["Entrega real", fecha(r.fecha_entrega_real)],
          ["Conformidad", fecha(r.fecha_conformidad)], ["Penalidad aplicada", soles(r.penalidad_aplicada)],
        ]} />
        <p>Conformidad dada por <strong>{r.conformante}</strong> ({r.conformante_cargo}).</p>
        {r.observaciones && <small>Observaciones: {r.observaciones}</small>}
      </section>
      <section className="seccion">
        <h2>Entregables y evidencias</h2>
        {sinEvidencia > 0 && <Aviso tipo="advertencia">{sinEvidencia} de {r.entregables.length} entregables se dieron por cumplidos sin evidencia. La verificación de integridad acredita el rastro registrado.</Aviso>}
        {r.entregables.map((item) => (
          <details className="panel desplegable" key={item.numero} open={item.evidencias.length > 0}>
            <summary><span>{item.numero}. {item.descripcion}</span><EstadoEntregable item={item} /></summary>
            {item.observacion && <p className="secundario">Observación: {item.observacion}</p>}
            {item.evidencias.length ? (
              <div className="rejilla tres">
                {item.evidencias.map((archivo, i) => (
                  <div className="archivo" key={i}>
                    {archivo.miniatura && <img className="miniatura" src={`data:image/png;base64,${archivo.miniatura}`} alt={archivo.nombre_archivo} loading="lazy" />}
                    <p>{archivo.nombre_archivo}</p>
                    <small className={archivo.coincide ? "" : "error-texto"}>
                      {archivo.coincide ? "Huella verificada" : "El archivo no coincide con su huella"} · SHA-256 <code>{archivo.sha256.slice(0, 16)}…</code>
                    </small>
                  </div>
                ))}
              </div>
            ) : <p>Sin evidencia adjunta.</p>}
          </details>
        ))}
      </section>
    </>
  );
}

export function Verificar() {
  const [params, setParams] = useSearchParams();
  const [consulta, setConsulta] = useState(0);
  const codigo = (params.get("c") ?? "").trim();
  function buscar(evento) {
    evento.preventDefault();
    const valor = new FormData(evento.currentTarget).get("codigo").trim();
    if (valor === codigo) setConsulta((n) => n + 1);
    else setParams(valor ? { c: valor } : {});
  }
  return (
    <div className="verificador">
      <Encabezado titulo="Verificar sello" descripcion="Consulta una conformidad por su código y comprueba la integridad de su rastro." />
      <form className="panel formulario-en-linea" onSubmit={buscar} key={codigo}>
        <Campo titulo="Código del sello"><input name="codigo" defaultValue={codigo} placeholder="Pega el código del sello" /></Campo>
        <button className="primario"><ScanLine size={18} /> Verificar</button>
      </form>
      {codigo ? <Consulta key={`${codigo}-${consulta}`} codigo={codigo} /> : <Aviso>Escanea el QR del sello o pega aquí su código.</Aviso>}
    </div>
  );
}
