"""Migraciones simples: aplica en orden los archivos migraciones/NNN_*.sql.

Cada archivo se aplica una sola vez y queda anotado en `migracion_aplicada`.
"""
from pathlib import Path

from sqlalchemy.engine import Engine

CARPETA = Path(__file__).resolve().parent.parent / "migraciones"


def aplicar(engine: Engine, carpeta: Path = CARPETA) -> list[str]:
    """Aplica las migraciones pendientes y devuelve sus nombres."""
    aplicadas_ahora: list[str] = []
    conexion = engine.raw_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS migracion_aplicada ("
            " nombre TEXT PRIMARY KEY,"
            " aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        conexion.commit()
        cursor.execute("SELECT nombre FROM migracion_aplicada")
        ya_aplicadas = {fila[0] for fila in cursor.fetchall()}
        conexion.commit()

        for archivo in sorted(carpeta.glob("*.sql")):
            if archivo.name in ya_aplicadas:
                continue
            # Sin parámetros, psycopg admite varias sentencias en una llamada.
            cursor.execute(archivo.read_text(encoding="utf-8"))
            cursor.execute(
                "INSERT INTO migracion_aplicada (nombre) VALUES (%s)", (archivo.name,)
            )
            conexion.commit()  # cada migración es una transacción
            aplicadas_ahora.append(archivo.name)
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
    return aplicadas_ahora
