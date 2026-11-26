"""Sesión HTTP y dependencias compartidas por los routers de Conforme."""
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from conforme import auth, config, db
from conforme.permisos import Actor

COOKIE = "conforme_sesion"
DURACION_SESION = 8 * 60 * 60
FIRMADOR = URLSafeTimedSerializer(config.leer("SESSION_SECRET") or token_urlsafe(48),
                                   salt="conforme-sesion")


def sesion_db():
    try:
        with db.sesion() as sesion:
            yield sesion
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Los datos cambiaron. Actualiza la página e inténtalo de nuevo.") from error
        raise


Sesion = Annotated[Session, Depends(sesion_db, scope="function")]


def usuario_id(request: Request) -> int | None:
    valor = request.cookies.get(COOKIE)
    if valor:
        try:
            return FIRMADOR.loads(valor, max_age=DURACION_SESION)
        except BadData:
            pass
    return None


def actor_actual(sesion: Sesion, identificador: Annotated[int | None, Depends(usuario_id)]) -> Actor:
    actor = auth.actor_por_id(sesion, identificador) if identificador is not None else None
    if actor is None:
        raise HTTPException(401, "Inicia sesión para continuar.")
    return actor


UsuarioActual = Annotated[Actor, Depends(actor_actual)]


