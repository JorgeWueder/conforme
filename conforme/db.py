"""Engine único y sesiones cortas.

El engine vive en una variable de módulo: Streamlit reejecuta el script en cada
interacción, pero no vuelve a importar los módulos, así que no se abren
conexiones nuevas en cada rerun.
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from conforme import config

_engine: Engine | None = None


def crear_engine(url: str) -> Engine:
    return create_engine(
        config.normalizar_url(url),
        pool_pre_ping=True,  # Neon suspende la base por inactividad
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
    )


def obtener_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = crear_engine(config.url_base_datos())
    return _engine


@contextmanager
def sesion():
    """Sesión que confirma al salir sin error y revierte si hay excepción."""
    with Session(obtener_engine()) as s:
        with s.begin():
            yield s
