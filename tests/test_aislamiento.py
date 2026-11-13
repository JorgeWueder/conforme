"""Las anomalías sembradas son la "respuesta correcta" para medir la detección.
Si la aplicación pudiera leerlas, la medición no valdría nada."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROHIBIDO = ("anomalia_sembrada", "AnomaliaSembrada", "anomalias_sembradas")


def test_nada_dentro_de_conforme_ni_de_las_paginas_menciona_las_anomalias_sembradas():
    archivos = [*(RAIZ / "conforme").rglob("*.py"), *(RAIZ / "paginas").rglob("*.py"),
                RAIZ / "app.py"]
    assert len(archivos) > 15
    culpables = [str(a.relative_to(RAIZ)) for a in archivos
                 if any(p in a.read_text(encoding="utf-8") for p in PROHIBIDO)]
    assert culpables == []
