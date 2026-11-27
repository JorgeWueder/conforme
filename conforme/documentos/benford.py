"""Ley de Benford sobre el primer dígito de un conjunto de montos. Función pura.

En muchos conjuntos de montos reales el primer dígito sigue P(d) = log10(1 + 1/d): el 1
aparece ~30 % de las veces y el 9 menos del 5 %. Montos inventados a mano suelen alejarse.
Es una señal estadística para priorizar la revisión, nunca una prueba de fraude.

La conformidad se mide con la desviación absoluta media (MAD) de Nigrini, que no depende
del tamaño de la muestra como el chi-cuadrado.
"""
import math
from collections import Counter
from decimal import Decimal

from conforme import normativa

ESPERADO = {d: math.log10(1 + 1 / d) for d in range(1, 10)}
NIVELES = {
    "conforme": "Se ajusta a Benford",
    "aceptable": "Ajuste aceptable",
    "marginal": "Desviación marginal",
    "anomalia": "Desviación fuerte",
    "insuficiente": "Muestra insuficiente",
}


def primer_digito(monto) -> int | None:
    valor = abs(Decimal(str(monto)))
    if valor < 1:
        return None
    return int(str(valor.normalize()).lstrip("0.")[0]) if valor else None


def analizar(montos: list[tuple[str, Decimal]]) -> dict:
    """`montos`: (etiqueta, monto). Devuelve la distribución y su interpretación."""
    validos = [(etiqueta, Decimal(str(m))) for etiqueta, m in montos if m is not None and Decimal(str(m)) >= 1]
    n = len(validos)
    conteo = Counter(primer_digito(m) for _, m in validos)
    observado = {d: (conteo[d] / n if n else 0.0) for d in range(1, 10)}
    distribucion = [{"digito": d, "esperado": round(ESPERADO[d], 4), "observado": round(observado[d], 4),
                     "cantidad": conteo[d]} for d in range(1, 10)]
    rango = (float(max(m for _, m in validos)) / float(min(m for _, m in validos))) if n else 0.0
    suficiente = n >= normativa.BENFORD_MUESTRA_MINIMA and rango >= normativa.BENFORD_RANGO_MINIMO
    mad = sum(abs(observado[d] - ESPERADO[d]) for d in range(1, 10)) / 9 if n else None
    chi2 = sum((conteo[d] - n * ESPERADO[d]) ** 2 / (n * ESPERADO[d]) for d in range(1, 10)) if n else None
    if not suficiente:
        nivel = "insuficiente"
        motivo = (f"Solo hay {n} monto(s)" if n < normativa.BENFORD_MUESTRA_MINIMA
                  else f"Los montos varían poco (el mayor es {rango:.0f} veces el menor)")
        lectura = (f"{motivo}. Benford necesita al menos {normativa.BENFORD_MUESTRA_MINIMA} montos que abarquen "
                   "varios órdenes de magnitud: no se saca conclusión estadística.")
    else:
        if mad < normativa.BENFORD_MAD_CONFORME:
            nivel = "conforme"
        elif mad < normativa.BENFORD_MAD_ACEPTABLE:
            nivel = "aceptable"
        elif mad < normativa.BENFORD_MAD_MARGINAL:
            nivel = "marginal"
        else:
            nivel = "anomalia"
        lectura = {
            "conforme": "La distribución de primeros dígitos es la esperada. No hay señal estadística.",
            "aceptable": "Pequeñas diferencias normales en datos reales. No requiere acción.",
            "marginal": "Hay diferencias que conviene mirar: revisa las partidas señaladas.",
            "anomalia": "La distribución se aleja mucho de lo esperado: revisa a fondo las partidas señaladas.",
        }[nivel]
    # Dígitos sobrerrepresentados y las partidas que los llevan.
    sobre = [d for d in range(1, 10)
             if suficiente and observado[d] - ESPERADO[d] >= normativa.BENFORD_EXCESO_DIGITO]
    sospechosas = []
    if suficiente and nivel in ("marginal", "anomalia"):
        sospechosas = [{"etiqueta": e, "monto": str(m), "motivo": f"Empieza por {primer_digito(m)}, dígito en exceso"}
                       for e, m in validos if primer_digito(m) in sobre]
    repetidos = Counter(m for _, m in validos)
    for monto, veces in repetidos.items():
        if veces >= 3 and n >= 10:
            sospechosas.append({"etiqueta": f"{veces} montos idénticos", "monto": str(monto),
                                "motivo": "El mismo monto exacto se repite"})
    return {
        "total_montos": n, "muestra_suficiente": suficiente, "rango": round(rango, 1),
        "distribucion": distribucion, "mad": round(mad, 4) if mad is not None else None,
        "chi_cuadrado": round(chi2, 2) if chi2 is not None else None,
        "nivel": nivel, "titulo": NIVELES[nivel], "lectura": lectura,
        "digitos_en_exceso": sobre, "partidas_sospechosas": sospechosas[:25],
    }
