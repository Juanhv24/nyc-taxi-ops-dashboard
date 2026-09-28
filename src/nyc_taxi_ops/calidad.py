"""Reglas de calidad de datos.

Cada regla produce una columna booleana (prefijo ``q_``) y el tratamiento se
decide por métrica, no por fila: un viaje con la hora de llegada corrupta
sigue siendo un viaje válido para contar demanda, pero no para medir
duración o velocidad. Las máscaras ``valido_*`` resumen esa decisión.
"""

import numpy as np
import pandas as pd

from . import config

CLAVE_VIAJE = ["VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID"]

# Catálogo de reglas: nombre visible, tratamiento y justificación. Se usa para
# construir la tabla de calidad del tablero y del notebook.
REGLAS = {
    "q_anulacion": (
        "Cargo anulado (par cargo + reverso)",
        "Excluir",
        "El proveedor registra la anulación como una segunda fila con los mismos datos del "
        "viaje y montos negativos; el par suma $0 y no corresponde a un servicio cobrado.",
    ),
    "q_duplicado": (
        "Registro duplicado",
        "Excluir (se conserva uno)",
        "Misma clave de viaje (proveedor, horas de recogida y llegada, origen y destino) "
        "sin montos negativos: el viaje quedó registrado dos veces.",
    ),
    "q_duracion_no_positiva": (
        "Duración ≤ 0",
        "Excluir",
        "La llegada es anterior o igual a la recogida: imposibilidad física.",
    ),
    "q_no_realizado": (
        "Viaje no realizado probable",
        "Excluir",
        "Sin distancia, menos de un minuto y cobro cercano al banderazo: el taxímetro se "
        "activó sin que hubiera trayecto.",
    ),
    "q_tiempo_invalido": (
        "Duración o velocidad imposible",
        "Excluir solo de métricas de tiempo",
        "Duración menor a 1 min, mayor a 3 h (medidor sin cerrar) o velocidad > 80 mph. "
        "La hora de recogida sigue siendo válida para contar demanda.",
    ),
    "q_monto_implausible": (
        "Monto implausible, mayor a $1,000",
        "Excluir de métricas de ingreso",
        "Montos incompatibles con cualquier trayecto urbano; se tratan como error de "
        "digitación y pasan a la auditoría.",
    ),
    "q_distancia_imputable": (
        "Distancia no registrada en viaje taximetrado",
        "Imputar",
        "Tarifa estándar con cobro y duración positivos pero distancia 0: el trayecto "
        "existió y la distancia se estima con el modelo validado.",
    ),
    "q_distancia_no_aplica": (
        "Distancia no registrada en tarifa no taximetrada",
        "Excluir de métricas por milla",
        "Tarifas negociadas, planas o con zona desconocida donde el taxímetro no mide "
        "distancia; no hay base para estimarla.",
    ),
    "q_pasajeros_invalido": (
        "Número de pasajeros 0 o mayor a 6",
        "Marcar como faltante",
        "Campo digitado por el conductor, sin variables que permitan estimarlo; se deja "
        "como faltante y se excluye solo del cálculo de ocupación.",
    ),
    "q_zona_desconocida": (
        "Zona desconocida o fuera de NYC (264 y 265)",
        "Conservar con categoría explícita",
        "La propia TLC no publica la ubicación; eliminar estos viajes borraría la "
        "movilidad hacia fuera de la ciudad.",
    ),
}


