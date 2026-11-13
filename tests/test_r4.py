from conforme.reglas import r4_misma_persona as r4
from tests.fabrica import SOLICITANTE, conformidad, foto


def test_positivo_solicitante_da_la_conformidad():
    alertas = r4.evaluar(foto(conformidad=conformidad(conformante_id=SOLICITANTE)))
    assert len(alertas) == 1
    assert alertas[0].regla == "R4"
    assert alertas[0].persona_implicada_id == SOLICITANTE
    assert "Ana Pérez Soto figura como solicitante" in alertas[0].explicacion


def test_negativo_personas_distintas():
    assert r4.evaluar(foto()) == []


def test_borde_sin_conformidad_no_alerta():
    assert r4.evaluar(foto(conformidad=None)) == []
