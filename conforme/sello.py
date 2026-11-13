"""Sello de conformidad: código no adivinable, QR y PNG descargable.

Funciones puras (sin base de datos). La consulta pública y el sellado
contra la base viven en `repositorio.py`.
"""
import hashlib
import io
import json
import re
import secrets
from urllib.parse import urlsplit

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from conforme import config
from conforme.bitacora import _normalizar

# 12 bytes aleatorios = 96 bits; en base64 URL-safe son 16 caracteres.
_BYTES_CODIGO = 12
_PATRON_CODIGO = re.compile(r"[A-Za-z0-9_-]{16}")
LADO_MINIATURA = 240


def generar_codigo() -> str:
    return secrets.token_urlsafe(_BYTES_CODIGO)


def codigo_valido(codigo: str | None) -> bool:
    """Descarta de entrada lo que no tiene la forma de un código (no toca la base)."""
    return bool(codigo) and _PATRON_CODIGO.fullmatch(codigo) is not None


def huella(valor) -> str:
    """SHA-256 de un valor en JSON canónico (claves ordenadas; fechas y montos como texto)."""
    canonico = json.dumps(_normalizar(valor), sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def url_base(origen_actual: str | None = None) -> str:
    """URL pública de la app: BASE_URL si está definida; si no, desde donde se sirve la app
    ahora mismo (así el QR del despliegue apunta bien aunque falte el secreto); y, solo
    como último recurso, localhost."""
    configurada = config.leer("BASE_URL")
    if configurada:
        return configurada.rstrip("/")
    return (origen_actual or "http://localhost:8501").rstrip("/")


def _servidor(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def aviso_url_base(origen_actual: str | None) -> str | None:
    """Aviso si BASE_URL apunta a un servidor distinto de aquel desde el que se sirve la app
    (el QR llevaría a otra parte). Se compara solo el servidor, no el puerto: en local,
    localhost:8501 y localhost:8502 son lo mismo. Sin BASE_URL no hay nada que avisar."""
    configurada = config.leer("BASE_URL")
    if not configurada or not origen_actual:
        return None
    if _servidor(configurada) == _servidor(origen_actual):
        return None
    return (f"El QR y el enlace apuntan a «{configurada.rstrip('/')}», pero esta app se "
            f"sirve desde «{origen_actual}». Corrige BASE_URL en los secretos "
            f"(o bórrala: se usaría {origen_actual}).")


def url_verificacion(codigo: str, base: str | None = None) -> str:
    return f"{(base if base is not None else url_base()).rstrip('/')}/verificar?c={codigo}"


def _qr(texto: str) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(texto)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def png_qr(codigo: str, base: str | None = None) -> bytes:
    salida = io.BytesIO()
    _qr(url_verificacion(codigo, base)).save(salida, format="PNG")
    return salida.getvalue()


def _fuente(tamano: int):
    try:
        return ImageFont.load_default(size=tamano)
    except TypeError:  # Pillow antiguo: sin tamaño
        return ImageFont.load_default()


def png_sello(codigo: str, expediente: str, sello_hash: str, base: str | None = None) -> bytes:
    """Tarjeta descargable: QR, código del sello, expediente y hash de bitácora."""
    qr = _qr(url_verificacion(codigo, base))  # sin reescalar: los módulos deben quedar nítidos
    ancho, alto = 520, 640
    lienzo = Image.new("RGB", (ancho, alto), "white")
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rectangle((0, 0, ancho - 1, alto - 1), outline="#1f3a5f", width=4)
    dibujo.text((ancho // 2, 40), "SELLO DE CONFORMIDAD", fill="#1f3a5f",
                font=_fuente(26), anchor="mm")
    dibujo.text((ancho // 2, 72), "Datos sintéticos · demostración académica", fill="#777777",
                font=_fuente(15), anchor="mm")
    lienzo.paste(qr, ((ancho - qr.width) // 2, 95))
    dibujo.text((ancho // 2, 540), expediente, fill="black", font=_fuente(24), anchor="mm")
    dibujo.text((ancho // 2, 573), f"Código: {codigo}", fill="black", font=_fuente(18),
                anchor="mm")
    dibujo.text((ancho // 2, 603), f"Hash: {sello_hash[:32]}…", fill="#555555",
                font=_fuente(14), anchor="mm")
    salida = io.BytesIO()
    lienzo.save(salida, format="PNG")
    return salida.getvalue()


def miniatura(contenido: bytes) -> bytes | None:
    """Miniatura PNG de una imagen; None si el archivo no se puede abrir como imagen."""
    try:
        imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido))).convert("RGB")
    except Exception:
        return None
    imagen.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
    salida = io.BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()