def marcar_calidad(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega (en el mismo DataFrame) las columnas ``q_*`` y las máscaras de validez."""

    en_periodo = df["tpep_pickup_datetime"].between(
        config.PERIODO_INICIO, config.PERIODO_FIN, inclusive="left"
    )
    df["q_fuera_periodo"] = ~en_periodo

    # Anulaciones y duplicados. Un grupo con la misma clave que contiene algún
    # monto negativo es un par cargo + reverso; sin negativos es un duplicado.
    negativo = (df["fare_amount"] < 0) | (df["total_amount"] < 0)
    en_grupo = df.duplicated(CLAVE_VIAJE, keep=False)
    grupo_con_negativo = (
        negativo[en_grupo].groupby([df.loc[en_grupo, c] for c in CLAVE_VIAJE]).transform("any")
    )
    anulacion = negativo.copy()
    anulacion.loc[grupo_con_negativo.index] = anulacion.loc[grupo_con_negativo.index] | grupo_con_negativo
    df["q_anulacion"] = anulacion
    df["q_duplicado"] = df.duplicated(CLAVE_VIAJE, keep="first") & ~df["q_anulacion"]

    df["q_duracion_no_positiva"] = df["duracion_min"] <= 0
    df["q_no_realizado"] = (
        (df["trip_distance"] == 0)
        & (df["duracion_min"] > 0)
        & (df["duracion_min"] < config.DURACION_MIN_MIN)
        & df["fare_amount"].between(0, config.NO_REALIZADO_TARIFA_MAX)
    )

    velocidad = df["trip_distance"] / (df["duracion_min"] / 60)
    df["q_tiempo_invalido"] = (
        (df["duracion_min"] < config.DURACION_MIN_MIN)
        | (df["duracion_min"] > config.DURACION_MAX_MIN)
        | ((df["duracion_min"] > 0) & (velocidad > config.VELOCIDAD_MAX_MPH))
    )
    df["q_monto_implausible"] = (df["fare_amount"] > config.MONTO_MAX_PLAUSIBLE) | (
        df["total_amount"] > config.MONTO_MAX_PLAUSIBLE
    )

    zona_desconocida = df["PULocationID"].isin(
        [config.ZONA_DESCONOCIDA, config.ZONA_FUERA_NYC]
    ) | df["DOLocationID"].isin([config.ZONA_DESCONOCIDA, config.ZONA_FUERA_NYC])
    df["q_zona_desconocida"] = zona_desconocida

    excluido = (
        df["q_fuera_periodo"]
        | df["q_anulacion"]
        | df["q_duplicado"]
        | df["q_duracion_no_positiva"]
        | df["q_no_realizado"]
    )
    distancia_cero = (df["trip_distance"] == 0) & (df["fare_amount"] > 0) & ~excluido
    imputable = (
        distancia_cero
        & (df["RatecodeID"] == 1)
        & (df["fare_amount"] > config.BANDERAZO)
        & df["duracion_min"].between(config.DURACION_MIN_MIN, config.DURACION_MAX_MIN)
        & ~df["q_monto_implausible"]
    )
    df["q_distancia_imputable"] = imputable
    df["q_distancia_no_aplica"] = distancia_cero & ~imputable

    pasajeros_invalido = (df["passenger_count"] == 0) | (df["passenger_count"] > config.PASAJEROS_MAX)
    df["q_pasajeros_invalido"] = pasajeros_invalido
    df["pasajeros"] = df["passenger_count"].astype("float32").where(~pasajeros_invalido)

    df["valido_demanda"] = ~excluido
    df["valido_ingreso"] = df["valido_demanda"] & ~df["q_monto_implausible"]
    # valido_tiempo se completa tras la imputación, porque también exige
    # una distancia utilizable (observada o imputada).
    df["valido_tiempo"] = df["valido_ingreso"] & ~df["q_tiempo_invalido"]
    return df


def ingreso_servicio(df: pd.DataFrame) -> pd.Series:
    """Tarifa + recargos + propina.

    Excluye peajes, el impuesto MTA y el recargo de mejora, que el conductor
    traslada a terceros. Las propinas en efectivo no quedan registradas, por lo
    que este ingreso subestima el de los viajes pagados en efectivo.
    """
    return (df["fare_amount"] + df["extra"] + df["tip_amount"]).astype("float64")


def resumen_calidad(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla de reglas con conteo, porcentaje, tratamiento y justificación."""
    total = len(df)
    filas = []
    for columna, (nombre, tratamiento, justificacion) in REGLAS.items():
        n = int(df[columna].sum())
        filas.append(
            {
                "regla": nombre,
                "columna": columna,
                "viajes": n,
                "pct": n / total * 100,
                "tratamiento": tratamiento,
                "justificacion": justificacion,
            }
        )
    return pd.DataFrame(filas)


def embudo(df: pd.DataFrame) -> pd.DataFrame:
    """Registros que se descuentan en cada regla de exclusión, en orden."""
    pasos = [
        ("Registros originales", None),
        ("Cargos anulados", "q_anulacion"),
        ("Duplicados", "q_duplicado"),
        ("Duración ≤ 0", "q_duracion_no_positiva"),
        ("Viajes no realizados", "q_no_realizado"),
    ]
    restante = np.ones(len(df), dtype=bool)
    filas = []
    for nombre, columna in pasos:
        if columna is None:
            filas.append({"paso": nombre, "descontados": 0, "restantes": int(restante.sum())})
            continue
        descontar = restante & df[columna].to_numpy()
        restante &= ~df[columna].to_numpy()
        filas.append({"paso": nombre, "descontados": int(descontar.sum()), "restantes": int(restante.sum())})
    return pd.DataFrame(filas)
