"""Interfaz de línea de comandos.

Uso:
    uv run nyc-taxi-ops descargar   # baja los datos crudos a data/raw
    uv run nyc-taxi-ops procesar    # construye data/processed/viajes_marcados.parquet
    uv run nyc-taxi-ops sitio       # regenera los JSON del tablero en docs/data
    uv run nyc-taxi-ops todo        # los tres pasos en orden
"""

import argparse

from . import agregados, datos, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="nyc-taxi-ops", description=__doc__.split("\n")[0])
    parser.add_argument("comando", choices=["descargar", "procesar", "sitio", "todo"])
    parser.add_argument("--forzar", action="store_true", help="vuelve a descargar aunque el archivo exista")
    args = parser.parse_args()

    if args.comando in ("descargar", "todo"):
        datos.descargar_datos(forzar=args.forzar)
    if args.comando in ("procesar", "todo"):
        base = pipeline.construir_base()
    if args.comando == "sitio":
        base = pipeline.cargar_base()
    if args.comando in ("sitio", "todo"):
        agregados.exportar_sitio(base)


if __name__ == "__main__":
    main()
