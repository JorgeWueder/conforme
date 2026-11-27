"""Capa de adaptadores desacoplados (mockup hoy, integraciones reales en Fase 7)."""
from conforme.adaptadores.agente import AdaptadorAgenteIA, obtener_agente
from conforme.adaptadores.fuentes import AdaptadorFuentesPublicas, obtener_fuentes
from conforme.adaptadores.notificaciones import AdaptadorNotificaciones, obtener_notificaciones
from conforme.adaptadores.siaf import AdaptadorSiaf, VerificacionSiaf, obtener_siaf


def estado_adaptadores() -> dict[str, dict]:
    agente = obtener_agente()
    fuentes = obtener_fuentes()
    siaf = obtener_siaf()
    notificaciones = obtener_notificaciones()
    return {
        "fuentes_publicas": {"modo": fuentes.modo, "listo": True},
        "siaf": {"modo": siaf.modo, "listo": True},
        "notificaciones": {"modo": notificaciones.modo, "listo": True},
        "agente_ia": {"modo": agente.modo, "listo": agente.disponible()},
    }


__all__ = [
    "AdaptadorAgenteIA",
    "AdaptadorFuentesPublicas",
    "AdaptadorNotificaciones",
    "AdaptadorSiaf",
    "VerificacionSiaf",
    "estado_adaptadores",
    "obtener_agente",
    "obtener_fuentes",
    "obtener_notificaciones",
    "obtener_siaf",
]
