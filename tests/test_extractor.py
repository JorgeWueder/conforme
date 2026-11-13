"""Lectura con IA: extractor (con modelo simulado), respaldo y aprobación humana.

Ninguna prueba llama a un modelo real.
"""
import io

import pytest
from pypdf import PdfWriter
from sqlalchemy import text

from conforme import config, repositorio
from conforme.errores import ErrorValidacion
from conforme.ia import extractor
from conforme.ia.extractor import EntregableIA, PropuestaIA, Veredicto
from conforme.permisos import PermisoDenegado
from tests.conftest import actor_de
from tests.test_conformidad import _pendiente

PDF = extractor.PDF_EJEMPLO.read_bytes()


class ModeloFalso:
    """Imita lo que usa el extractor de un modelo de LangChain."""

    def __init__(self, respuesta=None, error=None, veredicto=None, error_veredicto=None):
        self.respuesta, self.error = respuesta, error
        self.veredicto, self.error_veredicto = veredicto, error_veredicto
        self.mensajes = None   # mensajes de la lectura del PDF
        self.llamadas = []     # (esquema, mensajes) de todas las llamadas
        self._esquema = None

    def with_structured_output(self, esquema):
        assert esquema in (PropuestaIA, Veredicto)
        self._esquema = esquema
        return self

    def invoke(self, mensajes):
        self.llamadas.append((self._esquema, mensajes))
        if self._esquema is Veredicto:
            if self.error_veredicto:
                raise self.error_veredicto
            return self.veredicto
        self.mensajes = mensajes
        if self.error:
            raise self.error
        return self.respuesta


PROPUESTA = PropuestaIA(
    entregables=[EntregableIA(numero=1, descripcion="Informe inicial"),
                 EntregableIA(numero=2, descripcion="Informe final")],
    plazo_dias=20, penalidades=["Mora: 0.5 % por día"],
)


# --- Sin base de datos ----------------------------------------------------------

def test_el_pdf_de_ejemplo_tiene_texto():
    texto = extractor.texto_de_pdf(PDF)
    assert "Entregables" in texto and "Plazo de ejecución" in texto


def test_el_respaldo_es_valido_y_coincide_con_el_pdf_de_ejemplo():
    respaldo = extractor.cargar_respaldo()
    texto = extractor.texto_de_pdf(PDF)
    assert respaldo.entregables and respaldo.plazo_dias == 15
    assert respaldo.objeto and respaldo.corresponde_al_expediente is None
    assert all(e.descripcion[:30] in texto for e in respaldo.entregables)


def test_pdf_invalido_o_sin_texto_se_rechaza_con_mensaje_claro():
    sin_texto = io.BytesIO()
    escritor = PdfWriter()
    escritor.add_blank_page(200, 200)
    escritor.write(sin_texto)
    for contenido, parte in [(b"", "vacío"), (b"no soy un pdf", "PDF"),
                             (sin_texto.getvalue(), "OCR"),
                             (b"%PDF" + b"0" * (extractor.TAMANO_MAXIMO + 1), "5 MB")]:
        with pytest.raises(ErrorValidacion, match=parte):
            extractor.extraer(contenido, modelo=ModeloFalso(PROPUESTA))


def test_con_modelo_se_usa_su_resultado_sin_aviso():
    modelo = ModeloFalso(PROPUESTA)
    r = extractor.extraer(PDF, modelo=modelo)
    assert r.origen == "modelo" and r.aviso is None
    assert r.propuesta == PROPUESTA
    roles = [m[0] for m in modelo.mensajes]
    assert roles == ["system", "human"]
    assert "no instrucciones" in modelo.mensajes[0][1]


def test_el_texto_enviado_al_modelo_tiene_tope():
    modelo = ModeloFalso(PROPUESTA)
    extractor.extraer(PDF, modelo=modelo)
    assert len(modelo.mensajes[1][1]) <= extractor.CARACTERES_MAXIMOS + 20  # + rótulo


