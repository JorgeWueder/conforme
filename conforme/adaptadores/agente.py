"""Adaptador del agente de IA (eve local con cuenta ChatGPT/Codex)."""
from typing import Protocol

from conforme.ia import eve


class AdaptadorAgenteIA(Protocol):
    modo: str

    def disponible(self) -> bool: ...

    def solicitar(self, mensaje: str | list[dict], contexto: dict, esquema: dict) -> dict: ...


class AgenteEve:
    modo = "eve"

    def disponible(self) -> bool:
        return eve.configurado()

    def solicitar(self, mensaje: str | list[dict], contexto: dict, esquema: dict) -> dict:
        return eve.solicitar(mensaje, contexto, esquema)


_AGENTE = AgenteEve()


def obtener_agente() -> AdaptadorAgenteIA:
    return _AGENTE
