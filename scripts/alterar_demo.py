"""Altera (y restaura) un registro de la bitácora para mostrar "íntegra" → "alterada" en vivo.

Uso:  python -m scripts.alterar_demo               altera el registro de conformidad del caso estrella
      python -m scripts.alterar_demo --restaurar   devuelve el registro a su valor original
      python -m scripts.alterar_demo --si          no pregunta antes de alterar (uso en scripts)

Actúa sobre la base de DATABASE_URL. Antes de tocar nada muestra QUÉ base es (dev, test, demo)
y, para alterar, pide escribir su nombre. Guarda el valor original en `.alterar_demo.json`
(no se versiona). Es una herramienta de demostración: la aplicación nunca modifica registros.
"""
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from conforme import config, db
from datos import caso_estrella

ARCHIVO = Path(__file__).resolve().parent.parent / ".alterar_demo.json"


def etiqueta_de_base(url: str, demo: str | None = None, test: str | None = None) -> str:
    """«demo», «test» o «dev» según el servidor y la base de la URL (se compara contra las
    URL de DATABASE_URL_DEMO y DATABASE_URL_TEST; cualquier otra se considera «dev»)."""
    def clave(u):
        v = make_url(config.normalizar_url(u))
        return (v.host or "", v.database or "")

    actual = clave(url)
    if demo and clave(demo) == actual:
        return "demo"
    if test and clave(test) == actual:
        return "test"
    return "dev"


def describir_base() -> tuple[str, str]:
    """(etiqueta, «servidor/base») de la base a la que apunta DATABASE_URL."""
    url = config.url_base_datos()
    v = make_url(url)
    etiqueta = etiqueta_de_base(url, config.leer("DATABASE_URL_DEMO"),
                                config.leer("DATABASE_URL_TEST"))
    return etiqueta, f"{v.host}/{v.database}"


def confirmar(etiqueta: str, destino: str, sin_preguntar: bool) -> None:
    print(f"Base de datos destino: {etiqueta.upper()}  ({destino})")
    if sin_preguntar:
        return
    if not sys.stdin.isatty():
        sys.exit("No hay terminal interactiva: usa --si para confirmar sin preguntar.")
    escrito = input(f"Escribe «{etiqueta}» para alterar el registro, o Enter para cancelar: ")
    if escrito.strip().lower() != etiqueta:
        sys.exit("Cancelado: no se modificó nada.")


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
    etiqueta, destino = describir_base()
    restaurando = "--restaurar" in sys.argv
    if restaurando:
        print(f"Base de datos destino: {etiqueta.upper()}  ({destino})")
    else:
        confirmar(etiqueta, destino, "--si" in sys.argv)
    with db.sesion() as s:
        print(restaurar(s) if restaurando else alterar(s))
