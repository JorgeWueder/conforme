from datetime import date, timedelta

from conforme import normativa
from conforme.reglas import r6_recurrencia_proveedor as r6
from tests.fabrica import SOLICITANTE, foto, vecino

ORDEN = date(2026, 8, 3)
VENTANA = normativa.R6_VENTANA_DIAS


def _previo(n, dias_antes, **cambios):
    return vecino(n, f"EXP-2026-{n:04d}", ORDEN - timedelta(days=dias_antes), **cambios)


def _evaluar(*previos, **cambios):
    return r6.evaluar(foto(fecha_orden=ORDEN, proveedor="Servicios Andina S.A.C.",
                           proveedor_id=7, previos_mismo_proveedor=tuple(previos), **cambios))


def test_positivo_tercer_expediente_del_proveedor_en_la_ventana():
    alertas = _evaluar(_previo(1, 40, monto="20000.00"), _previo(2, 10, monto="30000.00"))
    assert len(alertas) == 1
    a = alertas[0]
    assert (a.regla, a.clave, a.persona_implicada_id) == ("R6", "proveedor-recurrente", SOLICITANTE)
    assert a.datos["expedientes"] == 3 and a.datos["anteriores"] == ["EXP-2026-0001", "EXP-2026-0002"]
    assert a.datos["proveedor_id"] == 7 and a.datos["suma_montos"] == "98000.00"
    assert "Servicios Andina S.A.C. figura en 3 expedientes" in a.explicacion
    assert "EXP-2026-0001" in a.explicacion and "EXP-2026-0002" in a.explicacion
    assert "40 días" in a.explicacion and "S/ 98,000.00" in a.explicacion


def test_negativo_con_menos_expedientes_que_el_umbral():
    assert _evaluar() == []
    assert _evaluar(_previo(1, 10)) == []


def test_borde_justo_en_la_ventana_y_un_dia_despues():
    assert len(_evaluar(_previo(1, VENTANA), _previo(2, 5))) == 1
    assert _evaluar(_previo(1, VENTANA + 1), _previo(2, 5)) == []


def test_los_previos_fuera_de_la_ventana_no_cuentan():
    # tres previos, pero solo uno dentro de la ventana: con este suman 2
    assert _evaluar(_previo(1, 200), _previo(2, 150), _previo(3, 5)) == []
    # dos dentro de la ventana y uno lejano: alerta con 3, no con 4
    alertas = _evaluar(_previo(1, 200), _previo(2, 30), _previo(3, 5))
    assert len(alertas) == 1 and alertas[0].datos["expedientes"] == 3


def test_cuarto_expediente_tambien_alerta_y_cuenta_a_todos():
    alertas = _evaluar(_previo(1, 60), _previo(2, 30), _previo(3, 5))
    assert len(alertas) == 1 and alertas[0].datos["expedientes"] == 4


def test_no_depende_del_orden_en_que_llegan_los_previos():
    a = _evaluar(_previo(1, 40), _previo(2, 10))
    b = _evaluar(_previo(2, 10), _previo(1, 40))
    assert a == b
