"""Fase 3: revisión documental y forense (lectura, cuadre, Benford, metadatos, similitud,
TDR, vigencias) y su flujo con permisos."""
import math
import random
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from conforme.documentos import analisis, benford, letras, lectura
from conforme.documentos import repositorio as documentos
from conforme.errores import ErrorValidacion
from conforme.modelos import Expediente
from conforme.permisos import PermisoDenegado
from conforme.proveedores import fuentes
from scripts import casos_documentos, casos_evaluacion
from tests.conftest import actor_de

HOY = date(2026, 11, 27)


def test_monto_en_letras():
    assert letras.monto_en_letras(Decimal("27350.00")) == "veintisiete mil trescientos cincuenta con 00/100"
    assert letras.monto_en_letras(Decimal("21001.50")) == "veintiun mil uno con 50/100"
    assert letras.coincide(Decimal("33600"), "TREINTA Y TRES MIL SEISCIENTOS CON 00/100 SOLES")
    assert not letras.coincide(Decimal("19900"), "DIECINUEVE MIL NOVECIENTOS NOVENTA CON 00/100")


def test_benford_con_pocos_montos_no_concluye():
    resultado = benford.analizar([(str(i), Decimal(m)) for i, m in enumerate([1200, 450, 3300])])
    assert resultado["nivel"] == "insuficiente" and not resultado["muestra_suficiente"]
    assert "no se saca conclusión" in resultado["lectura"]


def test_benford_distingue_montos_naturales_de_inventados():
    azar = random.Random(7)
    naturales = [(str(i), Decimal(str(round(10 ** azar.uniform(1, 6), 2)))) for i in range(600)]
    assert benford.analizar(naturales)["nivel"] in ("conforme", "aceptable")
    inventados = [(str(i), Decimal(azar.randint(5, 9) * 10 ** azar.randint(1, 4) + azar.randint(0, 9)))
                  for i in range(200)]
    resultado = benford.analizar(inventados)
    assert resultado["nivel"] == "anomalia"
    assert set(resultado["digitos_en_exceso"]) <= {5, 6, 7, 8, 9} and resultado["partidas_sospechosas"]
    assert math.isclose(sum(d["esperado"] for d in resultado["distribucion"]), 1, abs_tol=1e-3)


def _documentos_demo():
    docs, postor_id = [], {}
    nombres = {fuentes.RUC_TECNOLAB: "Tecnolab", fuentes.RUC_KALLPA: "Kallpa", fuentes.RUC_SERVIMAX: "Servimax"}
    for i, (ruc, archivos) in enumerate(casos_documentos.documentos().items(), start=1):
        postor_id[ruc] = i
        for j, (tipo, nombre, contenido) in enumerate(archivos):
            docs.append(analisis.Documento(
                id=i * 10 + j, postor_id=i, postor=nombres[ruc], ruc=ruc, tipo=tipo, nombre=nombre,
                sha256=f"{i}{j}" * 32, lectura=lectura.leer(nombre, "application/pdf", contenido)))
    inicio = {postor_id[r]: fuentes.consultar(r, "").padron.inicio_actividades for r in postor_id}
    ctx = analisis.Contexto(hoy=HOY, inicio_actividades=inicio, descripcion=casos_evaluacion.LABORATORIO, entregables=[
        "Plan de mantenimiento y cronograma", "Informe técnico de mantenimiento por equipo",
        "Certificados de calibración vigentes"])
    return docs, ctx


def test_lectura_de_pdf_extrae_partidas_totales_y_metadatos():
    docs, _ = _documentos_demo()
    cotizacion = next(d for d in docs if d.nombre == "cotizacion-tecnolab.pdf").lectura
    assert len(cotizacion.partidas) == 5
    assert cotizacion.totales["total"] == Decimal("27350.00") and cotizacion.totales["igv"] == Decimal("4172.03")
    assert cotizacion.autor == "Carlos Rios" and cotizacion.creador == "Microsoft Word 2019"
    assert cotizacion.creado.year == 2026


def test_analisis_detecta_las_trampas_del_caso_demo():
    docs, ctx = _documentos_demo()
    r = analisis.analizar(docs, ctx)
    b = r["bloques"]
    textos = lambda clave: " | ".join(h["que"] for h in b[clave]["hallazgos"])
    assert r["veredicto"] == "anomalia"
    # Montos: Kallpa multiplica mal y su monto en letras no cuadra; Tecnolab y Servimax sí.
    assert "Partida mal calculada en Kallpa" in textos("montos")
    assert "monto en letras de Kallpa" in textos("montos")
    assert "Tecnolab" not in textos("montos") and "Servimax" not in textos("montos")
    assert b["montos"]["detalle"]["benford"]["nivel"] == "insuficiente"
    # Metadatos y similitud: Kallpa y Servimax son gemelas.
    assert "Cotizaciones gemelas: Kallpa y Servimax" in textos("metadatos")
    assert "Kallpa y Servimax" in textos("similitud") and "Tecnolab" not in textos("similitud")
    # TDR: Tecnolab cubre todo; Kallpa no.
    checklist = {c["postor"]: {i["estado"] for i in c["items"]} for c in b["tdr"]["detalle"]["checklist"]}
    assert checklist["Tecnolab"] == {"acreditado"} and "no_cumple" in checklist["Kallpa"]
    # Coherencia: RUC ajeno, constancia vencida y experiencia anterior a la empresa.
    coherencia = textos("coherencia")
    assert "menciona otro RUC" in coherencia and "venció el 30/06/2026" in coherencia
    assert "antes de que Kallpa existiera" in coherencia
    assert "Tecnolab" not in coherencia


