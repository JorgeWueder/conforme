"use client";

import { useRouter } from "next/navigation";
import { Building2, Plus, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { api, useAccion, useDatos } from "../api";
import { Carga, Encabezado, EstadoAccion, Volver } from "../ui";

const hoy = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "America/Lima" }).format(new Date());

function fila(nombres) {
  const datos = Object.fromEntries(nombres.map((nombre) => [nombre, ""]));
  return { ...datos, clave: crypto.randomUUID() };
}

function iniciales(datos) {
  return datos.map((datos, i) => ({ ...datos, clave: String(i) }));
}

export function FormularioPrevencion({ revision }) {
  const compra = revision?.compra;
  const router = useRouter();
  const accion = useAccion();
  const [candidatos, setCandidatos] = useState(() => iniciales(compra?.candidatos ?? [{}]));
  const [intervinientes, setIntervinientes] = useState(() => iniciales(compra?.intervinientes ?? []));
  const retorno = revision ? `/prevencion/${revision.id}` : "/prevencion";

  function guardar(evento) {
    evento.preventDefault();
    const datos = new FormData(evento.currentTarget);
    const valores = Object.fromEntries(Array.from(datos).filter(([clave]) => !clave.includes(".")));
    const filas = (lista, tipo, campos, opcionales = []) => lista.map(({ clave }) =>
      Object.fromEntries(campos.map((campo) => {
        const valor = datos.get(`${tipo}.${clave}.${campo}`).trim();
        return [campo, opcionales.includes(campo) && !valor ? null : valor];
      })),
    );
    const entrada = {
      ...valores,
      tdr: valores.tdr || null,
      candidatos: filas(candidatos, "candidato", ["ruc", "nombre", "proforma", "importe"], ["proforma", "importe"]),
      intervinientes: filas(intervinientes, "interviniente", ["rol", "designacion", "referencia"]),
    };
    accion.ejecutar(async () => {
      const guardada = await api(revision ? retorno : "/prevencion", {
        method: revision ? "PUT" : "POST", data: revision ? { version: revision.version, compra: entrada } : entrada,
      });
      router.push(`/prevencion/${guardada.id}`);
    });
  }

  return <div className="prevencion prev-formulario-pagina">
    <Encabezado titulo={revision ? "Editar revisión" : "Nueva revisión"} descripcion="Identifica la compra y a quiénes participan.">
      <Volver to={retorno}>{revision ? "Volver a la revisión" : "Revisión previa"}</Volver>
    </Encabezado>
    <form className="prev-formulario" onSubmit={guardar}>
      <fieldset>
        <legend>Datos de la compra</legend>
        <div className="prev-campos">
          <label>Requerimiento<input name="requerimiento" maxLength={200} defaultValue={compra?.requerimiento} required /></label>
          <label>RUC de la entidad<input name="entidad_ruc" pattern="[0-9]{11}" inputMode="numeric" maxLength={11}
            defaultValue={compra?.entidad_ruc} required /></label>
          <label className="prev-campo-completo">Objeto de la compra<textarea name="objeto" rows={2} minLength={5} maxLength={1500}
            defaultValue={compra?.objeto} required /></label>
          <label>Unidad usuaria<input name="unidad" maxLength={200} defaultValue={compra?.unidad} required /></label>
          <label>Rubro<input name="rubro" maxLength={200} defaultValue={compra?.rubro} required /></label>
          <label>Modalidad<input name="modalidad" maxLength={200} defaultValue={compra?.modalidad ?? "Contrato menor"} required /></label>
          <label>Fecha de evaluación<input name="fecha" type="date" min="2018-01-01" max={hoy()}
            defaultValue={compra?.fecha ?? hoy()} required /></label>
          <label>Importe estimado<input name="importe" type="number" min=".01" step=".01" defaultValue={compra?.importe} required /></label>
          <label>Moneda<select name="moneda" defaultValue={compra?.moneda ?? "PEN"}>
            <option value="PEN">Soles (PEN)</option><option value="USD">Dólares (USD)</option></select></label>
          <label className="prev-campo-completo">Referencia del TDR <span>Opcional</span>
            <input name="tdr" maxLength={200} defaultValue={compra?.tdr ?? ""} /></label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Candidatos</legend>
        {candidatos.map((c, i) => <div className="prev-formulario-fila" key={c.clave}>
          <div className="prev-formulario-fila-cabecera">
            <h3><Building2 size={17} /> Candidato {i + 1}</h3>
            {candidatos.length > 1 && <button type="button" aria-label={`Quitar candidato ${i + 1}`}
              onClick={() => setCandidatos((lista) => lista.filter((v) => v.clave !== c.clave))}><Trash2 size={16} /></button>}
          </div>
          <div className="prev-campos">
            <label>RUC<input name={`candidato.${c.clave}.ruc`} pattern="[0-9]{11}" inputMode="numeric" maxLength={11}
              defaultValue={c.ruc} required /></label>
            <label>Razón social<input name={`candidato.${c.clave}.nombre`} maxLength={200} defaultValue={c.nombre} required /></label>
            <label>Referencia de cotización <span>Opcional</span><input name={`candidato.${c.clave}.proforma`}
              maxLength={200} defaultValue={c.proforma ?? ""} /></label>
            <label>Importe de la cotización <span>Opcional</span><input name={`candidato.${c.clave}.importe`}
              type="number" min=".01" step=".01" defaultValue={c.importe ?? ""} /></label>
          </div>
        </div>)}
        <button className="prev-agregar" type="button" disabled={candidatos.length >= 12}
          onClick={() => setCandidatos((lista) => [...lista, fila(["ruc", "nombre", "proforma", "importe"])])}>
          <Plus size={17} />Agregar candidato</button>
      </fieldset>
      <fieldset>
        <legend>Intervinientes</legend>
        <p className="secundario">Registra el rol y la referencia a su designación para comprobar vínculos con la compra.</p>
        {intervinientes.map((persona, i) => <div className="prev-formulario-fila" key={persona.clave}>
          <div className="prev-formulario-fila-cabecera">
            <h3><Users size={17} /> Interviniente {i + 1}</h3>
            <button type="button" aria-label={`Quitar interviniente ${i + 1}`}
              onClick={() => setIntervinientes((lista) => lista.filter((p) => p.clave !== persona.clave))}><Trash2 size={16} /></button>
          </div>
          <div className="prev-campos">
            <label>Rol<input name={`interviniente.${persona.clave}.rol`} maxLength={200} defaultValue={persona.rol} required /></label>
            <label>Persona designada<input name={`interviniente.${persona.clave}.designacion`} maxLength={200}
              defaultValue={persona.designacion} required /></label>
            <label className="prev-campo-completo">Referencia de designación<input name={`interviniente.${persona.clave}.referencia`}
              maxLength={200} defaultValue={persona.referencia} required /></label>
          </div>
        </div>)}
        <button className="prev-agregar" type="button" disabled={intervinientes.length >= 12}
          onClick={() => setIntervinientes((lista) => [...lista, fila(["rol", "designacion", "referencia"])])}>
          <Plus size={17} />Agregar interviniente</button>
      </fieldset>
      <EstadoAccion accion={accion} />
      <div className="prev-formulario-pie">
        <button type="submit" className="primario" disabled={accion.pendiente}>
          {accion.pendiente ? "Guardando…" : revision ? "Guardar cambios" : "Crear revisión"}
        </button>
      </div>
    </form>
  </div>;
}

export function EditarPrevencion({ id }) {
  const recurso = useDatos(`/prevencion/${id}`);
  if (!recurso.datos) return <Carga recurso={recurso} />;
  return <FormularioPrevencion key={recurso.datos.version} revision={recurso.datos} />;
}
