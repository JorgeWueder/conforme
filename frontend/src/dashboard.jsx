"use client";

import Link from "next/link";
import {
  AlertTriangle, ArrowUpRight, Bell, CheckCircle2, FileSearch, ScanSearch, ShieldCheck, Wallet,
} from "lucide-react";
import { useDatos } from "./api";
import { ESTADOS_FLUJO, ROLES, SEMAFOROS, SEVERIDADES, rutaAlerta, rutaExpediente, soles } from "./dominio";
import { useSesion } from "./sesion";
import { Carga, Encabezado, Indicador } from "./ui";

const COLORES = {
  verde: "#147a56",
  ambar: "#d49b27",
  rojo: "#b91c1c",
  azul: "#004aad",
  neutro: "#8fa2bc",
};

const ETIQUETA_ADAPTADOR = {
  fuentes_publicas: "Fuentes públicas",
  siaf: "SIAF",
  notificaciones: "Avisos",
  agente_ia: "Agente IA",
};

function Kpi({ titulo, valor, ayuda, icono, tono = "neutro", to }) {
  const contenido = <>
    <span className="dash-kpi-cabecera"><span>{titulo}</span>{icono}</span>
    <strong>{valor}</strong>
    {ayuda && <small>{ayuda}</small>}
  </>;
  return to
    ? <Link className={`dash-kpi dash-kpi-${tono}`} href={to}>{contenido}</Link>
    : <div className={`dash-kpi dash-kpi-${tono}`}>{contenido}</div>;
}

