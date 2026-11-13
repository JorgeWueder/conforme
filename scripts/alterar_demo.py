"""Altera (y restaura) un registro de la bitácora para mostrar "íntegra" → "alterada" en vivo.

Uso:  python -m scripts.alterar_demo               altera el registro de conformidad del caso estrella
      python -m scripts.alterar_demo --restaurar   devuelve el registro a su valor original

Actúa sobre la base de DATABASE_URL. Guarda el valor original en `.alterar_demo.json`
(no se versiona). Es una herramienta de demostración: la aplicación nunca modifica registros.
"""
import json
import sys
from pathlib import Path

from sqlalchemy import text

from conforme import db
from datos import caso_estrella

ARCHIVO = Path(__file__).resolve().parent.parent / ".alterar_demo.json"


def alterar(sesion) -> str:
    if ARCHIVO.exists():
        sys.exit("Ya hay un registro alterado. Restáuralo primero con --restaurar.")
    fila = sesion.execute(text(
        "SELECT b.id, b.detalle, c.codigo_sello FROM bitacora b "
        "JOIN expediente e ON e.id = b.expediente_id "
        "JOIN conformidad c ON c.expediente_id = e.id "
        "WHERE e.codigo = :codigo AND b.accion = 'conformidad.registrada'"
    ), {"codigo": caso_estrella.CODIGO}).first()
    if fila is None:
        sys.exit(f"No se encontró la conformidad de {caso_estrella.CODIGO}. ¿Sembraste la base?")
    ARCHIVO.write_text(json.dumps({"id": fila.id, "detalle": fila.detalle}), encoding="utf-8")
    sesion.execute(
        text("UPDATE bitacora SET detalle = jsonb_set(detalle, '{penalidad_aplicada}', "
             "'\"3200.00\"') WHERE id = :id"),
        {"id": fila.id},
    )
    return f"Registro n.º {fila.id} alterado (penalidad aplicada pasó a 3200.00). Sello: {fila.codigo_sello}"


def restaurar(sesion) -> str:
    if not ARCHIVO.exists():
        sys.exit("No hay nada que restaurar (no existe .alterar_demo.json).")
    guardado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    sesion.execute(
        text("UPDATE bitacora SET detalle = CAST(:detalle AS jsonb) WHERE id = :id"),
        {"id": guardado["id"], "detalle": json.dumps(guardado["detalle"])},
    )
    ARCHIVO.unlink()
    return f"Registro n.º {guardado['id']} restaurado."


if __name__ == "__main__":
    with db.sesion() as s:
        print(restaurar(s) if "--restaurar" in sys.argv else alterar(s))
