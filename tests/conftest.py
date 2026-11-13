"""Fixtures de pruebas.

Las pruebas con base usan DATABASE_URL_TEST y BORRAN su esquema: debe ser una
base dedicada. Sin esa variable, esas pruebas se omiten (no se dan por buenas).
"""
import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from conforme import db, migraciones
from datos import generador
from scripts.sembrar import sembrar, vaciar

load_dotenv()
URL_TEST = os.environ.get("DATABASE_URL_TEST")
PASSWORD_PRUEBA = "clave-de-prueba"


@pytest.fixture(scope="session")
def engine():
    if not URL_TEST:
        pytest.skip("Sin DATABASE_URL_TEST: se omiten las pruebas con base de datos.")
    if URL_TEST == os.environ.get("DATABASE_URL"):
        pytest.exit("DATABASE_URL_TEST no puede ser la misma base que DATABASE_URL.")
    eng = db.crear_engine(URL_TEST)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    migraciones.aplicar(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def sesion(engine):
    """Sesión sobre una base con tablas vacías."""
    with Session(engine) as s:
        vaciar(s)
        s.commit()
        yield s
        s.rollback()


@pytest.fixture(scope="module")
def base_sembrada(engine):
    with Session(engine) as s:
        vaciar(s)
        sembrar(s, generador.generar(), PASSWORD_PRUEBA)
        s.commit()


@pytest.fixture
def sesion_sembrada(engine, base_sembrada):
    """Sesión sobre los datos sintéticos completos (solo lectura en las pruebas)."""
    with Session(engine) as s:
        yield s
        s.rollback()


def actor_de(sesion, username):
    """Actor autenticado con la contraseña de prueba."""
    from conforme import auth

    actor = auth.autenticar(sesion, username, PASSWORD_PRUEBA)
    assert actor is not None, username
    return actor


@pytest.fixture(autouse=True)
def _sin_cache_de_verificacion(monkeypatch):
    """La verificación pública reutiliza resultados unos segundos; las pruebas necesitan que
    cada llamada recalcule (salvo las de test_verificacion_cache.py, que lo fijan a mano)."""
    from conforme import bitacora

    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 0.0)
    monkeypatch.setattr(bitacora, "INTERVALO_MINIMO_FORZADO", 0.0)
    bitacora._cache.update(clave=None, momento=0.0, resultado=None)


@pytest.fixture(autouse=True)
def _sin_ia_real(monkeypatch):
    """Ninguna prueba debe llamar a un modelo de pago, aunque el .env tenga claves: los
    tests que necesitan un proveedor lo simulan con monkeypatch."""
    for nombre in ("LLM_PROVIDER", "LLM_MODEL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(nombre, raising=False)
