"""Estilo común de las figuras de los notebooks (mismos colores que el tablero)."""

import matplotlib.pyplot as plt
import seaborn as sns

from . import config

AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#b5b3ab"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
RETICULA = "#e1e0d9"
SECUENCIAL = sns.blend_palette(["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"], as_cmap=True)


def estilo() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "axes.edgecolor": RETICULA,
            "axes.labelcolor": TINTA_2,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "grid.color": RETICULA,
            "xtick.color": TINTA_2,
            "ytick.color": TINTA_2,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def guardar(fig, nombre: str) -> None:
    """Guarda la figura en reports/figures para reutilizarla en el README."""
    config.FIGURAS.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURAS / nombre)
