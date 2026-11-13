"""Login simple: usuario y contraseña con hash PBKDF2 (biblioteca estándar)."""
import hashlib
import hmac
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from conforme.modelos import Persona, Usuario
from conforme.permisos import Actor

_ITERACIONES = 200_000


def hash_password(password: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, _ITERACIONES)
    return f"pbkdf2_sha256${_ITERACIONES}${sal.hex()}${derivado.hex()}"


def verificar_password(password: str, guardado: str) -> bool:
    try:
        _, iteraciones, sal_hex, hash_hex = guardado.split("$")
        derivado = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(sal_hex), int(iteraciones)
        )
    except ValueError:
        return False
    return hmac.compare_digest(derivado.hex(), hash_hex)


def autenticar(sesion: Session, username: str, password: str) -> Actor | None:
    fila = sesion.execute(
        select(Usuario, Persona)
        .join(Persona, Persona.id == Usuario.persona_id)
        .where(Usuario.username == username.strip().lower())
    ).first()
    if fila is None or not verificar_password(password, fila.Usuario.password_hash):
        return None
    usuario, persona = fila.Usuario, fila.Persona
    return Actor(
        usuario_id=usuario.id,
        persona_id=persona.id,
        area_id=persona.area_id,
        rol=usuario.rol,
        nombre=f"{persona.nombres} {persona.apellidos}",
        username=usuario.username,
    )
