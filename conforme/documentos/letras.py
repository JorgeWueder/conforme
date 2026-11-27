"""Montos en letras, como se escriben en comprobantes y cotizaciones peruanas
(«SON: DOS MIL QUINIENTOS CON 00/100 SOLES»)."""
import re
import unicodedata
from decimal import Decimal

_UNIDADES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
             "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
             "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro",
             "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
             "setecientos", "ochocientos", "novecientos"]


def _hasta_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    centenas, resto = divmod(n, 100)
    partes = [_CENTENAS[centenas]] if centenas else []
    if resto < 30:
        partes.append(_UNIDADES[resto])
    else:
        decenas, unidades = divmod(resto, 10)
        partes.append(_DECENAS[decenas] + (f" y {_UNIDADES[unidades]}" if unidades else ""))
    return " ".join(p for p in partes if p)


def entero_en_letras(n: int) -> str:
    if n == 0:
        return "cero"
    millones, resto = divmod(n, 1_000_000)
    miles, unidades = divmod(resto, 1000)
    partes = []
    if millones:
        partes.append("un millón" if millones == 1 else f"{entero_en_letras(millones)} millones")
    if miles:
        partes.append("mil" if miles == 1 else f"{_hasta_mil(miles)} mil")
    if unidades:
        partes.append(_hasta_mil(unidades))
    texto = " ".join(partes)
    return re.sub(r"uno( mil| millones)", r"un\1", texto)


def monto_en_letras(monto: Decimal) -> str:
    entero = int(monto)
    centimos = int((monto - entero) * 100)
    return f"{entero_en_letras(entero)} con {centimos:02d}/100"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\b(soles|nuevos)\b", " ", texto)
    return re.sub(r"[^a-z0-9/ ]+", " ", re.sub(r"\s+", " ", texto)).split()


def coincide(monto: Decimal, en_letras: str) -> bool:
    return normalizar(monto_en_letras(monto)) == normalizar(en_letras)
