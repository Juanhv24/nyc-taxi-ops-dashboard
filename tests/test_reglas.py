"""Pruebas de las reglas de calidad, imputación y auditoría con viajes sintéticos."""

import numpy as np
import pandas as pd
import pytest

from nyc_taxi_ops import auditoria, calidad, config, datos, imputacion


def viaje(**cambios) -> dict:
    """Viaje estándar válido de 2 millas y 10 minutos en Manhattan."""
    base = {
        "VendorID": 2,
        "tpep_pickup_datetime": pd.Timestamp("2017-01-10 08:00"),
        "duracion": 10.0,
        "passenger_count": 1,
        "trip_distance": 2.0,
        "RatecodeID": 1,
        "PULocationID": 161,
        "DOLocationID": 237,
        "payment_type": 1,
        "fare_amount": 9.0,
        "extra": 0.0,
        "mta_tax": 0.5,
        "tip_amount": 2.0,
        "tolls_amount": 0.0,
        "improvement_surcharge": 0.3,
    }
    base.update(cambios)
    return base


def construir(viajes: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(viajes)
    df["tpep_dropoff_datetime"] = df["tpep_pickup_datetime"] + pd.to_timedelta(df.pop("duracion"), unit="min")
    if "total_amount" not in df or df["total_amount"].isna().any():
        componentes = df[["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge"]].sum(axis=1)
        df["total_amount"] = df.get("total_amount", pd.Series(np.nan, index=df.index)).fillna(componentes)
    df["duracion_min"] = (df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]).dt.total_seconds() / 60
    df["fecha"] = df["tpep_pickup_datetime"].dt.normalize()
    df["hora"] = df["tpep_pickup_datetime"].dt.hour
    df["dia_semana"] = df["tpep_pickup_datetime"].dt.dayofweek
    df["tipo_dia"] = datos.tipo_de_dia(df["tpep_pickup_datetime"])
    df["franja"] = datos.franja_horaria(df["hora"])
    zonas = pd.DataFrame(
        {
            "LocationID": [1, 132, 161, 237, 264, 265],
            "distrito": ["Newark (EWR)", "Queens", "Manhattan", "Manhattan", "Desconocido", "Fuera de NYC"],
            "zona": ["Newark Airport", "JFK Airport", "Midtown Center", "Upper East Side South", "Zona desconocida", "Fuera de NYC"],
            "tipo_servicio": ["EWR", "Airports", "Yellow Zone", "Yellow Zone", "Desconocido", "Fuera de NYC"],
        }
    )
    return datos.unir_zonas(df, zonas)


def procesar(viajes: list[dict]) -> pd.DataFrame:
    df = calidad.marcar_calidad(construir(viajes))
    df, _ = imputacion.imputar_distancia(df)
    return auditoria.marcar_auditoria(df)


# ---------------------------------------------------------------------------
# Calidad
# ---------------------------------------------------------------------------
def test_par_cargo_reverso_se_marca_completo():
    cargo = viaje(payment_type=2)
    reverso = viaje(payment_type=3, fare_amount=-9.0, mta_tax=-0.5, tip_amount=0.0, improvement_surcharge=-0.3)
    df = calidad.marcar_calidad(construir([cargo, reverso, viaje(PULocationID=237)]))
    assert df["q_anulacion"].tolist() == [True, True, False]
    assert not df["q_duplicado"].any()
    assert df["valido_demanda"].tolist() == [False, False, True]


def test_duplicado_sin_negativos_conserva_uno():
    df = calidad.marcar_calidad(construir([viaje(), viaje()]))
    assert df["q_duplicado"].tolist() == [False, True]


@pytest.mark.parametrize(
    ("cambios", "columna"),
    [
        ({"duracion": 0.0}, "q_duracion_no_positiva"),
        ({"duracion": 0.5, "trip_distance": 0.0, "fare_amount": 2.5}, "q_no_realizado"),
        ({"duracion": 23 * 60.0}, "q_tiempo_invalido"),
        ({"duracion": 2.0, "trip_distance": 10.0}, "q_tiempo_invalido"),  # 300 mph
        ({"fare_amount": 625_900.8}, "q_monto_implausible"),
        ({"passenger_count": 0}, "q_pasajeros_invalido"),
        ({"PULocationID": 264}, "q_zona_desconocida"),
    ],
)
def test_reglas_de_calidad(cambios, columna):
    df = calidad.marcar_calidad(construir([viaje(**cambios)]))
    assert df[columna].iloc[0]


