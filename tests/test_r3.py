from datetime import date, timedelta

from conforme import normativa
from conforme.reglas import r3_conformidad_tardia as r3
from tests.fabrica import conformidad, foto

ENTREGA = date(2026, 9, 17)
MAXIMO = normativa.CONFORMIDAD_PLAZO_MAXIMO_DIAS


def _con_conformidad_a(dias):
    return r3.evaluar(foto(fecha_entrega_real=ENTREGA,
                           conformidad=conformidad(ENTREGA + timedelta(days=dias))))


def test_positivo_conformidad_muy_posterior():
    alertas = _con_conformidad_a(MAXIMO + 13)
    assert len(alertas) == 1
    assert alertas[0].regla == "R3"
    assert alertas[0].datos == {"dias_transcurridos": MAXIMO + 13, "dias_maximo": MAXIMO}
    assert "13 días de exceso" in alertas[0].explicacion


def test_negativo_conformidad_el_mismo_dia():
    assert _con_conformidad_a(0) == []


def test_borde_justo_en_el_maximo_y_un_dia_despues():
    assert _con_conformidad_a(MAXIMO) == []
    alertas = _con_conformidad_a(MAXIMO + 1)
    assert len(alertas) == 1
    assert "1 día de exceso" in alertas[0].explicacion


def test_borde_sin_conformidad_o_sin_entrega_no_alerta():
    assert r3.evaluar(foto(conformidad=None)) == []
    assert r3.evaluar(foto(fecha_entrega_real=None)) == []
