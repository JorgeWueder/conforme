import { useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, useAccion, useDatos } from "./api";
import { fecha, hoy, rutaExpediente, soles } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Indicador, Resumen, Semaforo, Tabla, Volver } from "./ui";

const estadoConformidad = (fila) => fila.observaciones_pendientes ? "Con observaciones"
  : fila.tiene_conformidad ? "Registrada" : "Pendiente";

const columnas = (actor, destinoFila) => [
  { titulo: "Expediente", valor: (f) => f.codigo, render: (f) => <>
    <Link className="codigo-expediente" to={destinoFila(f.id)}>{f.codigo}</Link>
    <small className="dato-tabla">{f.numero_orden} · {fecha(f.fecha_orden)}</small>
    <div className="estado-fila-movil">
      <small>{f.observaciones_pendientes ? estadoConformidad(f)
        : f.tiene_conformidad ? "Con conformidad" : "Sin conformidad"}</small>
      {f.tiene_pago && actor.rol !== "area_usuaria" && <small>Pago registrado</small>}
      {f.alertas_altas + f.alertas_medias > 0 && <Semaforo color={f.semaforo} />}
    </div>
  </> },
  { titulo: "Prestación", valor: (f) => f.descripcion, clase: "celda-texto prestacion",
    render: (f) => <>
      <span className="recorte" title={f.descripcion}>{f.descripcion}</span>
      <small className="dato-tabla">{f.proveedor}</small>
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
  { titulo: "Conformidad", valor: estadoConformidad, clase: "columna-amplia",
    render: (f) => <Indicador tono={f.observaciones_pendientes ? "ambar" : f.tiene_conformidad ? "verde" : "neutro"}>
      {estadoConformidad(f)}
    </Indicador> },
  ...(actor.rol === "area_usuaria" ? [] : [{ titulo: "Pago", valor: (f) => f.tiene_pago ? "Registrado" : "Pendiente", clase: "columna-amplia" }]),
  { titulo: "Alertas", valor: (f) => ({ rojo: 0, ambar: 1, verde: 2 }[f.semaforo]), clase: "columna-amplia",
    render: (f) => f.alertas_altas + f.alertas_medias ? <Semaforo color={f.semaforo} /> : "—" },
];

const VISTAS = {
  rojo: (f) => f.semaforo === "rojo",
  ambar: (f) => f.semaforo === "ambar",
  verde: (f) => f.semaforo === "verde",
  pendiente: (f) => !f.tiene_conformidad,
  observadas: (f) => f.observaciones_pendientes > 0,
  por_pagar: (f) => f.tiene_conformidad && !f.tiene_pago && !f.observaciones_pendientes,
};

export function Expedientes({ actor, soloPendientes = false }) {
  const [params, setParams] = useSearchParams();
  const texto = params.get("q") ?? "";
  const filtro = params.get("ver");
  const vista = Object.hasOwn(VISTAS, filtro) && (!soloPendientes || ["rojo", "ambar", "verde", "observadas"].includes(filtro))
    ? filtro : null;
  const tipo = params.get("tipo") === "bien" ? "bien" : "servicio";
  const navegar = useNavigate();
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
  const todos = recurso.datos?.filter((fila) => fila.tipo === tipo && (!soloPendientes || !fila.tiene_conformidad));
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
        acciones={!soloPendientes && actor.rol === "area_usuaria" && <Link className="boton primario" to="/nuevo-expediente"><Plus size={17} />Registrar orden de servicio</Link>} />
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
            ...(!soloPendientes ? [{
              clave: "pendiente", titulo: actor.rol === "tesoreria" ? "Falta sustento" : "Sin conformidad", valor: contar("pendiente"),
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

export function NuevoExpediente() {
  const proveedores = useDatos("/proveedores");
  const [modo, setModo] = useState("manual");
  const [manual, setManual] = useState([{ id: 0, numero: 1, descripcion: "" }]);
  const [csv, setCsv] = useState(null);
  const cargaCsv = useAccion();
  const registro = useAccion();
  const navegar = useNavigate();
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
      const { id } = await api("/expedientes", { method: "POST", data: {
        ...datos, fecha_inicio_prestacion: datos.fecha_inicio_prestacion || null,
        tipo: "servicio", conformidad_plazo_especial: datos.conformidad_plazo_especial === "on",
        entregables, origen_entregables: modo,
      } });
      const destino = rutaExpediente(id);
      navegar(modo === "tdr" ? destino + "/tdr" : destino, { state: { aviso: "Expediente registrado." } });
    });
  }

  return (
    <>
      <Encabezado titulo="Registrar orden de servicio">
        <Volver to="/expedientes">Expedientes</Volver>
      </Encabezado>
      {proveedores.datos ? <form className="formulario" onSubmit={registrar}>
        <section className="panel formulario">
          <h2>Orden de servicio</h2>
          <div className="rejilla dos">
            <Campo titulo="N.º de orden de servicio"><input name="numero_orden" placeholder="OS-2026-00301" required /></Campo>
            <Campo titulo="Proveedor"><select name="proveedor_id" required defaultValue="">
              <option value="" disabled>Elige un proveedor</option>
              {proveedores.datos.map((p) => <option key={p.id} value={p.id}>{p.razon_social} (RUC {p.ruc})</option>)}
            </select></Campo>
          </div>
          <Campo titulo="Objeto del servicio"><textarea name="descripcion" required /></Campo>
          <div className="rejilla tres">
            <Campo titulo="Referencia del proyecto (opcional)"><input name="proyecto_referencia" placeholder="PIC-2026-018" maxLength={120} /></Campo>
            <Campo titulo="Plazo (días calendario)"><input name="plazo_dias" type="number" min="1" defaultValue="30" required /></Campo>
            <Campo titulo="Monto (S/)"><input name="monto" type="number" min="0.01" step="0.01" required /></Campo>
            <Campo titulo="Fecha del requerimiento"><input name="fecha_requerimiento" type="date" defaultValue={hoyPeru} required /></Campo>
            <Campo titulo="Fecha de la orden"><input name="fecha_orden" type="date" defaultValue={hoyPeru} required /></Campo>
            <Campo titulo="Inicio pactado de la prestación"><input name="fecha_inicio_prestacion" type="date" /></Campo>
          </div>
          <label className="casilla"><input type="checkbox" name="conformidad_plazo_especial" />
            La conformidad requiere pruebas o corresponde a una consultoría (20 días)</label>
        </section>
        <section className="panel formulario">
          <h2>Entregables de los TDR</h2>
          <Campo titulo="Forma de registro"><select value={modo} onChange={(e) => setModo(e.target.value)}>
            <option value="manual">Registro manual</option><option value="csv">Importar CSV</option>
            <option value="tdr">Extraer de los TDR</option>
          </select></Campo>
          {modo === "manual" && <EditorManual filas={manual} setFilas={setManual} />}
          {modo === "tdr" && <p className="secundario">Después de registrar la orden, carga el PDF y revisa los entregables extraídos.</p>}
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
        <EstadoAccion accion={registro} />
        <div className="acciones"><button className="primario"
          disabled={registro.pendiente || (modo === "csv" && (!csv || csv.errores.length))}>Registrar expediente</button></div>
      </form> : <Carga recurso={proveedores} />}
    </>
  );
}
