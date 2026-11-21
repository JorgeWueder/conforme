import { useState } from "react";
import { CircleAlert, CircleCheck } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { api, useAccion, useDatos } from "./api";
import { fecha, hoy, rutaExpediente, soles } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Volver } from "./ui";

const diasEntre = (desde, hasta) => Math.round((Date.parse(hasta) - Date.parse(desde)) / 86_400_000);
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

/** Lo que las reglas R1–R4 dirían si se guardara el formulario tal como está. */
function revisionPrevia({ actor, expediente, entregables, estado, entrega, fechaConformidad, penalidad, calculo }) {
  const avisos = [];
  const sinEvidencia = entregables.filter(({ id }) => estado[id].cumplido && !estado[id].archivos);
  if (sinEvidencia.length) {
    avisos.push(["R1", `${plural(sinEvidencia.length, "entregable cumplido", "entregables cumplidos")} sin evidencia: n.º ${sinEvidencia.map((e) => e.numero).join(", ")}.`]);
  }
  if (calculo && calculo.dias_atraso > 0
      && Number(calculo.penalidad_esperada) - Number(penalidad || 0) > Number(calculo.tolerancia)) {
    avisos.push(["R2", `Hay ${plural(calculo.dias_atraso, "día", "días")} de atraso y la penalidad esperada es ${soles(calculo.penalidad_esperada)}. Aplicada: ${soles(Number(penalidad || 0))}.`]);
  }
  if (calculo && entrega && fechaConformidad) {
    const transcurridos = diasEntre(entrega, fechaConformidad);
    if (transcurridos > calculo.plazo_maximo_conformidad) {
      avisos.push(["R3", `La conformidad se daría ${plural(transcurridos, "día", "días")} después de la entrega. El máximo considerado es ${plural(calculo.plazo_maximo_conformidad, "día", "días")}.`]);
    }
  }
  if (actor.persona_id === expediente.solicitante_id) {
    avisos.push(["R4", "Figuras como solicitante de este requerimiento. Si tú das la conformidad no habrá una segunda persona que confirme la recepción."]);
  }
  return avisos;
}

