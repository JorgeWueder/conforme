from datetime import date

from conforme.reglas import r5_pago_sin_conformidad as r5
from tests.fabrica import TESORERO, conformidad, foto, pago

CONFORMIDAD = date(2026, 9, 18)


def test_positivo_pago_sin_conformidad():
    alertas = r5.evaluar(foto(conformidad=None, pagos=(pago(7),)))
    assert len(alertas) == 1
    assert alertas[0].regla == "R5"
    assert alertas[0].clave == "pago-7"
    assert alertas[0].persona_implicada_id == TESORERO
    assert "no tiene conformidad registrada" in alertas[0].explicacion


def test_positivo_conformidad_posterior_al_pago():
    alertas = r5.evaluar(foto(conformidad=conformidad(CONFORMIDAD),
                              pagos=(pago(7, date(2026, 9, 15)),)))
    assert len(alertas) == 1
    assert "3 días después del pago" in alertas[0].explicacion


def test_negativo_pago_posterior_a_la_conformidad():
    assert r5.evaluar(foto(conformidad=conformidad(CONFORMIDAD),
                           pagos=(pago(7, date(2026, 9, 30)),))) == []


def test_negativo_sin_pagos():
    assert r5.evaluar(foto(conformidad=None)) == []


def test_borde_pago_el_mismo_dia_de_la_conformidad_no_alerta():
    assert r5.evaluar(foto(conformidad=conformidad(CONFORMIDAD),
                           pagos=(pago(7, CONFORMIDAD),))) == []


def test_borde_cada_pago_irregular_tiene_su_alerta():
    alertas = r5.evaluar(foto(conformidad=conformidad(CONFORMIDAD), pagos=(
        pago(7, date(2026, 9, 10)), pago(8, date(2026, 9, 30)), pago(9, date(2026, 9, 12)))))
    assert [a.clave for a in alertas] == ["pago-7", "pago-9"]
