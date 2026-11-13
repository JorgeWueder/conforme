"""El expediente de referencia de la fábrica no debe activar ninguna regla."""
from conforme.reglas import motor
from tests.fabrica import foto


def test_expediente_limpio_no_alerta():
    assert motor.evaluar(foto()) == []


def test_sin_conformidad_ni_pagos_no_alerta():
    assert motor.evaluar(foto(conformidad=None)) == []
