"""Generador de datos 100 % sintéticos con semilla fija.

No toca la base de datos: devuelve listas de diccionarios que se enlazan por
claves naturales (sigla, dni, ruc, código). `scripts/sembrar.py` las inserta.

DNI y RUC llevan un prefijo que marca el dato como sintético. Los RUC reales
empiezan en 10, 15, 16, 17 o 20, así que 99 no existe. Para el DNI, 99 es un
SUPUESTO por confirmar (ver PLAN.md).
"""
import hashlib
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from faker import Faker

from datos import caso_estrella

SEMILLA = 20261125
PREFIJO_DNI = "99"
PREFIJO_RUC = "99"
FECHA_REFERENCIA = date(2026, 11, 1)  # "hoy" fijo, para que los datos no cambien

N_PERSONAS_POR_AREA = 5
N_PROVEEDORES = 120
N_EXPEDIENTES = 300  # incluye el caso estrella

# (nombre, sigla, rol de sus usuarios)
AREAS = [
    ("Logística y Abastecimiento", "LOG", "area_usuaria"),
    ("Tesorería", "TES", "tesoreria"),
    ("Órgano de Control Institucional", "OCI", "auditor"),
    ("Tecnologías de la Información", "TI", "area_usuaria"),
    ("Recursos Humanos", "RH", "area_usuaria"),
    ("Infraestructura y Mantenimiento", "INF", "area_usuaria"),
    ("Comunicaciones e Imagen", "COM", "area_usuaria"),
    ("Asesoría Jurídica", "AJ", "area_usuaria"),
    ("Planeamiento y Presupuesto", "PP", "area_usuaria"),
    ("Servicios Generales", "SG", "area_usuaria"),
    ("Bienestar y Capacitación", "BC", "area_usuaria"),
    ("Gestión Ambiental", "GA", "area_usuaria"),
]
CARGOS = ["Jefatura de área", "Especialista", "Analista", "Asistente administrativo", "Técnico"]

_RAZON_1 = ["Servicios", "Inversiones", "Corporación", "Grupo", "Consorcio", "Soluciones",
            "Distribuidora", "Comercial", "Constructora", "Suministros", "Tecnologías", "Logística"]
_RAZON_2 = ["Andina", "del Pacífico", "Altiplano", "Sol Naciente", "Cordillera", "Rímac",
            "Los Olivos", "Misti", "Huascarán", "Amazonía", "Costa Verde", "El Tumi",
            "Santa Rosa", "Inti", "Chavín", "Paracas", "Qhapaq", "Vilcanota"]
_RAZON_SUFIJO = ["S.A.C.", "E.I.R.L.", "S.R.L.", "S.A."]

_SERVICIOS = [
    "Servicio de mantenimiento de equipos de cómputo",
    "Servicio de limpieza y desinfección de ambientes",
    "Servicio de vigilancia y seguridad",
    "Servicio de impresión de material institucional",
    "Servicio de capacitación al personal",
    "Servicio de soporte y desarrollo de software",
    "Servicio de mantenimiento de áreas verdes",
    "Servicio de pintado de fachadas e interiores",
    "Servicio de consultoría para diagnóstico de procesos",
    "Servicio de transporte de personal",
    "Servicio de fumigación y control de plagas",
    "Servicio de mantenimiento de ascensores",
]
_BIENES = [
    "Adquisición de útiles de escritorio",
    "Adquisición de equipos de cómputo",
    "Adquisición de mobiliario de oficina",
    "Adquisición de materiales de limpieza",
    "Adquisición de tóner y suministros de impresión",
    "Adquisición de equipos de protección personal",
    "Adquisición de materiales eléctricos",
    "Adquisición de licencias de software",
    "Adquisición de luminarias LED",
    "Adquisición de materiales de ferretería",
]
_PLAZOS = [15, 30, 45, 60, 90, 120]


def _momento(rng: random.Random, dia: date) -> datetime:
    """Una hora de oficina del día indicado, en UTC."""
    return datetime.combine(
        dia, time(rng.randint(13, 22), rng.randint(0, 59), rng.randint(0, 59)), timezone.utc
    )


