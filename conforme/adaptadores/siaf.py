"""Adaptador de consulta de devengado y registro de referencia SIAF.

En modo `simulado` valida el formato de la referencia y deja constancia simulada.
En Fase 7 se conecta la consulta real al SIAF sin cambiar el flujo de Tesorería.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from conforme import config


@dataclass(frozen=True)
class VerificacionSiaf:
    verificado: bool
    modo: str
    referencia: str | None
    mensaje: str


class AdaptadorSiaf(Protocol):
    modo: str

    def consultar_devengado(
        self, *, numero_orden: str, monto: Decimal, referencia_siaf: str | None,
    ) -> VerificacionSiaf: ...


class SiafSimulado:
    modo = "simulado"

    def consultar_devengado(
        self, *, numero_orden: str, monto: Decimal, referencia_siaf: str | None,
    ) -> VerificacionSiaf:
        ref = (referencia_siaf or "").strip() or None
        if ref:
            return VerificacionSiaf(
                verificado=True,
                modo=self.modo,
                referencia=ref,
                mensaje=f"Referencia SIAF {ref} registrada en modo simulado para la orden {numero_orden}.",
            )
        return VerificacionSiaf(
            verificado=True,
            modo=self.modo,
            referencia=None,
            mensaje="Pago registrado sin referencia SIAF (validación externa simulada).",
        )


_REGISTRO: dict[str, AdaptadorSiaf] = {
    "simulado": SiafSimulado(),
}


def registrar(nombre: str, adaptador: AdaptadorSiaf) -> None:
    _REGISTRO[nombre] = adaptador


def obtener_siaf() -> AdaptadorSiaf:
    modo = (config.leer("ADAPTADOR_SIAF", "simulado") or "simulado").strip().lower()
    return _REGISTRO.get(modo, _REGISTRO["simulado"])
