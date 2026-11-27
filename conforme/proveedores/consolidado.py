"""Informe consolidado de un postor: cruza las seis dimensiones. Función pura.

Veredictos:
- «apto»: ninguna dimensión con observaciones.
- «apto_con_observaciones»: hay puntos por revisar o una alerta que no impide contratar;
  se puede seleccionar, pero el sustento debe explicar cómo se atendieron.
- «no_recomendado»: hay un impedimento (inhabilitación, RUC no activo o no habido,
  vínculo con un funcionario de la compra), dos o más alertas, o un riesgo combinado
  grave. El sistema no permite seleccionarlo.
"""
from conforme.proveedores.dimensiones import ALERTA, DIMENSIONES, LIMPIO, REVISAR

VEREDICTOS = {
    "apto": "Apto",
    "apto_con_observaciones": "Apto con observaciones",
    "no_recomendado": "No recomendado",
}


def _tiene(dimension: dict, marca: str) -> bool:
    return any(h.get(marca) for h in dimension["hallazgos"])


def consolidar(dimensiones: dict[str, dict]) -> dict:
    faltan = [DIMENSIONES[c] for c in DIMENSIONES if c not in dimensiones]
    if faltan:
        raise ValueError("Faltan dimensiones por analizar: " + ", ".join(faltan))
    estados = {clave: d["estado"] for clave, d in dimensiones.items()}
    conteo = {nivel: sum(1 for e in estados.values() if e == nivel) for nivel in (ALERTA, REVISAR, LIMPIO)}
    impedimentos = [h["que"] for d in dimensiones.values() for h in d["hallazgos"] if h.get("impide")]

    riesgos = []
    reciente = _tiene(dimensiones["empresa"], "reciente")
    personas = estados["personas"] != LIMPIO
    precio_atipico = _tiene(dimensiones["precio"], "precio_atipico")
    if reciente and personas:
        riesgos.append({"titulo": "Empresa recién creada con personas vinculadas",
                        "detalle": "Una empresa nueva cuyas personas se cruzan con la compra u otros postores "
                                   "es el patrón típico de una empresa creada para la ocasión.", "grave": True})
    if reciente and precio_atipico:
        riesgos.append({"titulo": "Empresa recién creada con precio atípico",
                        "detalle": "Sin trayectoria y con un precio muy distinto al estimado: riesgo alto de incumplimiento.",
                        "grave": False})
    if estados["colusion"] == ALERTA and estados["personas"] == ALERTA:
        riesgos.append({"titulo": "Posible falsa competencia",
                        "detalle": "Comparte datos de contacto y personas con otro postor: las cotizaciones "
                                   "no reflejan una competencia real.", "grave": True})
    if _tiene(dimensiones["empresa"], "rubro_distinto") and precio_atipico:
        riesgos.append({"titulo": "Rubro distinto y precio atípico",
                        "detalle": "No se dedica a este tipo de prestación y su precio se aleja del estimado.",
                        "grave": False})

    if impedimentos or conteo[ALERTA] >= 2 or any(r["grave"] for r in riesgos):
        veredicto = "no_recomendado"
        if impedimentos:
            motivo = f"Impedimento para contratar. {impedimentos[0]}."
        elif any(r["grave"] for r in riesgos):
            motivo = next(r["titulo"] for r in riesgos if r["grave"]) + "."
        else:
            motivo = f"Tiene alertas en {conteo[ALERTA]} dimensiones."
    elif conteo[ALERTA] or conteo[REVISAR]:
        veredicto = "apto_con_observaciones"
        motivo = (f"{conteo[ALERTA] + conteo[REVISAR]} dimensión(es) con puntos por revisar: "
                  "explica en el sustento cómo se atendieron.")
    else:
        veredicto = "apto"
        motivo = "Las seis dimensiones están limpias."
    return {
        "veredicto": veredicto,
        "titulo": VEREDICTOS[veredicto],
        "motivo": motivo,
        "conteo": conteo,
        "riesgos_combinados": riesgos,
        "impedimentos": impedimentos,
        "dimensiones": {clave: {"estado": d["estado"], "resumen": d["resumen"]} for clave, d in dimensiones.items()},
    }
