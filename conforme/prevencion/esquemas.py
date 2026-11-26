"""Datos de la compra y actuaciones de la revisión."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Ruc = Annotated[str, StringConstraints(pattern=r"^[0-9]{11}$")]
Texto = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Nota = Annotated[str, StringConstraints(min_length=5, max_length=1800)]
Importe = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


def ruc_valido(ruc: str) -> bool:
    if len(ruc) != 11 or not ruc.isascii() or not ruc.isdecimal() or ruc[:2] not in {"10", "15", "16", "17", "20"}:
        return False
    suma = sum(int(digito) * peso for digito, peso in zip(ruc, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return (11 - suma % 11) % 10 == int(ruc[-1])


class Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Candidato(Entrada):
    ruc: Ruc
    nombre: Texto
    proforma: Texto | None = None
    importe: Importe | None = None


class Interviniente(Entrada):
    rol: Texto
    designacion: Texto
    referencia: Texto


class Compra(Entrada):
    requerimiento: Texto
    objeto: Annotated[str, StringConstraints(min_length=5, max_length=1500)]
    entidad_ruc: Ruc
    unidad: Texto
    rubro: Texto
    modalidad: Texto
    fecha: date
    importe: Importe
    moneda: Literal["PEN", "USD"] = "PEN"
    tdr: Texto | None = None
    candidatos: Annotated[list[Candidato], Field(min_length=1, max_length=12)]
    intervinientes: Annotated[list[Interviniente], Field(max_length=12)] = Field(default_factory=list)

    @field_validator("candidatos")
    @classmethod
    def candidatos_unicos(cls, candidatos):
        if len({c.ruc for c in candidatos}) != len(candidatos):
            raise ValueError("Cada RUC debe figurar una sola vez.")
        return candidatos

    @model_validator(mode="after")
    def validar_fecha(self):
        if self.fecha.year < 2018:
            raise ValueError("Usa una fecha de revisión desde 2018.")
        return self


class VersionEsperada(Entrada):
    version: int = Field(ge=1)


class EditarRevision(VersionEsperada):
    compra: Compra


class Constancia(VersionEsperada):
    control: Texto
    resultado: Literal["verificado", "pendiente", "no_aplica", "derivado"]
    referencia: Texto
    nota: Nota
    fecha_hecho: date | None = None


class ResolverHallazgo(VersionEsperada):
    hallazgo: Texto
    resultado: Literal["aclarado", "descartado", "derivado", "pendiente"]
    referencia: Texto
    nota: Nota


class Cierre(VersionEsperada):
    nota: Nota
    expediente_id: int | None = Field(default=None, gt=0)


class Investigar(VersionEsperada):
    ruc: Ruc
    acto: Texto | None = None


class Analizar(VersionEsperada):
    ruc: Ruc | None = None
    simular: bool = True