def test_el_modelo_recibe_el_expediente_para_comprobar_la_correspondencia():
    modelo = ModeloFalso(PROPUESTA)
    exp = {"tipo": "bien", "descripcion": "Adquisición de luminarias LED", "plazo_dias": 90}
    extractor.extraer(PDF, modelo=modelo, expediente=exp)
    mensaje = modelo.mensajes[1][1]
    assert "luminarias LED" in mensaje and "90 días" in mensaje
    assert mensaje.index("EXPEDIENTE") < mensaje.index("DOCUMENTO:")
    assert "corresponde_al_expediente" in modelo.mensajes[0][1]


EXPEDIENTE = {"plazo_dias": 15}


def _avisos(**cambios):
    datos = dict(objeto="Limpieza", corresponde_al_expediente=True,
                 entregables=[EntregableIA(numero=1, descripcion="Plan de trabajo")],
                 plazo_dias=15)
    datos.update(cambios)
    return extractor.avisos_de_coherencia(PropuestaIA(**datos), EXPEDIENTE, "modelo", [])


def test_sin_discrepancias_no_hay_avisos():
    assert _avisos() == []


def test_documento_que_no_corresponde_es_un_error_con_su_motivo():
    [(nivel, texto)] = _avisos(corresponde_al_expediente=False,
                               motivo_discrepancia="Trata de luminarias")
    assert nivel == "error" and "NO parece corresponder" in texto and "luminarias" in texto


def test_correspondencia_desconocida_es_un_aviso_y_menciona_el_respaldo():
    [(nivel, texto)] = _avisos(corresponde_al_expediente=None)
    assert nivel == "aviso" and "No se pudo comprobar" in texto
    [(_, texto)] = extractor.avisos_de_coherencia(
        extractor.cargar_respaldo(), {"plazo_dias": 15}, "respaldo", [])
    assert "respaldo" in texto


def test_plazo_distinto_es_un_aviso():
    [(nivel, texto)] = _avisos(plazo_dias=30)
    assert nivel == "aviso" and "30 días" in texto and "15 días" in texto
    assert _avisos(plazo_dias=None) == []


def test_entregables_repetidos_se_avisan_sin_importar_mayusculas_ni_punto_final():
    avisos = extractor.avisos_de_coherencia(
        PropuestaIA(corresponde_al_expediente=True, entregables=[
            EntregableIA(numero=1, descripcion="Plan de trabajo."),
            EntregableIA(numero=2, descripcion="Otro")]),
        EXPEDIENTE, "modelo", ["plan DE trabajo"])
    assert len(avisos) == 1 and "n.º 1" in avisos[0][1]


@pytest.mark.parametrize("modelo", [
    ModeloFalso(error=TimeoutError("sin respuesta")),
    ModeloFalso(error=RuntimeError("clave inválida")),
    ModeloFalso({"entregables": "no es una lista"}),
    ModeloFalso(PropuestaIA(entregables=[])),
])
def test_si_el_modelo_falla_o_responde_mal_se_usa_el_respaldo_con_aviso(modelo):
    r = extractor.extraer(PDF, modelo=modelo)
    assert r.origen == "respaldo"
    assert r.aviso
    assert r.propuesta == extractor.cargar_respaldo()
    assert "clave inválida" not in r.aviso  # el aviso no filtra el mensaje del proveedor


def test_sin_proveedor_configurado_se_usa_el_respaldo(monkeypatch):
    monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: defecto)
    r = extractor.extraer(PDF)
    assert r.origen == "respaldo" and "configurado" in r.aviso


def test_crear_modelo_segun_el_entorno(monkeypatch):
    def entorno(**valores):
        monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: valores.get(nombre, defecto))

    entorno()
    assert extractor.crear_modelo() is None
    entorno(LLM_PROVIDER="anthropic")  # sin clave
    assert extractor.crear_modelo() is None
    entorno(LLM_PROVIDER="otro", ANTHROPIC_API_KEY="x")
    assert extractor.crear_modelo() is None
    entorno(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="clave-de-prueba")
    modelo = extractor.crear_modelo()  # solo se construye: no hay llamada de red
    assert type(modelo).__name__ == "ChatAnthropic"


