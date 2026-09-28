"""Imputación de la distancia en viajes taximetrados sin distancia registrada.

La distancia faltante es un problema real del dataset (a diferencia de un
faltante artificial): son viajes con tarifa estándar, cobro y duración
positivos pero distancia 0. Antes de imputar se comparan tres estrategias
enmascarando distancias conocidas, de modo que el error se mide contra el
valor verdadero:

1. Mediana global (estrategia estadística de referencia).
2. Mediana condicional por par de zonas origen-destino.
3. Regresión lineal de la distancia sobre la tarifa y la duración. El
   tarifario hace que la tarifa sea casi una función determinística de la
   distancia y del tiempo en tráfico lento, así que invertir esa relación es
   la estrategia con mayor fundamento de dominio.
"""

import numpy as np
import pandas as pd

from . import config

METODOS = ["Mediana global", "Mediana por par de zonas", "Regresión tarifa + duración"]


def base_entrenamiento(df: pd.DataFrame) -> pd.DataFrame:
    """Viajes estándar con distancia conocida y comparables a los imputables."""
    mascara = (
        df["valido_tiempo"]
        & (df["RatecodeID"] == 1)
        & (df["trip_distance"] > 0)
        & (df["fare_amount"] > config.BANDERAZO)
        & ~df["q_zona_desconocida"]
    )
    return df.loc[mascara, ["trip_distance", "fare_amount", "duracion_min", "PULocationID", "DOLocationID"]]


def ajustar_regresion(base: pd.DataFrame) -> np.ndarray:
    """Coeficientes [intercepto, tarifa, duración] por mínimos cuadrados."""
    X = np.column_stack([np.ones(len(base)), base["fare_amount"], base["duracion_min"]])
    coeficientes, *_ = np.linalg.lstsq(X, base["trip_distance"].to_numpy(dtype="float64"), rcond=None)
    return coeficientes


def predecir_regresion(coeficientes: np.ndarray, tarifa: pd.Series, duracion: pd.Series) -> np.ndarray:
    X = np.column_stack([np.ones(len(tarifa)), tarifa, duracion])
    # Una distancia estimada negativa no tiene sentido físico; el mínimo
    # medible del taxímetro es 0.01 millas.
    return np.clip(X @ coeficientes, 0.01, None)


def comparar_metodos(
    df: pd.DataFrame, n_muestra: int = 300_000, frac_prueba: float = 0.2
) -> tuple[pd.DataFrame, dict]:
    """Enmascara distancias conocidas y mide el error de cada estrategia.

    Devuelve la tabla de métricas y un diccionario con los valores reales y
    estimados del conjunto de prueba (para graficar).
    """
    rng = np.random.default_rng(config.SEMILLA)
    base = base_entrenamiento(df)
    muestra = base.sample(n=min(n_muestra, len(base)), random_state=config.SEMILLA)
    es_prueba = rng.random(len(muestra)) < frac_prueba
    entrenamiento, prueba = muestra[~es_prueba], muestra[es_prueba]
    real = prueba["trip_distance"].to_numpy(dtype="float64")

    mediana_global = entrenamiento["trip_distance"].median()
    medianas_par = entrenamiento.groupby(["PULocationID", "DOLocationID"])["trip_distance"].median()
    llaves = pd.MultiIndex.from_frame(prueba[["PULocationID", "DOLocationID"]])
    por_par = medianas_par.reindex(llaves).to_numpy(dtype="float64")
    coeficientes = ajustar_regresion(entrenamiento)

    estimados = {
        "Mediana global": np.full(len(prueba), mediana_global),
        "Mediana por par de zonas": np.where(np.isnan(por_par), mediana_global, por_par),
        "Regresión tarifa + duración": predecir_regresion(
            coeficientes, prueba["fare_amount"], prueba["duracion_min"]
        ),
    }

    filas = []
    for metodo in METODOS:
        error = np.abs(estimados[metodo] - real)
        filas.append(
            {
                "metodo": metodo,
                "mae": error.mean(),
                "mediana_error_abs": np.median(error),
                "rmse": np.sqrt((error**2).mean()),
                "std_estimada": estimados[metodo].std(),
                "std_real": real.std(),
            }
        )
    tabla = pd.DataFrame(filas)
    tabla.attrs["n_entrenamiento"] = len(entrenamiento)
    tabla.attrs["n_prueba"] = len(prueba)
    return tabla, {"real": real, **estimados}


def imputar_distancia(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Crea ``distancia_final`` imputando con la regresión ajustada sobre toda la base.

    Modifica el DataFrame recibido para no duplicar ~1.5 GB en memoria.
    """
    coeficientes = ajustar_regresion(base_entrenamiento(df))
    df["distancia_final"] = df["trip_distance"].astype("float64")
    df["distancia_imputada"] = df["q_distancia_imputable"]
    mascara = df["distancia_imputada"]
    df.loc[mascara, "distancia_final"] = predecir_regresion(
        coeficientes, df.loc[mascara, "fare_amount"], df.loc[mascara, "duracion_min"]
    )
    # Los viajes sin distancia utilizable (no taximetrados) quedan como
    # faltantes en lugar de 0, para no arrastrar ceros a las métricas por milla.
    df.loc[df["q_distancia_no_aplica"], "distancia_final"] = np.nan
    df["valido_tiempo"] = df["valido_tiempo"] & (df["distancia_final"] > 0)
    return df, coeficientes
