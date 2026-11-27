"""Adaptadores de fuentes externas (modo simulado).

Cada función imita una consulta a una fuente pública (padrón RUC de SUNAT, registro de
sancionados del Tribunal de Contrataciones, composición societaria). Hoy responden con
datos 100 % sintéticos; en la integración real (Fase 7) se reemplaza el cuerpo de cada
función sin tocar las dimensiones ni las pantallas.

Un RUC que no figura en el registro simulado recibe una ficha genérica «sin observaciones»
marcada como tal, para que la demostración no dependa de inventar datos de empresas reales.
"""
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256

SIMULADO = True
PREFIJO_DNI = "99"  # mismo prefijo que los datos sintéticos (datos/generador.py)


def ruc_con_verificador(base10: str) -> str:
    """Completa un RUC de 10 dígitos con su dígito verificador."""
    suma = sum(int(d) * p for d, p in zip(base10, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    return base10 + str((11 - suma % 11) % 10)


@dataclass(frozen=True)
class Padron:
    razon_social: str
    estado: str                 # ACTIVO, BAJA DE OFICIO, SUSPENSIÓN TEMPORAL
    condicion: str              # HABIDO, NO HABIDO
    inicio_actividades: date
    ciiu: str | None
    actividad: str | None
    palabras_rubro: tuple[str, ...]
    domicilio: str
    trabajadores: int | None
    generico: bool = False


@dataclass(frozen=True)
class Sancion:
    tipo: str                   # inhabilitacion, multa
    resolucion: str
    desde: date
    hasta: date | None
    motivo: str


@dataclass(frozen=True)
class Vinculado:
    dni: str
    nombre: str
    rol: str                    # representante_legal, socio, apoderado, gerente


@dataclass(frozen=True)
class FichaEmpresa:
    padron: Padron
    sanciones: tuple[Sancion, ...] = ()
    vinculados: tuple[Vinculado, ...] = ()
    telefonos: tuple[str, ...] = field(default_factory=tuple)
    correos: tuple[str, ...] = field(default_factory=tuple)


# --- Registro sintético ---------------------------------------------------------------
# Personas: el DNI 99900010 es la solicitante sintética del caso de demostración
# (ver scripts/sembrar.py). Así la dimensión «Personas de interés» tiene un vínculo real
# que detectar dentro de los datos de prueba.
DNI_SOLICITANTE_DEMO = f"{PREFIJO_DNI}900010"

RUC_TECNOLAB = ruc_con_verificador("2060112233")
RUC_KALLPA = ruc_con_verificador("2061498877")
RUC_SERVIMAX = ruc_con_verificador("2060554411")
RUC_REDNORTE = ruc_con_verificador("2060778899")
RUC_CONECTA = ruc_con_verificador("2060334455")

_REGISTRO: dict[str, FichaEmpresa] = {
    RUC_TECNOLAB: FichaEmpresa(
        padron=Padron(
            razon_social="TECNOLAB SERVICIOS INTEGRALES S.A.C.", estado="ACTIVO", condicion="HABIDO",
            inicio_actividades=date(2014, 3, 10), ciiu="3312",
            actividad="Reparación y mantenimiento de maquinaria y equipo",
            palabras_rubro=("mantenimiento", "equipos", "laboratorio", "calibracion"),
            domicilio="Av. América Sur 1450, Trujillo", trabajadores=18),
        vinculados=(Vinculado(f"{PREFIJO_DNI}700101", "Carlos Augusto Ríos Benites", "representante_legal"),
                    Vinculado(f"{PREFIJO_DNI}700102", "Lucía Fernanda Ríos Benites", "socio")),
        telefonos=("044-281450",), correos=("ventas@tecnolab-sim.pe",),
    ),
    RUC_KALLPA: FichaEmpresa(
        padron=Padron(
            razon_social="INVERSIONES KALLPA ANDINA E.I.R.L.", estado="ACTIVO", condicion="HABIDO",
            inicio_actividades=date(2026, 7, 2), ciiu="4690",
            actividad="Venta al por mayor no especializada",
            palabras_rubro=("venta", "mayor", "comercializacion"),
            domicilio="Jr. Bolívar 812, Of. 3, Trujillo", trabajadores=1),
        vinculados=(Vinculado(DNI_SOLICITANTE_DEMO, "Rosa Elena Paredes Gil", "socio"),
                    Vinculado(f"{PREFIJO_DNI}700201", "Jorge Luis Paredes Vela", "representante_legal")),
        telefonos=("949-555-120",), correos=("kallpa.andina.sim@gmail.com",),
    ),
    RUC_SERVIMAX: FichaEmpresa(
        padron=Padron(
            razon_social="GRUPO SERVIMAX DEL NORTE S.A.C.", estado="ACTIVO", condicion="HABIDO",
            inicio_actividades=date(2019, 11, 15), ciiu="3312",
            actividad="Reparación y mantenimiento de maquinaria y equipo",
            palabras_rubro=("mantenimiento", "equipos", "servicios"),
            domicilio="Jr. Bolívar 812, Of. 5, Trujillo", trabajadores=6),
        sanciones=(Sancion("inhabilitacion", "Res. N.º 0412-2026-TCP-S2 (simulada)", date(2026, 5, 20),
                           date(2027, 5, 19), "Presentó documentación falsa en un procedimiento anterior"),),
        vinculados=(Vinculado(f"{PREFIJO_DNI}700201", "Jorge Luis Paredes Vela", "apoderado"),
                    Vinculado(f"{PREFIJO_DNI}700301", "Mario César Gutiérrez Lau", "representante_legal")),
        telefonos=("949-555-120",), correos=("servimax.norte.sim@gmail.com",),
    ),
    RUC_REDNORTE: FichaEmpresa(
        padron=Padron(
            razon_social="RED NORTE TELECOMUNICACIONES S.A.C.", estado="ACTIVO", condicion="HABIDO",
            inicio_actividades=date(2012, 8, 1), ciiu="6190",
            actividad="Otras actividades de telecomunicaciones",
            palabras_rubro=("red", "datos", "telecomunicaciones", "soporte", "cableado"),
            domicilio="Av. España 2210, Trujillo", trabajadores=35),
        vinculados=(Vinculado(f"{PREFIJO_DNI}700401", "Patricia Soledad Vega Ruiz", "representante_legal"),),
        telefonos=("044-205500",), correos=("proyectos@rednorte-sim.pe",),
    ),
    RUC_CONECTA: FichaEmpresa(
        padron=Padron(
            razon_social="CONECTA SOLUCIONES TI E.I.R.L.", estado="ACTIVO", condicion="HABIDO",
            inicio_actividades=date(2021, 2, 18), ciiu="6202",
            actividad="Consultoría informática y gestión de instalaciones informáticas",
            palabras_rubro=("soporte", "red", "datos", "informatica", "tecnico"),
            domicilio="Calle Los Pinos 145, Víctor Larco", trabajadores=9),
        sanciones=(Sancion("multa", "Res. N.º 1188-2024-TCP-S1 (simulada)", date(2024, 9, 3), None,
                           "Retraso injustificado en la firma de un contrato"),),
        vinculados=(Vinculado(f"{PREFIJO_DNI}700501", "Óscar Iván Linares Chávez", "representante_legal"),),
        telefonos=("044-610233",), correos=("contacto@conecta-sim.pe",),
    ),
}


def _generica(ruc: str, razon_social: str) -> FichaEmpresa:
    semilla = sha256(ruc.encode()).digest()
    return FichaEmpresa(padron=Padron(
        razon_social=razon_social.upper(), estado="ACTIVO", condicion="HABIDO",
        inicio_actividades=date(2008 + semilla[0] % 12, 1 + semilla[1] % 12, 1 + semilla[2] % 28),
        ciiu=None, actividad=None, palabras_rubro=(), domicilio="Trujillo (dato simulado)",
        trabajadores=None, generico=True,
    ))


def consultar(ruc: str, razon_social: str) -> FichaEmpresa:
    """Ficha completa de la empresa en las fuentes (simuladas)."""
    return _REGISTRO.get(ruc) or _generica(ruc, razon_social)


def personas_de_empresas_sancionadas(hoy: date) -> dict[str, list[str]]:
    """DNI → razones sociales con sanción vigente en las que figura esa persona."""
    resultado: dict[str, list[str]] = {}
    for ficha in _REGISTRO.values():
        if any(s.tipo == "inhabilitacion" and (s.hasta is None or s.hasta >= hoy) for s in ficha.sanciones):
            for v in ficha.vinculados:
                resultado.setdefault(v.dni, []).append(ficha.padron.razon_social)
    return resultado