# --- Con base de datos ----------------------------------------------------------

def _preparar(s):
    inf2 = actor_de(s, "inf2")
    exp = _pendiente(s, inf2)
    return inf2, exp


def _proponer(s, actor, exp, propuesta=PROPUESTA, origen="modelo", aviso=None):
    return repositorio.registrar_propuesta_ia(
        s, actor, exp["id"], archivo_nombre="tdr.pdf", archivo_sha256="a" * 64,
        propuesta=propuesta, origen=origen, aviso=aviso)


def _entregables(s, actor, exp):
    return repositorio.listar_entregables(s, actor, exp["id"])


def test_proponer_no_toca_los_entregables(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    antes = _entregables(s, actor, exp)
    _proponer(s, actor, exp)
    assert _entregables(s, actor, exp) == antes
    [propuesta] = repositorio.listar_extracciones(s, actor, exp["id"])
    assert propuesta["estado"] == "propuesta" and propuesta["origen"] == "modelo"
    assert len(propuesta["resultado"]["entregables"]) == 2


def test_aprobar_anade_entregables_con_origen_ia_y_deja_bitacora(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    antes = _entregables(s, actor, exp)
    ultimo = max(e["numero"] for e in antes)
    ide = _proponer(s, actor, exp)
    n = repositorio.aprobar_extraccion(s, actor, ide, ["Informe inicial (editado)", "  ", "Final"])
    assert n == 2
    nuevos = _entregables(s, actor, exp)[len(antes):]
    assert [(e["numero"], e["descripcion"], e["origen"]) for e in nuevos] == [
        (ultimo + 1, "Informe inicial (editado)", "ia"), (ultimo + 2, "Final", "ia")]
    acciones = s.execute(text(
        "SELECT accion, actor_id, documento_sha256 FROM bitacora WHERE expediente_id = :e "
        "AND accion LIKE 'ia.%' ORDER BY id"), {"e": exp["id"]}).all()
    assert [a.accion for a in acciones] == ["ia.propuesta", "ia.aprobada"]
    assert all(a.actor_id == actor.persona_id and a.documento_sha256 == "a" * 64
               for a in acciones)
    [x] = repositorio.listar_extracciones(s, actor, exp["id"])
    assert x["estado"] == "aprobada"


def test_rechazar_no_crea_entregables(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    antes = _entregables(s, actor, exp)
    ide = _proponer(s, actor, exp, origen="respaldo", aviso="sin clave")
    repositorio.rechazar_extraccion(s, actor, ide, "no corresponde")
    assert _entregables(s, actor, exp) == antes
    [x] = repositorio.listar_extracciones(s, actor, exp["id"])
    assert x["estado"] == "rechazada"
    assert s.execute(text("SELECT count(*) FROM bitacora WHERE expediente_id = :e "
                          "AND accion = 'ia.rechazada'"), {"e": exp["id"]}).scalar_one() == 1


def test_una_propuesta_se_revisa_una_sola_vez(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    ide = _proponer(s, actor, exp)
    repositorio.rechazar_extraccion(s, actor, ide)
    with pytest.raises(ErrorValidacion, match="ya fue revisada"):
        repositorio.aprobar_extraccion(s, actor, ide, ["X"])
    with pytest.raises(ErrorValidacion, match="ya fue revisada"):
        repositorio.rechazar_extraccion(s, actor, ide)


def test_no_se_aprueba_una_lista_vacia(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    ide = _proponer(s, actor, exp)
    with pytest.raises(ErrorValidacion, match="al menos un entregable"):
        repositorio.aprobar_extraccion(s, actor, ide, ["", "   "])
    assert repositorio.listar_extracciones(s, actor, exp["id"])[0]["estado"] == "propuesta"


def test_solo_el_area_usuaria_de_ese_expediente_puede_proponer_y_aprobar(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    ide = _proponer(s, actor, exp)
    for usuario in ("tes1", "oci1"):
        otro = actor_de(s, usuario)
        with pytest.raises(PermisoDenegado):
            _proponer(s, otro, exp)
        with pytest.raises(PermisoDenegado):
            repositorio.aprobar_extraccion(s, otro, ide, ["X"])
        with pytest.raises(PermisoDenegado):
            repositorio.rechazar_extraccion(s, otro, ide)
    ajeno = actor_de(s, "log1")
    assert ajeno.area_id != actor.area_id and ajeno.rol == actor.rol
    with pytest.raises(PermisoDenegado):
        repositorio.aprobar_extraccion(s, ajeno, ide, ["X"])


def test_con_conformidad_ya_no_se_pueden_ampliar_los_entregables(sesion_sembrada):
    s = sesion_sembrada
    inf1 = actor_de(s, "inf1")
    con_conformidad = next(x for x in repositorio.listar_expedientes(s, inf1)
                           if x["tiene_conformidad"])
    with pytest.raises(ErrorValidacion, match="ya tiene conformidad"):
        _proponer(s, inf1, con_conformidad)


# --- Correspondencia documento-expediente: paso aislado --------------------------

LUMINARIAS = {"tipo": "bien", "descripcion": "Adquisición de luminarias LED", "plazo_dias": 90}
LIMPIEZA = {"tipo": "servicio", "plazo_dias": 15,
            "descripcion": "Servicio de limpieza y desinfección de ambientes"}


def _doc(**cambios):
    datos = dict(objeto="Servicio de limpieza y desinfección de ambientes",
                 entregables=[EntregableIA(numero=1, descripcion="Plan de trabajo")])
    datos.update(cambios)
    return PropuestaIA(**datos)


def test_la_inyeccion_que_fuerza_corresponde_true_se_ignora():
    """El modelo principal «obedece» al documento y dice true; el paso aislado dice false."""
    modelo = ModeloFalso(_doc(corresponde_al_expediente=True),
                         veredicto=Veredicto(corresponde=False, motivo="Son distintos"))
    r = extractor.extraer(PDF, modelo=modelo, expediente=LUMINARIAS)
    assert r.propuesta.corresponde_al_expediente is False
    assert r.propuesta.motivo_discrepancia == "Son distintos"


def test_el_paso_aislado_solo_ve_el_objeto_y_la_descripcion_no_el_texto_del_pdf():
    modelo = ModeloFalso(_doc(), veredicto=Veredicto(corresponde=True))
    extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA)
    [(_, mensajes)] = [(e, m) for e, m in modelo.llamadas if e is Veredicto]
    visto = " ".join(texto for _, texto in mensajes)
    assert "Servicio de limpieza y desinfección de ambientes" in visto
    assert "Plan de trabajo" not in visto and "DOCUMENTO:" not in visto
    assert extractor.texto_de_pdf(PDF)[:60] not in visto


def test_un_false_del_modelo_principal_se_respeta_aunque_el_aislado_diga_true():
    modelo = ModeloFalso(_doc(corresponde_al_expediente=False, motivo_discrepancia="Dudo"),
                         veredicto=Veredicto(corresponde=True))
    r = extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA)
    assert r.propuesta.corresponde_al_expediente is False
    assert r.propuesta.motivo_discrepancia == "Dudo"


def test_si_ambos_coinciden_corresponde():
    modelo = ModeloFalso(_doc(corresponde_al_expediente=True),
                         veredicto=Veredicto(corresponde=True))
    r = extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA)
    assert r.propuesta.corresponde_al_expediente is True
    assert r.propuesta.motivo_discrepancia == ""


def test_si_falla_el_paso_aislado_se_usa_la_comparacion_lexica():
    modelo = ModeloFalso(_doc(), error_veredicto=TimeoutError("sin red"))
    assert extractor.extraer(PDF, modelo=modelo, expediente=LUMINARIAS
                             ).propuesta.corresponde_al_expediente is False
    assert extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA
                             ).propuesta.corresponde_al_expediente is True


def test_sin_objeto_no_se_puede_juzgar():
    modelo = ModeloFalso(_doc(objeto="", corresponde_al_expediente=True),
                         veredicto=Veredicto(corresponde=True))
    r = extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA)
    assert r.propuesta.corresponde_al_expediente is None


def test_el_objeto_se_acota_antes_de_compararlo():
    modelo = ModeloFalso(_doc(objeto="limpieza " * 200), veredicto=Veredicto(corresponde=True))
    r = extractor.extraer(PDF, modelo=modelo, expediente=LIMPIEZA)
    assert len(r.propuesta.objeto) <= extractor.LARGO_OBJETO


def test_el_respaldo_tambien_se_contrasta_con_el_expediente(monkeypatch):
    monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: defecto)
    luminarias = extractor.extraer(PDF, expediente=LUMINARIAS)
    limpieza = extractor.extraer(PDF, expediente=LIMPIEZA)
    assert luminarias.origen == limpieza.origen == "respaldo"
    assert luminarias.propuesta.corresponde_al_expediente is False
    assert limpieza.propuesta.corresponde_al_expediente is True
    sin_expediente = extractor.extraer(PDF)
    assert sin_expediente.propuesta.corresponde_al_expediente is None