function Formulario({ actor, expediente, entregables }) {
  const [movil, setMovil] = useState(false);
  const [entregaEditada, setEntrega] = useState(hoy());
  const [fechaConformidad, setFechaConformidad] = useState(hoy());
  const [penalidad, setPenalidad] = useState("0");
  const [estado, setEstado] = useState(() => Object.fromEntries(
    entregables.map(({ id }) => [id, { cumplido: true, archivos: 0, fotos: 0 }]),
  ));
  const entrega = expediente.fecha_entrega_real ?? entregaEditada;
  const calculo = useDatos(entrega ? `/expedientes/${expediente.id}/penalidad?entrega=${entrega}` : null).datos;
  const accion = useAccion();
  const navegar = useNavigate();

  const cambiar = (id, cambio) => setEstado((actual) => ({ ...actual, [id]: { ...actual[id], ...cambio } }));
  const estadoConTotal = Object.fromEntries(Object.entries(estado).map(([id, e]) => [id, { ...e, archivos: e.archivos + e.fotos }]));
  const avisos = revisionPrevia({
    actor, expediente, entregables, estado: estadoConTotal, entrega, fechaConformidad, penalidad, calculo,
  });
  const fechaInvalida = entrega && fechaConformidad && fechaConformidad < entrega;

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

  const esperada = calculo && Number(calculo.penalidad_esperada);
  return (
    <>
      <label className="casilla"><input type="checkbox" checked={movil} onChange={(e) => setMovil(e.target.checked)} /> Vista móvil</label>
      <form className={`formulario ${movil ? "formulario-movil" : ""}`} onSubmit={registrar}>
        <section className="panel formulario">
          <h2>1. Fechas y penalidad</h2>
          <div className="rejilla tres">
            {expediente.fecha_entrega_real ? <p><strong>Entrega real</strong><br />{fecha(expediente.fecha_entrega_real)}</p>
              : <Campo titulo="Fecha de entrega real" ayuda="Día en que el proveedor entregó el bien o terminó el servicio.">
                <input type="date" name="fecha_entrega_real" value={entregaEditada} onChange={(e) => setEntrega(e.target.value)} required /></Campo>}
            <Campo titulo="Fecha de la conformidad">
              <input type="date" name="fecha_conformidad" value={fechaConformidad}
                onChange={(e) => setFechaConformidad(e.target.value)} required /></Campo>
            <Campo titulo="Penalidad aplicada (S/)">
              <input name="penalidad_aplicada" type="number" min="0" step="0.01" value={penalidad}
                onChange={(e) => setPenalidad(e.target.value)} required /></Campo>
          </div>
          {fechaInvalida && <Aviso tipo="error">La fecha de la conformidad no puede ser anterior a la entrega.</Aviso>}
          {calculo && (calculo.dias_atraso > 0 ? (
            <div className="calculo">
              <p>Fecha límite {fecha(calculo.fecha_limite)}. Entrega con <strong>{plural(calculo.dias_atraso, "día", "días")} de atraso</strong>:
                penalidad esperada <strong>{soles(esperada)}</strong> (tope {soles(calculo.penalidad_tope)}).</p>
              {Number(penalidad || 0) !== esperada && <button type="button" onClick={() => setPenalidad(calculo.penalidad_esperada)}>
                Usar {soles(esperada)}</button>}
            </div>
          ) : <p className="secundario">Entrega dentro del plazo (fecha límite {fecha(calculo.fecha_limite)}). No corresponde penalidad.</p>)}
        </section>

        <section className="seccion">
          <h2>2. Entregables</h2>
          <p className="secundario">Marca cada entregable y adjunta su evidencia en JPG, PNG o PDF, hasta 5 MB por archivo.</p>
          <div className="tarjetas">
            {entregables.map((item) => {
              const { cumplido, archivos } = estadoConTotal[item.id];
              return (
                <fieldset className="panel formulario" key={item.id}>
                  <legend>{item.numero}. {item.descripcion}</legend>
                  <label className="casilla"><input type="checkbox" name={`cumplido-${item.id}`} checked={cumplido}
                    onChange={(e) => cambiar(item.id, { cumplido: e.target.checked })} /> Cumplido</label>
                  <div className="rejilla dos">
                    <Campo titulo="Evidencia"><input type="file" name={`archivo-${item.id}`} accept="image/jpeg,image/png,application/pdf" multiple
                      onChange={(e) => cambiar(item.id, { archivos: e.target.files.length })} /></Campo>
                    <label className={movil ? "campo" : "campo captura"}>
                      <span>Tomar una foto</span><input type="file" name={`foto-${item.id}`} accept="image/*" capture="environment"
                        onChange={(e) => cambiar(item.id, { fotos: e.target.files.length })} />
                    </label>
                  </div>
                  <Campo titulo={cumplido ? "Observación (opcional)" : "Motivo del incumplimiento"}>
                    <input name={`observacion-${item.id}`} /></Campo>
                  {cumplido && !archivos && <small className="texto-ambar"><CircleAlert size={14} /> Sin evidencia: se generará la alerta R1.</small>}
                  {cumplido && archivos > 0 && <small className="texto-verde"><CircleCheck size={14} /> {plural(archivos, "archivo", "archivos")} listo{archivos === 1 ? "" : "s"}.</small>}
                </fieldset>
              );
            })}
          </div>
        </section>

        <Campo titulo="Observaciones generales (opcional)"><textarea name="observaciones" /></Campo>

        <section className={`panel revision ${avisos.length ? "revision-avisos" : "revision-ok"}`} aria-live="polite">
          <h2>3. Antes de guardar</h2>
          {avisos.length ? <>
            <p>Con estos datos se {avisos.length === 1 ? "generará 1 alerta" : `generarán ${avisos.length} alertas`}. Puedes corregirlo o guardar igual.</p>
            <ul>{avisos.map(([regla, texto]) => <li key={regla}><strong>{regla}</strong> · {texto}</li>)}</ul>
          </> : <p><CircleCheck size={16} /> Con estos datos no se espera ninguna alerta.</p>}
        </section>

        <EstadoAccion accion={accion} />
        <div><button className="primario" disabled={accion.pendiente || fechaInvalida}>
          {accion.pendiente ? "Guardando…" : "Guardar conformidad"}</button></div>
      </form>
    </>
  );
}

export function Conformidad({ actor }) {
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
          : <Formulario key={id} actor={actor} expediente={expediente} entregables={recurso.datos.entregables} />}
      </> : <Carga recurso={recurso} />}
    </>
  );
}
