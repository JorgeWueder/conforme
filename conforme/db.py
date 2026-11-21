"""Pool de conexiones compartido y sesiones cortas por operación."""
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from conforme import config

_engine: Engine | None = None
_inicio_engine = Lock()


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
        with _inicio_engine:
            if _engine is None:
                _engine = crear_engine(config.url_base_datos())
    return _engine


@contextmanager
def sesion():
    """Sesión que confirma al salir sin error y revierte si hay excepción."""
    with Session(obtener_engine()) as s:
        with s.begin():
            yield s
