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
