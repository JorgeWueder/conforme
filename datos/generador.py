"""Generador de datos 100 % sintéticos con semilla fija.

No toca la base de datos: devuelve listas de diccionarios que se enlazan por
claves naturales (sigla, dni, ruc, código). `scripts/sembrar.py` las inserta.

Las anomalías sembradas se devuelven aparte, en "anomalias": son la respuesta
correcta contra la que `scripts/medir_deteccion.py` compara las alertas.

DNI y RUC llevan un prefijo que marca el dato como sintético. Los RUC reales
empiezan en 10, 15, 16, 17 o 20, así que 99 no existe. Para el DNI, 99 es un
SUPUESTO por confirmar (ver PLAN.md).
"""
import hashlib
import random
import struct
import zlib
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from faker import Faker

from conforme import normativa
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

_ENTREGABLES_SERVICIO = [
    "Plan de trabajo",
    "Informe de avance",
    "Acta de ejecución del servicio",
    "Registro fotográfico de los trabajos",
    "Informe final",
]
_ENTREGABLES_BIEN = [
    "Entrega de los bienes en almacén",
    "Guía de remisión firmada",
    "Acta de instalación y pruebas",
    "Certificados de garantía",
    "Manuales y fichas técnicas",
]

# Anomalías sembradas (se etiquetan en la tabla de anomalías) y casos trampa.
# R5A = pago sin conformidad; R5B = pago anterior a la conformidad.
# ATRASO_OK = entrega tardía con la penalidad completa: NO debe alertar.
_PLAN_ANOMALIAS = (["R1"] * 5 + ["R2"] * 5 + ["R3"] * 5 + ["R4"] * 5
                   + ["R5A"] * 3 + ["R5B"] * 2 + ["ATRASO_OK"] * 5)
_PROPORCION_CON_CONFORMIDAD = 0.88
_PROPORCION_CON_PAGO = 0.80


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


def _png(rgb: tuple[int, int, int], ancho: int = 16, alto: int = 12) -> bytes:
    """Imagen PNG mínima de un solo color. Sin compresión, para que los bytes
    (y por tanto el SHA-256) no dependan de la versión de zlib."""
    def bloque(tipo: bytes, cuerpo: bytes) -> bytes:
        return (struct.pack(">I", len(cuerpo)) + tipo + cuerpo
                + struct.pack(">I", zlib.crc32(tipo + cuerpo)))

    filas = (b"\x00" + bytes(rgb) * ancho) * alto
    return (b"\x89PNG\r\n\x1a\n"
            + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
            + bloque(b"IDAT", zlib.compress(filas, 0))
            + bloque(b"IEND", b""))


def _evidencia(rng: random.Random, codigo: str, numero: int, indice: int) -> dict:
    contenido = _png((rng.randint(40, 215), rng.randint(40, 215), rng.randint(40, 215)))
    return {
        "nombre_archivo": f"{codigo}-entregable-{numero}-foto-{indice}.png",
        "mime": "image/png",
        "tamano": len(contenido),
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "contenido": contenido,
    }


def _conformidad(rng: random.Random, exp: dict, numeros: list[int], conformante_dni: str,
                 fecha_conformidad: date, penalidad: Decimal, sin_evidencia: set[int],
                 observaciones: str = "") -> tuple[dict, list[dict]]:
    """Conformidad con todos los entregables cumplidos, y sus eventos de bitácora."""
    codigo = exp["codigo"]
    ts = _momento(rng, fecha_conformidad)
    items = []
    for numero in numeros:
        n = 0 if numero in sin_evidencia else rng.randint(1, 2)
        items.append({
            "numero": numero,
            "cumplido": True,
            "observacion": "",
            "evidencias": [_evidencia(rng, codigo, numero, i + 1) for i in range(n)],
        })
    conformidad = {
        "expediente_codigo": codigo,
        "conformante_dni": conformante_dni,
        "fecha_conformidad": fecha_conformidad,
        "observaciones": observaciones,
        "penalidad_aplicada": penalidad,
        "registrada_en": ts,
        "items": items,
    }
    eventos = [{
        "ts": ts,
        "actor_dni": conformante_dni,
        "accion": "conformidad.registrada",
        "entidad": "conformidad",
        "ref": ("conformidad", codigo),
        "expediente_codigo": codigo,
        "detalle": {
            "fecha_conformidad": fecha_conformidad,
            "fecha_entrega_real": exp["fecha_entrega_real"],
            "penalidad_aplicada": penalidad,
            "entregables": len(numeros),
            "entregables_cumplidos": len(numeros),
            "resumen": f"{len(numeros)} de {len(numeros)} entregables dados por cumplidos.",
        },
        "documento_sha256": None,
    }]
    for item in items:
        for indice, evidencia in enumerate(item["evidencias"]):
            eventos.append({
                "ts": ts,
                "actor_dni": conformante_dni,
                "accion": "evidencia.adjuntada",
                "entidad": "evidencia",
                "ref": ("evidencia", codigo, item["numero"], indice),
                "expediente_codigo": codigo,
                "detalle": {"documento": evidencia["nombre_archivo"],
                            "entregable": item["numero"]},
                "documento_sha256": evidencia["sha256"],
            })
    return conformidad, eventos


