from conforme.reglas import r4_misma_persona as r4
from tests.fabrica import SOLICITANTE, TESORERO, conformidad, foto, pago


def test_positivo_conformidad_y_pago_por_misma_persona():
    alertas = r4.evaluar(foto(conformidad=conformidad(conformante_id=TESORERO), pagos=(pago(),)))
    assert len(alertas) == 1
    assert alertas[0].regla == "R4"
    assert alertas[0].persona_implicada_id == TESORERO
    assert alertas[0].datos["pago_id"] == 1


def test_negativo_personas_distintas():
    assert r4.evaluar(foto(pagos=(pago(),))) == []


def test_negativo_solicitante_da_la_conformidad_en_ruta_dine():
    assert r4.evaluar(foto(conformidad=conformidad(conformante_id=SOLICITANTE))) == []


def test_borde_sin_conformidad_no_alerta():
    assert r4.evaluar(foto(conformidad=None)) == []
