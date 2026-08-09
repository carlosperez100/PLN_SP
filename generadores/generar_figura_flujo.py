# -*- coding: utf-8 -*-
"""Figura del FLUJO COMPLETO del canal (para el paper y la presentacion).

Tres bandas:
  1. Construccion del corpus (MIMIC + codigos -> supervision debil -> corpus)
  2. Modelado y validacion (TF-IDF -> Etapa 1 -> Etapa 2 -> cascada/experto)
  3. Transferencia al espanol (ERSP -> 4 tareas) y destino (matriz GEMSES)

Salidas:
  paper/figuras/fig5_flujo.pdf        (vectorial, \\textwidth en IEEE)
  presentacion/fig_flujo_completo.png (300 dpi)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

GRANATE = "#7B1522"
GRANATE_CLARO = "#F2E4E6"
AZUL = "#2E5F7F"
AZUL_CLARO = "#E4EDF3"
VERDE = "#1D6F54"
VERDE_CLARO = "#E1F0EA"
GRIS = "#5A6268"
TINTA = "#1F2428"

fig, ax = plt.subplots(figsize=(12.8, 5.0))
ax.set_xlim(0, 128)
ax.set_ylim(0, 50)
ax.axis("off")


def box(x, y, w, h, titulo, sub, borde, fondo, tam_t=11, tam_s=9):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
        linewidth=1.4, edgecolor=borde, facecolor=fondo, zorder=2))
    ax.text(x + w / 2, y + h - 2.6, titulo, ha="center", va="center",
            fontsize=tam_t, fontweight="bold", color=borde, zorder=3)
    ax.text(x + w / 2, y + (h - 2.6) / 2 - 0.4, sub, ha="center",
            va="center", fontsize=tam_s, color=TINTA, zorder=3,
            linespacing=1.35)


def flecha(x1, y1, x2, y2, color=GRIS, estilo="-", curva=0.0):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
        linewidth=1.6, color=color, linestyle=estilo,
        connectionstyle=f"arc3,rad={curva}", zorder=1))


def etiqueta_banda(x, y, texto, color):
    ax.text(x, y, texto, fontsize=8.5, fontweight="bold", color=color,
            ha="left", va="center")


# ------------------------- banda 1: construccion del corpus (arriba) ------
Y1 = 36
etiqueta_banda(2, Y1 + 12.5, "1 · CONSTRUCCIÓN DEL CORPUS", AZUL)
box(2, Y1, 24, 11, "MIMIC-IV-Note v2.2",
    "331,793 notas clínicas\n+ códigos CIE-9 / CIE-10", AZUL, AZUL_CLARO)
box(34, Y1, 27, 11, "Etiquetado por supervisión débil",
    "Tier A: códigos por prefijo\nTier B: 35 patrones + NegEx",
    AZUL, AZUL_CLARO)
box(69, Y1, 24, 11, "Corpus de modelado",
    "70,000 notas clínicas\nprevalencia real 20.12 %", AZUL, AZUL_CLARO)
flecha(26.5, Y1 + 5.5, 33.5, Y1 + 5.5)
flecha(61.5, Y1 + 5.5, 68.5, Y1 + 5.5)

# auditoria (lateral derecha de la banda 1)
box(101, Y1, 25, 11, "Auditoría de validez",
    "7 modos de fallo corregidos\n(confusor de época CIE-9/10)",
    "#B57A0E", "#FAF0DC")
flecha(93.5, Y1 + 5.5, 100.5, Y1 + 5.5, color="#B57A0E", estilo="--")

# ------------------------- banda 2: modelado y validacion (centro) --------
Y2 = 18
etiqueta_banda(2, Y2 + 12.5, "2 · MODELADO Y VALIDACIÓN", GRANATE)
box(2, Y2, 24, 11, "Vectorización TF-IDF",
    "palabra (1–2) + carácter (3–5)\npartición POR PACIENTE",
    GRANATE, GRANATE_CLARO)
box(34, Y2, 24, 11, "Etapa 1 · Detección",
    "¿hay evento adverso?\ncon abstención (6/6)", GRANATE, GRANATE_CLARO)
box(66, Y2, 24, 11, "Etapa 2 · Naturaleza",
    "8 clases del Anexo 02", GRANATE, GRANATE_CLARO)
box(98, Y2, 28, 11, "Evaluación honesta",
    "cascada extremo a extremo\n+ juicio experto (163 casos)",
    VERDE, VERDE_CLARO)
flecha(26.5, Y2 + 5.5, 33.5, Y2 + 5.5)
flecha(58.5, Y2 + 5.5, 65.5, Y2 + 5.5)
flecha(90.5, Y2 + 5.5, 97.5, Y2 + 5.5)

# conexion banda 1 -> banda 2 (codo por la izquierda)
flecha(81, Y1 - 0.8, 14, Y2 + 11.8, curva=0.25)

# ------------------------- banda 3: espanol y destino (abajo) -------------
Y3 = 2
etiqueta_banda(2, Y3 + 10.5, "3 · TRANSFERENCIA Y DESTINO", VERDE)
box(2, Y3, 30, 9, "Corpus ERSP — texto peruano real",
    "8,799 reportes en español · etiqueta de ORO", VERDE, VERDE_CLARO,
    tam_t=10.5)
box(40, Y3, 30, 9, "4 tareas con etiqueta de oro",
    "tipo · naturaleza · severidad · código de evento",
    VERDE, VERDE_CLARO, tam_t=10.5)
box(98, Y3, 28, 9, "Matriz GEMSES (destino)",
    "prioridad Verde/Amarillo/Rojo\n+ responsable", GRANATE,
    GRANATE_CLARO, tam_t=10.5)
flecha(32.5, Y3 + 4.5, 39.5, Y3 + 4.5)
flecha(70.5, Y3 + 4.5, 97.5, Y3 + 4.5, estilo="--")
# de validacion (banda 2) al destino
flecha(112, Y2 - 0.8, 112, Y3 + 9.8)

plt.tight_layout(pad=0.4)
RAIZ = Path(r"T:\MIMIC\PLN_SP")
pdf = RAIZ / "paper" / "figuras" / "fig5_flujo.pdf"
png = RAIZ / "presentacion" / "fig_flujo_completo.png"
fig.savefig(pdf, bbox_inches="tight")
fig.savefig(png, dpi=300, bbox_inches="tight")
print("[OK]", pdf)
print("[OK]", png)
