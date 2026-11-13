"""Carga los datos sintéticos.

Uso:  python -m scripts.sembrar              (solo sobre una base vacía)
      python -m scripts.sembrar --reiniciar  (BORRA todos los datos y vuelve a cargar)
"""
import sys
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from conforme import auth, bitacora, config, db, repositorio
from conforme.modelos import (
    Area, Conformidad, ConformidadEntregable, Entregable, Evidencia, Expediente, Pago,
    Persona, Proveedor, Usuario,
)
from conforme.reglas import motor
from datos import generador

_TABLAS = ("anomalia_sembrada, extraccion_ia, alerta_revision, alerta, pago, evidencia, "
           "conformidad_entregable, conformidad, entregable, bitacora, expediente, "
           "usuario, persona, proveedor, area")


def vaciar(sesion: Session) -> None:
    sesion.execute(text(f"TRUNCATE {_TABLAS} RESTART IDENTITY CASCADE"))


def sembrar(sesion: Session, conjunto: dict, password: str) -> dict:
    """Inserta el conjunto generado, pasa el motor de reglas y encadena toda la
    historia en la bitácora. Devuelve los conteos de lo insertado."""
    areas = {a["sigla"]: Area(**a) for a in conjunto["areas"]}
    sesion.add_all(areas.values())
    sesion.flush()

    personas = {}
    for p in conjunto["personas"]:
        datos = {k: v for k, v in p.items() if k != "area_sigla"}
        personas[p["dni"]] = Persona(**datos, area_id=areas[p["area_sigla"]].id)
    sesion.add_all(personas.values())
    sesion.flush()

    # Una sola contraseña de demostración: se calcula el hash una vez.
    hash_demo = auth.hash_password(password, bytes.fromhex(conjunto["sal_password"]))
    sesion.add_all(
        Usuario(
            persona_id=personas[u["persona_dni"]].id,
            username=u["username"],
            password_hash=hash_demo,
            rol=u["rol"],
        )
        for u in conjunto["usuarios"]
    )

    proveedores = {p["ruc"]: Proveedor(**p) for p in conjunto["proveedores"]}
    sesion.add_all(proveedores.values())
    sesion.flush()

    primer_evento = {}
    for e in conjunto["eventos"]:
        primer_evento.setdefault(e["expediente_codigo"], e["ts"])

    expedientes = {}
    for x in conjunto["expedientes"]:
        datos = {k: v for k, v in x.items()
                 if k not in ("area_sigla", "proveedor_ruc", "solicitante_dni")}
        expedientes[x["codigo"]] = Expediente(
            **datos,
            area_id=areas[x["area_sigla"]].id,
            proveedor_id=proveedores[x["proveedor_ruc"]].id,
            solicitante_id=personas[x["solicitante_dni"]].id,
            creado_en=primer_evento[x["codigo"]],
        )
    sesion.add_all(expedientes.values())
    sesion.flush()

    # --- F2: entregables, conformidades con evidencias y pagos -----------------
    # `refs` resuelve la entidad de cada evento de bitácora del generador.
    refs = {}
    entregables = {
        (e["expediente_codigo"], e["numero"]): Entregable(
            expediente_id=expedientes[e["expediente_codigo"]].id, numero=e["numero"],
            descripcion=e["descripcion"], origen=e["origen"])
        for e in conjunto["entregables"]
    }
    sesion.add_all(entregables.values())

    for c in conjunto["conformidades"]:
        refs["conformidad", c["expediente_codigo"]] = Conformidad(
            expediente_id=expedientes[c["expediente_codigo"]].id,
            conformante_id=personas[c["conformante_dni"]].id,
            fecha_conformidad=c["fecha_conformidad"], observaciones=c["observaciones"],
            penalidad_aplicada=c["penalidad_aplicada"], registrada_en=c["registrada_en"],
        )
    for p in conjunto["pagos"]:
        refs["pago", p["expediente_codigo"]] = Pago(
            expediente_id=expedientes[p["expediente_codigo"]].id, fecha_pago=p["fecha_pago"],
            monto=p["monto"], penalidad_descontada=p["penalidad_descontada"],
            registrado_por=personas[p["registrado_por_dni"]].id,
            registrado_en=p["registrado_en"],
        )
    sesion.add_all(refs.values())
    sesion.flush()

    items = {}
    for c in conjunto["conformidades"]:
        codigo = c["expediente_codigo"]
        for item in c["items"]:
            items[codigo, item["numero"]] = ConformidadEntregable(
                conformidad_id=refs["conformidad", codigo].id,
                entregable_id=entregables[codigo, item["numero"]].id,
                cumplido=item["cumplido"], observacion=item["observacion"],
            )
    sesion.add_all(items.values())
    sesion.flush()

    evidencias = {}
    for c in conjunto["conformidades"]:
        codigo = c["expediente_codigo"]
        for item in c["items"]:
            for indice, archivo in enumerate(item["evidencias"]):
                evidencias["evidencia", codigo, item["numero"], indice] = Evidencia(
                    conformidad_entregable_id=items[codigo, item["numero"]].id,
                    subido_por=personas[c["conformante_dni"]].id,
                    subido_en=c["registrada_en"], **archivo,
                )
    sesion.add_all(evidencias.values())
    sesion.flush()
    refs.update(evidencias)

    if conjunto["anomalias"]:
        sesion.execute(
            text("INSERT INTO anomalia_sembrada (expediente_id, regla, nota) "
                 "VALUES (:expediente_id, :regla, :nota)"),
            [{"expediente_id": expedientes[a["expediente_codigo"]].id,
              "regla": a["regla"], "nota": a["nota"]} for a in conjunto["anomalias"]],
        )

    eventos = [
        {
            "ts": e["ts"],
            "actor_id": personas[e["actor_dni"]].id,
            "accion": e["accion"],
            "entidad": e["entidad"],
            "entidad_id": (refs[e["ref"]].id if e.get("ref")
                           else expedientes[e["expediente_codigo"]].id),
            "expediente_id": expedientes[e["expediente_codigo"]].id,
            "detalle": e["detalle"],
            "documento_sha256": e["documento_sha256"],
        }
        for e in conjunto["eventos"]
    ]

    # El motor genera las alertas igual que en la aplicación. No conoce las
    # anomalías sembradas: solo ve expedientes, conformidades y pagos.
    # Cada alerta se fecha un segundo después del hecho que la origina.
    segundo = timedelta(seconds=1)
    ts_conformidad = {refs["conformidad", c["expediente_codigo"]].expediente_id: c["registrada_en"]
                      for c in conjunto["conformidades"]}
    ts_pago = {refs["pago", p["expediente_codigo"]].id: p["registrado_en"]
               for p in conjunto["pagos"]}

    def ts_de(foto, propuesta):
        if propuesta.regla == "R5":
            antes = ts_pago[propuesta.datos["pago_id"]]
            if foto.expediente_id in ts_conformidad:
                antes = max(antes, ts_conformidad[foto.expediente_id])
            return antes + segundo
        return ts_conformidad[foto.expediente_id] + segundo

    eventos_alerta = motor.sincronizar(sesion, ts_de=ts_de, registrar=False)
    eventos.extend(eventos_alerta)
    # El sello se coloca 2 s después de la conformidad (las alertas van a +1 s), así la
    # bitácora sigue en orden cronológico.
    pendientes, eventos_sello = repositorio.preparar_sellado(
        sesion, ts_de=lambda c: c.registrada_en + 2 * segundo)
    eventos.extend(eventos_sello)
    eventos.sort(key=lambda e: e["ts"])  # orden estable: a igual momento, el de llegada
    bitacora.registrar_lote(sesion, eventos)
    sellados = repositorio.asignar_sellos(sesion, pendientes)

    return {
        "areas": len(areas), "personas": len(personas), "proveedores": len(proveedores),
        "expedientes": len(expedientes), "entregables": len(entregables),
        "conformidades": len(conjunto["conformidades"]), "sellos": sellados, "evidencias": len(evidencias),
        "pagos": len(conjunto["pagos"]), "anomalias": len(conjunto["anomalias"]),
        "alertas": len(eventos_alerta), "bitacora": len(eventos),
    }


if __name__ == "__main__":
    password = config.leer("DEMO_PASSWORD")
    if not password:
        sys.exit("Falta DEMO_PASSWORD en el entorno (.env).")
    reiniciar = "--reiniciar" in sys.argv
    with db.sesion() as s:
        if reiniciar:
            vaciar(s)
        elif s.execute(select(func.count()).select_from(Area)).scalar_one() > 0:
            sys.exit("La base ya tiene datos. Usa --reiniciar para borrarlos y recargar.")
        conteos = sembrar(s, generador.generar(), password)
    print("Sembrado: " + ", ".join(f"{n} {nombre}" for nombre, n in conteos.items()) + ".")
    print("Usuarios de demostración: inf1 (área usuaria), tes1 (tesorería), oci1 (auditor).")
