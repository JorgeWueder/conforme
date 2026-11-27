"""Prepara un archivo de evidencia para guardarlo: valida, reduce y calcula su huella."""
import hashlib
import io
from datetime import date, datetime
from pathlib import PurePath, PureWindowsPath

from PIL import Image, ImageOps
from pypdf import PdfReader

from conforme.errores import ErrorValidacion

TAMANO_MAXIMO = 5 * 1024 * 1024  # igual que el CHECK de la tabla evidencia
LADO_MAXIMO = 1600
MIMES_ADMITIDOS = ("image/jpeg", "image/png", "application/pdf")


def fecha_de_metadatos(mime: str, contenido: bytes) -> date | None:
    """Fecha declarada por el archivo, solo como señal: los metadatos se pueden alterar."""
    try:
        if mime == "application/pdf":
            creada = PdfReader(io.BytesIO(contenido)).metadata.creation_date
            return creada.date() if creada else None
        with Image.open(io.BytesIO(contenido)) as imagen:
            texto = imagen.getexif().get(36867) or imagen.getexif().get(306)
        return datetime.strptime(texto[:10], "%Y:%m:%d").date() if texto else None
    except Exception:  # metadatos ausentes o archivo que no se puede inspeccionar
        return None


def preparar(nombre_archivo: str, mime: str, contenido: bytes) -> dict:
    """Devuelve nombre_archivo, mime, tamano, sha256 y contenido listos para insertar.

    Las fotos más grandes que LADO_MAXIMO se reducen y se guardan como JPEG.
    El SHA-256 es el del contenido que efectivamente se guarda.
    """
    nombre_archivo = PureWindowsPath(nombre_archivo or "").name
    if nombre_archivo in ("", ".."):
        nombre_archivo = "evidencia"
    if mime not in MIMES_ADMITIDOS:
        raise ErrorValidacion(
            f"«{nombre_archivo}»: tipo de archivo no admitido. Usa JPG, PNG o PDF.")
    if not contenido:
        raise ErrorValidacion(f"«{nombre_archivo}» está vacío.")

    if mime.startswith("image/"):
        try:
            imagen = Image.open(io.BytesIO(contenido))
            imagen.load()
        except Exception:
            raise ErrorValidacion(f"«{nombre_archivo}» no es una imagen válida.") from None
        if max(imagen.size) > LADO_MAXIMO:
            imagen = ImageOps.exif_transpose(imagen).convert("RGB")
            imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = io.BytesIO()
            imagen.save(salida, format="JPEG", quality=85)
            contenido = salida.getvalue()
            mime = "image/jpeg"
            nombre_archivo = str(PurePath(nombre_archivo).with_suffix(".jpg"))

    if len(contenido) > TAMANO_MAXIMO:
        raise ErrorValidacion(f"«{nombre_archivo}» supera el máximo de 5 MB.")
    return {
        "nombre_archivo": nombre_archivo,
        "mime": mime,
        "tamano": len(contenido),
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "contenido": contenido,
    }
