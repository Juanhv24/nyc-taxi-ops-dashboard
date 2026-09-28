"""Descarga y carga de los datos crudos."""

import shutil
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import config

COLUMNAS_VIAJES = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "RatecodeID",
    "PULocationID",
    "DOLocationID",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
]

# Tipos compactos: reducen el uso de memoria de ~1.2 GB a ~0.6 GB sin perder
# precisión relevante (montos en centavos y distancias en centésimas de milla).
TIPOS = {
    "VendorID": "int8",
    "passenger_count": "int8",
    "RatecodeID": "int16",
    "PULocationID": "int16",
    "DOLocationID": "int16",
    "payment_type": "int8",
    "trip_distance": "float32",
    "fare_amount": "float64",
    "extra": "float32",
    "mta_tax": "float32",
    "tip_amount": "float32",
    "tolls_amount": "float32",
    "improvement_surcharge": "float32",
    "total_amount": "float64",
}


def descargar_datos(forzar: bool = False) -> None:
    """Descarga los archivos crudos a data/raw, probando cada fuente en orden."""
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    for nombre, urls in config.FUENTES.items():
        destino = config.DATA_RAW / nombre
        if destino.exists() and not forzar:
            print(f"[ok] {nombre} ya existe")
            continue
        for url in urls:
            try:
                print(f"[descarga] {nombre} <- {url}")
                _descargar(url, destino)
                break
            except Exception as error:  # noqa: BLE001 - se prueba la siguiente fuente
                print(f"[aviso] falló {url}: {error}")
        else:
            raise RuntimeError(f"No fue posible descargar {nombre}")


def _descargar(url: str, destino: Path) -> None:
    temporal = destino.with_suffix(destino.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as respuesta, open(temporal, "wb") as archivo:
        shutil.copyfileobj(respuesta, archivo)
    temporal.replace(destino)


def cargar_viajes(ruta: Path = config.ARCHIVO_VIAJES) -> pd.DataFrame:
    """Carga los viajes con tipos compactos y variables derivadas básicas."""
    tabla = pq.read_table(ruta, columns=COLUMNAS_VIAJES)
    df = tabla.to_pandas(self_destruct=True)
    del tabla
    df = df.astype(TIPOS)

    df["duracion_min"] = (
        (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60
    ).astype("float32")

    fecha = df["tpep_pickup_datetime"]
    df["fecha"] = fecha.dt.normalize()
    df["hora"] = fecha.dt.hour.astype("int8")
    df["dia_semana"] = fecha.dt.dayofweek.astype("int8")  # 0 = lunes
    df["tipo_dia"] = tipo_de_dia(fecha)
    df["franja"] = franja_horaria(df["hora"])
    return df


def tipo_de_dia(fechas: pd.Series) -> pd.Categorical:
    """Laborable (lunes a viernes no festivo) o fin de semana / festivo."""
    festivo = fechas.dt.normalize().isin(pd.to_datetime(list(config.FESTIVOS)))
    fin_de_semana = fechas.dt.dayofweek >= 5
    etiquetas = np.where(fin_de_semana | festivo, "Fin de semana/festivo", "Laborable")
    return pd.Categorical(etiquetas, categories=["Laborable", "Fin de semana/festivo"])


def franja_horaria(horas: pd.Series) -> pd.Categorical:
    etiquetas = np.empty(len(horas), dtype=object)
    for nombre, rango in config.FRANJAS.items():
        etiquetas[np.isin(horas.to_numpy(), list(rango))] = nombre
    return pd.Categorical(etiquetas, categories=list(config.FRANJAS))


def cargar_zonas(ruta: Path = config.ARCHIVO_ZONAS) -> pd.DataFrame:
    """Carga el catálogo de zonas con etiquetas explícitas para 264 y 265.

    En el archivo de la TLC ambos códigos traen campos vacíos. En vez de
    dejarlos nulos se les asigna una categoría explícita, para que los viajes
    se conserven y sigan siendo trazables.
    """
    zonas = pd.read_csv(ruta)
    zonas.columns = ["LocationID", "distrito", "zona", "tipo_servicio"]
    fijas = {
        config.ZONA_DESCONOCIDA: ("Desconocido", "Zona desconocida", "Desconocido"),
        config.ZONA_FUERA_NYC: ("Fuera de NYC", "Fuera de NYC", "Fuera de NYC"),
    }
    for location_id, (distrito, zona, servicio) in fijas.items():
        mascara = zonas["LocationID"] == location_id
        zonas.loc[mascara, ["distrito", "zona", "tipo_servicio"]] = [distrito, zona, servicio]
    zonas["distrito"] = zonas["distrito"].replace({"EWR": "Newark (EWR)"})
    return zonas


def unir_zonas(df: pd.DataFrame, zonas: pd.DataFrame) -> pd.DataFrame:
    """Agrega distrito y zona de origen y destino como categorías."""
    for prefijo, columna in (("pu", "PULocationID"), ("do", "DOLocationID")):
        mapa_distrito = zonas.set_index("LocationID")["distrito"]
        mapa_zona = zonas.set_index("LocationID")["zona"]
        df[f"{prefijo}_distrito"] = df[columna].map(mapa_distrito).astype("category")
        df[f"{prefijo}_zona"] = df[columna].map(mapa_zona).astype("category")
    return df
