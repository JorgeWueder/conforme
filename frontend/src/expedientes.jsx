import { useEffect, useState } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, useAccion, useDatos } from "./api";
import { SEMAFOROS, capitalizar, fecha, hoy, rutaExpediente, soles } from "./dominio";
import { Aviso, Campo, Carga, Encabezado, EstadoAccion, Filtros, Semaforo, Tabla, Volver } from "./ui";

const columnas = [
  { titulo: "Código", valor: (f) => f.codigo, render: (f) => <Link to={rutaExpediente(f.id)}>{f.codigo}</Link> },
  { titulo: "Semáforo", valor: (f) => ({ rojo: 0, ambar: 1, verde: 2 }[f.semaforo]), render: (f) => <Semaforo color={f.semaforo} /> },
  { titulo: "Descripción", valor: (f) => f.descripcion },
  { titulo: "Área", valor: (f) => f.area_sigla },
  { titulo: "Tipo", valor: (f) => capitalizar(f.tipo) },
  { titulo: "Proveedor", valor: (f) => f.proveedor },
  { titulo: "Orden", valor: (f) => f.fecha_orden, render: (f) => fecha(f.fecha_orden) },
  { titulo: "Plazo (días)", valor: (f) => f.plazo_dias },
  { titulo: "Monto", valor: (f) => Number(f.monto), render: (f) => soles(f.monto) },
  { titulo: "Conformidad", valor: (f) => f.tiene_conformidad ? "Registrada" : "Pendiente" },
  { titulo: "Alertas sin cerrar", valor: (f) => f.alertas_altas + f.alertas_medias },
];

export function Expedientes({ actor }) {
  const [params, setParams] = useSearchParams();
  const texto = params.get("q") ?? "";
  const colores = params.getAll("color");
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
  const filas = recurso.datos?.filter((f) => !colores.length || colores.includes(f.semaforo));
  return (
    <>
      <Encabezado titulo="Expedientes" descripcion="Consulta el estado de las órdenes, conformidades y pagos."
        acciones={actor.rol === "area_usuaria" && <Link className="boton primario" to="/nuevo-expediente"><Plus size={17} />Nuevo expediente</Link>} />
      <div className="panel barra-filtros">
        <Campo titulo="Buscar expedientes" icono={<Search size={18} aria-hidden="true" />}>
          <input type="search" placeholder="Código, descripción o proveedor"
            value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        </Campo>
        <Filtros titulo="Semáforo" opciones={SEMAFOROS} valores={colores}
          onChange={(valores) => setParams((actuales) => {
            actuales.delete("color");
            for (const color of valores) actuales.append("color", color);
            return actuales;
          }, { replace: true })} />
      </div>
      {filas ? <>
        <p className="secundario">{filas.length} expedientes {actor.rol === "area_usuaria" ? "de tu área" : "de toda la entidad"}.
          Rojo indica alertas altas sin cerrar, ámbar solo medias y verde ninguna sin cerrar.</p>
        <Tabla columnas={columnas} filas={filas} etiqueta="Expedientes" />
      </> : <Carga recurso={recurso} />}
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
        ? manual.filter((f) => f.numero !== "" || f.descripcion.trim()).map(({ numero, descripcion }) => ({ numero, descripcion }))
        : csv.entregables;
      const { id } = await api("/expedientes", { method: "POST", data: {
        ...datos, fecha_inicio_prestacion: datos.fecha_inicio_prestacion || null,
        entregables, origen_entregables: modo,
      } });
      navegar(rutaExpediente(id), { state: { aviso: "Expediente registrado." } });
    });
  }

  return (
    <>
      <Encabezado titulo="Nuevo expediente" descripcion="El expediente queda en tu área y tú figuras como solicitante.">
        <Volver to="/expedientes">Expedientes</Volver>
      </Encabezado>
      {proveedores.datos ? <form className="formulario" onSubmit={registrar}>
        <section className="panel formulario">
          <h2>Datos de la orden</h2>
          <div className="rejilla dos">
            <Campo titulo="Tipo"><select name="tipo"><option value="servicio">Servicio</option><option value="bien">Bien</option></select></Campo>
            <Campo titulo="Proveedor"><select name="proveedor_id" required defaultValue="">
              <option value="" disabled>Elige un proveedor</option>
              {proveedores.datos.map((p) => <option key={p.id} value={p.id}>{p.razon_social} (RUC {p.ruc})</option>)}
            </select></Campo>
          </div>
          <Campo titulo="Descripción del bien o servicio"><textarea name="descripcion" required /></Campo>
          <div className="rejilla tres">
            <Campo titulo="Número de la orden"><input name="numero_orden" placeholder="OS-2026-00301" required /></Campo>
            <Campo titulo="Plazo (días calendario)"><input name="plazo_dias" type="number" min="1" defaultValue="30" required /></Campo>
            <Campo titulo="Monto (S/)"><input name="monto" type="number" min="0.01" step="0.01" required /></Campo>
            <Campo titulo="Fecha del requerimiento"><input name="fecha_requerimiento" type="date" defaultValue={hoyPeru} required /></Campo>
            <Campo titulo="Fecha de la orden"><input name="fecha_orden" type="date" defaultValue={hoyPeru} required /></Campo>
            <Campo titulo="Inicio de la prestación"><input name="fecha_inicio_prestacion" type="date" defaultValue={hoyPeru} /></Campo>
          </div>
        </section>
        <section className="panel formulario">
          <h2>Entregables</h2>
          <Campo titulo="Cómo cargarlos"><select value={modo} onChange={(e) => setModo(e.target.value)}>
            <option value="manual">A mano</option><option value="csv">Desde un archivo CSV</option>
          </select></Campo>
          {modo === "manual" ? <EditorManual filas={manual} setFilas={setManual} /> : <>
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

export function ElegirConformidad() {
  const recurso = useDatos("/expedientes");
  const navegar = useNavigate();
  const pendientes = recurso.datos?.filter((e) => !e.tiene_conformidad);
  return (
    <>
      <Encabezado titulo="Registrar conformidad" />
      {pendientes ? pendientes.length ? (
        <div className="panel">
          <Campo titulo="Expediente"><select defaultValue="" onChange={(e) => navegar(`${rutaExpediente(e.target.value)}/conformidad`)}>
            <option value="" disabled>Elige un expediente</option>
            {pendientes.map((e) => <option value={e.id} key={e.id}>{e.codigo} · {e.descripcion}</option>)}
          </select></Campo>
        </div>
      ) : <Aviso>No hay expedientes de tu área sin conformidad.</Aviso> : <Carga recurso={recurso} />}
    </>
  );
}
