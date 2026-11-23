from datetime import date, timedelta

from conforme.reglas import r8_fechas_incoherentes as r8
from tests.fabrica import CONFORMANTE, SOLICITANTE, TESORERO, conformidad, foto, pago

# foto() por defecto: orden 3 ago, entrega 17 sep, conformidad 18 sep.
ORDEN, ENTREGA = date(2026, 8, 3), date(2026, 9, 17)


def _claves(alertas):
    return sorted(a.clave for a in alertas)


def test_expediente_coherente_no_alerta():
    assert r8.evaluar(foto()) == []
    coherente = foto(fecha_requerimiento=date(2026, 7, 20), fecha_inicio_prestacion=date(2026, 8, 4),
                     pagos=(pago(fecha=date(2026, 9, 30)),))
    assert r8.evaluar(coherente) == []


def test_borde_fechas_iguales_no_alertan():
    iguales = foto(fecha_requerimiento=ORDEN, fecha_inicio_prestacion=ENTREGA,
                   conformidad=conformidad(fecha=ENTREGA), pagos=(pago(fecha=ORDEN),))
    assert r8.evaluar(iguales) == []


def test_sin_entrega_ni_conformidad_solo_se_revisan_requerimiento_y_pagos():
    assert r8.evaluar(foto(fecha_entrega_real=None, conformidad=None,
                           fecha_inicio_prestacion=date(2030, 1, 1))) == []


def test_orden_antes_del_requerimiento():
    alertas = r8.evaluar(foto(fecha_requerimiento=ORDEN + timedelta(days=2)))
    assert _claves(alertas) == ["orden-antes-de-requerimiento"]
    assert alertas[0].regla == "R8" and alertas[0].persona_implicada_id == SOLICITANTE
    assert "la orden figura antes de que se pidiera" in alertas[0].explicacion
    assert alertas[0].datos == {"fecha_orden": "2026-08-03", "fecha_requerimiento": "2026-08-05"}


def test_entrega_antes_de_la_orden():
    alertas = r8.evaluar(foto(fecha_entrega_real=ORDEN - timedelta(days=1),
                              conformidad=conformidad(fecha=ORDEN)))
    assert _claves(alertas) == ["entrega-antes-de-orden"]
    assert alertas[0].persona_implicada_id == CONFORMANTE
    assert "se entregó antes de que existiera la orden" in alertas[0].explicacion


def test_entrega_antes_del_inicio_de_la_prestacion():
    alertas = r8.evaluar(foto(fecha_inicio_prestacion=ENTREGA + timedelta(days=2)))
    assert _claves(alertas) == ["entrega-antes-de-inicio"]
    assert alertas[0].persona_implicada_id == CONFORMANTE
    assert "se entregó antes de empezar" in alertas[0].explicacion


def test_conformidad_antes_de_la_entrega():
    alertas = r8.evaluar(foto(conformidad=conformidad(fecha=ENTREGA - timedelta(days=2))))
    assert _claves(alertas) == ["conformidad-antes-de-entrega"]
    assert alertas[0].persona_implicada_id == CONFORMANTE
    assert "se dio conformidad antes de recibir" in alertas[0].explicacion
    assert alertas[0].datos == {"fecha_conformidad": "2026-09-15", "fecha_entrega_real": "2026-09-17"}


def test_pago_antes_de_la_orden_una_alerta_por_pago():
    alertas = r8.evaluar(foto(pagos=(pago(id=4, fecha=ORDEN - timedelta(days=3)),
                                     pago(id=5, fecha=date(2026, 9, 30)),
                                     pago(id=6, fecha=ORDEN - timedelta(days=1)))))
    assert _claves(alertas) == ["pago-antes-de-orden-4", "pago-antes-de-orden-6"]
    assert {a.persona_implicada_id for a in alertas} == {TESORERO}


def test_pago_anterior_a_la_conformidad_pero_posterior_a_la_orden_es_de_r5_no_de_r8():
    assert r8.evaluar(foto(pagos=(pago(fecha=date(2026, 9, 1)),))) == []


def test_varias_incoherencias_dan_una_alerta_por_tipo():
    alertas = r8.evaluar(foto(
        fecha_requerimiento=ORDEN + timedelta(days=1),
        fecha_inicio_prestacion=ENTREGA + timedelta(days=1),
        conformidad=conformidad(fecha=ENTREGA - timedelta(days=1)),
    ))
    assert _claves(alertas) == ["conformidad-antes-de-entrega", "entrega-antes-de-inicio",
                                "orden-antes-de-requerimiento"]
    assert len({a.clave for a in alertas}) == len(alertas)
