"""Adaptador de fuentes públicas (SUNAT, OECE/RNP, sanciones TCP y composición societaria).

En modo `simulado` (por defecto) delega en `conforme.proveedores.fuentes`.
En Fase 7 basta registrar una implementación que cumpla `AdaptadorFuentesPublicas`
y configurar `ADAPTADOR_FUENTES=real` sin tocar las 6 dimensiones ni las pantallas.
"""
from datetime import date
from typing import Protocol

from conforme import config
from conforme.proveedores import fuentes as _simulado
from conforme.proveedores.fuentes import FichaEmpresa


class AdaptadorFuentesPublicas(Protocol):
    modo: str

    def consultar_empresa(self, ruc: str, razon_social: str) -> FichaEmpresa: ...

    def personas_en_empresas_sancionadas(self, hoy: date) -> dict[str, list[str]]: ...


class FuentesSimuladas:
    modo = "simulado"

    def consultar_empresa(self, ruc: str, razon_social: str) -> FichaEmpresa:
        return _simulado.consultar(ruc, razon_social)

    def personas_en_empresas_sancionadas(self, hoy: date) -> dict[str, list[str]]:
        return _simulado.personas_de_empresas_sancionadas(hoy)


_REGISTRO: dict[str, AdaptadorFuentesPublicas] = {
    "simulado": FuentesSimuladas(),
}


def registrar(nombre: str, adaptador: AdaptadorFuentesPublicas) -> None:
    _REGISTRO[nombre] = adaptador


def obtener_fuentes() -> AdaptadorFuentesPublicas:
    modo = (config.leer("ADAPTADOR_FUENTES", "simulado") or "simulado").strip().lower()
    return _REGISTRO.get(modo, _REGISTRO["simulado"])
