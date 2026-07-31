# -*- coding: utf-8 -*-
"""Figuras del paper MIA-10 (PLN). Se generan DESDE los resultados del
pipeline, igual que el texto: ninguna cifra se transcribe a mano.

Cuatro figuras, cada una elegida por el trabajo que hace el dato:
  fig1_roc            curva ROC del detector (compromiso, una serie)
  fig2_confusion      matriz de confusión (magnitud, rampa secuencial)
  fig3_ventana        efecto de la ventana de contexto (comparación, 2 series)
  fig4_ersp_clases    F1 por naturaleza en el corpus español (magnitud ordenada)

Paleta verificada con el validador de la guía de visualización: banda de
luminosidad, piso de croma, separación para daltonismo (protan ΔE 10.3,
tritan 21.8), piso de visión normal (ΔE 19.1) y contraste — todas pasan.

Uso:  python generar_figuras.py
Salida: paper/figuras/*.pdf  (vectorial, para LaTeX)
"""
import json
import pickle
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit

D = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
FIG = Path(r"T:\MIMIC\tesis\10_curso_PLN_MIA10\paper\figuras")
FIG.mkdir(parents=True, exist_ok=True)

VERDE, ORO = "#0F8A6E", "#B8860B"
TINTA, SUAVE = "#1A1A1A", "#8A8A8A"
SEED, TEST = 42, 0.20

