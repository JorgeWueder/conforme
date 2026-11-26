"""Caso reproducible con datos ficticios para la demostración."""
from datetime import date, timedelta

from conforme.prevencion.esquemas import Compra


def compra_demo() -> Compra:
    return Compra.model_validate({
        "requerimiento": "REQ-DEMO-014",
        "objeto": "Limpieza y desinfección de ambientes",
        "entidad_ruc": "99000000000",
        "unidad": "Servicios Generales",
        "rubro": "Limpieza",
        "modalidad": "Contrato menor",
        "fecha": date.today(),
        "importe": "18400.00",
        "tdr": "TDR-DEMO-014 v1",
        "candidatos": [
            {"ruc": "99000000001", "nombre": "Servicios Las Palmeras SAC", "importe": "17900.00", "proforma": "COT-01"},
            {"ruc": "99000000002", "nombre": "Limpieza Moche EIRL", "importe": "18150.00", "proforma": "COT-02"},
            {"ruc": "99000000003", "nombre": "Grupo Valle Norte SAC", "importe": "18400.00", "proforma": "COT-03"},
        ],
        "intervinientes": [
            {"rol": "Responsable técnico", "designacion": "Persona ficticia A", "referencia": "MEM-014"},
            {"rol": "Comprador", "designacion": "Persona ficticia B", "referencia": "MEM-015"},
        ],
    })


def resultados(compra: dict) -> tuple[list[dict], list[dict]]:
    corte = compra["fecha"]
    fuentes = [
        dict(id=nombre, nombre=etiqueta, estado=estado, fecha_corte=corte, alcance="Datos del caso ficticio", url=None)
        for nombre, etiqueta, estado in [
            ("sunat", "Padrón tributario", "consultada"),
            ("tcp", "Inhabilitaciones TCP", "consultada"),
            ("orden", "Órdenes y servicios", "consultada"),
            ("vinculo", "Relaciones declaradas", "consultada"),
            ("penalidad", "Penalidades de contratistas", "sin_edicion"),
        ]
    ]
    alta = date.fromisoformat(corte) - timedelta(days=45)
    hallazgos = [
        dict(id="demo:sancion", ruc="99000000001", frente="F03", prioridad="verificar",
             titulo="Inhabilitación publicada por verificar",
             detalle="La edición ficticia contiene una coincidencia exacta y un acto posterior que requiere contraste.",
             evidencias=[dict(fuente="Inhabilitaciones TCP · demo", fecha=corte, acto="TCP-DEMO-017",
                              extracto="RUC 99000000001 asociado a la resolución ficticia TCP-DEMO-017.")]),
        dict(id="demo:trayectoria", ruc="99000000002", frente="F04", prioridad="contexto",
             titulo="Inicio de actividades reciente",
             detalle="Solicita sustento de capacidad y experiencia pertinente al servicio.",
             evidencias=[dict(fuente="Constancia tributaria · demo", fecha=str(alta),
                              extracto=f"Inicio de actividades acreditado en la constancia ficticia: {alta}.")]),
        dict(id="demo:vinculo", ruc="99000000003", frente="F07", prioridad="verificar",
             titulo="Vínculo declarado con un interviniente",
             detalle="Deriva la comprobación del vínculo y su alcance a una persona independiente.",
             evidencias=[dict(fuente="Declaración de intereses · demo", fecha=corte, acto="DJI-DEMO-08",
                              extracto="La declaración ficticia vincula al candidato con el comprador designado.")]),
        dict(id="demo:necesidad", ruc=None, frente="F08", prioridad="aclarar",
             titulo="Dos órdenes previas con objeto similar",
             detalle="Confirma si corresponden a la misma necesidad y registra la justificación.",
             evidencias=[dict(fuente="Órdenes y servicios · demo", fecha=corte, acto="OS-DEMO-006",
                              extracto="Limpieza y desinfección de ambientes de otra sede.")]),
    ]
    return fuentes, hallazgos


def documentos(ruc: str, acto: str | None) -> list[dict]:
    if ruc != "99000000001" or acto not in (None, "TCP-DEMO-017", "TCP-DEMO-018"):
        return []
    return [
        dict(id="demo-acto", titulo="Resolución ficticia TCP-DEMO-017", fecha=None, url=None,
             paginas=[dict(numero=1, texto="La resolución TCP-DEMO-017 impone una inhabilitación temporal a Servicios Las Palmeras SAC, RUC 99000000001.")]),
        dict(id="demo-posterior", titulo="Resolución ficticia TCP-DEMO-018", fecha=None, url=None,
             paginas=[dict(numero=1, texto="La resolución TCP-DEMO-018 suspende provisionalmente los efectos del acto TCP-DEMO-017 mientras se resuelve el recurso.")]),
    ]
