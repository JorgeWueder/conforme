"""Importa una edición de un dataset público al índice de Prevención."""
from argparse import ArgumentParser
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from conforme import db
from conforme.prevencion.fuentes import FUENTES
from conforme.prevencion.ingesta import descargar, publicar


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("fuente", choices=FUENTES)
    insumo = parser.add_mutually_exclusive_group()
    insumo.add_argument("--archivo", type=Path, help="Archivo oficial descargado por el operador.")
    insumo.add_argument("--url", help="URL directa de la edición publicada por la fuente.")
    parser.add_argument("--corte", type=date.fromisoformat, help="Fecha de corte YYYY-MM-DD.")
    parser.add_argument("--alcance", help="Partición estable, p. ej. 2026 · La Libertad para órdenes.")
    parser.add_argument("--codificacion", help="Sobrescribe la detección automática de UTF-8 o Windows-1252.")
    parser.add_argument("--columna", action="append", default=[], metavar="CAMPO=ENCABEZADO",
                        help="Asigna columnas de una edición con cabecera distinta.")
    args = parser.parse_args()
    fuente = FUENTES[args.fuente]
    url = args.url or fuente.archivo
    if not args.archivo and not url:
        parser.error("Indica --url o --archivo con la edición oficial de CONOSCE.")
    if args.fuente == "orden" and not args.alcance:
        parser.error("Indica --alcance para identificar la partición de órdenes.")
    if args.fuente in ("sunat", "orden", "penalidad") and not args.corte:
        parser.error("Indica --corte con la fecha de publicación informada por la fuente.")
    if any("=" not in valor for valor in args.columna):
        parser.error("El formato de --columna es campo=encabezado.")
    asignacion = dict(valor.split("=", 1) for valor in args.columna)
    origen = url if not args.archivo else fuente.url
    # Las URLs de descarga de terceros pueden contener tokens firmados tras redirecciones;
    # el manifiesto conserva la URL pública original.
    with TemporaryDirectory(prefix="conforme-prevencion-") as temporal:
        archivo = args.archivo
        if archivo is None:
            partes = urlsplit(url)
            nombre = Path(partes.path).name
            archivo = Path(temporal) / (nombre if nombre not in ("", ".", "..") else "edicion")
            descargar(url, archivo)
        with db.sesion() as sesion:
            edicion, total = publicar(
                sesion, archivo, args.fuente, args.corte, args.alcance or "Nacional · empresas",
                origen, args.codificacion, asignacion,
            )
    print(f"Edición {edicion}: {total} filas publicadas." if total is not None else f"Edición {edicion}: ya publicada.")


if __name__ == "__main__":
    main()