function GraficoAnillo({ titulo, subtitulo, segmentos, totalEtiqueta = "total", enlace }) {
  const total = segmentos.reduce((s, x) => s + x.valor, 0);
  const radio = 46;
  const circunferencia = 2 * Math.PI * radio;
  let acumulado = 0;

  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <small>{subtitulo}</small>}
        </div>
        {enlace && <Link href={enlace[0]}>{enlace[1]} <ArrowUpRight size={14} /></Link>}
      </div>
      <div className="dash-anillo-wrap">
        <svg className="dash-anillo" viewBox="0 0 120 120" role="img" aria-label={`${titulo}: ${total}`}>
          <circle cx="60" cy="60" r={radio} fill="none" stroke="#e4ebf4" strokeWidth="14" />
          {total > 0 && segmentos.map((seg) => {
            if (!seg.valor) return null;
            const fraccion = seg.valor / total;
            const largo = fraccion * circunferencia;
            const offset = -acumulado * circunferencia;
            acumulado += fraccion;
            return (
              <circle
                key={seg.clave}
                cx="60" cy="60" r={radio}
                fill="none"
                stroke={COLORES[seg.tono] ?? COLORES.azul}
                strokeWidth="14"
                strokeDasharray={`${largo} ${circunferencia - largo}`}
                strokeDashoffset={offset}
                transform="rotate(-90 60 60)"
              />
            );
          })}
          <text x="60" y="58" textAnchor="middle" className="dash-anillo-total">{total}</text>
          <text x="60" y="73" textAnchor="middle" className="dash-anillo-etiqueta">{totalEtiqueta}</text>
        </svg>
        <ul className="dash-leyenda">
          {segmentos.map((seg) => {
            const pct = total ? Math.round((seg.valor / total) * 100) : 0;
            return (
              <li key={seg.clave}>
                <span className="dash-punto" style={{ background: COLORES[seg.tono] ?? COLORES.azul }} aria-hidden="true" />
                <span>{seg.nombre}</span>
                <strong>{seg.valor} <small>({pct}%)</small></strong>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function GraficoBarras({ titulo, subtitulo, items, tono = "azul", vacio = "Sin registros.", enlace }) {
  const max = Math.max(1, ...items.map((i) => i.valor));
  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <small>{subtitulo}</small>}
        </div>
        {enlace && <Link href={enlace[0]}>{enlace[1]} <ArrowUpRight size={14} /></Link>}
      </div>
      {items.length === 0 || items.every((i) => i.valor === 0) ? (
        <p className="secundario">{vacio}</p>
      ) : (
        <ul className="dash-barras">
          {items.map((item) => {
            const pct = Math.round((item.valor / max) * 100);
            const tonoItem = item.tono ?? tono;
            return (
              <li key={item.clave ?? item.nombre}>
                <div className="dash-barra-texto">
                  <span>{item.nombre}</span>
                  <strong>{item.valor}</strong>
                </div>
                <div className="dash-barra-pista">
                  <div className={`dash-barra-relleno tono-${tonoItem}`} style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function EmbudoPreventivo({ etapas }) {
  const max = Math.max(1, ...etapas.map((e) => e.valor));
  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>Avance del filtro preventivo</h2>
          <small>Flujo desde TDR hasta selección aprobada antes del SIGA</small>
        </div>
        <Link href="/prevencion">Ir a bandeja <ArrowUpRight size={14} /></Link>
      </div>
      <ul className="dash-embudo">
        {etapas.map((e) => (
          <li key={e.etapa}>
            <span>{e.etapa}</span>
            <div className="dash-embudo-pista">
              <div className="dash-embudo-barra" style={{ width: `${Math.round((e.valor / max) * 100)}%` }} />
            </div>
            <strong>{e.valor}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

function GraficoBenfordMini({ benford }) {
  if (!benford) return null;
  const maxPct = Math.max(
    0.35,
    ...benford.digitos.map((d) => Math.max(d.esperado, d.observado)),
  );
  const ancho = 360;
  const alto = 148;
  const baseY = 124;
  const escalaY = 104 / maxPct;
  const pasoX = ancho / 9;
  const tonoNivel = benford.nivel === "anomalia" ? "rojo" : benford.nivel === "revisar" ? "ambar" : "verde";

  const puntosLinea = benford.digitos.map((d, i) => {
    const x = i * pasoX + pasoX / 2;
    const y = baseY - d.esperado * escalaY;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>Ley de Benford ({benford.fuente === "pagos" ? "pagos" : "órdenes"} UNT)</h2>
          <small>{benford.total} montos analizados · MAD {benford.mad != null ? Number(benford.mad).toFixed(4) : "—"}</small>
        </div>
        <div className="acciones">
          <Indicador tono={tonoNivel}>{benford.titulo}</Indicador>
          <Link href="/documentos">Auditar <ArrowUpRight size={14} /></Link>
        </div>
      </div>
      <svg className="dash-benford-svg" viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label="Distribución de primeros dígitos de Benford">
        <line x1="0" y1={baseY} x2={ancho} y2={baseY} stroke="#cbd5e1" strokeWidth="1" />
        {benford.digitos.map((d, i) => {
          const x = i * pasoX + 7;
          const barW = pasoX - 14;
          const hObs = Math.max(2, d.observado * escalaY);
          const color = d.sospechoso ? "#b91c1c" : "#004aad";
          return (
            <g key={d.digito}>
              <rect x={x} y={baseY - hObs} width={barW} height={hObs} rx="3" fill={color} opacity="0.88" />
              <text x={x + barW / 2} y={baseY + 15} textAnchor="middle" fontSize="11" fill="#4c5f7a" fontWeight="600">
                {d.digito}
              </text>
              <text x={x + barW / 2} y={Math.max(12, baseY - hObs - 4)} textAnchor="middle" fontSize="9.5" fill={color} fontWeight="600">
                {Math.round(d.observado * 100)}%
              </text>
            </g>
          );
        })}
        <polyline fill="none" stroke="#d49b27" strokeWidth="2.5" points={puntosLinea} />
        {benford.digitos.map((d, i) => (
          <circle key={`e-${d.digito}`} cx={i * pasoX + pasoX / 2} cy={baseY - d.esperado * escalaY} r="3.2" fill="#d49b27" />
        ))}
      </svg>
      <div className="dash-benford-leyenda">
        <span><i className="dash-punto" style={{ background: "#004aad" }} /> Observado normal</span>
        <span><i className="dash-punto" style={{ background: "#b91c1c" }} /> Dígito con exceso anómalo</span>
        <span><i className="dash-punto" style={{ background: "#d49b27" }} /> Curva esperada (Benford)</span>
      </div>
    </section>
  );
}

function CuadroEvaluaciones({ casos, esDec }) {
  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>Evaluaciones prioritarias</h2>
          <small>{esDec ? "Acceso directo a los expedientes en curso" : "Consulta en solo lectura"}</small>
        </div>
        <Link href="/prevencion">Ver todas <ArrowUpRight size={14} /></Link>
      </div>
      {casos.length === 0 ? (
        <p className="secundario">No hay evaluaciones activas.</p>
      ) : (
        <ul className="dash-lista">
          {casos.map((c) => {
            const [texto, , tono] = ESTADOS_FLUJO[c.estado_flujo] ?? [c.estado_flujo, "", "neutro"];
            return (
              <li key={c.id} className="dash-item">
                <div className="dash-item-info">
                  <strong>{c.codigo} · {soles(c.monto)}</strong>
                  <p>{c.descripcion}</p>
                  <small>{c.area} · {c.analizados}/{c.postores} postores analizados</small>
                </div>
                <div className="acciones">
                  <Indicador tono={c.me_toca_revisar ? "ambar" : tono}>
                    {c.me_toca_revisar ? "Te toca revisar" : texto}
                  </Indicador>
                  <Link className="boton" href={`/prevencion/${c.id}`}>Abrir</Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function CuadroAlertas({ alertas, titulo = "Alertas recientes", soloLectura = false }) {
  return (
    <section className="dash-panel">
      <div className="dash-panel-cabecera">
        <div>
          <h2>{titulo}</h2>
          <small>{soloLectura ? `${alertas.abiertas} escalada(s) automáticamente a Auditoría e Integridad` : `${alertas.abiertas} abierta(s) en tu ámbito`}</small>
        </div>
        {!soloLectura && <Link href="/alertas">Ver bandeja <ArrowUpRight size={14} /></Link>}
      </div>
      {alertas.recientes.length === 0 ? (
        <p className="secundario">{soloLectura ? "Sin señales de riesgo detectadas aún." : "Sin alertas abiertas en este ámbito. Todo en orden."}</p>
      ) : (
        <ul className="dash-lista">
          {alertas.recientes.map((a) => {
            const destino = soloLectura
              ? (a.regla?.startsWith("D") ? `/documentos/${a.expediente_id}` : `/prevencion/${a.expediente_id}`)
              : rutaAlerta(a.id);
            return (
              <li key={a.id} className="dash-item">
                <div className="dash-item-info">
                  <strong>{a.expediente} · {a.nombre}</strong>
                  <p>{a.explicacion}</p>
                </div>
                <div className="acciones">
                  <Indicador tono={a.severidad === "alta" ? "rojo" : "ambar"}>{SEVERIDADES[a.severidad]}</Indicador>
                  <Link className="boton" href={destino}>{soloLectura ? "Ver caso" : "Revisar"}</Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function TiraAdaptadores({ adaptadores }) {
  if (!adaptadores) return null;
  return (
    <footer className="dash-adaptadores" aria-label="Estado de adaptadores">
      <strong>Integraciones (adaptadores):</strong>
      <div className="dash-adaptadores-lista">
        {Object.entries(adaptadores).map(([clave, info]) => (
          <span key={clave}>
            {ETIQUETA_ADAPTADOR[clave] ?? clave}
            <Indicador tono={info.modo === "eve" ? (info.listo ? "verde" : "ambar") : "neutro"}>
              {info.modo === "eve" ? (info.listo ? "eve activo" : "inactivo") : info.modo.replace("_", " ")}
            </Indicador>
          </span>
        ))}
      </div>
    </footer>
  );
}

export function Dashboard() {
  const { actor } = useSesion();
  const recurso = useDatos("/dashboard");
  const d = recurso.datos;

  if (!d) {
    return <>
      <Encabezado titulo="Dashboard" descripcion="Cargando resumen del sistema…" />
      <Carga recurso={recurso} />
    </>;
  }

  const rol = d.rol;
  const sem = d.resumen_general.por_semaforo || {};
  const segmentosSemaforo = [
    { clave: "rojo", nombre: SEMAFOROS.rojo, valor: sem.rojo ?? 0, tono: "rojo" },
    { clave: "ambar", nombre: SEMAFOROS.ambar, valor: sem.ambar ?? 0, tono: "ambar" },
    { clave: "verde", nombre: SEMAFOROS.verde, valor: sem.verde ?? 0, tono: "verde" },
  ];

  return (
    <div className="dash">
      <Encabezado
        titulo="Dashboard de control"
        descripcion={`Vista priorizada para ${ROLES[rol] ?? rol}. Muestra únicamente la información dentro de tu alcance.`}
        acciones={rol === "abastecimiento" ? (
          <div className="acciones">
            <Link className="boton primario" href="/prevencion"><ScanSearch size={16} /> Evaluar proveedores</Link>
            <Link className="boton" href="/documentos"><FileSearch size={16} /> Revisión documental</Link>
          </div>
        ) : rol === "auditor" ? (
          <div className="acciones">
            <Link className="boton primario" href="/alertas?ambito=seguimiento_oci"><Bell size={16} /> Bandeja de alertas</Link>
            <Link className="boton" href="/integridad"><ShieldCheck size={16} /> Integridad y decisiones</Link>
          </div>
        ) : rol === "tesoreria" ? (
          <Link className="boton primario" href="/pagos"><Wallet size={16} /> Verificación y pagos</Link>
        ) : null}
      />

      {/* --- VISTA ABASTECIMIENTO (dec1 / dec2) --------------------------------------- */}
      {rol === "abastecimiento" && d.preventivo && <>
        <div className="dash-kpis">
          <Kpi
            titulo={d.preventivo.me_toca_revisar > 0 ? "Revisiones independientes para ti" : "Evaluaciones en curso"}
            valor={d.preventivo.me_toca_revisar > 0 ? d.preventivo.me_toca_revisar : d.preventivo.por_analizar}
            ayuda={d.preventivo.me_toca_revisar > 0
              ? "Esperan tu revisión independiente"
              : `${d.preventivo.en_revision_independiente} en revisión independiente · ${d.preventivo.aprobadas} aprobada(s)`}
            tono={d.preventivo.me_toca_revisar > 0 ? "ambar" : "neutro"}
            icono={<ScanSearch size={17} />}
            to="/prevencion"
          />
          <Kpi
            titulo="Postores no recomendados"
            valor={`${d.preventivo.postores_no_recomendados} / ${d.preventivo.postores_total}`}
            ayuda={Number(d.preventivo.monto_riesgo_evitado) > 0
              ? `Riesgo filtrado: ${soles(d.preventivo.monto_riesgo_evitado)}`
              : "Analiza y consolida los postores"}
            tono={d.preventivo.postores_no_recomendados > 0 ? "rojo" : "verde"}
            icono={<AlertTriangle size={17} />}
            to="/prevencion"
          />
          <Kpi
            titulo="Alertas escaladas a Auditoría"
            valor={d.alertas.abiertas}
            ayuda={`${d.alertas.altas} alta(s) · derivadas automáticamente`}
            tono={d.alertas.altas > 0 ? "rojo" : "ambar"}
            icono={<Bell size={17} />}
            to="/prevencion"
          />
          <Kpi
            titulo="Documentación con anomalías"
            valor={d.preventivo.documentos.anomalias}
            ayuda={`${d.preventivo.documentos.analizados} expediente(s) con análisis forense`}
            tono={d.preventivo.documentos.anomalias > 0 ? "rojo" : "verde"}
            icono={<FileSearch size={17} />}
            to="/documentos"
          />
        </div>

        <div className="dash-rejilla">
          <GraficoAnillo
            titulo="Veredicto de postores evaluados"
            subtitulo="Resultado consolidado tras las 6 dimensiones"
            segmentos={d.preventivo.veredictos_postores}
            totalEtiqueta="postores"
            enlace={["/prevencion", "Ver evaluaciones"]}
          />
          <EmbudoPreventivo etapas={d.preventivo.embudo} />
        </div>

        <div className="dash-rejilla">
          <GraficoBarras
            titulo="Riesgos detectados por dimensión"
            subtitulo="Hallazgos en alerta o por revisar acumulados"
            items={d.preventivo.hallazgos_por_dimension}
            tono="rojo"
            vacio="Analiza los posibles proveedores en un expediente para ver distribución por dimensión."
            enlace={["/prevencion", "Analizar"]}
          />
          <GraficoBenfordMini benford={d.benford} />
        </div>

        <div className="dash-rejilla">
          <CuadroEvaluaciones casos={d.preventivo.casos_prioritarios} esDec />
          <CuadroAlertas alertas={d.alertas} titulo="Señales escaladas a Auditoría" soloLectura />
        </div>
      </>}

      {/* --- VISTA AUDITORÍA E INTEGRIDAD (aud1 / oci1) ------------------------------- */}
      {rol === "auditor" && d.integridad && <>
        <div className="dash-kpis">
          <Kpi
            titulo="Conflictos bloqueantes"
            valor={d.integridad.conflictos_bloqueantes}
            ayuda={`${d.integridad.conflictos_total} conflicto(s) registrados`}
            tono={d.integridad.conflictos_bloqueantes > 0 ? "rojo" : "verde"}
            icono={<AlertTriangle size={17} />}
            to="/integridad"
          />
          <Kpi
            titulo="Revisiones independientes pendientes"
            valor={d.integridad.revisiones_pendientes}
            ayuda="Control de doble especialista (DEC)"
            tono={d.integridad.revisiones_pendientes > 0 ? "ambar" : "verde"}
            icono={<ScanSearch size={17} />}
            to="/prevencion"
          />
          <Kpi
            titulo="Alertas escaladas abiertas"
            valor={d.integridad.seguimiento_abierto}
            ayuda={`${d.integridad.actuaciones} decisión(es) en bitácora`}
            tono={d.integridad.seguimiento_abierto > 0 ? "rojo" : "verde"}
            icono={<Bell size={17} />}
            to="/alertas?ambito=seguimiento_oci"
          />
          <Kpi
            titulo="Integridad de bitácora"
            valor={d.integridad.cadena_integra ? "Íntegra" : "Alterada"}
            ayuda={`${d.integridad.registros_bitacora} registros encadenados (SHA-256)`}
            tono={d.integridad.cadena_integra ? "verde" : "rojo"}
            icono={<CheckCircle2 size={17} />}
            to="/bitacora"
          />
        </div>

        <div className="dash-rejilla">
          <GraficoAnillo
            titulo="Semáforo global de expedientes"
            subtitulo={`${d.resumen_general.expedientes} expedientes monitoreados`}
            segmentos={segmentosSemaforo}
            totalEtiqueta="expedientes"
            enlace={["/expedientes", "Ver expedientes"]}
          />
          <GraficoBenfordMini benford={d.benford} />
        </div>

        <div className="dash-rejilla">
          <GraficoBarras
            titulo="Alertas abiertas por tipo"
            subtitulo="Principales señales preventivas, documentales y operativas"
            items={d.alertas.por_regla}
            tono="ambar"
            enlace={["/alertas", "Bandeja de alertas"]}
          />
          {d.preventivo && (
            <GraficoAnillo
              titulo="Veredicto de postores evaluados"
              subtitulo="Filtro preventivo de la Unidad de Abastecimiento"
              segmentos={d.preventivo.veredictos_postores}
              totalEtiqueta="postores"
              enlace={["/prevencion", "Monitorear"]}
            />
          )}
        </div>

        <div className="dash-rejilla">
          {d.preventivo && <CuadroEvaluaciones casos={d.preventivo.casos_prioritarios} esDec={false} />}
          <CuadroAlertas alertas={d.alertas} titulo="Alertas prioritarias" />
        </div>
      </>}

      {/* --- VISTA TESORERÍA ---------------------------------------------------------- */}
      {rol === "tesoreria" && d.pagos && <>
        <div className="dash-kpis">
          <Kpi titulo="Listos para pagar" valor={d.pagos.listos} ayuda="6 de 6 controles conformes" tono="verde" icono={<Wallet size={17} />} to="/pagos?ver=listo" />
          <Kpi titulo="Órdenes bloqueadas" valor={d.pagos.bloqueados} ayuda="Falta al menos un control" tono="rojo" icono={<AlertTriangle size={17} />} to="/pagos?ver=bloqueado" />
          <Kpi titulo="Pagos registrados" valor={d.pagos.pagados} ayuda="Con verificación previa" tono="neutro" icono={<CheckCircle2 size={17} />} to="/pagos?ver=pagado" />
          <Kpi titulo="Alertas operativas" valor={d.alertas.abiertas} ayuda={`${d.alertas.altas} altas`} tono={d.alertas.altas > 0 ? "rojo" : "ambar"} icono={<Bell size={17} />} to="/alertas" />
        </div>
        <div className="dash-rejilla">
          <GraficoAnillo
            titulo="Estado de verificación de pagos"
            segmentos={[
              { clave: "listo", nombre: "Listos para pagar", valor: d.pagos.listos, tono: "verde" },
              { clave: "bloqueado", nombre: "Bloqueados", valor: d.pagos.bloqueados, tono: "rojo" },
              { clave: "pagado", nombre: "Pagados", valor: d.pagos.pagados, tono: "azul" },
            ]}
            totalEtiqueta="órdenes"
            enlace={["/pagos", "Ir a pagos"]}
          />
          <GraficoBarras
            titulo="Principales motivos de bloqueo"
            subtitulo="Controles que detienen el pago actualmente"
            items={d.pagos.por_motivo}
            tono="rojo"
          />
        </div>
        <div className="dash-rejilla">
          <GraficoBenfordMini benford={d.benford} />
          <CuadroAlertas alertas={d.alertas} titulo="Alertas operativas de pago" />
        </div>
      </>}

      {/* --- VISTA ÁREA USUARIA (acotada solo a su área) ------------------------------ */}
      {rol === "area_usuaria" && <>
        <div className="dash-kpis">
          <Kpi titulo="Expedientes de tu área" valor={d.resumen_general.expedientes} tono="neutro" to="/expedientes" />
          <Kpi titulo="Sin conformidad" valor={d.resumen_general.sin_conformidad} tono="ambar" to="/conformidad" />
          <Kpi titulo="Observaciones pendientes" valor={d.resumen_general.con_observaciones_pendientes} tono="ambar" to="/expedientes?ver=observadas" />
          <Kpi titulo="Alertas de tu área" valor={d.alertas.abiertas} tono={d.alertas.altas > 0 ? "rojo" : "neutro"} to="/alertas" />
        </div>
        <div className="dash-rejilla">
          <GraficoAnillo
            titulo="Semáforo de tus expedientes"
            segmentos={segmentosSemaforo}
            totalEtiqueta="expedientes"
            enlace={["/expedientes", "Ver expedientes"]}
          />
          <CuadroAlertas alertas={d.alertas} titulo="Alertas de tu área" />
        </div>
      </>}

      <TiraAdaptadores adaptadores={d.adaptadores} />
    </div>
  );
}
