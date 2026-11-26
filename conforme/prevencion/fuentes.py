"""Fuentes y comprobaciones que utiliza la ficha."""
from dataclasses import dataclass

SUNAT = "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"
PADRON_ZIP = "https://www2.sunat.gob.pe/padron_reducido_ruc.zip"
OECE = "https://osce-gob-pe.atlassian.net/wiki/spaces/PNDA/overview?homepageId=106889218"
ADJUNTOS = "https://osce-gob-pe.atlassian.net/wiki/rest/api/content/106889218/child/attachment"
CONOSCE = "https://www.gob.pe/14272-acceder-al-portal-de-datos-abiertos-del-osce"
REPORTES = "https://conosce.oece.gob.pe/buscador/assets/67ae6c4a/reportes"
FUP = "https://www.gob.pe/7342-acceder-a-la-ficha-unica-del-proveedor"
CONTROL = "https://www.gob.pe/9257-buscar-informes-de-control-a-las-entidades-publicas"
RESOLUCIONES = "https://www.gob.pe/institucion/oece/normas-legales"
SANCIONES = "https://www.gob.pe/689"
MESES = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
         "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")


@dataclass(frozen=True)
class Fuente:
    frente: str
    nombre: str
    url: str
    archivo: str | None = None
    max_dias: int | None = None


FUENTES = {
    "sunat": Fuente("F01", "Padrón reducido SUNAT", SUNAT, PADRON_ZIP, 7),
    "tcp": Fuente("F03", "OECE · Inhabilitaciones TCP", OECE, f"{ADJUNTOS}/att106892477/download", 14),
    "multa": Fuente("F03", "OECE · Multas TCP", OECE, f"{ADJUNTOS}/att106892483/download", 14),
    "judicial": Fuente("F03", "OECE · Mandatos judiciales", OECE, f"{ADJUNTOS}/att106892495/download", 45),
    "penalidad": Fuente("F05", "OECE · Penalidades de contratistas", OECE, f"{ADJUNTOS}/att106892469/download", 45),
    "vinculo": Fuente("F06", "OECE · Composición jurídica declarada", OECE, f"{ADJUNTOS}/att106892500/download", 45),
    "orden": Fuente("F08", "OECE · Órdenes de compra y servicio", CONOSCE),
}


@dataclass(frozen=True)
class Control:
    frente: str
    titulo: str
    url: str
    instruccion: str
    por_candidato: bool = True
    obligatorio: bool = False


CONTROLES = {
    "identidad": Control("F01", "Identidad tributaria",
        "https://www.gob.pe/institucion/sunat/pages/565-consultar-el-estado-del-ruc",
        "Coteja el RUC, la razón social, el estado y la condición con la cotización.", obligatorio=True),
    "rnp": Control("F02", "Inscripción y capítulo del RNP", FUP,
        "Registra la constancia, vigencia y capítulo, o la excepción aplicable a la compra.", obligatorio=True),
    "impedimentos": Control("F03", "Impedimentos aplicables", FUP,
        "Confirma el acto, la identidad, la fecha de efecto y cualquier recurso, suspensión o rectificación.", obligatorio=True),
    "trayectoria": Control("F04", "Trayectoria, capacidad y licencias", "https://www.gob.pe/14273",
        "Distingue constitución, inicio de actividades y primera orden observada. Coteja experiencia y licencias pertinentes."),
    "desempeno": Control("F05", "Informes de control y desempeño", CONTROL,
        "Busca por entidad y número de orden o acto. Identifica el rol atribuido, la etapa y el desenlace."),
    "representacion": Control("F06", "Representación y poderes", "https://www.gob.pe/institucion/sunarp/pages/50685-consultar-gratis-partidas-registrales",
        "Contrasta fecha, alcance y vigencia de la relación societaria o el poder."),
    "intervinientes": Control("F07", "Intervinientes y conflictos declarados", "https://appdji.contraloria.gob.pe/DJIC/",
        "Contrasta la designación y las declaraciones pertinentes. Deriva a revisión independiente si corresponde.",
        por_candidato=False, obligatorio=True),
    "personas": Control("F07", "Constancia institucional sobre intervinientes",
        "https://www.gob.pe/818-consultar-el-registro-nacional-de-sanciones-contra-servidores-civiles-rnssc",
        "Si la comprobación corresponde a la compra, solicita al canal competente la referencia de la constancia.",
        por_candidato=False),
    "necesidad": Control("F08", "Unidad de necesidad y planificación", CONOSCE,
        "Contrasta el objeto, la unidad, el periodo, la moneda y el sustento de las compras parecidas.", por_candidato=False),
    "competencia": Control("F09", "Competencia y cotizaciones",
        "https://www.gob.pe/institucion/indecopi/pages/10720-buscar-resoluciones-del-indecopi",
        "Registra documentos de oferta y explica coincidencias, retiros o condiciones del mercado.", por_candidato=False),
    "precio": Control("F10", "Precio comparable y cambios del TDR", "https://www.gob.pe/77158",
        "Compara unidad, lugar, impuestos, fechas y especificación. Coteja las versiones del TDR.", por_candidato=False),
    "listas": Control("F11", "Registros especiales pertinentes",
        "https://www.worldbank.org/en/projects-operations/procurement/debarred-firms",
        "Confirma identidad, país, fecha y alcance en el canal aplicable. Consulta la FUP para el efecto en la compra."),
}
