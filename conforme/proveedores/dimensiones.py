"""Las seis dimensiones del análisis de un posible proveedor. Funciones puras.

Cada dimensión devuelve un resultado con:
- `estado`: «limpio», «revisar» o «alerta» (se muestra como verde, ámbar o rojo);
- `resumen`: una línea en español claro;
- `hallazgos`: qué se encontró, por qué importa y qué acción corresponde;
- `fuentes`: qué se consultó y qué respondió (para profundizar a demanda).

Las reglas son deterministas: el mismo expediente da siempre el mismo resultado.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from conforme import normativa
from conforme.proveedores.fuentes import FichaEmpresa

LIMPIO, REVISAR, ALERTA = "limpio", "revisar", "alerta"
_ORDEN = {LIMPIO: 0, REVISAR: 1, ALERTA: 2}

DIMENSIONES = {
    "antecedentes": "Antecedentes y sanciones",
    "empresa": "Empresa real y capacidad",
    "personas": "Personas de interés y empresas clon",
    "colusion": "Colusión entre postores",
    "precio": "Precio y mercado",
    "desempeno": "Desempeño previo en la entidad",
}

ROLES_VINCULADO = {
    "representante_legal": "representante legal", "socio": "socio", "apoderado": "apoderado",
    "gerente": "gerente",
}


@dataclass(frozen=True)
class Postor:
    id: int
    ruc: str
    razon_social: str
    monto_cotizado: Decimal
    plazo_dias: int
    contacto_correo: str | None = None
    contacto_telefono: str | None = None
    direccion: str | None = None


@dataclass(frozen=True)
class Funcionario:
    dni: str
    nombre: str
    papel: str          # p. ej. «solicitante del requerimiento», «evaluador de Abastecimiento»


@dataclass(frozen=True)
class Historial:
    expedientes: int = 0
    con_penalidad: int = 0
    con_atraso: int = 0
    entregables_observados: int = 0
    conformidades_devueltas: int = 0
    ordenes_12m: int = 0
    codigos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Contexto:
    descripcion: str
    valor_estimado: Decimal
    plazo_dias: int
    hoy: date
    funcionarios: tuple[Funcionario, ...] = ()
    otros: tuple[tuple[Postor, FichaEmpresa], ...] = ()
    personas_sancionadas: dict[str, list[str]] = field(default_factory=dict)
    historial: Historial = Historial()
    comparables: tuple[tuple[str, Decimal], ...] = ()   # (código, monto) de compras parecidas


def _hallazgo(nivel, que, por_que, accion, **extra):
    return {"nivel": nivel, "que": que, "por_que": por_que, "accion": accion, **extra}


def _resultado(clave, hallazgos, fuentes, resumen_limpio, **extra):
    estado = max((h["nivel"] for h in hallazgos), key=_ORDEN.get, default=LIMPIO)
    if hallazgos:
        principales = [h["que"] for h in hallazgos if h["nivel"] == estado]
        resumen = principales[0] + (f" (y {len(hallazgos) - 1} más)" if len(hallazgos) > 1 else "")
    else:
        resumen = resumen_limpio
    return {"clave": clave, "titulo": DIMENSIONES[clave], "estado": estado, "resumen": resumen,
            "hallazgos": hallazgos, "fuentes": fuentes, "simulado": True, **extra}


def _normalizar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _direccion_base(texto: str | None) -> str:
    """Dirección sin oficina ni interior: «Jr. Bolívar 812, Of. 3» y «Of. 5» coinciden."""
    base = _normalizar(texto).split(",")[0]
    return re.sub(r"\s+", " ", base).strip()


_VACIAS = {"de", "del", "la", "las", "los", "el", "y", "e", "para", "en", "con", "por", "a", "al",
           "servicio", "servicios", "adquisicion", "contratacion", "un", "una"}


def palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9]+", _normalizar(texto)) if len(p) > 3 and p not in _VACIAS}


def _meses_entre(desde: date, hasta: date) -> int:
    return (hasta.year - desde.year) * 12 + hasta.month - desde.month - (hasta.day < desde.day)


# --- 1. Antecedentes y sanciones --------------------------------------------------------

def antecedentes(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    hallazgos = []
    for s in ficha.sanciones:
        vigente = s.hasta is None or s.hasta >= ctx.hoy
        if s.tipo == "inhabilitacion" and vigente:
            hallazgos.append(_hallazgo(
                ALERTA, f"Inhabilitado para contratar con el Estado hasta el {s.hasta:%d/%m/%Y}",
                f"{s.resolucion}: {s.motivo}. Mientras dure la sanción, el proveedor está impedido de contratar.",
                "Descarta a este postor. No puede ser seleccionado.", impide=True))
        elif s.tipo == "inhabilitacion":
            hallazgos.append(_hallazgo(
                REVISAR, f"Tuvo una inhabilitación que ya venció ({s.hasta:%d/%m/%Y})",
                f"{s.resolucion}: {s.motivo}.",
                "No impide contratar, pero anota el antecedente en tu sustento."))
        else:
            hallazgos.append(_hallazgo(
                REVISAR, f"Registra una multa del Tribunal ({s.desde:%m/%Y})",
                f"{s.resolucion}: {s.motivo}.",
                "Verifica si la multa está pagada y considéralo en la comparación."))
    fuentes = [{"nombre": "Registro de inhabilitados y multas del Tribunal de Contrataciones",
                "resultado": f"{len(ficha.sanciones)} registro(s)" if ficha.sanciones else "Sin registros"}]
    return _resultado("antecedentes", hallazgos, fuentes, "Sin sanciones, multas ni inhabilitaciones registradas.")


# --- 2. Empresa real y capacidad --------------------------------------------------------

def empresa(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    p = ficha.padron
    hallazgos = []
    if p.estado != "ACTIVO":
        hallazgos.append(_hallazgo(
            ALERTA, f"El RUC figura como «{p.estado}»",
            "Una empresa que no está activa en SUNAT no puede emitir comprobantes válidos.",
            "Descarta a este postor.", impide=True))
    if p.condicion != "HABIDO":
        hallazgos.append(_hallazgo(
            ALERTA, "El contribuyente figura como «NO HABIDO»",
            "SUNAT no ubica a la empresa en su domicilio fiscal: es un indicio fuerte de empresa de fachada.",
            "Descarta a este postor.", impide=True))
    meses = _meses_entre(p.inicio_actividades, ctx.hoy)
    if meses < normativa.EMPRESA_ANTIGUEDAD_MINIMA_MESES:
        hallazgos.append(_hallazgo(
            REVISAR, f"Empresa creada hace {max(meses, 0)} meses",
            "Una empresa muy reciente puede no tener la experiencia ni la estructura para cumplir.",
            "Pide constancias de experiencia y verifica que pueda ejecutar el servicio.", reciente=True))
    if p.palabras_rubro:
        if not palabras(ctx.descripcion) & set(p.palabras_rubro):
            hallazgos.append(_hallazgo(
                REVISAR, "Su actividad registrada no coincide con lo que se compra",
                f"En SUNAT figura como «{p.actividad}» (CIIU {p.ciiu}), que no corresponde al objeto del requerimiento.",
                "Pide que acredite experiencia en este tipo de prestación.", rubro_distinto=True))
    if p.trabajadores is not None and p.trabajadores <= 1:
        hallazgos.append(_hallazgo(
            REVISAR, "Declara un solo trabajador",
            "Con ese tamaño es difícil ejecutar la prestación sin subcontratarla.",
            "Verifica con qué personal ejecutará el servicio."))
    fuentes = [{"nombre": "Padrón RUC de SUNAT",
                "resultado": (f"{p.estado} · {p.condicion} · inicio {p.inicio_actividades:%d/%m/%Y}"
                              + (f" · CIIU {p.ciiu} {p.actividad}" if p.ciiu else "")
                              + (f" · {p.trabajadores} trabajador(es)" if p.trabajadores is not None else ""))
                + (" (ficha genérica: el RUC no está en el registro simulado)" if p.generico else "")},
               {"nombre": "Domicilio fiscal", "resultado": p.domicilio}]
    return _resultado("empresa", hallazgos, fuentes,
                      f"Activa y habida desde {p.inicio_actividades.year}; su rubro es compatible."
                      if p.palabras_rubro else f"Activa y habida desde {p.inicio_actividades.year}.")


# --- 3. Personas de interés y empresas clon ---------------------------------------------

def personas(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    hallazgos = []
    funcionarios = {f.dni: f for f in ctx.funcionarios}
    for v in ficha.vinculados:
        rol = ROLES_VINCULADO.get(v.rol, v.rol)
        if v.dni in funcionarios:
            f = funcionarios[v.dni]
            hallazgos.append(_hallazgo(
                ALERTA, f"{v.nombre}, {rol} del postor, es {f.papel}",
                "Quien interviene en la compra no puede tener interés en el proveedor: es un conflicto de intereses.",
                "No selecciones a este postor y registra el vínculo para el OCI.", impide=True,
                vinculo={"dni": v.dni, "nombre": v.nombre, "papel": f.papel}))
        for otro, ficha_otro in ctx.otros:
            if any(w.dni == v.dni for w in ficha_otro.vinculados):
                hallazgos.append(_hallazgo(
                    ALERTA, f"{v.nombre} también figura en {otro.razon_social}",
                    "Dos postores con las mismas personas detrás no compiten de verdad (empresas clon).",
                    "Trata a ambos postores como uno solo y considera descartarlos."))
        if v.dni in ctx.personas_sancionadas and ficha.padron.razon_social not in ctx.personas_sancionadas[v.dni]:
            empresas = ", ".join(ctx.personas_sancionadas[v.dni])
            hallazgos.append(_hallazgo(
                REVISAR, f"{v.nombre} figura en una empresa inhabilitada ({empresas})",
                "Puede ser una empresa creada para eludir la sanción de otra.",
                "Verifica la relación entre ambas empresas antes de seleccionarla."))
    fuentes = [{"nombre": "Composición societaria y representantes (simulado)",
                "resultado": "; ".join(f"{v.nombre} ({ROLES_VINCULADO.get(v.rol, v.rol)})" for v in ficha.vinculados)
                or "Sin personas registradas"},
               {"nombre": "Funcionarios que intervienen en la compra",
                "resultado": "; ".join(f"{f.nombre} ({f.papel})" for f in ctx.funcionarios) or "—"}]
    personas_ = [{"dni": v.dni, "nombre": v.nombre, "rol": ROLES_VINCULADO.get(v.rol, v.rol)} for v in ficha.vinculados]
    return _resultado("personas", hallazgos, fuentes,
                      "Ninguna persona del postor coincide con funcionarios ni con otros postores.",
                      personas=personas_)


# --- 4. Colusión entre postores ---------------------------------------------------------

def colusion(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    hallazgos = []
    propios_tel = {_digitos(t) for t in (postor.contacto_telefono, *ficha.telefonos) if _digitos(t)}
    propios_correo = {_normalizar(c) for c in (postor.contacto_correo, *ficha.correos) if c}
    propia_dir = {_direccion_base(d) for d in (postor.direccion, ficha.padron.domicilio)
                  if d and "simulado" not in d}
    for otro, ficha_otro in ctx.otros:
        tel = {_digitos(t) for t in (otro.contacto_telefono, *ficha_otro.telefonos) if _digitos(t)}
        correo = {_normalizar(c) for c in (otro.contacto_correo, *ficha_otro.correos) if c}
        direccion = {_direccion_base(d) for d in (otro.direccion, ficha_otro.padron.domicilio)
                     if d and "simulado" not in d}
        coincidencias = []
        if propios_tel & tel:
            coincidencias.append("el mismo teléfono")
        if propios_correo & correo:
            coincidencias.append("el mismo correo")
        if propia_dir & direccion:
            coincidencias.append("la misma dirección")
        if coincidencias:
            hallazgos.append(_hallazgo(
                ALERTA, f"Comparte {' y '.join(coincidencias)} con {otro.razon_social}",
                "Cotizaciones de supuestos competidores con datos de contacto iguales sugieren que las prepara la misma persona.",
                "No tomes estas cotizaciones como competencia real; documenta el hecho."))
        if otro.monto_cotizado and abs(postor.monto_cotizado - otro.monto_cotizado) / otro.monto_cotizado \
                < normativa.PRECIO_COTIZACIONES_GEMELAS:
            hallazgos.append(_hallazgo(
                REVISAR, f"Cotiza casi lo mismo que {otro.razon_social}",
                "Montos casi idénticos entre postores distintos pueden indicar cotizaciones coordinadas.",
                "Compara el detalle de ambas cotizaciones."))
    fuentes = [{"nombre": "Cruce de cotizaciones del expediente",
                "resultado": f"Comparado con {len(ctx.otros)} postor(es)" if ctx.otros else "Es el único postor"}]
    return _resultado("colusion", hallazgos, fuentes,
                      "Sin datos repetidos con los demás postores." if ctx.otros
                      else "Es el único postor: no hay con quién cruzar.")


# --- 5. Precio y mercado ----------------------------------------------------------------

def precio(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    hallazgos = []
    estimado = ctx.valor_estimado
    variacion = (postor.monto_cotizado - estimado) / estimado
    porcentaje = f"{abs(variacion) * 100:.0f} %"
    if variacion >= normativa.PRECIO_SOBREPRECIO_ALERTA:
        hallazgos.append(_hallazgo(
            ALERTA, f"Cotiza {porcentaje} por encima del valor estimado",
            "Un precio muy superior al estimado puede ser sobreprecio.",
            "Pide el sustento del precio o prefiere otra cotización."))
    elif variacion >= normativa.PRECIO_SOBREPRECIO_REVISAR:
        hallazgos.append(_hallazgo(
            REVISAR, f"Cotiza {porcentaje} por encima del valor estimado",
            "Está por encima de lo previsto para esta compra.",
            "Verifica si el precio se justifica (alcance, calidad, plazo)."))
    elif -variacion >= normativa.PRECIO_BAJO_ALERTA:
        hallazgos.append(_hallazgo(
            ALERTA, f"Cotiza {porcentaje} por debajo del valor estimado",
            "Un precio tan bajo puede ser temerario: riesgo de incumplimiento o de adendas posteriores.",
            "Pide la estructura de costos antes de considerarlo.", precio_atipico=True))
    elif -variacion >= normativa.PRECIO_BAJO_REVISAR:
        hallazgos.append(_hallazgo(
            REVISAR, f"Cotiza {porcentaje} por debajo del valor estimado",
            "Es bastante más barato que lo previsto: conviene confirmar que cubre todo el TDR.",
            "Pide el desagregado de la cotización.", precio_atipico=True))
    if postor.plazo_dias > ctx.plazo_dias:
        hallazgos.append(_hallazgo(
            REVISAR, f"Ofrece {postor.plazo_dias} días; el requerimiento pide {ctx.plazo_dias}",
            "Un plazo mayor al requerido no cumple el TDR.",
            "Confirma si acepta el plazo del requerimiento."))
    if ctx.comparables:
        promedio = sum(m for _, m in ctx.comparables) / len(ctx.comparables)
        texto_hist = f"Promedio {promedio:,.2f} en {len(ctx.comparables)} compra(s) parecida(s)"
    else:
        texto_hist = "Sin compras comparables en la entidad"
    fuentes = [{"nombre": "Valor estimado del requerimiento", "resultado": f"S/ {estimado:,.2f}"},
               {"nombre": "Cotización del postor", "resultado": f"S/ {postor.monto_cotizado:,.2f} "
                f"({'+' if variacion >= 0 else '−'}{porcentaje})"},
               {"nombre": "Histórico interno de compras", "resultado": texto_hist}]
    return _resultado("precio", hallazgos, fuentes,
                      f"Precio coherente con el valor estimado ({'+' if variacion >= 0 else '−'}{porcentaje}).",
                      variacion=float(round(variacion, 4)))


# --- 6. Desempeño previo en la entidad --------------------------------------------------

def desempeno(postor: Postor, ficha: FichaEmpresa, ctx: Contexto) -> dict:
    h = ctx.historial
    hallazgos = []
    incidencias = h.con_penalidad + h.con_atraso
    if incidencias >= normativa.DESEMPENO_PENALIDADES_ALERTA:
        hallazgos.append(_hallazgo(
            ALERTA, f"{incidencias} atrasos o penalidades en contrataciones anteriores",
            "Tiene un historial reiterado de incumplimientos con la entidad.",
            "Pondéralo en la selección y exige garantías de cumplimiento."))
    elif incidencias >= normativa.DESEMPENO_PENALIDADES_REVISAR:
        hallazgos.append(_hallazgo(
            REVISAR, f"{incidencias} atraso(s) o penalidad(es) en contrataciones anteriores",
            "Ya incumplió plazos con la entidad.",
            "Revisa esos expedientes antes de decidir."))
    if h.entregables_observados or h.conformidades_devueltas:
        hallazgos.append(_hallazgo(
            REVISAR, f"{h.entregables_observados} entregable(s) observado(s) en el pasado",
            "Sus entregas anteriores necesitaron correcciones.",
            "Define bien los entregables y la evidencia exigida."))
    if h.ordenes_12m >= normativa.DESEMPENO_CONCENTRACION_ORDENES_12M:
        hallazgos.append(_hallazgo(
            REVISAR, f"Ya tiene {h.ordenes_12m} órdenes con la entidad en los últimos 12 meses",
            "La concentración de órdenes en un mismo proveedor reduce la competencia.",
            "Justifica por qué no se elige a otro proveedor."))
    fuentes = [{"nombre": "Expedientes anteriores en Conforme",
                "resultado": (f"{h.expedientes} expediente(s): " + ", ".join(h.codigos[:6])
                              + ("…" if len(h.codigos) > 6 else "")) if h.expedientes
                else "Sin contrataciones anteriores con la entidad"}]
    return _resultado("desempeno", hallazgos, fuentes,
                      f"{h.expedientes} contratación(es) anteriores sin incidencias." if h.expedientes
                      else "Sin contrataciones anteriores con la entidad.")


FUNCIONES = {
    "antecedentes": antecedentes, "empresa": empresa, "personas": personas,
    "colusion": colusion, "precio": precio, "desempeno": desempeno,
}


def evaluar(postor: Postor, ficha: FichaEmpresa, ctx: Contexto, claves=None) -> dict[str, dict]:
    return {clave: FUNCIONES[clave](postor, ficha, ctx) for clave in (claves or FUNCIONES)}
