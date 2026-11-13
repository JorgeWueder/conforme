"""Semáforo de un expediente. Se calcula, no se guarda.

Rojo: alguna alerta de severidad alta sin cerrar. Ámbar: solo medias sin
cerrar. Verde: ninguna alerta sin cerrar. Una alerta escalada sigue sin cerrar.
"""
ROJO = "rojo"
AMBAR = "ambar"
VERDE = "verde"


def calcular(altas_sin_cerrar: int, medias_sin_cerrar: int) -> str:
    if altas_sin_cerrar > 0:
        return ROJO
    if medias_sin_cerrar > 0:
        return AMBAR
    return VERDE
