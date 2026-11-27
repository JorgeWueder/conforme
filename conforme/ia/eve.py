"""Llamadas estructuradas al agente local eve, sin retener una sesión de base de datos."""
import json
from time import monotonic
from uuid import uuid4

import httpx

from conforme import config


class EveNoDisponible(Exception):
    pass


def configurado() -> bool:
    return bool(config.leer("CONFORME_EVE_URL") and config.leer("CONFORME_EVE_TOKEN"))


def solicitar(mensaje: str | list[dict], contexto: dict, esquema: dict) -> dict:
    base, token = config.leer("CONFORME_EVE_URL"), config.leer("CONFORME_EVE_TOKEN")
    if not base or not token:
        raise EveNoDisponible("El agente eve no está configurado.")
    api = base.rstrip("/") + "/eve/v1/session"
    cuerpo = {"message": mensaje, "clientContext": contexto,
              "outputSchema": esquema, "operationId": uuid4().hex}
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=5),
                          headers={"Authorization": "Bearer " + token}) as cliente:
            respuesta = cliente.post(api, json=cuerpo)
            respuesta.raise_for_status()
            recibo = respuesta.json()
            ruta = f"{api}/{recibo['sessionId']}"
            try:
                limite = monotonic() + 60
                resultado = None
                with cliente.stream("GET", ruta + "/stream") as eventos:
                    eventos.raise_for_status()
                    for linea in eventos.iter_lines():
                        if monotonic() > limite:
                            break
                        if not linea:
                            continue
                        evento = json.loads(linea)
                        for hecho in evento.get("facts", []):
                            tipo, datos = hecho.get("type"), hecho.get("data") or {}
                            if tipo == "content.completed" and datos.get("kind") == "result":
                                resultado = datos.get("value")
                            if tipo == "delivery.settled" and datos.get("deliveryId") == recibo["deliveryId"]:
                                if datos.get("outcome") == "handled" and isinstance(resultado, dict):
                                    return resultado
                                raise EveNoDisponible("El agente no completó la revisión.")
                            if tipo in ("session.ended", "turn.paused"):
                                raise EveNoDisponible("La revisión del agente se interrumpió.")
                        if evento.get("$eve") == "stream.ended":
                            break
                raise EveNoDisponible("El agente no devolvió un resultado completo.")
            finally:
                try:
                    cliente.post(ruta + "/end", timeout=3)
                except httpx.HTTPError:
                    pass
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise EveNoDisponible("No se pudo consultar el agente eve.") from error