def _eventos_iniciales(rng: random.Random, exp: dict, personas_logistica: list[dict]) -> list[dict]:
    orden = exp["numero_orden"]
    return [
        {
            "ts": _momento(rng, exp["fecha_requerimiento"]),
            "actor_dni": exp["solicitante_dni"],
            "accion": "expediente.registrado",
            "entidad": "expediente",
            "expediente_codigo": exp["codigo"],
            "detalle": {"codigo": exp["codigo"], "monto": exp["monto"], "plazo_dias": exp["plazo_dias"]},
            "documento_sha256": None,
        },
        {
            "ts": _momento(rng, exp["fecha_orden"]),
            "actor_dni": rng.choice(personas_logistica)["dni"],
            "accion": "orden.emitida",
            "entidad": "expediente",
            "expediente_codigo": exp["codigo"],
            "detalle": {"numero_orden": orden, "documento": f"{orden}.pdf"},
            "documento_sha256": hashlib.sha256(f"documento sintético {orden}".encode()).hexdigest(),
        },
    ]


def generar(semilla: int = SEMILLA) -> dict:
    rng = random.Random(semilla)
    fake = Faker("es_MX")
    fake.seed_instance(semilla)

    areas = [{"nombre": n, "sigla": s} for n, s, _ in AREAS]

    personas, usuarios = [], []
    for _, sigla, rol in AREAS:
        for i in range(N_PERSONAS_POR_AREA):
            dni = f"{PREFIJO_DNI}{len(personas) + 1:06d}"
            personas.append({
                "dni": dni,
                "nombres": fake.first_name(),
                "apellidos": f"{fake.last_name()} {fake.last_name()}",
                "cargo": CARGOS[i],
                "area_sigla": sigla,
            })
            usuarios.append({"username": f"{sigla.lower()}{i + 1}", "persona_dni": dni, "rol": rol})

    proveedores, usados = [], set()
    while len(proveedores) < N_PROVEEDORES:
        razon = f"{rng.choice(_RAZON_1)} {rng.choice(_RAZON_2)} {rng.choice(_RAZON_SUFIJO)}"
        if razon in usados:
            continue
        usados.add(razon)
        proveedores.append({"ruc": f"{PREFIJO_RUC}{len(proveedores) + 1:09d}", "razon_social": razon})

    por_area: dict[str, list[dict]] = {}
    for p in personas:
        por_area.setdefault(p["area_sigla"], []).append(p)
    siglas_usuarias = [s for _, s, rol in AREAS if rol == "area_usuaria"]

    expedientes, eventos = [], []
    for n in range(1, N_EXPEDIENTES):  # el último número queda para el caso estrella
        sigla = rng.choice(siglas_usuarias)
        tipo = rng.choice(["servicio", "bien"])
        requerimiento = date(2026, 1, 5) + timedelta(days=rng.randint(0, 240))
        orden = requerimiento + timedelta(days=rng.randint(5, 20))
        inicio = orden + timedelta(days=rng.randint(1, 5))
        plazo = rng.choice(_PLAZOS)
        limite = orden + timedelta(days=plazo)
        # F1 genera solo expedientes "limpios"; las anomalías se siembran en F2.
        entrega = None
        if limite <= FECHA_REFERENCIA:
            entrega = max(inicio, limite - timedelta(days=rng.randint(0, 5)))
        exp = {
            "codigo": f"EXP-2026-{n:04d}",
            "tipo": tipo,
            "descripcion": rng.choice(_SERVICIOS if tipo == "servicio" else _BIENES),
            "area_sigla": sigla,
            "proveedor_ruc": rng.choice(proveedores)["ruc"],
            "solicitante_dni": rng.choice(por_area[sigla])["dni"],
            "numero_orden": f"{'OS' if tipo == 'servicio' else 'OC'}-2026-{n:05d}",
            "fecha_requerimiento": requerimiento,
            "fecha_orden": orden,
            "fecha_inicio_prestacion": inicio,
            "plazo_dias": plazo,
            "fecha_entrega_real": entrega,
            "monto": Decimal(rng.randrange(150_000, 18_000_000)) / 100,
        }
        expedientes.append(exp)
        eventos.extend(_eventos_iniciales(rng, exp, por_area["LOG"]))

    dni_por_username = {u["username"]: u["persona_dni"] for u in usuarios}
    estrella = dict(caso_estrella.EXPEDIENTE)
    estrella["proveedor_ruc"] = proveedores[0]["ruc"]
    estrella["solicitante_dni"] = dni_por_username[caso_estrella.USERNAME_SOLICITANTE]
    expedientes.append(estrella)
    eventos.extend(_eventos_iniciales(rng, estrella, por_area["LOG"]))

    # La bitácora se encadena en orden cronológico.
    eventos.sort(key=lambda e: (e["ts"], e["expediente_codigo"], e["accion"]))

    return {
        "areas": areas,
        "personas": personas,
        "usuarios": usuarios,
        "proveedores": proveedores,
        "expedientes": expedientes,
        "eventos": eventos,
        "sal_password": rng.randbytes(16).hex(),
    }
