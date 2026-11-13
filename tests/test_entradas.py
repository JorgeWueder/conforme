"""Lectura de entregables desde CSV y preparación de evidencias."""
import hashlib
import io

import pytest
from PIL import Image

from conforme import entregables, evidencias
from conforme.errores import ErrorValidacion


def test_csv_valido_con_bom_y_comillas():
    contenido = ('\ufeffnumero,descripcion\n2,"Informe final, con anexos"\n'
                 '1,Plan de trabajo\n\n').encode("utf-8")
    filas, errores = entregables.leer_csv(contenido)
    assert errores == []
    assert filas == [{"numero": 1, "descripcion": "Plan de trabajo"},
                     {"numero": 2, "descripcion": "Informe final, con anexos"}]


def test_csv_con_punto_y_coma():
    filas, errores = entregables.leer_csv("numero;descripcion\n1;Acta\n".encode("latin-1"))
    assert errores == [] and filas == [{"numero": 1, "descripcion": "Acta"}]


@pytest.mark.parametrize("contenido, fragmento", [
    (b"", "vac"),
    (b"nro,detalle\n1,Acta\n", "encabezado"),
    (b"numero,descripcion\n", "al menos un entregable"),
    (b"numero,descripcion\nuno,Acta\n", "Fila 1: el n"),
    (b"numero,descripcion\n1,Acta\n1,Informe\n", "repetido"),
    (b"numero,descripcion\n1,\n", "Fila 1: falta la descripci"),
    (b"numero,descripcion\n1,Informe, con coma\n", "comillas"),
])
def test_csv_invalido_explica_el_problema(contenido, fragmento):
    filas, errores = entregables.leer_csv(contenido)
    assert any(fragmento in e for e in errores), errores


def _imagen(lado, formato="PNG"):
    salida = io.BytesIO()
    Image.new("RGB", (lado, lado // 2), (200, 30, 30)).save(salida, format=formato)
    return salida.getvalue()


def test_imagen_pequena_se_guarda_tal_cual():
    original = _imagen(400)
    e = evidencias.preparar("foto.png", "image/png", original)
    assert e["contenido"] == original
    assert e["sha256"] == hashlib.sha256(original).hexdigest()
    assert e["tamano"] == len(original)


def test_imagen_grande_se_reduce_a_1600():
    e = evidencias.preparar("C:\\fotos\\grande.png", "image/png", _imagen(4000))
    assert e["mime"] == "image/jpeg" and e["nombre_archivo"] == "grande.jpg"
    assert max(Image.open(io.BytesIO(e["contenido"])).size) == 1600
    assert e["sha256"] == hashlib.sha256(e["contenido"]).hexdigest()


def test_pdf_se_acepta_sin_tocar():
    e = evidencias.preparar("acta.pdf", "application/pdf", b"%PDF-1.4 sintetico")
    assert e["contenido"] == b"%PDF-1.4 sintetico"


@pytest.mark.parametrize("nombre, mime, contenido", [
    ("virus.exe", "application/octet-stream", b"MZ"),
    ("vacio.pdf", "application/pdf", b""),
    ("falsa.png", "image/png", b"esto no es una imagen"),
    ("enorme.pdf", "application/pdf", b"x" * (evidencias.TAMANO_MAXIMO + 1)),
])
def test_evidencia_invalida_se_rechaza(nombre, mime, contenido):
    with pytest.raises(ErrorValidacion):
        evidencias.preparar(nombre, mime, contenido)
