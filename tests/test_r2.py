from datetime import date
from decimal import Decimal

from conforme import normativa
from conforme.reglas import r2_penalidad as r2
from tests.fabrica import conformidad, foto

ENTREGA_12_DIAS_TARDE = date(2026, 9, 29)  # límite: 17 sep 2026


def test_positivo_caso_estrella_12_dias_sin_penalidad():
    alertas = r2.evaluar(foto(fecha_entrega_real=ENTREGA_12_DIAS_TARDE,
                              conformidad=conformidad(date(2026, 10, 2))))
    assert len(alertas) == 1
    a = alertas[0]
    assert a.regla == "R2"
    assert a.datos["dias_atraso"] == 12
    assert a.datos["penalidad_esperada"] == "3200.00"
    assert a.datos["tope"] == "4800.00"
    assert ("12 días de atraso × S/ 266.67 por día = S/ 3,200.00 esperados "
            "(tope S/ 4,800.00); aplicado S/ 0.00") in a.explicacion


def test_negativo_entrega_a_tiempo_o_el_mismo_dia_del_limite():
    assert r2.evaluar(foto(fecha_entrega_real=date(2026, 9, 10))) == []
    assert r2.evaluar(foto(fecha_entrega_real=date(2026, 9, 17))) == []


def test_negativo_atraso_con_penalidad_completa():
    assert r2.evaluar(foto(fecha_entrega_real=ENTREGA_12_DIAS_TARDE,
                           conformidad=conformidad(date(2026, 10, 2), "3200.00"))) == []


def test_borde_penalidad_parcial_alerta_por_la_diferencia():
    alertas = r2.evaluar(foto(fecha_entrega_real=ENTREGA_12_DIAS_TARDE,
                              conformidad=conformidad(date(2026, 10, 2), "1600.00")))
    assert len(alertas) == 1
    assert "aplicado S/ 1,600.00. Diferencia: S/ 1,600.00" in alertas[0].explicacion


def test_borde_tolerancia_de_un_centimo():
    def con(aplicada):
        return r2.evaluar(foto(fecha_entrega_real=ENTREGA_12_DIAS_TARDE,
                               conformidad=conformidad(date(2026, 10, 2), aplicada)))
    assert con("3199.99") == []       # falta S/ 0.01: dentro de la tolerancia
    assert len(con("3199.98")) == 1   # falta S/ 0.02: alerta


def test_borde_plazo_60_contra_61_cambia_el_factor():
    monto = Decimal("60000.00")
    # 60 días: F = 0.40 -> 0.10 × 60,000 / (0.40 × 60) = 250.00 por día
    assert normativa.penalidad_diaria(monto, 60) == Decimal("250")
    # 61 días: F = 0.25 -> 0.10 × 60,000 / (0.25 × 61) = 393.44 por día
    assert normativa.penalidad_diaria(monto, 61).quantize(Decimal("0.01")) == Decimal("393.44")
    assert normativa.penalidad_esperada(monto, 60, 2) == Decimal("500.00")
    assert normativa.penalidad_esperada(monto, 61, 2) == Decimal("786.89")


def test_borde_tope_del_diez_por_ciento():
    # 30 días de atraso × 266.67 = 8,000 > tope de 4,800.
    assert normativa.penalidad_esperada(Decimal("48000.00"), 45, 30) == Decimal("4800.00")
    entrega = date(2026, 10, 17)
    alertas = r2.evaluar(foto(fecha_entrega_real=entrega,
                              conformidad=conformidad(date(2026, 10, 18))))
    assert alertas[0].datos["penalidad_esperada"] == "4800.00"
    assert "supera el tope de S/ 4,800.00" in alertas[0].explicacion
    # Con el tope aplicado completo ya no alerta.
    assert r2.evaluar(foto(fecha_entrega_real=entrega,
                           conformidad=conformidad(date(2026, 10, 18), "4800.00"))) == []


def test_borde_sin_conformidad_o_sin_entrega_no_alerta():
    assert r2.evaluar(foto(fecha_entrega_real=ENTREGA_12_DIAS_TARDE, conformidad=None)) == []
    assert r2.evaluar(foto(fecha_entrega_real=None)) == []
