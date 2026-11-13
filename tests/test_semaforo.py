from conforme import normativa
from conforme.reglas import semaforo


def test_colores():
    assert semaforo.calcular(0, 0) == semaforo.VERDE
    assert semaforo.calcular(0, 2) == semaforo.AMBAR
    assert semaforo.calcular(1, 0) == semaforo.ROJO
    assert semaforo.calcular(1, 3) == semaforo.ROJO


def test_cada_regla_tiene_severidad_y_nombre():
    assert set(normativa.SEVERIDAD_POR_REGLA) == {"R1", "R2", "R3", "R4", "R5"}
    assert set(normativa.NOMBRE_REGLA) == set(normativa.SEVERIDAD_POR_REGLA)
    assert set(normativa.SEVERIDAD_POR_REGLA.values()) == {"alta", "media"}
