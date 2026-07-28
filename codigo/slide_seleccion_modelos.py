# -*- coding: utf-8 -*-
"""
Genera la lámina 16:9 "¿Con qué criterio se eligió el modelo?" para la
exposición del trabajo final MIA-10.

    python codigo/slide_seleccion_modelos.py
-> presentacion/slide_seleccion_modelos.png (1920x1080)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "presentacion" / "slide_seleccion_modelos.png"

NAVY = "#0F2B46"
AZUL = "#1B5E8C"
VERDE = "#0E8A6B"
ROJO = "#B03A2E"
AMBAR = "#B9770E"
GRIS = "#5A6773"
GRIS_CL = "#EDF1F5"
BLANCO = "#FFFFFF"

FIG_W, FIG_H, DPI = 19.20, 10.80, 100

plt.rcParams["font.family"] = "DejaVu Sans"

fig = plt.figure(figsize=(FIG_W, FIG_H), dpi=DPI)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")
ax.add_patch(Rectangle((0, 0), 100, 100, color=BLANCO, zorder=0))


def caja(x, y, w, h, color, r=0.6, z=1, ec="none", lw=0):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=color, edgecolor=ec, linewidth=lw, zorder=z))


def txt(x, y, s, size=13, color=NAVY, weight="normal", ha="left", va="center",
        z=3, style="normal"):
    ax.text(x, y, s, fontsize=size, color=color, fontweight=weight,
            ha=ha, va=va, zorder=z, fontstyle=style)


# ---------------------------------------------------------------- encabezado
caja(0, 88.5, 100, 11.5, NAVY, r=0)
txt(4, 95.6, "¿Con qué criterio se eligió el modelo?", 32, BLANCO, "bold")
txt(4, 91.0, "Metodología de selección en dos etapas — filtros duros de admisibilidad "
             "→ matriz de decisión ponderada", 15.5, "#AFC6DC")
txt(96, 95.0, "MIA-10 · PLN", 15, "#7FA8C9", "bold", ha="right")
txt(96, 91.3, "Carlos Pérez Pérez", 12.5, "#7FA8C9", ha="right")

# --------------------------------------------------- franja: definir la tarea
caja(4, 80.4, 92, 6.6, GRIS_CL)
caja(4, 80.4, 0.55, 6.6, AZUL)
txt(6.2, 85.0, "PASO 0 · La tarea define la métrica, y la métrica define el ranking pertinente",
    14.5, NAVY, "bold")
txt(95, 85.0, "✗  no MMLU · no BLEU/ROUGE · no perplejidad", 13.2, ROJO, "bold", ha="right")
txt(6.2, 82.1, "Clasificación multietiqueta de documentos  y ∈ {0,1}¹²   →   métrica primaria "
               "F1-macro   →   ranking de CLASIFICACIÓN  (MTEB / MMTEB, IberBench)",
    13.2, GRIS)

# ============================ COLUMNA IZQUIERDA — ETAPA 1 ==================
X0, W = 4, 45
caja(X0, 15.5, W, 61.5, "#FAFBFC", ec="#D5DDE5", lw=1.2)
caja(X0, 71.4, W, 5.6, AZUL)
txt(X0 + 1.6, 74.2, "ETAPA 1 · Filtros duros de admisibilidad", 16, BLANCO, "bold")
txt(X0 + 1.6, 68.4, "Una restricción del problema, no una preferencia.",
    12.8, GRIS, style="italic")
txt(X0 + 1.6, 65.9, "Lo que no la pasa sale del espacio de búsqueda y NO se puntúa.",
    12.8, GRIS, style="italic")

filtros = [
    ("F4", "LLM por API pública\n(OpenAI / ChatGPT)",
     "PhysioNet lo PROHÍBE expresamente\npara datos MIMIC", ROJO),
    ("F5", "LLM cloud con vía de\ncumplimiento (Azure, Vertex)",
     "Admisible con opt-out documentado,\npero de pago → ruta del piloto", AMBAR),
    ("F3", "LLM local 7B+\n(Llama, Qwen, Mistral)",
     "Excede la RAM del servidor (2.5 GB)\ny exige GPU", ROJO),
    ("F3", "Bio_ClinicalBERT con\nfine-tuning completo",
     "8–12 h por época en CPU\n→ se reserva al piloto con GPU", AMBAR),
    ("F2", "bsc-bio-ehr-es / BETO /\nMarIA (español)",
     "El corpus de esta etapa es inglés\n→ son los candidatos del OE5", AMBAR),
]
TOP, ALTO, PASO = 63.4, 7.0, 8.2
for i, (cod, cand, motivo, col) in enumerate(filtros):
    top = TOP - i * PASO
    caja(X0 + 1.6, top - ALTO, W - 3.2, ALTO, BLANCO, ec="#DFE6ED", lw=1)
    caja(X0 + 1.6, top - ALTO, 0.5, ALTO, col)
    cy = top - ALTO / 2
    caja(X0 + 2.8, cy - 1.25, 3.5, 2.5, col, r=0.35)
    txt(X0 + 4.55, cy, cod, 12.5, BLANCO, "bold", ha="center")
    txt(X0 + 7.4, cy, cand, 12.6, NAVY, "bold")
    txt(X0 + 24.6, cy, motivo, 11.4, GRIS)

caja(X0 + 1.6, 16.5, W - 3.2, 5.4, "#FDF3E3", ec="#E8C89A", lw=1)
txt(X0 + 3.2, 20.1, "El filtro F4 (cumplimiento del DUA) es el que casi nadie aplica",
    13, "#8C5A1B", "bold")
txt(X0 + 3.2, 17.8, "En datos clínicos credencializados la restricción legal PRECEDE a la métrica.",
    12.2, "#8C5A1B")

# ============================ COLUMNA DERECHA — ETAPA 2 ===================
X1, W1 = 51.5, 44.5
caja(X1, 15.5, W1, 61.5, "#FAFBFC", ec="#D5DDE5", lw=1.2)
caja(X1, 71.4, W1, 5.6, VERDE)
txt(X1 + 1.6, 74.2, "ETAPA 2 · Matriz de decisión ponderada", 16, BLANCO, "bold")
txt(X1 + 1.6, 68.4, "7 criterios · pesos = 1.00 · escala 0–4", 12.8, GRIS, style="italic")
txt(X1 + 1.6, 65.9, "C1–C6 son A PRIORI (antes de correr nada) · C7 es el único posterior",
    12.8, GRIS, style="italic")

cols_x = [X1 + 25.2, X1 + 31.9, X1 + 38.8]
txt(X1 + 1.8, 61.6, "CRITERIO", 11.4, GRIS, "bold")
txt(X1 + 21.6, 61.6, "PESO", 11.4, GRIS, "bold", ha="center")
for cx, (nom, col) in zip(cols_x, [("Linear\nSVC", VERDE), ("Log\nReg", GRIS),
                                   ("ClinicalBERT\ncongelado", GRIS)]):
    txt(cx, 61.9, nom, 10.8, col, "bold", ha="center")

filas = [
    ("C1  Correspondencia con la tarea", "0.20", 4, 4, 2),
    ("C2  Ajuste al dominio clínico", "0.10", 2, 2, 4),
    ("C3  Transferibilidad al español (OE5)", "0.15", 3, 3, 1),
    ("C4  Viabilidad de cómputo (CPU, ≤2.5 GB)", "0.15", 4, 4, 2),
    ("C5  Cumplimiento del DUA (100 % local)", "0.15", 4, 4, 4),
    ("C6  Interpretabilidad / auditabilidad", "0.10", 4, 4, 2),
    ("C7  Desempeño empírico  (posterior)", "0.15", 4, 3, 1),
]
y = 58.4
for i, (crit, peso, a, b, c) in enumerate(filas):
    if i % 2 == 0:
        caja(X1 + 1.4, y - 1.55, W1 - 2.8, 3.1, "#F2F5F8", r=0.2)
    es_post = crit.startswith("C7")
    txt(X1 + 1.8, y, crit, 12.1, AZUL if es_post else NAVY,
        "bold" if es_post else "normal")
    txt(X1 + 21.6, y, peso, 12.1, GRIS, ha="center")
    for cx, v in zip(cols_x, (a, b, c)):
        col = VERDE if v == 4 else (ROJO if v <= 1 else NAVY)
        txt(cx, y, str(v), 13.2, col, "bold", ha="center")
    y -= 3.35

ax.plot([X1 + 1.4, X1 + W1 - 1.4], [y + 0.95, y + 0.95], color="#C8D2DC", lw=1.4, zorder=3)
y -= 0.85
txt(X1 + 1.8, y, "Puntaje A PRIORI  (C1–C6)", 12.6, AZUL, "bold")
for cx, v in zip(cols_x, ("3.59", "3.59", "2.41")):
    txt(cx, y, v, 13.4, AZUL, "bold", ha="center")
y -= 3.6
caja(X1 + 1.4, y - 1.8, W1 - 2.8, 3.6, "#E4F3ED", r=0.25)
txt(X1 + 1.8, y, "PUNTAJE FINAL  (C1–C7)", 12.8, NAVY, "bold")
for cx, v, col in zip(cols_x, ("3.65", "3.50", "2.20"), (VERDE, GRIS, ROJO)):
    txt(cx, y, v, 14.2, col, "bold", ha="center")

# --- seleccionado
caja(X1 + 1.6, 16.5, W1 - 3.2, 10.4, VERDE, r=0.5)
txt(X1 + 3.4, 24.5, "★  MODELO SELECCIONADO", 12.4, "#B7E4D3", "bold")
txt(X1 + 3.4, 21.6, "TF-IDF (palabra + char) + LinearSVC", 18.5, BLANCO, "bold")
txt(X1 + 3.4, 19.1, "3.65 / 4.00  =  91.2 %", 13.2, "#D6EFE5", "bold")
txt(X1 + 3.4, 17.4, "F1-macro 0.515 · κ 0.581 · exactitud 0.731 ± 0.007 (CV 5-fold)",
    12.2, "#D6EFE5")

# ------------------------------------------------------------------ hallazgo
caja(4, 3.2, 92, 11.3, NAVY, r=0.5)
txt(6, 12.3, "EL MARCO PREDIJO EL HALLAZGO CONTRAINTUITIVO", 14, "#7FB8A3", "bold")
txt(6, 9.4, "El puntaje a priori ya separaba la familia léxica (3.59) del transformer clínico "
            "congelado (2.41)  —  antes de ejecutar un solo experimento.", 14, BLANCO)
txt(6, 6.7, "La hipótesis «ClinicalBERT ≥ 75 %» quedó REFUTADA, y no es una anomalía local:",
    12.8, "#AFC6DC")
txt(6, 4.5, "García Subies et al. (JAMIA 2024, 12 corpus clínicos en español) concluyen que "
            "«los mejores modelos no son los clínicos, sino los de propósito general».",
    12.8, "#AFC6DC")

fig.savefig(SALIDA, dpi=DPI, facecolor=BLANCO)
print("Escrito:", SALIDA)