OBJETOS = ["Adquisición de luminarias LED", "Adquisición de útiles de escritorio",
           "Adquisición de materiales de ferretería",
           "Servicio de limpieza y desinfección de ambientes"]


def test_comparacion_lexica_acierta_la_matriz_y_nunca_da_un_falso_corresponde():
    for i, objeto in enumerate(OBJETOS):
        for j, descripcion in enumerate(OBJETOS):
            assert extractor.similitud_lexica(objeto, descripcion) is (i == j), (objeto, descripcion)
    # Reformulado: puede fallar hacia «no corresponde», pero no al revés.
    assert not extractor.similitud_lexica("Compra de papelería y útiles de oficina", OBJETOS[0])
    assert not extractor.similitud_lexica("", OBJETOS[0])


def test_esfuerzo_de_razonamiento_solo_en_modelos_que_lo_admiten(monkeypatch):
    def entorno(**valores):
        monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: valores.get(nombre, defecto))

    entorno(LLM_PROVIDER="openai", OPENAI_API_KEY="clave-de-prueba")
    assert extractor.crear_modelo("minimal").reasoning_effort == "minimal"  # gpt-5-nano
    assert extractor.crear_modelo().reasoning_effort is None
    entorno(LLM_PROVIDER="openai", OPENAI_API_KEY="clave-de-prueba", LLM_MODEL="gpt-4o")
    assert extractor.crear_modelo("minimal").reasoning_effort is None