def test_hora_de_llegada_corrupta_cuenta_para_demanda_pero_no_para_tiempo():
    df = calidad.marcar_calidad(construir([viaje(duracion=23.5 * 60)]))
    assert df["valido_demanda"].iloc[0]
    assert not df["valido_tiempo"].iloc[0]


# ---------------------------------------------------------------------------
# Imputación
# ---------------------------------------------------------------------------
def test_regresion_recupera_relacion_lineal():
    rng = np.random.default_rng(0)
    tarifa = rng.uniform(5, 50, 500)
    minutos = rng.uniform(5, 60, 500)
    base = pd.DataFrame({"fare_amount": tarifa, "duracion_min": minutos, "trip_distance": -1 + 0.4 * tarifa - 0.1 * minutos})
    coef = imputacion.ajustar_regresion(base)
    np.testing.assert_allclose(coef, [-1, 0.4, -0.1], atol=1e-6)
    assert imputacion.predecir_regresion(coef, pd.Series([0.0]), pd.Series([60.0]))[0] == pytest.approx(0.01)


def test_distancia_cero_en_viaje_taximetrado_se_imputa():
    normales = [viaje(trip_distance=d, fare_amount=2.5 + 2.5 * d + 1, duracion=4 * d + 2) for d in np.linspace(0.5, 8, 40)]
    sin_distancia = viaje(trip_distance=0.0, fare_amount=12.0, duracion=15.0, PULocationID=237, DOLocationID=161)
    negociado = viaje(trip_distance=0.0, fare_amount=45.0, duracion=0.5, RatecodeID=5, PULocationID=237)
    df = procesar(normales + [sin_distancia, negociado])
    fila_imputada = df.iloc[-2]
    assert fila_imputada["distancia_imputada"]
    assert 2 < fila_imputada["distancia_final"] < 5
    assert np.isnan(df.iloc[-1]["distancia_final"])


# ---------------------------------------------------------------------------
# Auditoría
# ---------------------------------------------------------------------------
def test_tarifa_dentro_de_la_banda_no_se_marca():
    # Mínimo: 2.50 + 2.50 × 2 = 7.50; máximo: 7.50 + 0.50 × 10 = 12.50
    df = procesar([viaje(fare_amount=f) for f in (7.5, 9.0, 12.5, 13.4)])
    assert not df["a_bajo_tarifario"].any()
    assert not df["a_sobre_tarifario"].any()


def test_tarifa_fuera_de_la_banda_se_marca_con_su_impacto():
    df = procesar([viaje(fare_amount=5.0), viaje(fare_amount=20.0, PULocationID=237)])
    assert df["a_bajo_tarifario"].tolist() == [True, False]
    assert df["a_sobre_tarifario"].tolist() == [False, True]
    assert df["impacto_bajo_tarifario"].iloc[0] == pytest.approx(2.5)
    assert df["impacto_sobre_tarifario"].iloc[1] == pytest.approx(7.5)


def test_tarifa_suburbana_dentro_de_la_ciudad():
    df = procesar([viaje(RatecodeID=4, fare_amount=18.0), viaje(RatecodeID=4, DOLocationID=265, fare_amount=40.0)])
    assert df["a_codigo_fuera_ciudad"].tolist() == [True, False]


def test_total_que_no_concilia():
    df = procesar([viaje(total_amount=13.75), viaje(PULocationID=237)])
    assert df["a_total_no_concilia"].tolist() == [True, False]
    assert df["impacto_total_no_concilia"].iloc[0] == pytest.approx(1.95)


def test_distancia_atipica_para_la_ruta():
    rng = np.random.default_rng(1)
    normales = [
        viaje(trip_distance=float(d), fare_amount=2.5 + 2.5 * float(d) + 1, duracion=12.0,
              tpep_pickup_datetime=pd.Timestamp("2017-01-10 08:00") + pd.Timedelta(minutes=i))
        for i, d in enumerate(rng.normal(2.0, 0.1, config.RUTA_MIN_VIAJES + 10))
    ]
    desvio = viaje(trip_distance=6.0, fare_amount=18.0, duracion=25.0, tpep_pickup_datetime=pd.Timestamp("2017-01-11 09:00"))
    df = procesar(normales + [desvio])
    assert df["a_desvio_ruta"].sum() == 1
    assert df["a_desvio_ruta"].iloc[-1]
