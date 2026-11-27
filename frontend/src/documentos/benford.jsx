"use client";

import { useState } from "react";
import { Indicador } from "../ui";

const TONO = { conforme: "verde", aceptable: "verde", marginal: "ambar", anomalia: "rojo", insuficiente: "neutro" };
const pct = (valor) => `${(valor * 100).toFixed(1)} %`;

/** Primer dígito: barras = observado; marca = esperado según Benford. Una sola escala. */
export function GraficaBenford({ resultado, titulo = "Primer dígito de los montos" }) {
  const [activo, setActivo] = useState(null);
  const ancho = 640;
  const alto = 250;
  const margen = { arriba: 16, derecha: 12, abajo: 34, izquierda: 44 };
  const zonaAncho = ancho - margen.izquierda - margen.derecha;
  const zonaAlto = alto - margen.arriba - margen.abajo;
  const datos = resultado.distribucion;
  const maximo = Math.max(0.35, ...datos.map((d) => d.observado), ...datos.map((d) => d.esperado));
  const tope = Math.ceil(maximo * 10) / 10;
  const y = (v) => margen.arriba + zonaAlto - (v / tope) * zonaAlto;
  const paso = zonaAncho / datos.length;
  const anchoBarra = Math.min(34, paso * 0.55);
  const lineas = Array.from({ length: Math.round(tope * 10) + 1 }, (_, i) => i / 10);
  const elegido = datos.find((d) => d.digito === activo);
  return (
    <figure className="benford">
      <figcaption>
        <strong>{titulo}</strong>
        <span className="benford-leyenda" aria-hidden="true">
          <span><i className="muestra muestra-observado" /> Observado</span>
          <span><i className="muestra muestra-esperado" /> Esperado (Benford)</span>
        </span>
      </figcaption>
      <div className="benford-lienzo">
        <svg viewBox={`0 0 ${ancho} ${alto}`} role="img"
          aria-label={`${titulo}. ${resultado.titulo}. ${resultado.total_montos} montos analizados.`}
          onMouseLeave={() => setActivo(null)}>
          {lineas.map((v) => (
            <g key={v}>
              <line x1={margen.izquierda} x2={ancho - margen.derecha} y1={y(v)} y2={y(v)} className="benford-rejilla" />
              <text x={margen.izquierda - 8} y={y(v) + 4} textAnchor="end" className="benford-eje">{Math.round(v * 100)} %</text>
            </g>
          ))}
          {datos.map((d, i) => {
            const centro = margen.izquierda + paso * i + paso / 2;
            const altoBarra = Math.max(0, y(0) - y(d.observado));
            const exceso = resultado.digitos_en_exceso?.includes(d.digito);
            return (
              <g key={d.digito} onMouseEnter={() => setActivo(d.digito)} onFocus={() => setActivo(d.digito)}
                onBlur={() => setActivo(null)} tabIndex={0}
                aria-label={`Dígito ${d.digito}: observado ${pct(d.observado)}, esperado ${pct(d.esperado)}`}>
                <rect x={centro - paso / 2} y={margen.arriba} width={paso} height={zonaAlto} className="benford-zona" />
                {altoBarra > 0 && <path className={`benford-barra ${exceso ? "benford-barra-exceso" : ""}`}
                  d={`M${centro - anchoBarra / 2},${y(0)} V${y(0) - altoBarra + 4} q0,-4 4,-4 H${centro + anchoBarra / 2 - 4} q4,0 4,4 V${y(0)} Z`} />}
                <line x1={centro - anchoBarra / 2 - 6} x2={centro + anchoBarra / 2 + 6} y1={y(d.esperado)} y2={y(d.esperado)}
                  className="benford-esperado" />
                <circle cx={centro} cy={y(d.esperado)} r={4} className="benford-esperado-punto" />
                <text x={centro} y={alto - 12} textAnchor="middle" className="benford-eje benford-digito">{d.digito}</text>
              </g>
            );
          })}
          <line x1={margen.izquierda} x2={ancho - margen.derecha} y1={y(0)} y2={y(0)} className="benford-base" />
        </svg>
        {elegido && <div className="benford-tooltip" role="status">
          <strong>Dígito {elegido.digito}</strong>
          <span>Observado: {pct(elegido.observado)} ({elegido.cantidad} montos)</span>
          <span>Esperado: {pct(elegido.esperado)}</span>
        </div>}
      </div>
      <details className="benford-tabla">
        <summary>Ver como tabla</summary>
        <table>
          <thead><tr><th scope="col">Dígito</th><th scope="col">Montos</th><th scope="col">Observado</th><th scope="col">Esperado</th></tr></thead>
          <tbody>{datos.map((d) => (
            <tr key={d.digito}><td>{d.digito}</td><td>{d.cantidad}</td><td>{pct(d.observado)}</td><td>{pct(d.esperado)}</td></tr>
          ))}</tbody>
        </table>
      </details>
    </figure>
  );
}

/** Veredicto de Benford en lenguaje claro, con la gráfica y las partidas a revisar. */
export function ResultadoBenford({ resultado, titulo }) {
  return (
    <div className="resultado-benford">
      <div className="fila-titulo">
        <p><Indicador tono={TONO[resultado.nivel]}>{resultado.titulo}</Indicador></p>
        <small>{resultado.total_montos} montos
          {resultado.mad != null && resultado.muestra_suficiente && ` · desviación media (MAD) ${resultado.mad.toFixed(4)}`}</small>
      </div>
      <p>{resultado.lectura}</p>
      {resultado.total_montos > 0 && <GraficaBenford resultado={resultado} titulo={titulo} />}
      {resultado.partidas_sospechosas?.length > 0 && <div>
        <h4>Montos para revisar</h4>
        <ul className="lista-simple">{resultado.partidas_sospechosas.map((p, i) => (
          <li key={i}><strong>{p.etiqueta}</strong> · S/ {Number(p.monto).toLocaleString("en-US", { minimumFractionDigits: 2 })} · {p.motivo}</li>
        ))}</ul>
      </div>}
      <small className="secundario">Benford es una señal estadística para priorizar la revisión; no prueba por sí sola un fraude.</small>
    </div>
  );
}
