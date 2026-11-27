"""Fase 2: evaluación de posibles proveedores por seis dimensiones y revisión independiente."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from conforme import repositorio
from conforme.errores import ErrorValidacion
from conforme.modelos import ConflictoInteres, Expediente
from conforme.permisos import PermisoDenegado
from conforme.proveedores import consolidado, dimensiones, fuentes
from conforme.proveedores import repositorio as evaluacion
from conforme.proveedores.dimensiones import Contexto, Funcionario, Postor
from scripts import casos_evaluacion
from tests.conftest import actor_de

HOY = date(2026, 11, 27)


def _postor(id_, ruc, nombre, monto, telefono=None, plazo=30):
    return Postor(id_, ruc, nombre, Decimal(monto), plazo, None, telefono, None)


def _caso_laboratorio():
    tecnolab = _postor(1, fuentes.RUC_TECNOLAB, "Tecnolab", "27350")
    kallpa = _postor(2, fuentes.RUC_KALLPA, "Kallpa", "19900", "949 555 120")
    servimax = _postor(3, fuentes.RUC_SERVIMAX, "Servimax", "33600", "949-555-120")
    postores = [tecnolab, kallpa, servimax]
    fichas = {p.id: fuentes.consultar(p.ruc, p.razon_social) for p in postores}

    def ctx(p):
        return Contexto(
            descripcion=casos_evaluacion.LABORATORIO, valor_estimado=Decimal("28500"), plazo_dias=30, hoy=HOY,
            funcionarios=(Funcionario(fuentes.DNI_SOLICITANTE_DEMO, "Rosa Elena Paredes Gil",
                                      "solicitante del requerimiento"),),
            otros=tuple((o, fichas[o.id]) for o in postores if o.id != p.id),
            personas_sancionadas=fuentes.personas_de_empresas_sancionadas(HOY))
    return {p.razon_social: dimensiones.evaluar(p, fichas[p.id], ctx(p)) for p in postores}


def test_postor_limpio_es_apto():
    resultado = _caso_laboratorio()["Tecnolab"]
    assert {d["estado"] for d in resultado.values()} == {"limpio"}
    assert consolidado.consolidar(resultado)["veredicto"] == "apto"


def test_empresa_reciente_vinculada_a_la_solicitante_no_es_recomendable():
    kallpa = _caso_laboratorio()["Kallpa"]
    assert kallpa["personas"]["estado"] == "alerta"
    assert kallpa["colusion"]["estado"] == "alerta"            # mismo teléfono que Servimax
    assert kallpa["empresa"]["estado"] == "revisar"            # 4 meses y rubro distinto
    assert kallpa["precio"]["estado"] == "revisar"             # 30 % bajo el estimado
    informe = consolidado.consolidar(kallpa)
    assert informe["veredicto"] == "no_recomendado"
    titulos = {r["titulo"] for r in informe["riesgos_combinados"]}
    assert "Empresa recién creada con personas vinculadas" in titulos
    assert "Posible falsa competencia" in titulos


def test_inhabilitado_tiene_impedimento():
    servimax = _caso_laboratorio()["Servimax"]
    assert servimax["antecedentes"]["estado"] == "alerta"
    informe = consolidado.consolidar(servimax)
    assert informe["veredicto"] == "no_recomendado"
    assert informe["impedimentos"]


def test_consolidar_exige_las_seis_dimensiones():
    incompleto = dict(_caso_laboratorio()["Tecnolab"])
    incompleto.pop("precio")
    with pytest.raises(ValueError, match="Precio y mercado"):
        consolidado.consolidar(incompleto)


@pytest.mark.parametrize("monto, estado", [("28500", "limpio"), ("33000", "revisar"), ("38000", "alerta"),
                                           ("20000", "revisar"), ("15000", "alerta")])
def test_umbrales_de_precio(monto, estado):
    postor = _postor(9, fuentes.RUC_TECNOLAB, "X", monto)
    ctx = Contexto(descripcion="x", valor_estimado=Decimal("28500"), plazo_dias=30, hoy=HOY)
    assert dimensiones.precio(postor, fuentes.consultar(postor.ruc, "X"), ctx)["estado"] == estado


def test_ruc_fuera_del_registro_recibe_ficha_generica():
    ficha = fuentes.consultar(fuentes.ruc_con_verificador("2060990011"), "Otra Empresa S.A.C.")
    assert ficha.padron.generico and not ficha.sanciones


# --- Flujo con base de datos -----------------------------------------------------------

@pytest.fixture
def casos(sesion_sembrada):
    sembrados = casos_evaluacion.sembrar_casos(sesion_sembrada)
    ids = {estado: sesion_sembrada.scalar(select(Expediente.id).where(Expediente.codigo == codigo))
           for codigo, estado in sembrados}
    return sesion_sembrada, ids


def _ids(sesion, actor, expediente_id):
    return {p["ruc"]: p["id"] for p in evaluacion.obtener(sesion, actor, expediente_id)["postores"]}


def test_flujo_completo_hasta_la_orden(casos):
    s, ids = casos
    exp_id = ids["por analizar"]
    inf1, dec1, dec2 = actor_de(s, "inf1"), actor_de(s, "dec1"), actor_de(s, "dec2")

    # El área usuaria no ve el análisis ni puede registrar conformidad sin orden.
    with pytest.raises(PermisoDenegado):
        evaluacion.obtener(s, inf1, exp_id)
    with pytest.raises(ErrorValidacion, match="aún no tiene orden"):
        repositorio.registrar_conformidad(s, inf1, exp_id, fecha_conformidad=HOY, penalidad_aplicada=0, items=[])

    evaluacion.analizar(s, dec1, exp_id)
    with pytest.raises(ErrorValidacion, match="Consolida"):
        evaluacion.enviar_a_revision(s, dec1, exp_id, seleccionado_id=1, sustento="x" * 30, descartes={},
                                     declaro_sin_conflicto=True)
    evaluacion.consolidar(s, dec1, exp_id)
    postores = _ids(s, dec1, exp_id)
    tecnolab, kallpa, servimax = (postores[r] for r in (fuentes.RUC_TECNOLAB, fuentes.RUC_KALLPA, fuentes.RUC_SERVIMAX))

    # Otro especialista no puede tocar la evaluación de dec1.
    with pytest.raises(PermisoDenegado, match="conduce"):
        evaluacion.analizar(s, dec2, exp_id)
    # No se puede seleccionar a un postor no recomendado.
    with pytest.raises(ErrorValidacion, match="no es seleccionable"):
        evaluacion.enviar_a_revision(s, dec1, exp_id, seleccionado_id=kallpa, sustento="x" * 30,
                                     descartes={tecnolab: "a", servimax: "b"}, declaro_sin_conflicto=True)
    # Cada descarte debe justificarse.
    with pytest.raises(ErrorValidacion, match="descarta"):
        evaluacion.enviar_a_revision(s, dec1, exp_id, seleccionado_id=tecnolab, sustento="x" * 30,
                                     descartes={kallpa: "Vinculada a la solicitante."}, declaro_sin_conflicto=True)
    # Sin declaración de conflicto de intereses no se envía.
    with pytest.raises(ErrorValidacion, match="conflicto de intereses"):
        evaluacion.enviar_a_revision(s, dec1, exp_id, seleccionado_id=tecnolab, sustento="x" * 30,
                                     descartes={kallpa: "a", servimax: "b"}, declaro_sin_conflicto=False)
    evaluacion.enviar_a_revision(
        s, dec1, exp_id, seleccionado_id=tecnolab, sustento="Única propuesta apta y con precio razonable.",
        descartes={kallpa: "Socia vinculada a la solicitante.", servimax: "Inhabilitada por el Tribunal."},
        declaro_sin_conflicto=True)
    assert s.get(Expediente, exp_id).estado_flujo == "pendiente_revision_independiente"
    vinculos = s.scalars(select(ConflictoInteres).where(ConflictoInteres.expediente_id == exp_id,
                                                        ConflictoInteres.tipo == "vinculo_detectado")).all()
    assert [v.proveedor_ruc for v in vinculos] == [fuentes.RUC_KALLPA] and vinculos[0].bloqueante

    # Cuatro ojos: dec1 no puede revisar su propia evaluación.
    with pytest.raises(PermisoDenegado, match="propia evaluación"):
        evaluacion.revisar_independiente(s, dec1, exp_id, aprobar=True, comentario="")
    with pytest.raises(ErrorValidacion, match="orden se registra"):
        evaluacion.confirmar_orden(s, inf1, exp_id, numero_orden="OS-1", fecha_orden=date.today())
    evaluacion.revisar_independiente(s, dec2, exp_id, aprobar=True, comentario="")

    # El área usuaria confirma la orden sobre el proveedor aprobado.
    evaluacion.confirmar_orden(s, inf1, exp_id, numero_orden="OS-2026-09001", fecha_orden=date.today())
    expediente = repositorio.obtener_expediente(s, inf1, exp_id)
    assert expediente["estado_flujo"] == "en_ejecucion"
    assert expediente["proveedor_ruc"] == fuentes.RUC_TECNOLAB
    assert expediente["monto"] == Decimal("27350.00")
    acciones = [e["accion"] for e in repositorio.linea_de_tiempo(s, inf1, exp_id)]
    assert acciones[0] == "requerimiento.registrado" and acciones[-1] == "orden.emitida"
    assert "evaluacion.aprobada" in acciones


def test_revision_observada_vuelve_a_evaluacion(casos):
    s, ids = casos
    exp_id = ids["en revisión independiente"]
    dec2 = actor_de(s, "dec2")
    with pytest.raises(ErrorValidacion, match="comentario"):
        evaluacion.revisar_independiente(s, dec2, exp_id, aprobar=False, comentario=" ")
    evaluacion.revisar_independiente(s, dec2, exp_id, aprobar=False, comentario="Falta comparar plazos.")
    vista = evaluacion.obtener(s, actor_de(s, "dec1"), exp_id)
    assert vista["expediente"]["estado_flujo"] == "en_evaluacion_proveedores"
    assert vista["evaluacion"]["estado_revision"] == "observada" and vista["puede_editar"]


def test_lectura_por_rol(casos):
    s, ids = casos
    exp_id = ids["en revisión independiente"]
    for usuario in ("tes1", "oci1"):
        vista = evaluacion.obtener(s, actor_de(s, usuario), exp_id)
        assert not vista["puede_editar"] and not vista["puede_revisar"]
        with pytest.raises(PermisoDenegado):
            evaluacion.analizar(s, actor_de(s, usuario), exp_id)
    assert evaluacion.obtener(s, actor_de(s, "dec2"), exp_id)["puede_revisar"]
    bandeja = {f["id"]: f for f in evaluacion.bandeja(s, actor_de(s, "dec2"))}
    assert bandeja[exp_id]["me_toca_revisar"]
    assert repositorio.obtener_expediente(s, actor_de(s, "inf1"), exp_id)["proveedor"] is None


def test_la_base_impide_que_el_evaluador_se_revise(casos):
    s, ids = casos
    with pytest.raises(IntegrityError):
        with s.begin_nested():
            s.execute(text("UPDATE revision_previa SET revisor_independiente_id = evaluador_id "
                           "WHERE expediente_id = :id"), {"id": ids["en revisión independiente"]})
