# -*- coding: utf-8 -*-
"""Mapa del ESTADO DEL ARTE v2 — cinco FLUJOS cronologicos (uno por linea de
literatura) que desembocan en ESTE TRABAJO. Cada carril: la evolucion en
3-4 hitos encadenados, la explicacion en simple y lo que el trabajo toma.

Salidas: presentacion/mapa_estado_arte.png (300 dpi) y .pdf
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

GRANATE = "#7B1522"
TINTA, GRIS = "#1F2428", "#5A6268"

fig, ax = plt.subplots(figsize=(17.0, 9.56))   # ~16:9, como la diapositiva
ax.set_xlim(0, 165)
ax.set_ylim(-7, 102)
ax.axis("off")

ax.text(82, 99, "Estado del arte: cinco caminos que desembocan en este trabajo",
        ha="center", fontsize=16, fontweight="bold", color=TINTA)
ax.text(82, 95.8, "Cada carril se lee de izquierda a derecha: cómo evolucionó esa línea de investigación y qué toma de ella este trabajo",
        ha="center", fontsize=9.5, color=GRIS)
ax.text(82, 93.2, "Detección automática de eventos adversos en notas clínicas · MIA-10 Procesamiento del Lenguaje Natural · Carlos Pérez Pérez · UNI 2026",
        ha="center", fontsize=8, color=GRIS)


def nodo(x, y, w, h, texto, col, fondo, tam=7.8, negrita=False, tcol=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle="round,pad=0.35,rounding_size=1.0",
                 linewidth=1.3, edgecolor=col, facecolor=fondo, zorder=3))
    ax.text(x + w/2, y + h/2, texto, ha="center", va="center",
            fontsize=tam, color=(tcol or TINTA), linespacing=1.32,
            fontweight=("bold" if negrita else "normal"), zorder=4)


def flecha_h(x1, x2, y, col):
    ax.add_patch(FancyArrowPatch((x1, y), (x2, y), arrowstyle="-|>",
                 mutation_scale=13, linewidth=1.5, color=col, zorder=2))


LANES = [
    # (color, fondo, titulo, [nodos...], en_simple, toma)
    ("#9A6508", "#FBF3E0",
     "1 · EL PROBLEMA CLÍNICO — el daño que nadie cuenta",
     ["1991 · Harvard\n(Brennan)\n3.7 % de pacientes\nsufre un evento",
      "2008 · de Vries\nmetaanálisis mundial:\n~9 % de incidencia",
      "2011 · Classen\neventos en el 33 %;\nlo voluntario pierde\n~90 % (GTT ve 10×)",
      "El reporte en papel\nve la DÉCIMA parte\ndel daño real"],
     "En simple: el daño existe, es frecuente y el sistema de reporte casi no lo ve.",
     "TOMA: la premisa (subregistro ~72 % EsSalud)\ny el techo a alcanzar (GTT)"),

    ("#7B1522", "#F8ECEE",
     "2 · PLN SOBRE NOTAS CLÍNICAS — leer lo que nadie lee",
     ["2001 · Chapman\nNegEx: «se descarta\nneumonía» NO cuenta\ncomo neumonía",
      "2011 · Murff (JAMA)\nel PLN encuentra\n59–91 % de las\ncomplicaciones",
      "los códigos al alta\napenas 5–46 %:\nla verdad está\nen el TEXTO",
      "Consenso: leer la\nnota supera a los\ncódigos administrativos"],
     "En simple: se le enseña a la computadora a leer la nota — sin confundir mencionar una enfermedad con padecerla.",
     "TOMA: el enfoque (texto libre > códigos)\ny NegEx dentro del Tier B"),

    ("#2E5F7F", "#EAF1F6",
     "3 · MODELOS DE LENGUAJE CLÍNICOS — cada generación lee más",
     ["2019 · BERT\n(Google) entiende\ncontexto · ventana\nde 512 tokens",
      "2019-20 · BioBERT y\nBio_ClinicalBERT:\npreentrenados en\npapers y notas MIMIC",
      "2022 · Clinical-\nLongformer:\nventana 4,096 (8×)",
      "2025 · BioClinical\nModernBERT:\nventana 8,192 (16×)"],
     "En simple: cerebros preentrenados; la evolución de la familia es cuánto texto pueden leer de golpe — la VENTANA.",
     "TOMA: sus rivales (fine-tuning en GPU)\ny el candidato fase 13 — HOY entrenando"),

    ("#1D6F54", "#E8F2EE",
     "4 · SUPERVISIÓN DÉBIL — etiquetar sin anotar a mano",
     ["2017 · Snorkel\n(Stanford): etiquetar\ncon REGLAS, no\ncon personas",
      "las reglas: códigos\ndiagnósticos (Tier A)\ny patrones de texto\n(Tier B)",
      "el precio: el corpus\nhereda los defectos\nde las reglas",
      "la salida: AUDITAR\nlas reglas, no\nasumirlas válidas"],
     "En simple: nadie puede leer 331,793 notas; las reglas sí — pero al corpus lo vigila una auditoría.",
     "TOMA: el etiquetado Tier A + Tier B\ny los 7 modos de fallo corregidos"),

    ("#5B4A8A", "#EFECF6",
     "5 · VALIDEZ Y CONFIABILIDAD — acertar por la razón correcta",
     ["2018 · Zech: la red\n«detectaba neumonía»...\nreconocía el HOSPITAL\n(99.9 %)",
      "2020 · Geirhos:\n«aprendizaje por\natajo» — acertar por\nla vía barata",
      "Cohen · Landis-Koch\nByrt (PABAK): medir\nprimero el acuerdo\nENTRE HUMANOS",
      "Un acierto alto\npuede ser un engaño:\nprobar POR QUÉ\nse acierta"],
     "En simple: la métrica bonita puede mentir; se demuestra la razón del acierto y se compara contra el acuerdo humano.",
     "TOMA: la caza del confusor (0.973 falso →\n0.843 honesto) y el kappa con 163 casos"),
]

# ----- caja final: ESTE TRABAJO (columna derecha, cruza todos los carriles)
BX, BW = 137, 26
ax.add_patch(FancyBboxPatch((BX, 6), BW, 82,
             boxstyle="round,pad=0.6,rounding_size=1.6",
             linewidth=2.4, edgecolor=GRANATE, facecolor="#FBF7F7", zorder=3))
ax.text(BX + BW/2, 83, "ESTE\nTRABAJO", ha="center", va="center",
        fontsize=15, fontweight="bold", color=GRANATE, linespacing=1.3)
ax.text(BX + BW/2, 44,
        "Detección automática\nde eventos adversos\nen notas clínicas\n\n"
        "· corpus etiquetado por\n  reglas AUDITADAS\n  (70,000 notas · 7 fallos\n  corregidos)\n\n"
        "· 7 modelos comparados\n  (léxico F1 0.459 vs\n  transformer 0.354;\n  detector: sens 0.762 ·\n  AUC 0.843 · VPP 0.455)\n\n"
        "· validado contra juicio\n  experto (163 casos ·\n  sens 0.945)\n\n"
        "· taxonomía peruana,\n  Anexo 02 (8,799 reportes\n  reales → 6,336 únicos ·\n  naturaleza 85 % · código\n  de evento 76 %, 41 clases)",
        ha="center", va="center", fontsize=7.9, color=TINTA, linespacing=1.42)

# ----- carriles
Y0, ALTO = 88.5, 16.5
for i, (col, fondo, titulo, nodos, simple, toma) in enumerate(LANES):
    ytop = Y0 - i * ALTO
    ylan = ytop - 13.8
    ax.text(2, ytop - 1.2, titulo, fontsize=10.5, fontweight="bold",
            color=col, va="center")
    # cadena de nodos
    x, w, h = 2, 22.5, 7.6
    ycaja = ytop - 10.6
    for j, txt in enumerate(nodos):
        nodo(x, ycaja, w, h, txt, col, fondo)
        if j < len(nodos) - 1:
            flecha_h(x + w + 0.4, x + w + 3.6, ycaja + h/2, col)
        x += w + 4.0
    # "toma" — puente al trabajo
    nodo(x, ycaja + 0.4, 26.5, h - 0.8, toma, col, "white", tam=7.6,
         negrita=True, tcol=col)
    flecha_h(x + 26.9, BX - 0.6, ycaja + h/2, col)
    # en simple
    ax.text(2, ycaja - 1.7, simple, fontsize=8.2, color=GRIS,
            style="italic", va="top")

# ----- pie de pagina: los 7 modos de fallo corregidos (renglones cortos:
# una linea fisica larga estira el lienzo con bbox_inches='tight')
ax.plot([2, 163], [-0.4, -0.4], color="#C9C9C9", linewidth=0.8)
ax.text(2, -1.6,
        "Los 7 modos de fallo del etiquetado, auditados y corregidos:   "
        "(1) muestreo no declarado — solo se examinaba el 9 % del corpus "
        "(301,793 notas sin revisar);\n"
        "(2) el comodín .* con re.DOTALL cruzaba la nota entera (−63.7 % de "
        "detecciones al acotarlo);   (3) códigos CIE-10 con punto frente a "
        "MIMIC sin punto (Tier A: 411 → 109,714 hospitalizaciones, 267×);\n"
        "(4) ausencia de clase negativa — el detector no podía abstenerse "
        "(corregido: abstención 6/6);   (5) confusor de época CIE-9/CIE-10 — "
        "el AUC 0.973 reconocía la plantilla de cada periodo, no el evento "
        "(→ 0.843 honesto);\n"
        "(6) 43 de 223 códigos eran reglas muertas por la diferencia "
        "OMS/CIE-10-CM (Medicación ×68 al corregir);   (7) percentiles de la "
        "matriz de priorización degenerados con n pequeño (invertían la "
        "prioridad).",
        fontsize=7.6, color=GRIS, va="top", linespacing=1.6)

plt.tight_layout(pad=0.3)
RAIZ = Path(r"T:\MIMIC\PLN_SP\presentacion")
fig.savefig(RAIZ / "mapa_estado_arte.png", dpi=300, bbox_inches="tight")
fig.savefig(RAIZ / "mapa_estado_arte.pdf", bbox_inches="tight")
print("[OK] mapa v2 — cinco flujos")
