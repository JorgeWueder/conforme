import { useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useNavegar } from "./navegacion";
import { useConsulta } from "./navegacion";
import { api, useAccion, useDatos } from "./api";
import { ESTADOS_FLUJO, fecha, hoy, rutaExpediente, soles, tieneOrden } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Indicador, Resumen, Semaforo, Tabla, Volver } from "./ui";

const estadoFlujo = (fila) => ESTADOS_FLUJO[fila.estado_flujo] ?? [fila.estado_flujo, "", "neutro"];

const columnas = (actor, destinoFila) => [
  { titulo: "Expediente", valor: (f) => f.codigo, render: (f) => <>
    <Link className="codigo-expediente" href={destinoFila(f.id)}>{f.codigo}</Link>
    <small className="dato-tabla">{f.numero_orden ? `${f.numero_orden} · ${fecha(f.fecha_orden)}`
      : `Requerimiento del ${fecha(f.fecha_requerimiento)}`}</small>
    <div className="estado-fila-movil">
      <small>{estadoFlujo(f)[0]}</small>
      {f.tiene_pago && actor.rol !== "area_usuaria" && <small>Pago registrado</small>}
      {f.alertas_altas + f.alertas_medias > 0 && <Semaforo color={f.semaforo} />}
    </div>
  </> },
  { titulo: "Prestación", valor: (f) => f.descripcion, clase: "celda-texto prestacion",
    render: (f) => <>
      <span className="recorte" title={f.descripcion}>{f.descripcion}</span>
      <small className="dato-tabla">{f.proveedor ?? "Proveedor por definir"}</small>
      <div className="datos-fila-movil">
        {actor.rol !== "area_usuaria" && <small>{f.area}</small>}
        <small>{soles(f.monto)}</small>
      </div>
    </> },
  ...(actor.rol === "area_usuaria" ? [] : [{
    titulo: "Área usuaria", valor: (f) => f.area, clase: "area-tabla columna-amplia",
    render: (f) => <span title={f.area}>{f.area}</span>,
  }]),
  { titulo: "Monto", valor: (f) => Number(f.monto), render: (f) => soles(f.monto), clase: "numero columna-amplia" },
  { titulo: "Estado", valor: (f) => estadoFlujo(f)[0], clase: "columna-amplia",
    render: (f) => {
      const [texto, quien, tono] = estadoFlujo(f);
      return <div className="celda-estado">
        <Indicador tono={f.observaciones_pendientes ? "ambar" : tono}>{texto}</Indicador>
        {quien && quien !== "—" && <small>Le toca: {quien}</small>}
      </div>;
    } },
  { titulo: "Alertas", valor: (f) => ({ rojo: 0, ambar: 1, verde: 2 }[f.semaforo]), clase: "columna-amplia",
    render: (f) => f.alertas_altas + f.alertas_medias ? <Semaforo color={f.semaforo} /> : "—" },
];

const VISTAS = {
  rojo: (f) => f.semaforo === "rojo",
  ambar: (f) => f.semaforo === "ambar",
  verde: (f) => f.semaforo === "verde",
  antes_orden: (f) => !tieneOrden(f),
  pendiente: (f) => tieneOrden(f) && !f.tiene_conformidad,
  observadas: (f) => f.observaciones_pendientes > 0,
  por_pagar: (f) => f.tiene_conformidad && !f.tiene_pago && !f.observaciones_pendientes,
};

