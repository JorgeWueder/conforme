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
from conforme.ia.extractor import EntregableIA, PropuestaIA
from conforme.permisos import PermisoDenegado
from tests.conftest import actor_de
from tests.test_conformidad import _pendiente

PDF = extractor.PDF_EJEMPLO.read_bytes()


class ModeloFalso:
    """Imita lo que usa el extractor de un modelo de LangChain."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.mensajes = respuesta, error, None

    def with_structured_output(self, esquema):
        assert esquema is PropuestaIA
        return self

    def invoke(self, mensajes):
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
