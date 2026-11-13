"""Compara las alertas del motor con las anomalías sembradas.

Uso:  python -m scripts.medir_deteccion

Cobertura = anomalías sembradas que el motor detectó / anomalías sembradas.
Precisión = alertas que corresponden a una anomalía sembrada / alertas.
Se compara por pareja (expediente, regla). Los falsos positivos se listan.

Este script (y las pruebas) son lo único que lee las anomalías sembradas.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from conforme import db


def medir(sesion: Session) -> dict:
    sembradas = {
        (f.codigo, f.regla): f.nota
        for f in sesion.execute(text(
            "SELECT e.codigo, a.regla, a.nota FROM anomalia_sembrada a "
            "JOIN expediente e ON e.id = a.expediente_id"))
    }
    alertas = {
        (f.codigo, f.regla): f.explicacion
        for f in sesion.execute(text(
            "SELECT e.codigo, a.regla, a.explicacion FROM alerta a "
            "JOIN expediente e ON e.id = a.expediente_id ORDER BY a.id"))
    }
    detectadas = sembradas.keys() & alertas.keys()
    return {
        "sembradas": len(sembradas),
        "alertas": len(alertas),
        "detectadas": len(detectadas),
        "no_detectadas": sorted((c, r, sembradas[c, r]) for c, r in sembradas.keys() - detectadas),
        "falsos_positivos": sorted((c, r, alertas[c, r]) for c, r in alertas.keys() - detectadas),
        "por_regla": {
            regla: (sum(1 for _, r in detectadas if r == regla),
                    sum(1 for _, r in sembradas if r == regla))
            for regla in sorted({r for _, r in sembradas})
        },
    }


def _porcentaje(parte: int, total: int) -> str:
    return f"{parte}/{total} ({100 * parte / total:.1f} %)" if total else "sin datos"


if __name__ == "__main__":
    with db.sesion() as s:
        m = medir(s)
    print(f"Anomalías sembradas (expediente, regla): {m['sembradas']}")
    print(f"Alertas del motor (expediente, regla):   {m['alertas']}")
    print(f"Cobertura: {_porcentaje(m['detectadas'], m['sembradas'])}")
    print(f"Precisión: {_porcentaje(m['detectadas'], m['alertas'])}")
    for regla, (detectadas, sembradas) in m["por_regla"].items():
        print(f"  {regla}: {detectadas}/{sembradas}")
    print(f"No detectadas: {len(m['no_detectadas'])}")
    for codigo, regla, nota in m["no_detectadas"]:
        print(f"  {codigo} {regla}: {nota}")
    print(f"Falsos positivos: {len(m['falsos_positivos'])}")
    for codigo, regla, explicacion in m["falsos_positivos"]:
        print(f"  {codigo} {regla}: {explicacion}")