def _pago(rng: random.Random, exp: dict, fecha_pago: date, penalidad: Decimal,
          tesoreros: list[dict]) -> tuple[dict, dict]:
    ts = _momento(rng, fecha_pago)
    pago = {
        "expediente_codigo": exp["codigo"],
        "fecha_pago": fecha_pago,
        "monto": exp["monto"] - penalidad,
        "penalidad_descontada": penalidad,
        "registrado_por_dni": rng.choice(tesoreros)["dni"],
        "registrado_en": ts,
    }
    evento = {
        "ts": ts,
        "actor_dni": pago["registrado_por_dni"],
        "accion": "pago.registrado",
        "entidad": "pago",
        "ref": ("pago", exp["codigo"]),
        "expediente_codigo": exp["codigo"],
        "detalle": {"fecha_pago": fecha_pago, "monto": pago["monto"],
                    "penalidad_descontada": penalidad},
        "documento_sha256": None,
    }
    return pago, evento


def _fase_2(rng: random.Random, generados: list[dict], estrella: dict,
            por_area: dict[str, list[dict]], dni_por_username: dict[str, str]) -> dict:
    """Entregables, conformidades, pagos y anomalías. Atrasa la entrega de los
    expedientes elegidos para R2 y ATRASO_OK (modifica `generados`)."""
    entregables, conformidades, pagos, anomalias, eventos = [], [], [], [], []
    numeros_de: dict[str, list[int]] = {}

    for exp in generados:
        catalogo = _ENTREGABLES_SERVICIO if exp["tipo"] == "servicio" else _ENTREGABLES_BIEN
        elegidos = sorted(rng.sample(range(len(catalogo)), rng.randint(2, 4)))
        numeros_de[exp["codigo"]] = list(range(1, len(elegidos) + 1))
        entregables.extend(
            {"expediente_codigo": exp["codigo"], "numero": n, "descripcion": catalogo[i],
             "origen": "manual"}
            for n, i in enumerate(elegidos, start=1)
        )

    candidatos = [x for x in generados if x["fecha_entrega_real"] is not None]
    rng.shuffle(candidatos)
    plan = {x["codigo"]: etiqueta for x, etiqueta in zip(candidatos, _PLAN_ANOMALIAS)}

    for exp in generados:
        if exp["fecha_entrega_real"] is None:
            continue  # todavía en plazo: sin conformidad ni pago
        codigo = exp["codigo"]
        etiqueta = plan.get(codigo) or (
            "NORMAL" if rng.random() < _PROPORCION_CON_CONFORMIDAD else "PENDIENTE")
        if etiqueta == "PENDIENTE":
            continue

        if etiqueta == "R5A":
            fecha_pago = exp["fecha_entrega_real"] + timedelta(days=rng.randint(5, 15))
            pago, evento = _pago(rng, exp, fecha_pago, Decimal("0.00"), por_area["TES"])
            pagos.append(pago)
            eventos.append(evento)
            anomalias.append({"expediente_codigo": codigo, "regla": "R5",
                              "nota": "Pago registrado sin conformidad."})
            continue

        penalidad = Decimal("0.00")
        if etiqueta in ("R2", "ATRASO_OK"):
            atraso = rng.randint(3, 20)
            exp["fecha_entrega_real"] = (
                normativa.fecha_limite(exp["fecha_orden"], exp["plazo_dias"])
                + timedelta(days=atraso))
            esperada = normativa.penalidad_esperada(exp["monto"], exp["plazo_dias"], atraso)
            if etiqueta == "ATRASO_OK":
                penalidad = esperada
            else:
                if rng.random() < 0.5:  # penalidad parcial
                    penalidad = (esperada / 2).quantize(Decimal("0.01"))
                anomalias.append({
                    "expediente_codigo": codigo, "regla": "R2",
                    "nota": f"{atraso} días de atraso; esperada {esperada}, aplicada {penalidad}.",
                })

        if etiqueta == "R4":
            conformante = exp["solicitante_dni"]
            anomalias.append({"expediente_codigo": codigo, "regla": "R4",
                              "nota": "Solicitante y conformante son la misma persona."})
        else:
            conformante = rng.choice(
                [p for p in por_area[exp["area_sigla"]] if p["dni"] != exp["solicitante_dni"]]
            )["dni"]

        if etiqueta == "R3":
            espera = rng.randint(normativa.CONFORMIDAD_PLAZO_MAXIMO_DIAS + 1, 25)
            anomalias.append({"expediente_codigo": codigo, "regla": "R3",
                              "nota": f"Conformidad {espera} días después de la entrega."})
        else:
            espera = rng.randint(0, 5)
        fecha_conformidad = exp["fecha_entrega_real"] + timedelta(days=espera)

        sin_evidencia = set()
        if etiqueta == "R1":
            sin_evidencia = set(rng.sample(numeros_de[codigo], rng.randint(1, 2)))
            anomalias.append({
                "expediente_codigo": codigo, "regla": "R1",
                "nota": f"Entregables sin evidencia: {sorted(sin_evidencia)}.",
            })

        conformidad, eventos_conformidad = _conformidad(
            rng, exp, numeros_de[codigo], conformante, fecha_conformidad, penalidad, sin_evidencia)
        conformidades.append(conformidad)
        eventos.extend(eventos_conformidad)

        if etiqueta == "R5B":
            fecha_pago = fecha_conformidad - timedelta(days=rng.randint(1, 10))
            anomalias.append({"expediente_codigo": codigo, "regla": "R5",
                              "nota": "Pago anterior a la fecha de la conformidad."})
        elif rng.random() < _PROPORCION_CON_PAGO:
            fecha_pago = fecha_conformidad + timedelta(days=rng.randint(3, 15))
        else:
            continue
        pago, evento = _pago(rng, exp, fecha_pago, penalidad, por_area["TES"])
        pagos.append(pago)
        eventos.append(evento)

    # Caso estrella.
    codigo = estrella["codigo"]
    numeros = list(range(1, len(caso_estrella.ENTREGABLES) + 1))
    entregables.extend(
        {"expediente_codigo": codigo, "numero": n, "descripcion": d, "origen": "manual"}
        for n, d in zip(numeros, caso_estrella.ENTREGABLES)
    )
    conformidad, eventos_conformidad = _conformidad(
        rng, estrella, numeros, dni_por_username[caso_estrella.USERNAME_CONFORMANTE],
        caso_estrella.CONFORMIDAD["fecha_conformidad"],
        caso_estrella.CONFORMIDAD["penalidad_aplicada"],
        {caso_estrella.ENTREGABLE_SIN_EVIDENCIA},
        caso_estrella.CONFORMIDAD["observaciones"],
    )
    conformidades.append(conformidad)
    eventos.extend(eventos_conformidad)
    anomalias.extend({"expediente_codigo": codigo, "regla": regla, "nota": nota}
                     for regla, nota in caso_estrella.ANOMALIAS)

    return {"entregables": entregables, "conformidades": conformidades, "pagos": pagos,
            "anomalias": anomalias, "eventos": eventos}


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
        # Aquí todos salen "limpios"; _fase_2 siembra después las anomalías.
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

    # F2 usa su propio generador de azar: así los datos de F1 no cambian.
    fase_2 = _fase_2(random.Random(semilla + 2), expedientes[:-1], estrella,
                     por_area, dni_por_username)
    eventos.extend(fase_2["eventos"])

    # La bitácora se encadena en orden cronológico; a igual momento se respeta
    # el orden en que se generaron (la conformidad antes que sus evidencias).
    posicion = {id(e): i for i, e in enumerate(eventos)}
    eventos.sort(key=lambda e: (e["ts"], e["expediente_codigo"], posicion[id(e)]))

    return {
        "areas": areas,
        "personas": personas,
        "usuarios": usuarios,
        "proveedores": proveedores,
        "expedientes": expedientes,
        "entregables": fase_2["entregables"],
        "conformidades": fase_2["conformidades"],
        "pagos": fase_2["pagos"],
        "anomalias": fase_2["anomalias"],
        "eventos": eventos,
        "sal_password": rng.randbytes(16).hex(),
    }
