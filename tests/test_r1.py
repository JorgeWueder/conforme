from conforme.reglas import r1_sin_evidencia as r1
from tests.fabrica import CONFORMANTE, entregable, foto


def test_positivo_un_entregable_cumplido_sin_evidencia():
    alertas = r1.evaluar(foto(entregables=(entregable(1), entregable(2, n_evidencias=0))))
    assert len(alertas) == 1
    assert alertas[0].regla == "R1"
    assert alertas[0].datos["sin_evidencia"] == [2]
    assert alertas[0].persona_implicada_id == CONFORMANTE
    assert "1 de 2 entregables" in alertas[0].explicacion
    assert "n.º 2" in alertas[0].explicacion


def test_varios_sin_evidencia_dan_una_sola_alerta():
    alertas = r1.evaluar(foto(entregables=(entregable(1, n_evidencias=0),
                                           entregable(2, n_evidencias=0))))
    assert len(alertas) == 1
    assert alertas[0].datos["sin_evidencia"] == [1, 2]


def test_negativo_todos_con_evidencia():
    assert r1.evaluar(foto()) == []


def test_borde_no_cumplido_sin_evidencia_no_alerta():
    # Declarar que algo NO se cumplió no requiere evidencia.
    assert r1.evaluar(foto(entregables=(entregable(1),
                                        entregable(2, cumplido=False, n_evidencias=0)))) == []


def test_borde_sin_conformidad_no_alerta():
    sin_marcar = (entregable(1, cumplido=None, n_evidencias=0),)
    assert r1.evaluar(foto(conformidad=None, entregables=sin_marcar)) == []