plt.rcParams.update({
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": SUAVE, "axes.linewidth": 0.6,
    "xtick.color": SUAVE, "ytick.color": SUAVE,
    "text.color": TINTA, "axes.labelcolor": TINTA,
    "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def marco(ax):
    """Ejes recesivos: solo izquierda e inferior, rejilla tenue."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis="y", color="#E8E8E8", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)


def guardar(fig, nombre):
    fig.savefig(FIG / f"{nombre}.pdf")
    plt.close(fig)
    print(f"  [OK] {nombre}.pdf")


print("Generando figuras...")

# =============================================== 1 y 2: ROC y confusión
OUT9 = D / "fase9_final"
if (OUT9 / "modelo_final.pkl").exists():
    df = pd.read_parquet(OUT9 / "dataset_final.parquet")
    with open(OUT9 / "modelo_final.pkl", "rb") as f:
        M = pickle.load(f)
    vec, clf = M["deteccion"]["vectorizador"], M["deteccion"]["clasificador"]

    gss = GroupShuffleSplit(n_splits=1, test_size=TEST, random_state=SEED)
    _, te = next(gss.split(df.text, df.y, groups=df.subject_id))
    test = df.iloc[te]
    dec = clf.decision_function(vec.transform(test.text))
    y = test.y.values

    # --- fig 1: ROC ---------------------------------------------------
    fpr, tpr, _ = roc_curve(y, dec)
    auc = roc_auc_score(y, dec)
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    marco(ax)
    ax.plot([0, 1], [0, 1], "--", color="#CFCFCF", linewidth=0.9, zorder=1)
    ax.plot(fpr, tpr, color=VERDE, linewidth=1.8, zorder=3)

    # punto de operación (umbral por defecto, dec >= 0)
    pred = (dec >= 0).astype(int)
    sens = ((pred == 1) & (y == 1)).sum() / (y == 1).sum()
    esp = ((pred == 0) & (y == 0)).sum() / (y == 0).sum()
    ax.plot(1 - esp, sens, "o", color=ORO, markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, zorder=4)
    ax.annotate(f"punto de operación\nsens {sens:.3f} · esp {esp:.3f}",
                xy=(1 - esp, sens), xytext=(0.34, 0.42),
                fontsize=6.5, color=TINTA,
                arrowprops=dict(arrowstyle="-", color=SUAVE, linewidth=0.6))
    ax.text(0.62, 0.16, f"AUC = {auc:.3f}", fontsize=9, color=VERDE,
            fontweight="bold")
    ax.set_xlabel("1 − especificidad")
    ax.set_ylabel("Sensibilidad")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    guardar(fig, "fig1_roc")

    # --- fig 2: matriz de confusión -----------------------------------
    cm = confusion_matrix(y, pred)
    fig, ax = plt.subplots(figsize=(2.9, 2.4))
    ax.imshow(cm, cmap="BuGn", aspect="auto")
    for i in range(2):
        for j in range(2):
            prop = cm[i, j] / cm.sum()
            ax.text(j, i, f"{cm[i,j]:,}", ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if prop > 0.22 else TINTA)
    ax.set_xticks([0, 1], ["Sin evento", "Con evento"])
    ax.set_yticks([0, 1], ["Sin evento", "Con evento"])
    ax.set_xlabel("Predicción del modelo")
    ax.set_ylabel("Etiqueta de referencia")
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.tick_params(length=0)
    guardar(fig, "fig2_confusion")
else:
    print("  [!] falta modelo_final.pkl — se omiten fig1 y fig2")

# =============================================== 3: ventana de contexto
f11 = D / "fase11" / "resultados_transformers.json"
if f11.exists():
    R = json.loads(f11.read_text(encoding="utf-8"))["resultados"]

    # Se localizan por contenido, no por cadena literal: los nombres cambiaron
    # (variantes «sin balanceo», truncado de 2300 -> 1150 car.) y la búsqueda
    # exacta devolvía None, omitiendo la figura EN SILENCIO. Detectado en la
    # auditoría del 31-jul-2026.
    def buscar(*must, sin=()):
        for k, m in R.items():
            if all(t in k for t in must) and not any(t in k for t in sin):
                return m
        return None

    completo = (buscar("TF-IDF", "sin balanceo", "completo")
                or buscar("TF-IDF", "completo"))
    trunc = (buscar("TF-IDF", "sin balanceo", "truncado")
             or buscar("TF-IDF", "truncado"))
    if not (completo and trunc):
        # Avisar sin abortar: un SystemExit aqui dejaba sin generar la fig4,
        # que no depende de estos datos.
        print(f"  [!] fig3 omitida: faltan las variantes completo/truncado en "
              f"fase11. Claves: {list(R)}")
    if completo and trunc:
        met = ["exactitud", "f1_macro", "kappa"]
        etiq = ["Exactitud", "F1-macro", "Kappa"]
        x = np.arange(len(met))
        fig, ax = plt.subplots(figsize=(3.3, 2.4))
        marco(ax)
        b1 = ax.bar(x - 0.19, [completo[m] for m in met], 0.34,
                    label="Texto completo", color=VERDE, zorder=3)
        b2 = ax.bar(x + 0.19, [trunc[m] for m in met], 0.34,
                    label="Truncado a la ventana del transformer",
                    color=ORO, zorder=3)
        for barras in (b1, b2):
            ax.bar_label(barras, fmt="%.3f", fontsize=6.5, padding=2,
                         color=TINTA)
        ax.set_xticks(x, etiq)
        ax.set_ylim(0, max(completo[m] for m in met) * 1.28)
        ax.set_ylabel("Valor")
        ax.legend(frameon=False, loc="upper right", ncols=1)
        guardar(fig, "fig3_ventana")
else:
    print("  [!] falta fase11 — se omite fig3")

# =============================================== 4: F1 por clase (ERSP)
oe5 = D / "oe5_ersp" / "informe_oe5.json"
if oe5.exists():
    t = json.loads(oe5.read_text(encoding="utf-8"))["tareas"]["T2_naturaleza"]
    pc = t["resultados"]["por_clase"]
    filas = sorted(pc.items(), key=lambda x: x[1]["f1"])
    nom = [c.title().replace(" / ", "/")[:26] for c, _ in filas]
    val = [v["f1"] for _, v in filas]
    n = [v["n"] for _, v in filas]

    fig, ax = plt.subplots(figsize=(3.4, 2.9))
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis="x", color="#E8E8E8", linewidth=0.5)
    ax.set_axisbelow(True)
    y = np.arange(len(nom))
    ax.barh(y, val, 0.62, color=VERDE, zorder=3)
    for i, (v, ni) in enumerate(zip(val, n)):
        ax.text(v + 0.015, i, f"{v:.2f}  (n={ni})", va="center",
                fontsize=6.3, color=TINTA)
    ax.set_yticks(y, nom)
    ax.set_xlim(0, 1.16)
    ax.set_xlabel("F1 por clase")
    ax.tick_params(length=0)
    guardar(fig, "fig4_ersp_clases")
else:
    print("  [!] falta informe_oe5 — se omite fig4")

print(f"\nfiguras en {FIG}")