def test_documentos_limpios_son_conformes():
    docs, ctx = _documentos_demo()
    tecnolab = [d for d in docs if d.postor == "Tecnolab"]
    assert analisis.analizar(tecnolab, ctx)["veredicto"] in ("conforme", "revisar")
    assert analisis.analizar(tecnolab, ctx)["bloques"]["coherencia"]["estado"] == "limpio"


# --- Con base de datos -----------------------------------------------------------------

@pytest.fixture
def laboratorio(sesion_sembrada):
    casos_evaluacion.sembrar_casos(sesion_sembrada)
    expediente_id = sesion_sembrada.scalar(select(Expediente.id).where(Expediente.descripcion == casos_evaluacion.LABORATORIO)
                                           .order_by(Expediente.id.desc()).limit(1))
    return sesion_sembrada, expediente_id


def test_flujo_y_permisos_de_la_revision_documental(laboratorio):
    s, exp_id = laboratorio
    dec1, tes1, oci1, inf1 = (actor_de(s, u) for u in ("dec1", "tes1", "oci1", "inf1"))
    with pytest.raises(PermisoDenegado):
        documentos.obtener(s, inf1, exp_id)
    with pytest.raises(PermisoDenegado):
        documentos.analizar(s, tes1, exp_id)
    vista = documentos.obtener(s, tes1, exp_id)
    assert not vista["puede_subir"] and not vista["puede_analizar"] and vista["revision"] is None
    assert sum(len(p["documentos"]) for p in vista["postores"]) == 6

    resultado = documentos.analizar(s, dec1, exp_id)
    assert resultado["veredicto"] == "anomalia"
    vista = documentos.obtener(s, oci1, exp_id)
    assert vista["revision"]["veredicto"] == "anomalia" and not vista["documentos_cambiaron"]

    # Un archivo idéntico en otro expediente se señala como reciclado.
    otro = s.scalar(select(Expediente.id).where(Expediente.descripcion == casos_evaluacion.RED))
    postor_otro = documentos.obtener(s, dec1, otro)["postores"][0]["id"]
    certificado = next(d for p in documentos.obtener(s, dec1, exp_id)["postores"] for d in p["documentos"]
                       if d["nombre_archivo"] == "certificado-experiencia-tecnolab.pdf")
    contenido = documentos.descargar(s, dec1, certificado["id"])["contenido"]
    with pytest.raises(ErrorValidacion, match="Formato no admitido"):
        documentos.subir_documento(s, dec1, otro, postor_otro, tipo="certificado", nombre_archivo="x.exe",
                                   mime="application/x-msdownload", contenido=b"MZ")
    documentos.subir_documento(s, dec1, otro, postor_otro, tipo="certificado", nombre_archivo="certificado.pdf",
                               mime="application/pdf", contenido=contenido)
    with pytest.raises(PermisoDenegado):
        documentos.analizar(s, oci1, otro)
    documentos.analizar(s, dec1, otro)
    coherencia = documentos.obtener(s, dec1, otro)["revision"]["resultados"]["coherencia"]
    assert any("idéntico a un archivo de" in h["que"] for h in coherencia["hallazgos"])
    assert documentos.obtener(s, dec1, exp_id)["documentos_cambiaron"] is False


def test_benford_transversal_por_rol(sesion_sembrada):
    s = sesion_sembrada
    resultado = documentos.benford_transversal(s, actor_de(s, "oci1"), fuente="ordenes")
    assert resultado["total_montos"] > 100 and resultado["muestra_suficiente"]
    assert resultado["nivel"] in ("conforme", "aceptable", "marginal", "anomalia")
    # Los pagos sintéticos varían menos de dos órdenes de magnitud: se avisa, no se concluye.
    pagos = documentos.benford_transversal(s, actor_de(s, "tes1"), fuente="pagos")
    assert pagos["nivel"] == "insuficiente" and "varían poco" in pagos["lectura"]
    with pytest.raises(PermisoDenegado):
        documentos.benford_transversal(s, actor_de(s, "inf1"))