export function Expedientes({ actor, soloPendientes = false }) {
  const [params, setParams] = useConsulta();
  const texto = params.get("q") ?? "";
  const filtro = params.get("ver");
  const vista = Object.hasOwn(VISTAS, filtro) && (!soloPendientes || ["rojo", "ambar", "verde", "observadas"].includes(filtro))
    ? filtro : null;
  const tipo = params.get("tipo") === "bien" ? "bien" : "servicio";
  const navegar = useNavegar();
  const [busqueda, setBusqueda] = useState(texto);
  useEffect(() => setBusqueda(texto), [texto]);
  useEffect(() => {
    if (busqueda === texto) return;
    const id = setTimeout(() => setParams((actuales) => {
      if (busqueda) actuales.set("q", busqueda);
      else actuales.delete("q");
      return actuales;
    }, { replace: true }), 250);
    return () => clearTimeout(id);
  }, [busqueda, texto, setParams]);
  const recurso = useDatos(`/expedientes?texto=${encodeURIComponent(texto)}`);
  const todos = recurso.datos?.filter((fila) => fila.tipo === tipo
    && (!soloPendientes || (tieneOrden(fila) && !fila.tiene_conformidad)));
  const filas = todos?.filter((f) => !vista || VISTAS[vista](f));
  const contar = (clave) => todos?.filter(VISTAS[clave]).length ?? "…";
  const cambiarVista = (clave) => setParams((actuales) => {
    if (clave) actuales.set("ver", clave);
    else actuales.delete("ver");
    return actuales;
  }, { replace: true });
  const area = actor.rol === "area_usuaria" ? recurso.datos?.[0]?.area : null;
  const titulo = soloPendientes ? "Conformidades pendientes" : tipo === "servicio" ? "Expedientes de servicio" : "Expedientes de bienes";
  const destinoFila = (id) => rutaExpediente(id) + (soloPendientes ? "/conformidad" : "");
  function cambiarTipo(evento) {
    const tipoElegido = evento.target.value;
    setParams((actuales) => {
      if (tipoElegido === "bien") actuales.set("tipo", tipoElegido);
      else actuales.delete("tipo");
      return actuales;
    }, { replace: true });
  }
  return (
    <>
      <Encabezado titulo={titulo} descripcion={area}
        acciones={!soloPendientes && actor.rol === "area_usuaria" && <Link className="boton primario" href="/nuevo-expediente"><Plus size={17} />Nuevo requerimiento</Link>} />
      <section className="registro-expedientes" aria-label={soloPendientes ? titulo : "Bandeja de expedientes"}>
        <div className="registro-controles">
          <div className="barra-filtros">
            <Campo titulo="Buscar expediente" icono={<Search size={17} aria-hidden="true" />}>
              <input type="search" placeholder="Expediente, orden, proyecto o proveedor"
                value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
            </Campo>
            <Campo titulo="Tipo de prestación">
              <select value={tipo} onChange={cambiarTipo}>
                <option value="servicio">Servicios</option><option value="bien">Bienes</option>
              </select>
            </Campo>
          </div>
          <Resumen activo={vista ?? "todos"} onChange={(clave) => cambiarVista(clave === "todos" ? null : clave)} opciones={[
            { clave: "todos", titulo: "Todos", valor: todos?.length ?? "…" },
            ...(!soloPendientes ? [{ clave: "antes_orden", titulo: "Antes de la orden", valor: contar("antes_orden"),
              ayuda: "Requerimientos con proveedores en evaluación o selección por confirmar" }] : []),
            ...(!soloPendientes ? [{
              clave: "pendiente", titulo: actor.rol === "tesoreria" ? "Falta conformidad" : "Sin conformidad", valor: contar("pendiente"),
            }] : []),
            { clave: "observadas", titulo: "Con observaciones", valor: contar("observadas"), tono: "ambar" },
            { clave: "rojo", titulo: "Alertas altas", valor: contar("rojo"), tono: "rojo" },
            { clave: "ambar", titulo: "Alertas medias", valor: contar("ambar"), tono: "ambar" },
            ...(actor.rol === "tesoreria" ? [{ clave: "por_pagar", titulo: "Sin pago registrado", valor: contar("por_pagar"),
              ayuda: "Con conformidad registrada y sin observaciones pendientes. Revisa las alertas antes del pago." }] : []),
          ]} />
        </div>
        {filas ? <>
          <Tabla columnas={columnas(actor, destinoFila)} filas={filas} etiqueta={soloPendientes ? titulo : "Expedientes"}
            alElegir={(fila) => navegar(destinoFila(fila.id))}
            vacio={vista || texto ? "No hay expedientes para estos filtros."
              : soloPendientes ? "No hay conformidades pendientes para este tipo de prestación."
                : "No hay expedientes registrados de este tipo."} />
          <p className="registro-pie" aria-live="polite">{filas.length} de {todos.length} expedientes</p>
        </> : <div className="registro-pie"><Carga recurso={recurso} /></div>}
      </section>
    </>
  );
}

