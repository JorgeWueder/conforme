import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api, useAccion, useDatos } from "./api";
import { fecha, hoy, rutaExpediente, soles } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Volver } from "./ui";

function Formulario({ expediente, entregables }) {
  const [movil, setMovil] = useState(false);
  const accion = useAccion();
  const navegar = useNavigate();
  function registrar(evento) {
    evento.preventDefault();
    const form = new FormData(evento.currentTarget);
    const data = new FormData();
    const items = entregables.map(({ id }) => {
      const archivos = [...form.getAll(`archivo-${id}`), form.get(`foto-${id}`)].filter((valor) => valor?.name);
      for (const archivo of archivos) data.append("archivos", archivo);
      return {
        entregable_id: id, cumplido: form.has(`cumplido-${id}`), observacion: form.get(`observacion-${id}`),
        cantidad_archivos: archivos.length,
      };
    });
    data.set("datos", JSON.stringify({
      fecha_conformidad: form.get("fecha_conformidad"), fecha_entrega_real: form.get("fecha_entrega_real"),
      penalidad_aplicada: form.get("penalidad_aplicada"), observaciones: form.get("observaciones"), items,
    }));
    accion.ejecutar(async () => {
      const { alertas } = await api(`/expedientes/${expediente.id}/conformidad`, { method: "POST", data });
      navegar(rutaExpediente(expediente.id), { state: {
        aviso: alertas ? `Conformidad registrada. El expediente tiene ${alertas} alertas.`
          : "Conformidad registrada. No se generaron alertas.",
      } });
    });
  }
  return (
    <>
      <label className="casilla"><input type="checkbox" checked={movil} onChange={(e) => setMovil(e.target.checked)} /> Vista móvil</label>
      <form className={`formulario ${movil ? "formulario-movil" : ""}`} onSubmit={registrar}>
        <div className="panel rejilla tres">
          {expediente.fecha_entrega_real ? <p><strong>Entrega real</strong><br />{fecha(expediente.fecha_entrega_real)}</p>
            : <Campo titulo="Fecha de entrega real"><input type="date" name="fecha_entrega_real" defaultValue={hoy()} required /></Campo>}
          <Campo titulo="Fecha de la conformidad"><input type="date" name="fecha_conformidad" defaultValue={hoy()} required /></Campo>
          <Campo titulo="Penalidad aplicada (S/)"><input name="penalidad_aplicada" type="number" min="0" step="0.01" defaultValue="0" required /></Campo>
        </div>
        <section className="seccion">
          <h2>Entregables</h2>
          <p className="secundario">Adjunta evidencia en JPG, PNG o PDF, hasta 5 MB por archivo. Los entregables marcados como cumplidos sin evidencia generan una alerta.</p>
          <div className="tarjetas">
            {entregables.map((item) => (
              <fieldset className="panel formulario" key={item.id}>
                <legend>{item.numero}. {item.descripcion}</legend>
                <label className="casilla"><input type="checkbox" name={`cumplido-${item.id}`} defaultChecked /> Cumplido</label>
                <Campo titulo="Observación (opcional)"><input name={`observacion-${item.id}`} /></Campo>
                <div className="rejilla dos">
                  <Campo titulo="Evidencia"><input type="file" name={`archivo-${item.id}`} accept="image/jpeg,image/png,application/pdf" multiple /></Campo>
                  <label className={movil ? "campo" : "campo captura"}>
                    <span>Tomar una foto</span><input type="file" name={`foto-${item.id}`} accept="image/*" capture="environment" />
                  </label>
                </div>
              </fieldset>
            ))}
          </div>
        </section>
        <Campo titulo="Observaciones generales (opcional)"><textarea name="observaciones" /></Campo>
        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente}>{accion.pendiente ? "Guardando…" : "Guardar conformidad"}</button></div>
      </form>
    </>
  );
}

export function Conformidad() {
  const { id } = useParams();
  const recurso = useDatos(`/expedientes/${id}`);
  const expediente = recurso.datos?.expediente;
  return (
    <>
      <Encabezado titulo="Registrar conformidad" descripcion={expediente && `${expediente.codigo} · ${expediente.descripcion}`}>
        <Volver to={rutaExpediente(id)}>Volver al detalle</Volver>
      </Encabezado>
      {expediente ? <>
        <p className="secundario">{expediente.proveedor} · {soles(expediente.monto)} · Plazo de {expediente.plazo_dias} días
          · Fecha límite {fecha(recurso.datos.fecha_limite)}</p>
        {expediente.tiene_conformidad ? <Aviso>Este expediente ya tiene una conformidad registrada.</Aviso>
          : !recurso.datos.entregables.length ? <Aviso tipo="advertencia">Este expediente no tiene entregables.</Aviso>
          : <Formulario key={id} expediente={expediente} entregables={recurso.datos.entregables} />}
      </> : <Carga recurso={recurso} />}
    </>
  );
}
