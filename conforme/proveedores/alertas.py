"""Generación idempotente de alertas preventivas (proveedores) y forenses (documentos)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from conforme import bitacora
from conforme.modelos import ESTADO_ABIERTA, Alerta


def sincronizar_alertas(sesion: Session, expediente_id: int, propuestas: list[dict]) -> int:
    """Inserta o actualiza alertas por clave (expediente, regla, clave) sin duplicar ni reabrir cerradas."""
    if not propuestas:
        return 0
    existentes = {
        (a.regla, a.clave): a
        for a in sesion.scalars(select(Alerta).where(Alerta.expediente_id == expediente_id))
    }
    ahora = datetime.now(timezone.utc)
    nuevas = 0
    for item in propuestas:
        par = (item["regla"], item["clave"])
        previa = existentes.get(par)
        if previa is None:
            alerta = Alerta(
                expediente_id=expediente_id,
                regla=item["regla"],
                clave=item["clave"],
                severidad=item["severidad"],
                explicacion=item["explicacion"],
                datos=item.get("datos") or {},
                persona_implicada_id=item.get("persona_implicada_id"),
                estado=ESTADO_ABIERTA,
                ambito=item.get("ambito", "preventiva_dec"),
                bloqueante=bool(item.get("bloqueante", False)),
                creada_en=ahora,
                actualizada_en=ahora,
            )
            sesion.add(alerta)
            sesion.flush()
            existentes[par] = alerta
            nuevas += 1
            bitacora.registrar(
                sesion, ts=ahora, actor_id=None, accion="alerta.generada",
                entidad="alerta", entidad_id=alerta.id, expediente_id=expediente_id,
                detalle={"regla": alerta.regla, "severidad": alerta.severidad,
                         "bloqueante": alerta.bloqueante, "resumen": alerta.explicacion},
            )
        else:
            if previa.explicacion != item["explicacion"] or previa.severidad != item["severidad"]:
                previa.explicacion = item["explicacion"]
                previa.severidad = item["severidad"]
                previa.datos = item.get("datos") or previa.datos
                previa.bloqueante = bool(item.get("bloqueante", previa.bloqueante))
                previa.actualizada_en = ahora
    return nuevas