function EditorManual({ filas, setFilas }) {
  const cambiar = (id, cambio) => setFilas((actuales) => actuales.map((fila) => fila.id === id ? { ...fila, ...cambio } : fila));
  function agregar() {
    const numero = Math.max(0, ...filas.map((fila) => Number(fila.numero))) + 1;
    setFilas([...filas, { id: siguienteId++, numero, descripcion: "" }]);
  }
  return (
    <>
      {filas.map(({ id, numero, descripcion }, indice) => (
        <div className="fila-editor" key={id}>
          <Campo titulo="N.º"><input aria-label={`Número del entregable ${indice + 1}`} type="number" min="1" value={numero}
            onChange={(e) => cambiar(id, { numero: e.target.value })} /></Campo>
          <Campo titulo="Descripción"><input aria-label={`Descripción del entregable ${indice + 1}`} value={descripcion}
            onChange={(e) => cambiar(id, { descripcion: e.target.value })} /></Campo>
          <button type="button" className="icono-boton" aria-label={`Quitar entregable ${indice + 1}`}
            onClick={() => setFilas(filas.filter((fila) => fila.id !== id))}><Trash2 size={17} /></button>
        </div>
      ))}
      <button type="button" onClick={agregar}><Plus size={17} />Añadir entregable</button>
    </>
  );
}

let siguienteId = 1;
const columnasCSV = [{ titulo: "N.º", valor: (f) => f.numero }, { titulo: "Descripción", valor: (f) => f.descripcion }];

function CotizacionesReferenciales({ filas, setFilas }) {
  const cambiar = (id, cambio) => setFilas((actuales) => actuales.map((fila) => fila.id === id ? { ...fila, ...cambio } : fila));
  return (
    <>
      {filas.map((fila, indice) => (
        <div className="fila-editor fila-cotizacion" key={fila.id}>
          <Campo titulo="RUC"><input aria-label={`RUC de la cotización ${indice + 1}`} inputMode="numeric" maxLength={11}
            value={fila.ruc} onChange={(e) => cambiar(fila.id, { ruc: e.target.value.replace(/\D/g, "") })} /></Campo>
          <Campo titulo="Razón social"><input aria-label={`Razón social de la cotización ${indice + 1}`} value={fila.razon_social}
            onChange={(e) => cambiar(fila.id, { razon_social: e.target.value })} /></Campo>
          <Campo titulo="Monto (S/)"><input aria-label={`Monto de la cotización ${indice + 1}`} type="number" min="0.01" step="0.01"
            value={fila.monto_cotizado} onChange={(e) => cambiar(fila.id, { monto_cotizado: e.target.value })} /></Campo>
          <Campo titulo="Plazo (días)"><input aria-label={`Plazo de la cotización ${indice + 1}`} type="number" min="1"
            value={fila.plazo_dias} onChange={(e) => cambiar(fila.id, { plazo_dias: e.target.value })} /></Campo>
          <button type="button" className="icono-boton" aria-label={`Quitar cotización ${indice + 1}`}
            onClick={() => setFilas(filas.filter((f) => f.id !== fila.id))}><Trash2 size={17} /></button>
        </div>
      ))}
      <button type="button" onClick={() => setFilas([...filas, { id: siguienteId++, ruc: "", razon_social: "", monto_cotizado: "", plazo_dias: "" }])}>
        <Plus size={17} />Añadir cotización</button>
    </>
  );
}

