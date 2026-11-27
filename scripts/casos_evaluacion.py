"""Casos de demostración de la evaluación de posibles proveedores (Fase 2).

Se cargan después de `scripts.sembrar` (que los llama al final) y usan las mismas funciones
que la aplicación, así que pasan por permisos, reglas y bitácora. No forman parte de la
siembra reproducible porque sus registros llevan la fecha del día en que se cargan.

Uso:  python -m scripts.casos_evaluacion   (tras sembrar)

Casos (área de inf1):
- Mantenimiento de equipos de laboratorio: tres postores sin analizar. Uno limpio, uno con
  la solicitante como socia, empresa recién creada y precio bajo, y uno inhabilitado que
  comparte teléfono y apoderado con el anterior. Para demostrar «Analizar todas».
- Soporte de la red de datos: ya evaluado por dec1 y enviado a revisión independiente;
  lo revisa dec2.
- Fumigación de ambientes: selección aprobada; inf1 confirma la orden.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from conforme import auth, db, repositorio
from conforme.ia.extractor import EntregableIA, PropuestaIA
from conforme.modelos import Area, Expediente, Persona, Usuario
from conforme.proveedores import fuentes
from conforme.proveedores import repositorio as evaluacion

LABORATORIO = "Servicio de mantenimiento preventivo y calibración de equipos de laboratorio de química"
RED = "Servicio de soporte técnico y mantenimiento de la red de datos del pabellón administrativo"
FUMIGACION = "Servicio de fumigación, desratización y desinfección de ambientes académicos"


def _actor(sesion: Session, username: str):
    usuario_id = sesion.scalar(select(Usuario.id).where(Usuario.username == username))
    return auth.actor_por_id(sesion, usuario_id)


def _tdr_simulado(sesion: Session, actor, expediente_id: int, descripciones: list[str]) -> None:
    """Completa el TDR de los casos ficticios sin llamar a un proveedor de IA."""
    expediente = sesion.get(Expediente, expediente_id)
    propuesta = PropuestaIA(
        objeto=expediente.descripcion, corresponde_al_expediente=True,
        plazo_dias=expediente.plazo_dias,
        entregables=[EntregableIA(numero=i, descripcion=d)
                     for i, d in enumerate(descripciones, start=1)])
    lectura_id = repositorio.registrar_propuesta_ia(
        sesion, actor, expediente_id, archivo_nombre="TDR simulado (caso de demostración)",
        archivo_sha256="0" * 64, propuesta=propuesta, origen="modelo",
        aviso="Lectura simulada para los casos de demostración.")
    repositorio.aprobar_extraccion(sesion, actor, lectura_id, descripciones)
    entregables = repositorio.listar_entregables(sesion, actor, expediente_id)
    repositorio.definir_criterios_evidencia(sesion, actor, expediente_id, [
        {"entregable_id": e["id"], "criterio_evidencia": f"Documento firmado que acredite: {e['descripcion']}"}
        for e in entregables])


def _asegurar_dec2(sesion: Session) -> None:
    """Bases sembradas antes de la Fase 2 no tienen el segundo especialista: se crea con la
    misma contraseña de demostración que dec1."""
    if sesion.scalar(select(Usuario.id).where(Usuario.username == "dec2")):
        return
    dec1 = sesion.scalar(select(Usuario).where(Usuario.username == "dec1"))
    area_id = sesion.get(Persona, dec1.persona_id).area_id
    persona = Persona(dni=f"{fuentes.PREFIJO_DNI}900002", nombres="Renzo", apellidos="Castañeda Ibáñez",
                      cargo="Especialista de Abastecimiento (revisión independiente)", area_id=area_id)
    sesion.add(persona)
    sesion.flush()
    sesion.add(Usuario(persona_id=persona.id, username="dec2", password_hash=dec1.password_hash,
                       rol="abastecimiento"))
    sesion.flush()


def sembrar_casos(sesion: Session, hoy: date | None = None) -> list[tuple[str, str]]:
    hoy = hoy or date.today()
    _asegurar_dec2(sesion)
    inf1, dec1, dec2 = _actor(sesion, "inf1"), _actor(sesion, "dec1"), _actor(sesion, "dec2")
    area = sesion.get(Area, inf1.area_id)
    solicitante = sesion.scalar(select(Persona).where(Persona.dni == fuentes.DNI_SOLICITANTE_DEMO))
    if solicitante is None:
        solicitante = Persona(dni=fuentes.DNI_SOLICITANTE_DEMO, nombres="Rosa Elena", apellidos="Paredes Gil",
                              cargo="Jefa del Laboratorio de Química", area_id=area.id)
        sesion.add(solicitante)
        sesion.flush()

    # 1. Laboratorio: listo para analizar.
    laboratorio = repositorio.crear_requerimiento(
        sesion, inf1, tipo="servicio", descripcion=LABORATORIO, fecha_requerimiento=hoy - timedelta(days=3),
        plazo_dias=30, monto="28500.00",
        entregables=[], origen_entregables="tdr",
        postores=[
            {"ruc": fuentes.RUC_TECNOLAB, "razon_social": "Tecnolab Servicios Integrales S.A.C.",
             "monto_cotizado": "27350.00", "plazo_dias": 30, "contacto_correo": "ventas@tecnolab-sim.pe",
             "contacto_telefono": "044-281450", "proforma_ref": "COT-TL-2026-118"},
            {"ruc": fuentes.RUC_KALLPA, "razon_social": "Inversiones Kallpa Andina E.I.R.L.",
             "monto_cotizado": "19900.00", "plazo_dias": 25, "contacto_correo": "kallpa.andina.sim@gmail.com",
             "contacto_telefono": "949 555 120", "proforma_ref": "PROF-0007"},
            {"ruc": fuentes.RUC_SERVIMAX, "razon_social": "Grupo Servimax del Norte S.A.C.",
             "monto_cotizado": "33600.00", "plazo_dias": 30, "contacto_correo": "servimax.norte.sim@gmail.com",
             "contacto_telefono": "949-555-120", "proforma_ref": "SMX-COT-552"},
        ])
    sesion.get(Expediente, laboratorio).solicitante_id = solicitante.id
    _tdr_simulado(sesion, inf1, laboratorio, ["Plan de mantenimiento y cronograma",
        "Informe técnico de mantenimiento por equipo", "Certificados de calibración vigentes"])
    from scripts.casos_documentos import sembrar_documentos  # evita una importación circular
    sembrar_documentos(sesion, laboratorio)

    # 2. Red de datos: evaluada por dec1, pendiente de revisión independiente (dec2).
    red = repositorio.crear_requerimiento(
        sesion, inf1, tipo="servicio", descripcion=RED, fecha_requerimiento=hoy - timedelta(days=8),
        plazo_dias=45, monto="42000.00",
        entregables=[], origen_entregables="tdr",
        postores=[
            {"ruc": fuentes.RUC_REDNORTE, "razon_social": "Red Norte Telecomunicaciones S.A.C.",
             "monto_cotizado": "42900.00", "plazo_dias": 45, "contacto_correo": "proyectos@rednorte-sim.pe",
             "contacto_telefono": "044-205500", "proforma_ref": "RN-2026-0331"},
            {"ruc": fuentes.RUC_CONECTA, "razon_social": "Conecta Soluciones TI E.I.R.L.",
             "monto_cotizado": "38700.00", "plazo_dias": 45, "contacto_correo": "contacto@conecta-sim.pe",
             "contacto_telefono": "044-610233", "proforma_ref": "CST-118"},
        ])
    _tdr_simulado(sesion, inf1, red, ["Diagnóstico de la red y plan de trabajo",
        "Informe de mantenimiento correctivo", "Informe final con mediciones de cableado"])
    evaluacion.analizar(sesion, dec1, red)
    evaluacion.consolidar(sesion, dec1, red)
    postores = {p["ruc"]: p for p in evaluacion.obtener(sesion, dec1, red)["postores"]}
    evaluacion.enviar_a_revision(
        sesion, dec1, red, seleccionado_id=postores[fuentes.RUC_REDNORTE]["id"],
        sustento="Única propuesta apta sin observaciones; trayectoria de más de diez años en redes y precio "
                 "2 % sobre el valor estimado, dentro de lo razonable.",
        descartes={postores[fuentes.RUC_CONECTA]["id"]:
                   "Registra una multa del Tribunal de Contrataciones y no acreditó experiencia en cableado estructurado."},
        declaro_sin_conflicto=True)

    # 3. Fumigación: selección aprobada; el área usuaria confirma la orden.
    fumigacion = repositorio.crear_requerimiento(
        sesion, inf1, tipo="servicio", descripcion=FUMIGACION, fecha_requerimiento=hoy - timedelta(days=12),
        plazo_dias=10, monto="6800.00",
        entregables=[], origen_entregables="tdr",
        postores=[
            {"ruc": fuentes.ruc_con_verificador("2060990011"), "razon_social": "Saneamiento Ambiental Chimú S.A.C.",
             "monto_cotizado": "6500.00", "plazo_dias": 10, "contacto_telefono": "044-299310"},
            {"ruc": fuentes.ruc_con_verificador("2060881122"), "razon_social": "Fumigaciones La Libertad E.I.R.L.",
             "monto_cotizado": "7150.00", "plazo_dias": 12, "contacto_telefono": "044-233871"},
        ])
    _tdr_simulado(sesion, inf1, fumigacion, ["Constancia de fumigación por ambiente",
        "Informe con productos y dosis aplicadas"])
    evaluacion.analizar(sesion, dec1, fumigacion)
    evaluacion.consolidar(sesion, dec1, fumigacion)
    postores = sorted(evaluacion.obtener(sesion, dec1, fumigacion)["postores"], key=lambda p: p["monto_cotizado"])
    evaluacion.enviar_a_revision(
        sesion, dec1, fumigacion, seleccionado_id=postores[0]["id"],
        sustento="Menor precio, cumple el plazo de 10 días del requerimiento y no presenta observaciones.",
        descartes={postores[1]["id"]: "Precio mayor y ofrece 12 días, por encima del plazo requerido."},
        declaro_sin_conflicto=True)
    evaluacion.revisar_independiente(sesion, dec2, fumigacion, aprobar=True,
                                     comentario="Selección coherente con el consolidado.")

    codigo = lambda i: sesion.get(Expediente, i).codigo
    return [(codigo(laboratorio), "por analizar"), (codigo(red), "en revisión independiente"),
            (codigo(fumigacion), "selección aprobada")]


if __name__ == "__main__":
    with db.sesion() as s:
        casos = sembrar_casos(s)
    print("Casos cargados: " + ", ".join(f"{c} ({e})" for c, e in casos) + ".")
