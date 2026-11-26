"use client";

import { useEffect, useState } from "react";
import {
  Check, CircleAlert, CircleCheck, Copy, QrCode, RefreshCw, ShieldCheck, ShieldX, X,
} from "lucide-react";
import { useConsulta } from "./navegacion";
import { useDatos } from "./api";
import { capitalizar, fecha, soles } from "./dominio";
import { Aviso, EstadoEntregable, Indicador } from "./ui";

function EsqueletoVerificacion() {
  return (
    <div className="constancia" role="status" aria-label="Verificando sello">
      <div className="esqueleto-caja esqueleto-banner">
        <div className="esqueleto-linea corta" />
        <div className="esqueleto-linea larga" />
      </div>
      <div className="esqueleto-caja esqueleto-hoja">
        <div className="esqueleto-linea media" />
        <div className="esqueleto-linea larga" />
        <div className="esqueleto-grilla">
          <div className="esqueleto-bloque" />
          <div className="esqueleto-bloque" />
          <div className="esqueleto-bloque" />
          <div className="esqueleto-bloque" />
        </div>
      </div>
    </div>
  );
}

function Consulta({ codigo }) {
  const [forzar, setForzar] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const recurso = useDatos(`/sellos/${encodeURIComponent(codigo)}?forzar=${forzar}`);
  const r = recurso.datos;

  useEffect(() => {
    if (!copiado) return;
    const id = setTimeout(() => setCopiado(false), 2000);
    return () => clearTimeout(id);
  }, [copiado]);

  function copiarEnlace() {
    navigator.clipboard?.writeText(window.location.href).then(() => setCopiado(true)).catch(() => {});
  }

  if (recurso.error) {
    return (
      <section className="veredicto veredicto-alterada" role="alert">
        <div className="veredicto-principal">
          <ShieldX size={22} className="veredicto-simbolo" aria-hidden="true" />
          <div className="veredicto-texto">
            <h2>No se encontró el sello</h2>
            <p>{recurso.error}</p>
            <small>Revisa que el código esté completo o vuelve a escanear el QR del documento.</small>
          </div>
        </div>
      </section>
    );
  }

  if (!r) return <EsqueletoVerificacion />;

  const sinEvidencia = r.entregables.filter((item) => item.cumplido && !item.evidencias.length).length;
  const totalEvidencias = r.entregables.reduce((acc, item) => acc + item.evidencias.length, 0);

  return (
    <div className="constancia">
      <section className={`veredicto ${r.integra ? "veredicto-integra" : "veredicto-alterada"}`}
        role={r.integra ? "status" : "alert"}>
        <div className="veredicto-principal">
          {r.integra
            ? <ShieldCheck size={22} className="veredicto-simbolo" aria-hidden="true" />
            : <ShieldX size={22} className="veredicto-simbolo" aria-hidden="true" />}
          <div className="veredicto-texto">
            <h2>{r.integra ? "Conformidad íntegra" : "Registro alterado"}</h2>
            {r.integra ? (
              <p>
                Bitácora verificada ({r.registros_verificados} registros), sello de contenido
                y huellas SHA-256 de {totalEvidencias === 1 ? "1 evidencia" : `${totalEvidencias} evidencias`} coinciden.
              </p>
            ) : (
              <>
                <p>El estado actual de esta conformidad no coincide con el sello emitido:</p>
                <ul>{r.problemas.map((problema, i) => <li key={i}>{problema}</li>)}</ul>
              </>
            )}
          </div>
        </div>
        <div className="veredicto-acciones">
          <small className="veredicto-tiempo">
            {r.desde_cache ? `Verificada hace ${Math.round(r.verificado_hace)} s` : "Recién verificada"}
          </small>
          <div className="acciones">
            <button type="button" className="boton-sutil" onClick={copiarEnlace}>
              {copiado ? <><Check size={14} /> Copiado</> : <><Copy size={14} /> Copiar enlace</>}
            </button>
            <button type="button" className="boton-sutil" disabled={recurso.pendiente}
              onClick={() => forzar ? recurso.recargar() : setForzar(true)}>
              <RefreshCw size={14} /> Verificar de nuevo
            </button>
          </div>
        </div>
      </section>

      <article className="constancia-hoja" aria-label="Detalle de conformidad verificada">
        <header className="constancia-banda constancia-encabezado">
          <div>
            <div className="constancia-expediente-fila">
              <h2>{r.expediente}</h2>
              <Indicador tono="neutro">{capitalizar(r.tipo)}</Indicador>
            </div>
            {r.descripcion && <p className="constancia-descripcion">{r.descripcion}</p>}
          </div>
          <div className="constancia-sello-meta">
            <small>Universidad Nacional de Trujillo</small>
            <code className="codigo-sello" title="Código del sello">{codigo}</code>
          </div>
        </header>

        <dl className="constancia-cifras">
          {!r.reducido && <div><dt>Monto contratado</dt><dd>{soles(r.monto)}</dd></div>}
          <div><dt>Entrega real</dt><dd>{fecha(r.fecha_entrega_real)}</dd></div>
          <div><dt>Fecha de conformidad</dt><dd>{fecha(r.fecha_conformidad)}</dd></div>
          {!r.reducido && <div><dt>Penalidad aplicada</dt><dd>{soles(r.penalidad_aplicada)}</dd></div>}
        </dl>

        <dl className="constancia-banda constancia-partes">
          {!r.reducido && <div>
            <dt>Conformidad otorgada por</dt>
            <dd><strong>{r.conformante}</strong><span>{r.conformante_cargo}</span></dd>
          </div>}
          <div>
            <dt>Área usuaria (UNT)</dt>
            <dd><strong>{r.area}</strong></dd>
          </div>
          {!r.reducido && <div>
            <dt>Proveedor</dt>
            <dd><strong>{r.proveedor}</strong></dd>
          </div>}
          {r.observaciones && (
            <div className="constancia-obs">
              <dt>Observaciones</dt>
              <dd>{r.observaciones}</dd>
            </div>
          )}
        </dl>
      </article>

      <section className="constancia-entregables" aria-labelledby="titulo-entregables">
        <div className="fila-titulo">
          <div>
            <h2 id="titulo-entregables">Entregables y evidencias</h2>
            <p className="secundario">
              {r.entregables.length} {r.entregables.length === 1 ? "entregable" : "entregables"}
              {" · "}{totalEvidencias} {totalEvidencias === 1 ? "evidencia adjunta" : "evidencias adjuntas"}
            </p>
          </div>
        </div>

        {sinEvidencia > 0 && (
          <Aviso tipo="advertencia">
            {sinEvidencia} de {r.entregables.length} entregables se dieron por cumplidos sin evidencia.
          </Aviso>
        )}

        <div className="entregables-grupo">
          {r.entregables.map((item) => (
            <details className="desplegable entregable-fila" key={item.numero} open={item.evidencias.length > 0}>
              <summary>
                <span className="entregable-titulo">
                  <span className="entregable-indice">{item.numero}.</span>
                  <span>{item.descripcion}</span>
                </span>
                <EstadoEntregable item={item} />
              </summary>
              <div className="entregable-cuerpo">
                {item.observacion && <p className="secundario">Observación: {item.observacion}</p>}
                {item.evidencias.length ? (
                  <div className="evidencias-rejilla">
                    {item.evidencias.map((archivo, i) => (
                      <figure className="evidencia-item" key={i}>
                        {archivo.miniatura && (
                          <div className="evidencia-marco">
                            <img className="miniatura" src={`data:image/png;base64,${archivo.miniatura}`}
                              alt={archivo.nombre_archivo} loading="lazy" />
                          </div>
                        )}
                        <figcaption className="evidencia-datos">
                          <span className="evidencia-nombre">{archivo.nombre_archivo}</span>
                          <small className={archivo.coincide ? "texto-verde" : "error-texto"}>
                            {archivo.coincide ? <CircleCheck size={13} /> : <CircleAlert size={13} />}
                            {archivo.coincide ? "Huella verificada" : "Archivo alterado"}
                          </small>
                          <small className="evidencia-hash">
                            <code title={archivo.sha256}>{archivo.sha256.slice(0, 16)}…</code>
                          </small>
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                ) : <p className="secundario">Sin evidencia adjunta.</p>}
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}

export function Verificar() {
  const [params, setParams] = useConsulta();
  const [consulta, setConsulta] = useState(0);
  const codigo = (params.get("c") ?? "").trim();
  const [entrada, setEntrada] = useState(codigo);

  useEffect(() => {
    setEntrada(codigo);
  }, [codigo]);

  function buscar(evento) {
    evento.preventDefault();
    const valor = entrada.trim();
    if (!valor) return;
    if (valor === codigo) setConsulta((n) => n + 1);
    else setParams({ c: valor });
  }

  function limpiar() {
    setEntrada("");
    setParams({});
  }

  return (
    <div className="verificador">
      <header className="verificador-encabezado">
        <h1>Verificar sello de conformidad</h1>
        <p>Comprueba la integridad de un registro de conformidad de la demo con su código de sello.</p>
      </header>

      <form className="verificador-barra" onSubmit={buscar} role="search">
        <label htmlFor="codigo-sello" className="solo-lector">Código del sello de conformidad</label>
        <div className="verificador-input-wrap">
          <QrCode size={18} className="verificador-icono" aria-hidden="true" />
          <input id="codigo-sello" name="codigo" value={entrada} required
            onChange={(e) => setEntrada(e.target.value)}
            autoComplete="off" spellCheck={false}
            placeholder="Código del sello" />
          {entrada && (
            <button type="button" className="boton-limpiar" aria-label="Limpiar código" onClick={limpiar}>
              <X size={15} />
            </button>
          )}
        </div>
        <button className="primario verificador-boton">Verificar</button>
      </form>

      {codigo ? (
        <Consulta key={`${codigo}-${consulta}`} codigo={codigo} />
      ) : (
        <dl className="verificador-notas" aria-label="Alcance de la verificación pública">
          <div>
            <dt>Dónde encontrar el código</dt>
            <dd>Está debajo del QR del sello descargable en el expediente.</dd>
          </div>
          <div>
            <dt>Qué se comprueba</dt>
            <dd>Los datos del registro, las huellas de las evidencias y la cadena de la bitácora.</dd>
          </div>
        </dl>
      )}
    </div>
  );
}
