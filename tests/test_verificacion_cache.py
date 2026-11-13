"""Verificación de la cadena con caché corto (página pública)."""
import time

from sqlalchemy import text

from conforme import bitacora


def _registrar(s, n=1):
    for i in range(n):
        bitacora.registrar(s, accion="prueba.evento", entidad="prueba", entidad_id=i,
                           detalle={"i": i})


def _contador(monkeypatch):
    llamadas = []
    original = bitacora.verificar_cadena

    def contada(sesion):
        llamadas.append(1)
        return original(sesion)

    monkeypatch.setattr(bitacora, "verificar_cadena", contada)
    return llamadas


def test_dentro_del_ttl_se_reutiliza_el_resultado(sesion, monkeypatch):
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 60.0)
    llamadas = _contador(monkeypatch)
    _registrar(sesion, 3)
    primera = bitacora.verificar_cadena_cacheada(sesion)
    segunda = bitacora.verificar_cadena_cacheada(sesion)
    assert (primera.desde_cache, segunda.desde_cache) == (False, True)
    assert primera.resultado.integra and segunda.resultado == primera.resultado
    assert len(llamadas) == 1


def test_pasado_el_ttl_se_recalcula(sesion, monkeypatch):
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 0.05)
    llamadas = _contador(monkeypatch)
    _registrar(sesion, 2)
    bitacora.verificar_cadena_cacheada(sesion)
    time.sleep(0.1)
    assert not bitacora.verificar_cadena_cacheada(sesion).desde_cache
    assert len(llamadas) == 2


def test_anadir_registros_invalida_el_cache_al_instante(sesion, monkeypatch):
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 60.0)
    llamadas = _contador(monkeypatch)
    _registrar(sesion, 2)
    bitacora.verificar_cadena_cacheada(sesion)
    _registrar(sesion)
    nueva = bitacora.verificar_cadena_cacheada(sesion)
    assert not nueva.desde_cache and nueva.resultado.total == 3 and len(llamadas) == 2


def test_borrar_la_cola_invalida_el_cache_al_instante(sesion, monkeypatch):
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 60.0)
    _registrar(sesion, 3)
    bitacora.verificar_cadena_cacheada(sesion)
    sesion.execute(text("DELETE FROM bitacora WHERE id = (SELECT max(id) FROM bitacora)"))
    despues = bitacora.verificar_cadena_cacheada(sesion)
    assert not despues.desde_cache and despues.resultado.total == 2


def test_alterar_un_registro_del_medio_se_ve_al_forzar_no_antes(sesion, monkeypatch):
    """Contrapartida documentada: sin cambiar el n.º de registros ni el último hash, una
    alteración en el medio espera al TTL, o se ve al instante pidiendo verificar de nuevo."""
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 60.0)
    monkeypatch.setattr(bitacora, "INTERVALO_MINIMO_FORZADO", 0.0)
    _registrar(sesion, 4)
    assert bitacora.verificar_cadena_cacheada(sesion).resultado.integra
    sesion.execute(text("UPDATE bitacora SET detalle = detalle || '{\"x\": 1}' "
                        "WHERE id = (SELECT min(id) FROM bitacora)"))
    assert bitacora.verificar_cadena_cacheada(sesion).resultado.integra  # aún en caché
    forzada = bitacora.verificar_cadena_cacheada(sesion, forzar=True)
    assert not forzada.desde_cache and not forzada.resultado.integra


def test_forzar_tiene_un_intervalo_minimo(sesion, monkeypatch):
    monkeypatch.setattr(bitacora, "TTL_VERIFICACION", 60.0)
    monkeypatch.setattr(bitacora, "INTERVALO_MINIMO_FORZADO", 60.0)
    llamadas = _contador(monkeypatch)
    _registrar(sesion, 2)
    bitacora.verificar_cadena_cacheada(sesion)
    assert bitacora.verificar_cadena_cacheada(sesion, forzar=True).desde_cache
    assert len(llamadas) == 1