# --- Límites: páginas, texto, filas y descripciones (avisan, no recortan en silencio) -----

def _pdf_de_paginas(n):
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = reportlab.Canvas(buf)
    for i in range(1, n + 1):
        c.drawString(72, 700, f"Pagina {i} de terminos de referencia")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_solo_se_leen_las_primeras_paginas_y_se_avisa():
    pdf = _pdf_de_paginas(extractor.PAGINAS_MAXIMAS + 5)
    modelo = ModeloFalso(PROPUESTA)
    r = extractor.extraer(pdf, modelo=modelo)
    assert any(f"primeras {extractor.PAGINAS_MAXIMAS} de {extractor.PAGINAS_MAXIMAS + 5}" in a
               for a in r.advertencias)
    enviado = modelo.mensajes[1][1]
    assert f"Pagina {extractor.PAGINAS_MAXIMAS} " in enviado
    assert f"Pagina {extractor.PAGINAS_MAXIMAS + 1} " not in enviado


def test_un_pdf_corto_no_genera_advertencias():
    r = extractor.extraer(PDF, modelo=ModeloFalso(PROPUESTA))
    assert r.advertencias == ()


def test_el_truncado_del_texto_se_avisa(monkeypatch):
    monkeypatch.setattr(extractor, "CARACTERES_MAXIMOS", 50)
    r = extractor.extraer(PDF, modelo=ModeloFalso(PROPUESTA))
    assert any("primeros 50" in a for a in r.advertencias)


