import Link from "next/link";
import { useState } from "react";
import { api, useAccion, useDatos } from "./api";
import { ESTADOS, fechaHora, rutaAlerta, rutaExpediente } from "./dominio";
import { Campo, Carga, Encabezado, EstadoAccion, Indicador, Tabla } from "./ui";

const TIPOS = {
  observacion_seguimiento: "Observación de seguimiento",
  requerimiento_info: "Requerimiento de información",
  recomendacion: "Recomendación",
  alerta_seguimiento: "Abrir alerta de seguimiento",
};
const ENTIDADES = { expediente: "Expediente", revision_previa: "Evaluación previa",
  conflicto_interes: "Conflicto de interés" };
const ESTADOS_REVISION = { pendiente: "Pendiente", aprobada: "Aprobada", observada: "Observada" };
const ESTADOS_CONFLICTO = { declarado: "Declarado", en_revision: "En revisión",
  mitigado: "Mitigado", confirmado: "Confirmado" };

export function Integridad() {
  const recurso = useDatos("/integridad");
  const accion = useAccion();
  const [entidad, setEntidad] = useState("expediente");
  const datos = recurso.datos;
  const opciones = entidad === "expediente" ? datos?.expedientes_disponibles ?? []
    : (entidad === "revision_previa" ? datos?.revisiones : datos?.conflictos)
    ?.map((f) => ({ id: f.id, texto: `${f.expediente} · ${entidad === "revision_previa" ? "Evaluación" : "Conflicto"} ${f.id}` })) ?? [];
  function registrar(evento) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    const valores = Object.fromEntries(new FormData(formulario));
    accion.ejecutar(async () => {
      await api("/integridad/actuaciones", { method: "POST", data: {
        entidad, entidad_id: Number(valores.entidad_id), tipo: valores.tipo,
        descripcion: valores.descripcion,
      } });
      formulario.reset();
      recurso.recargar();
      return "Actuación registrada en la bitácora.";
    });
  }
  if (!datos) return <><Encabezado titulo="Integridad y conflictos" /><Carga recurso={recurso} /></>;
  return <>
    <Encabezado titulo="Integridad y conflictos"
      descripcion="Monitoreo del OCI sobre expedientes, evaluaciones y conflictos. Las actuaciones de seguimiento no levantan bloqueos operativos." />
    <div className="tarjetas">
      <div className="panel cifra"><strong>{datos.expedientes}</strong><span>Expedientes monitoreados</span></div>
      <div className="panel cifra"><strong>{datos.conflictos_bloqueantes}</strong><span>Conflictos bloqueantes activos</span></div>
      <div className="panel cifra"><strong>{datos.revisiones_pendientes}</strong><span>Revisiones independientes pendientes</span></div>
      <Link className="panel cifra" href="/alertas?ambito=seguimiento_oci"><strong>{datos.seguimiento_abierto}</strong><span>Seguimientos abiertos</span></Link>
    </div>
    <section className="seccion">
      <div className="fila-titulo"><h2>Conflictos de interés</h2></div>
      <Tabla etiqueta="Conflictos de interés" filas={datos.conflictos} vacio="No hay conflictos registrados."
        columnas={[
          { titulo: "Expediente", valor: (f) => f.expediente, render: (f) => <Link href={rutaExpediente(f.expediente_id)}>{f.expediente}</Link> },
          { titulo: "Persona", valor: (f) => f.persona },
          { titulo: "Proveedor", valor: (f) => f.proveedor_ruc },
          { titulo: "Estado", valor: (f) => ESTADOS_CONFLICTO[f.estado] ?? f.estado },
          { titulo: "Efecto", valor: (f) => f.bloqueante ? "Bloqueante" : "Seguimiento",
            render: (f) => <Indicador tono={f.bloqueante ? "rojo" : "neutro"}>{f.bloqueante ? "Bloqueante" : "Seguimiento"}</Indicador> },
        ]} />
    </section>
    <section className="seccion">
      <h2>Revisión independiente</h2>
      <Tabla etiqueta="Revisiones independientes" filas={datos.revisiones} vacio="No hay evaluaciones previas."
        columnas={[
          { titulo: "Expediente", valor: (f) => f.expediente, render: (f) => <Link href={rutaExpediente(f.expediente_id)}>{f.expediente}</Link> },
          { titulo: "Evaluador", valor: (f) => f.evaluador },
          { titulo: "Revisor", valor: (f) => f.revisor },
          { titulo: "Estado", valor: (f) => ESTADOS_REVISION[f.estado] ?? f.estado,
            render: (f) => <Indicador tono={f.estado === "aprobada" ? "verde" : f.estado === "observada" ? "ambar" : "neutro"}>
              {ESTADOS_REVISION[f.estado] ?? f.estado}</Indicador> },
          { titulo: "Proveedor", valor: (f) => f.proveedor_ruc },
          { titulo: "Evaluación", valor: (f) => f.expediente_id,
            render: (f) => <Link href={`/prevencion/${f.expediente_id}`}>Ver evaluación</Link> },
        ]} />
    </section>
    <section className="seccion">
      <div className="fila-titulo"><h2>Seguimiento OCI</h2><Link className="boton" href="/documentos">Auditar documentos y Benford</Link></div>
      <Tabla etiqueta="Alertas de seguimiento" filas={datos.seguimiento} vacio="No hay alertas de seguimiento."
        columnas={[
          { titulo: "Alerta", valor: (f) => f.id, render: (f) => <Link href={rutaAlerta(f.id)}>N.º {f.id}</Link> },
          { titulo: "Expediente", valor: (f) => f.expediente },
          { titulo: "Motivo", valor: (f) => f.explicacion, clase: "celda-texto" },
          { titulo: "Estado", valor: (f) => ESTADOS[f.estado] },
        ]} />
    </section>
    <section className="seccion">
      <h2>Registrar actuación</h2>
      <EstadoAccion accion={accion} />
      <form className="panel formulario" onSubmit={registrar}>
        <Campo titulo="Sobre qué actúas"><select value={entidad} onChange={(e) => setEntidad(e.target.value)}>
          {Object.entries(ENTIDADES).map(([clave, nombre]) => <option key={clave} value={clave}>{nombre}</option>)}
        </select></Campo>
        <Campo titulo="Registro"><select name="entidad_id" key={entidad} required defaultValue="">
          <option value="" disabled>Selecciona un registro</option>
          {opciones.map((f) => <option key={f.id} value={f.id}>{f.texto}</option>)}
        </select></Campo>
        <Campo titulo="Tipo de actuación"><select name="tipo" required>
          {Object.entries(TIPOS).map(([clave, nombre]) => <option key={clave} value={clave}>{nombre}</option>)}
        </select></Campo>
        <Campo titulo="Descripción"><textarea name="descripcion" minLength={15} maxLength={2000} required /></Campo>
        <div><button className="primario" disabled={accion.pendiente || !opciones.length}>Registrar en bitácora</button></div>
      </form>
    </section>
    <section className="seccion">
      <h2>Actuaciones recientes</h2>
      <Tabla etiqueta="Actuaciones OCI" filas={datos.actuaciones} vacio="No hay actuaciones registradas."
        columnas={[
          { titulo: "Fecha", valor: (f) => f.creado_en, render: (f) => fechaHora(f.creado_en) },
          { titulo: "Expediente", valor: (f) => f.expediente, render: (f) => <Link href={rutaExpediente(f.expediente_id)}>{f.expediente}</Link> },
          { titulo: "Tipo", valor: (f) => TIPOS[f.tipo] },
          { titulo: "Descripción", valor: (f) => f.descripcion, clase: "celda-texto" },
          { titulo: "Autor", valor: (f) => f.autor },
        ]} />
    </section>
  </>;
}
