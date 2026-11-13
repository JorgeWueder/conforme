"""Carga los datos sintéticos.

Uso:  python -m scripts.sembrar              (solo sobre una base vacía)
      python -m scripts.sembrar --reiniciar  (BORRA todos los datos y vuelve a cargar)
"""
import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from conforme import auth, bitacora, config, db
from conforme.modelos import Area, Expediente, Persona, Proveedor, Usuario
from datos import generador

_TABLAS = "anomalia_sembrada, bitacora, expediente, usuario, persona, proveedor, area"


def vaciar(sesion: Session) -> None:
    sesion.execute(text(f"TRUNCATE {_TABLAS} RESTART IDENTITY CASCADE"))


def sembrar(sesion: Session, conjunto: dict, password: str) -> None:
    """Inserta el conjunto generado y encadena su historia en la bitácora."""
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

    bitacora.registrar_lote(sesion, [
        {
            "ts": e["ts"],
            "actor_id": personas[e["actor_dni"]].id,
            "accion": e["accion"],
            "entidad": e["entidad"],
            "entidad_id": expedientes[e["expediente_codigo"]].id,
            "expediente_id": expedientes[e["expediente_codigo"]].id,
            "detalle": e["detalle"],
            "documento_sha256": e["documento_sha256"],
        }
        for e in conjunto["eventos"]
    ])


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
        conjunto = generador.generar()
        sembrar(s, conjunto, password)
    print(
        f"Sembrado: {len(conjunto['areas'])} áreas, {len(conjunto['personas'])} personas, "
        f"{len(conjunto['proveedores'])} proveedores, {len(conjunto['expedientes'])} expedientes, "
        f"{len(conjunto['eventos'])} registros de bitácora."
    )
    print("Usuarios de demostración: inf1 (área usuaria), tes1 (tesorería), oci1 (auditor).")
