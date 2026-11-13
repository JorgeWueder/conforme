"""Validación de la lista de entregables y lectura desde CSV (numero,descripcion)."""
import csv
import io

MAXIMO = 50
MAXIMO_DESCRIPCION = 300  # caracteres


def validar(filas: list[dict]) -> tuple[list[dict], list[str]]:
    """Devuelve (entregables limpios, errores). Con errores, la lista no se usa."""
    limpios, errores, vistos = [], [], set()
    for posicion, fila in enumerate(filas, start=1):
        try:
            numero = int(str(fila.get("numero", "")).strip())
        except ValueError:
            numero = 0
        descripcion = str(fila.get("descripcion") or "").strip()
        if numero <= 0:
            errores.append(f"Fila {posicion}: el número debe ser un entero mayor que cero.")
        elif numero in vistos:
            errores.append(f"Fila {posicion}: el número {numero} está repetido.")
        vistos.add(numero)
        if not descripcion:
            errores.append(f"Fila {posicion}: falta la descripción.")
        elif len(descripcion) > MAXIMO_DESCRIPCION:
            errores.append(f"Fila {posicion}: la descripción supera los "
                           f"{MAXIMO_DESCRIPCION} caracteres ({len(descripcion)}).")
        limpios.append({"numero": numero, "descripcion": descripcion})
    if not filas:
        errores.append("Hace falta al menos un entregable.")
    if len(filas) > MAXIMO:
        errores.append(f"Son demasiados entregables: el máximo es {MAXIMO}.")
    return sorted(limpios, key=lambda e: e["numero"]), errores


def leer_csv(contenido: bytes) -> tuple[list[dict], list[str]]:
    """Lee un CSV con encabezado `numero,descripcion` (coma o punto y coma)."""
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    if not texto.strip():
        return [], ["El archivo está vacío."]
    primera = texto.splitlines()[0]
    separador = ";" if primera.count(";") > primera.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto), delimiter=separador)
    columnas = [(c or "").strip().lower() for c in (lector.fieldnames or [])]
    if columnas != ["numero", "descripcion"]:
        return [], [
            "El encabezado debe ser exactamente «numero,descripcion». "
            f"Se encontró: «{primera.strip()}»."
        ]
    lector.fieldnames = columnas
    filas = [f for f in lector if any((v or "").strip() for v in f.values() if isinstance(v, str))]
    if any(None in f for f in filas):
        return [], ["Hay filas con más de dos columnas. Si una descripción lleva comas, "
                    "enciérrala entre comillas."]
    return validar(filas)
