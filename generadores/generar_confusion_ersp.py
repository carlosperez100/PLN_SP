# -*- coding: utf-8 -*-
"""Matriz de confusion 9x9 de la NATURALEZA (Anexo 02) sobre el corpus ERSP
en espanol — la sugerencia del docente. Sale de las predicciones out-of-fold
ya calculadas (Excel de revision de los 8,799 casos): cada caso fue predicho
por un modelo que nunca lo vio.

Salidas: presentacion/anexo_fig6_confusion_ersp.png (300 dpi)
         paper/figuras/fig6_confusion_ersp.pdf
"""
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',
                              errors='replace')
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

X = Path(r"T:\MIMIC\tesis\_datos_trabajo\ERSP_8799_casos_revision.xlsx")
d = pd.read_excel(X, sheet_name="Casos")

# solo el corpus modelado con prediccion out-of-fold (sin heredadas/referenciales)
m = d[(d["Estado"] == "modelado")
      & (d["Origen de la predicción"].astype(str).str.startswith("out-of-fold"))
      & d["NATURALEZA — codificada"].notna()
      & (d["NATURALEZA — predicha"].astype(str).str.strip() != "")].copy()
real = m["NATURALEZA — codificada"].astype(str)
pred = m["NATURALEZA — predicha"].astype(str)

# orden por frecuencia real descendente (como la Tabla VIII)
orden = real.value_counts().index.tolist()
n = len(orden)
M = np.zeros((n, n), dtype=int)
idx = {c: i for i, c in enumerate(orden)}
for r, p in zip(real, pred):
    if p in idx:
        M[idx[r], idx[p]] += 1

CORTAS = {
    "CUIDADO DEL PACIENTE": "Cuidado del paciente",
    "GESTIÓN DE LA ORGANIZACIÓN": "Gestión de la organización",
    "MEDICACIÓN": "Medicación",
    "DISPOSITIVO MÉDICO / EQUIPO / BIEN": "Dispositivo / equipo",
    "INFECCIÓN ASOCIADA A LA ATENCIÓN": "Infección (IAAS)",
    "INSUMOS": "Insumos",
    "PROCEDIMIENTO": "Procedimiento",
    "HISTORIA CLÍNICA": "Historia clínica",
    "COMPORTAMIENTO": "Comportamiento",
}
labels = [CORTAS.get(c, c.title()) for c in orden]

# fila normalizada (comportamiento por clase real)
fila = M / M.sum(axis=1, keepdims=True).clip(min=1)

fig, ax = plt.subplots(figsize=(11.8, 8.6))
im = ax.imshow(fila, cmap="RdPu", vmin=0, vmax=1)

for i in range(n):
    for j in range(n):
        if M[i, j] == 0:
            continue
        pct = fila[i, j]
        col = "white" if pct > 0.55 else "#1F2428"
        peso = "bold" if i == j else "normal"
        ax.text(j, i, f"{M[i, j]}\n{pct:.0%}", ha="center", va="center",
                fontsize=8.6, color=col, fontweight=peso, linespacing=1.25)

ax.set_xticks(range(n))
ax.set_yticks(range(n))
ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9.5)
ax.set_yticklabels(labels, fontsize=9.5)
ax.set_xlabel("Predicción del modelo (LinearSVC, out-of-fold)",
              fontsize=11, labelpad=10)
ax.set_ylabel("Naturaleza codificada por el experto (Anexo 02)",
              fontsize=11, labelpad=10)
ax.set_title("Matriz de confusión — naturaleza del evento, corpus ERSP en "
             f"español (n = {M.sum():,})", fontsize=13, pad=14,
             color="#7B1522", fontweight="bold")
cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
cb.set_label("proporción de la fila", fontsize=9)
plt.tight_layout()

OUT1 = Path(r"T:\MIMIC\PLN_SP\presentacion\anexo_fig6_confusion_ersp.png")
OUT2 = Path(r"T:\MIMIC\PLN_SP\paper\figuras\fig6_confusion_ersp.pdf")
fig.savefig(OUT1, dpi=300, bbox_inches="tight")
fig.savefig(OUT2, bbox_inches="tight")
print(f"[OK] matriz {n}x{n} sobre {M.sum():,} casos out-of-fold")

# top confusiones fuera de la diagonal, para narrarlas
pares = [(orden[i], orden[j], M[i, j], fila[i, j])
         for i in range(n) for j in range(n) if i != j and M[i, j] > 0]
pares.sort(key=lambda t: -t[2])
print("\nTOP confusiones (real -> predicho):")
for r, p, c, f in pares[:8]:
    print(f"  {CORTAS.get(r, r):<28} -> {CORTAS.get(p, p):<28} {c:>4} casos ({f:.0%} de la fila)")