export function NuevoRequerimiento() {
  const [modo, setModo] = useState("manual");
  const [manual, setManual] = useState([{ id: 0, numero: 1, descripcion: "" }]);
  const [csv, setCsv] = useState(null);
  const [cotizaciones, setCotizaciones] = useState([]);
  const cargaCsv = useAccion();
  const registro = useAccion();
  const navegar = useNavegar();
  const hoyPeru = hoy();

  function importar(evento) {
    const archivo = evento.target.files[0];
    setCsv(null);
    if (!archivo) return;
    const data = new FormData();
    data.set("archivo", archivo);
    cargaCsv.ejecutar(async () => setCsv(await api("/entregables/csv", { method: "POST", data })));
  }

  function registrar(evento) {
    evento.preventDefault();
    const datos = Object.fromEntries(new FormData(evento.currentTarget));
    registro.ejecutar(async () => {
      const entregables = modo === "manual"
        ? manual.map(({ numero, descripcion }) => ({ numero, descripcion }))
        : modo === "csv" ? csv.entregables : [];
      const postores = cotizaciones.filter((c) => c.ruc || c.razon_social || c.monto_cotizado)
        .map(({ ruc, razon_social, monto_cotizado, plazo_dias }) => ({
          ruc, razon_social, monto_cotizado, plazo_dias: Number(plazo_dias) || 0,
        }));
      const { id } = await api("/expedientes", { method: "POST", data: {
        descripcion: datos.descripcion, proyecto_referencia: datos.proyecto_referencia || null,
        fecha_requerimiento: datos.fecha_requerimiento, plazo_dias: Number(datos.plazo_dias), monto: datos.monto,
        tipo: "servicio", conformidad_plazo_especial: datos.conformidad_plazo_especial === "on",
        entregables, origen_entregables: modo, postores,
      } });
      const destino = rutaExpediente(id);
      navegar(modo === "tdr" ? destino + "/tdr" : destino,
        { state: { aviso: "Requerimiento registrado. Abastecimiento evaluará a los posibles proveedores." } });
    });
  }

  return (
    <>
      <Encabezado titulo="Nuevo requerimiento de servicio"
        descripcion="Describe lo que necesitas. Abastecimiento evalúa a los posibles proveedores y, cuando la selección esté aprobada, registras la orden.">
        <Volver to="/expedientes">Expedientes</Volver>
      </Encabezado>
      <form className="formulario" onSubmit={registrar}>
        <section className="panel formulario">
          <h2>1. Qué necesitas</h2>
          <Campo titulo="Objeto del servicio" ayuda="Escríbelo como figura en los TDR."><textarea name="descripcion" maxLength={2000} required /></Campo>
          <div className="rejilla tres">
            <Campo titulo="Valor estimado (S/)" ayuda="Según tu indagación de mercado."><input name="monto" type="number" min="0.01" step="0.01" required /></Campo>
            <Campo titulo="Plazo de ejecución (días calendario)"><input name="plazo_dias" type="number" min="1" defaultValue="30" required /></Campo>
            <Campo titulo="Fecha del requerimiento"><input name="fecha_requerimiento" type="date" defaultValue={hoyPeru} max={hoyPeru} required /></Campo>
            <Campo titulo="Referencia del proyecto (opcional)"><input name="proyecto_referencia" placeholder="PIC-2026-018" maxLength={120} /></Campo>
          </div>
          <label className="casilla"><input type="checkbox" name="conformidad_plazo_especial" />
            La conformidad requiere pruebas o corresponde a una consultoría (20 días)</label>
        </section>
        <section className="panel formulario">
          <h2>2. Entregables de los TDR</h2>
          <Campo titulo="Forma de registro"><select value={modo} onChange={(e) => setModo(e.target.value)}>
            <option value="manual">Registro manual</option><option value="csv">Importar CSV</option>
            <option value="tdr">Extraer de los TDR con IA</option>
          </select></Campo>
          {modo === "manual" && <EditorManual filas={manual} setFilas={setManual} />}
          {modo === "tdr" && <p className="secundario">Después de registrar el requerimiento, carga el PDF y revisa los entregables extraídos.</p>}
          {modo === "csv" && <>
            <Campo titulo="Archivo CSV" ayuda="Usa el encabezado numero,descripcion y una fila por entregable.">
              <input type="file" accept=".csv,text/csv" onChange={importar} disabled={cargaCsv.pendiente} />
            </Campo>
            <EstadoAccion accion={cargaCsv} />
            {cargaCsv.pendiente && <p role="status">Leyendo CSV…</p>}
            {csv && (csv.errores.length ? <Aviso tipo="error"><ul>{csv.errores.map((error) => <li key={error}>{error}</li>)}</ul></Aviso>
              : <><Aviso tipo="exito">{csv.entregables.length} entregables leídos.</Aviso>
                <Tabla columnas={columnasCSV} filas={csv.entregables} etiqueta="Entregables del CSV" /></>)}
          </>}
        </section>
        <section className="panel formulario">
          <h2>3. Cotizaciones referenciales (opcional)</h2>
          <p className="secundario">Si ya pediste cotizaciones, regístralas para que Abastecimiento las evalúe.
            No eliges al proveedor: la selección la sustenta Abastecimiento y la aprueba otro especialista.</p>
          <CotizacionesReferenciales filas={cotizaciones} setFilas={setCotizaciones} />
        </section>
        <EstadoAccion accion={registro} />
        <div className="acciones"><button className="primario"
          disabled={registro.pendiente || (modo === "csv" && (!csv || csv.errores.length))}>Registrar requerimiento</button></div>
      </form>
    </>
  );
}