def test_mas_de_50_entregables_y_descripciones_largas_se_acotan_con_aviso():
    muchos = PropuestaIA(entregables=[EntregableIA(numero=i, descripcion=f"Entregable {i}")
                                      for i in range(1, 61)])
    r = extractor.extraer(PDF, modelo=ModeloFalso(muchos))
    assert len(r.propuesta.entregables) == 50
    assert any("60 entregables" in a for a in r.advertencias)

    largas = PropuestaIA(entregables=[EntregableIA(numero=1, descripcion="x" * 1000),
                                      EntregableIA(numero=2, descripcion="corta")])
    r = extractor.extraer(PDF, modelo=ModeloFalso(largas))
    assert len(r.propuesta.entregables[0].descripcion) == 300
    assert r.propuesta.entregables[0].descripcion.endswith("…")
    assert r.propuesta.entregables[1].descripcion == "corta"
    assert any("1 descripciones" in a for a in r.advertencias)


def test_el_respaldo_no_trae_advertencias_de_lectura(monkeypatch):
    monkeypatch.setattr(config, "leer", lambda nombre, defecto=None: defecto)
    assert extractor.extraer(PDF).advertencias == ()


def test_las_descripciones_largas_no_se_pueden_guardar():
    from conforme import entregables

    _, errores = entregables.validar([{"numero": 1, "descripcion": "x" * 301}])
    assert errores and "300 caracteres" in errores[0]
    assert entregables.validar([{"numero": 1, "descripcion": "x" * 300}])[1] == []


# --- Cupo de lecturas con IA (repositorio) -------------------------------------------

def test_solo_una_propuesta_pendiente_por_expediente(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    ide = _proponer(s, actor, exp)
    with pytest.raises(ErrorValidacion, match="propuesta pendiente"):
        repositorio.comprobar_cupo_ia(s, actor, exp["id"])
    with pytest.raises(ErrorValidacion, match="propuesta pendiente"):
        _proponer(s, actor, exp)
    repositorio.rechazar_extraccion(s, actor, ide)
    repositorio.comprobar_cupo_ia(s, actor, exp["id"])  # ya no bloquea
    _proponer(s, actor, exp)


def test_tope_de_lecturas_por_persona_y_hora(sesion_sembrada, monkeypatch):
    s = sesion_sembrada
    monkeypatch.setattr(repositorio, "LECTURAS_IA_POR_HORA", 2)
    actor, exp = _preparar(s)
    for _ in range(2):
        repositorio.rechazar_extraccion(s, actor, _proponer(s, actor, exp))
    with pytest.raises(ErrorValidacion, match="máximo de 2 lecturas"):
        repositorio.comprobar_cupo_ia(s, actor, exp["id"])
    otro = actor_de(s, "inf1")  # otra persona: su cupo es propio
    assert otro.persona_id != actor.persona_id
    repositorio.comprobar_cupo_ia(s, otro, exp["id"])


def test_lecturas_de_hace_mas_de_una_hora_no_cuentan(sesion_sembrada, monkeypatch):
    s = sesion_sembrada
    monkeypatch.setattr(repositorio, "LECTURAS_IA_POR_HORA", 1)
    actor, exp = _preparar(s)
    repositorio.rechazar_extraccion(s, actor, _proponer(s, actor, exp))
    s.execute(text("UPDATE extraccion_ia SET creado_en = now() - interval '2 hours'"))
    repositorio.comprobar_cupo_ia(s, actor, exp["id"])


def test_las_advertencias_de_lectura_se_guardan_con_la_propuesta(sesion_sembrada):
    s = sesion_sembrada
    actor, exp = _preparar(s)
    repositorio.registrar_propuesta_ia(
        s, actor, exp["id"], archivo_nombre="t.pdf", archivo_sha256="b" * 64,
        propuesta=PROPUESTA, origen="modelo", aviso=None, advertencias=("Solo 40 de 50 páginas",))
    [x] = repositorio.listar_extracciones(s, actor, exp["id"])
    assert x["resultado"]["advertencias"] == ["Solo 40 de 50 páginas"]
    assert PropuestaIA.model_validate(x["resultado"]).entregables  # sigue siendo válido
