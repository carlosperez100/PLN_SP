# -*- coding: utf-8 -*-
"""Ficha tecnica del proyecto: presupuesto de computo, volumen de datos,
codigo y hardware. Todas las cifras salen de artefactos reales (JSON de
resultados y logs del pipeline), no de estimaciones.

Salidas: presentacion/ficha_computo.png (300 dpi) · paper/figuras/fig7_computo.pdf
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

GRANATE, GRANATE_C = "#7B1522", "#F7EDEF"
AZUL, AZUL_C = "#2E5F7F", "#EAF1F6"
VERDE, VERDE_C = "#1D6F54", "#E8F2EE"
AMBAR, AMBAR_C = "#9A6508", "#FBF3E0"
TINTA, GRIS = "#1F2428", "#5A6268"

fig, ax = plt.subplots(figsize=(15.5, 9.6))
ax.set_xlim(0, 155)
ax.set_ylim(0, 96)
ax.axis("off")

ax.text(77.5, 92.6, "Ficha técnica del proyecto: presupuesto de cómputo y "
        "recursos", ha="center", fontsize=17, fontweight="bold", color=TINTA)
ax.text(77.5, 89.2, "Detección automática de eventos adversos hospitalarios "
        "en notas clínicas · abril–agosto 2026 · todas las cifras medidas de "
        "los logs y artefactos del pipeline",
        ha="center", fontsize=9.5, color=GRIS)


def panel(x, y, w, h, titulo, col, fondo):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle="round,pad=0.5,rounding_size=1.3", linewidth=1.5,
                 edgecolor=col, facecolor=fondo, zorder=2))
    ax.text(x + 1.8, y + h - 2.9, titulo, fontsize=11, fontweight="bold",
            color=col, va="center")


def filas(x, y, datos, dx=0, tam=9.3, salto=3.05, color_val=TINTA):
    for i, (k, v) in enumerate(datos):
        yy = y - i * salto
        ax.text(x, yy, k, fontsize=tam, color=GRIS, va="center")
        ax.text(x + dx, yy, v, fontsize=tam, color=color_val, va="center",
                fontweight="bold", ha="right")


# ---------------------------------------------- 1 · COMPUTO POR FASE
panel(2, 47, 74, 39, "1 · CÓMPUTO REGISTRADO POR FASE", GRANATE, GRANATE_C)
ax.text(3.8, 80.3, "Fase / experimento", fontsize=9, color=GRANATE,
        fontweight="bold")
ax.text(57, 80.3, "Duración", fontsize=9, color=GRANATE, fontweight="bold",
        ha="right")
ax.text(74, 80.3, "Dónde", fontsize=9, color=GRANATE, fontweight="bold",
        ha="right")
ax.plot([3.8, 74], [78.8, 78.8], color=GRANATE, linewidth=0.7)

COMPUTO = [
    ("Fase 3 · ablación sobre el corpus completo (331,793 notas)",
     "17 h 56 min", "CPU"),
    ("Fase 3 · Tier A corregido (6.4 M diagnósticos indexados)",
     "23 min", "CPU"),
    ("Fase 4 · 10 experimentos de OE2 (fuga, circularidad, umbral…)",
     "5 h 46 min", "CPU"),
    ("Fase 11 · Bio_ClinicalBERT ponderado (fine-tuning)",
     "3 h 57 min", "GPU"),
    ("Fase 11 · Bio_ClinicalBERT + BioBERT (fine-tuning)",
     "5 h 50 min", "GPU"),
    ("Fase 11 · 4 modelos TF-IDF + LinearSVC",
     "1 min 46 s", "CPU"),
    ("Fase 13 · BioClinical ModernBERT 1,024 tok (2 épocas)",
     "42 h 32 min", "GPU"),
    ("Fase 13 · Llama 3.2 3B local, 68 casos (zero-shot)",
     "47 min", "CPU"),
]
for i, (n, t, d) in enumerate(COMPUTO):
    yy = 76.3 - i * 3.35
    ax.text(3.8, yy, n, fontsize=9, color=TINTA, va="center")
    ax.text(57, yy, t, fontsize=9, color=TINTA, va="center", ha="right",
            fontweight="bold")
    col = VERDE if d == "GPU" else AZUL
    ax.text(74, yy, d, fontsize=8.4, color=col, va="center", ha="right",
            fontweight="bold")

ax.plot([3.8, 74], [49.6, 49.6], color=GRANATE, linewidth=0.7)
ax.text(3.8, 48.4, "TOTAL REGISTRADO  ·  77 h 12 min", fontsize=10.5,
        color=GRANATE, fontweight="bold", va="center")
ax.text(74, 48.4, "≈ 3.2 días de máquina", fontsize=9, color=GRIS,
        va="center", ha="right")

# ---------------------------------------------- 2 · HARDWARE
panel(79, 62.5, 74, 23.5, "2 · HARDWARE Y ENTORNO — todo local, sin nube",
      AZUL, AZUL_C)
filas(81, 80.5, [
    ("Equipo", "HP Victus 16 · 12 hilos · 15.6 GB RAM"),
    ("GPU", "NVIDIA GTX 1650 · 4 GB (Turing, sin Tensor Cores)"),
    ("Almacenamiento", "NVMe dedicado (T:) · 2.36 GB de artefactos"),
    ("Entorno", "Python 3.13 · venv aislado · torch cu126"),
    ("Coste en nube / API", "S/ 0.00 — 100 % software libre"),
], dx=71, salto=3.4)
ax.text(81, 64.2, "El DUA de PhysioNet exige procesamiento local: el texto "
        "clínico nunca salió de la máquina.", fontsize=8.6, color=AZUL,
        style="italic")

# ---------------------------------------------- 3 · DATOS
panel(79, 34.5, 74, 25.5, "3 · DATOS PROCESADOS", VERDE, VERDE_C)
filas(81, 54.5, [
    ("Notas clínicas examinadas (MIMIC-IV-Note)", "331,793"),
    ("Corpus de modelado (fase 9)", "70,000"),
    ("Hospitalizaciones del universo poblacional", "545,601"),
    ("Reportes peruanos con etiqueta de oro (ERSP)", "8,799 → 6,336"),
    ("Casos con juicio experto (241 veredictos)", "163"),
    ("Códigos CIE mapeados · patrones de texto", "223 · 35"),
], dx=71, salto=3.4)

# ---------------------------------------------- 4 · MODELOS Y CODIGO
panel(79, 6, 74, 26, "4 · MODELOS Y CÓDIGO", AMBAR, AMBAR_C)
filas(81, 26.5, [
    ("Configuraciones de modelo evaluadas", "14"),
    ("Familias comparadas (léxica · transformer · LLM)", "3"),
    ("Modos de fallo del etiquetado auditados", "7"),
    ("Scripts del pipeline y de análisis", "76"),
    ("Líneas de código propio", "21,681"),
    ("Referencias verificadas en fuente primaria", "34"),
], dx=71, salto=3.4)

# ---------------------------------------------- 5 · EL CONTRASTE
panel(2, 19, 74, 25, "5 · EL CONTRASTE QUE DEFINE EL TRABAJO", GRANATE,
      "#FFFFFF")
ax.text(3.8, 38.2, "Modelo ganador · TF-IDF + LinearSVC (texto completo)",
        fontsize=9.6, color=TINTA, fontweight="bold")
ax.text(74, 38.2, "F1-macro 0.459", fontsize=9.6, color=GRANATE,
        fontweight="bold", ha="right")
ax.text(3.8, 35.2, "     entrenamiento: 48 segundos, en CPU", fontsize=9,
        color=GRIS)

ax.text(3.8, 31.2, "Mejor transformer · BioClinical ModernBERT (1,024 tok)",
        fontsize=9.6, color=TINTA, fontweight="bold")
ax.text(74, 31.2, "F1-macro 0.428", fontsize=9.6, color=VERDE,
        fontweight="bold", ha="right")
ax.text(3.8, 28.2, "     entrenamiento: 42 h 32 min, en GPU", fontsize=9,
        color=GRIS)

ax.plot([3.8, 74], [25.8, 25.8], color="#D8D8D8", linewidth=0.7)
ax.text(3.8, 23.7, "3,190× más cómputo para el segundo lugar.", fontsize=10,
        color=GRANATE, fontweight="bold")
ax.text(3.8, 21.2, "A igual ventana el transformer ya gana (0.428 vs 0.388): "
        "la ventaja del léxico es\nver el documento completo, no la "
        "arquitectura.", fontsize=8.8, color=GRIS, linespacing=1.45,
        va="center")

# ---------------------------------------------- 6 · CRONOLOGIA
panel(2, 2, 74, 15.5, "6 · CRONOLOGÍA", AZUL, AZUL_C)
HITOS = [
    ("23 abr", "inicio del curso MIA-10"),
    ("mayo", "propuesta del trabajo final"),
    ("19 jul", "repositorio público del curso"),
    ("26–27 jul", "auditoría: 7 modos de fallo"),
    ("28–31 jul", "corrección del confusor + validación experta"),
    ("1 ago", "comparación con transformers · artículo"),
    ("16 ago", "exposición del trabajo final"),
    ("17–19 ago", "fase 13: modelos modernos en local"),
]
for i, (f, t) in enumerate(HITOS):
    col_x = 3.8 if i < 4 else 39
    yy = 12.4 - (i % 4) * 2.9
    ax.text(col_x, yy, f, fontsize=8.8, color=AZUL, fontweight="bold",
            va="center")
    ax.text(col_x + 8.5, yy, t, fontsize=8.8, color=TINTA, va="center")

ax.text(77.5, 0.2, "Fuente: logs y artefactos JSON del pipeline "
        "(github.com/carlosperez100/PLN_SP). Las fases 7–10 y 12 no "
        "instrumentaron duración, por lo que el total es una cota inferior.",
        ha="center", fontsize=7.8, color=GRIS, style="italic")

plt.tight_layout(pad=0.4)
RAIZ = Path(r"T:\MIMIC\PLN_SP")
fig.savefig(RAIZ / "presentacion" / "ficha_computo.png", dpi=300,
            bbox_inches="tight")
fig.savefig(RAIZ / "paper" / "figuras" / "fig7_computo.pdf",
            bbox_inches="tight")
print("[OK] ficha_computo.png / fig7_computo.pdf")
