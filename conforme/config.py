"""Configuración del servidor leída del entorno y del archivo .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def leer(nombre: str, defecto: str | None = None) -> str | None:
    return os.environ.get(nombre) or defecto


def normalizar_url(url: str) -> str:
    """Neon entrega 'postgresql://...'; SQLAlchemy necesita el driver psycopg 3."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def url_base_datos() -> str:
    url = leer("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta DATABASE_URL. Defínela en .env o en el entorno del servidor.")
    return normalizar_url(url)
