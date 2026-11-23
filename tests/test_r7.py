from datetime import date, timedelta
from decimal import Decimal

from conforme import normativa
from conforme.reglas import r7_compras_sucesivas as r7
from tests.fabrica import SOLICITANTE, foto, vecino

ORDEN = date(2026, 8, 3)
VENTANA = normativa.R7_VENTANA_DIAS
LIMPIEZA = "Servicio de limpieza y desinfección de ambientes"


def _previo(n, dias_antes, descripcion=LIMPIEZA, monto="10000.00"):
    return vecino(n, f"EXP-2026-{n:04d}", ORDEN - timedelta(days=dias_antes),
                  monto=monto, descripcion=descripcion)


def _evaluar(*previos, descripcion=LIMPIEZA, monto="15000.00"):
    return r7.evaluar(foto(fecha_orden=ORDEN, descripcion=descripcion, monto=Decimal(monto),
                           proveedor="Corporación Inti S.R.L.", proveedor_id=9,
                           previos_mismo_proveedor=tuple(previos)))


def test_positivo_segunda_compra_de_lo_mismo_al_mismo_proveedor():
    alertas = _evaluar(_previo(1, 20, monto="10000.00"))
    assert len(alertas) == 1
    a = alertas[0]
    assert (a.regla, a.clave, a.persona_implicada_id) == ("R7", "compras-sucesivas", SOLICITANTE)
    assert a.datos["compras"] == 2 and a.datos["anteriores"] == ["EXP-2026-0001"]
    assert a.datos["suma_montos"] == "25000.00" and a.datos["proveedor_id"] == 9
    assert "se contrató 2 veces a Corporación Inti S.R.L." in a.explicacion
    assert "EXP-2026-0001 (S/ 10,000.00" in a.explicacion and "S/ 25,000.00" in a.explicacion
    assert "20 días" in a.explicacion


def test_negativo_sin_previos_o_con_otra_prestacion():
    assert _evaluar() == []
    assert _evaluar(_previo(1, 10, descripcion="Servicio de vigilancia y seguridad")) == []


def test_borde_justo_en_la_ventana_y_un_dia_despues():
    assert len(_evaluar(_previo(1, VENTANA))) == 1
    assert _evaluar(_previo(1, VENTANA + 1)) == []


def test_la_descripcion_se_compara_sin_mayusculas_ni_espacios_repetidos():
    assert len(_evaluar(_previo(1, 5, descripcion="  servicio de LIMPIEZA   y desinfección de ambientes "))) == 1


def test_sin_descripcion_no_alerta():
    assert _evaluar(_previo(1, 5, descripcion=""), descripcion="") == []
    assert _evaluar(_previo(1, 5, descripcion="   "), descripcion="   ") == []


def test_solo_cuentan_los_previos_de_la_misma_prestacion():
    alertas = _evaluar(_previo(1, 5, descripcion="Servicio de vigilancia y seguridad"),
                       _previo(2, 8), _previo(3, 12))
    assert len(alertas) == 1 and alertas[0].datos["compras"] == 3
    assert alertas[0].datos["anteriores"] == ["EXP-2026-0003", "EXP-2026-0002"]
