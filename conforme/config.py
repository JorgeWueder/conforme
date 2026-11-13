"""Configuración leída del entorno (o de st.secrets en Streamlit Cloud).

Nada sensible se escribe en el repositorio.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def leer(nombre: str, defecto: str | None = None) -> str | None:
    valor = os.environ.get(nombre)
    if valor:
        return valor
    try:
        import streamlit as st

        if nombre in st.secrets:
            return str(st.secrets[nombre])
    except Exception:
        pass
    return defecto


def normalizar_url(url: str) -> str:
    """Neon entrega 'postgresql://...'; SQLAlchemy necesita el driver psycopg 3."""
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def url_base_datos() -> str:
    url = leer("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta DATABASE_URL. Defínela en .env (local) o en los secretos de Streamlit."
        )
    return normalizar_url(url)
