"""La siembra completa (datos + alertas del motor) es reproducible."""
from sqlalchemy import text

from datos import generador
from scripts.sembrar import sembrar, vaciar
from tests.conftest import PASSWORD_PRUEBA


def _huella(sesion):
    conteos = sembrar(sesion, generador.generar(), PASSWORD_PRUEBA)
    ultimo = sesion.execute(text("SELECT hash FROM bitacora ORDER BY id DESC LIMIT 1")).scalar_one()
    return conteos, ultimo


def test_dos_siembras_dejan_la_misma_huella(sesion):
    primera = _huella(sesion)
    vaciar(sesion)
    segunda = _huella(sesion)
    assert primera == segunda
    assert primera[0]["alertas"] == primera[0]["anomalias"] == 28
