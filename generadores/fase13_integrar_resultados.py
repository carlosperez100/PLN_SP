# -*- coding: utf-8 -*-
"""Integra los resultados de la FASE 13 cuando termine el fine-tuning.

Lee los artefactos de la fase 13 (ModernBERT final o su progreso por época,
y la evaluación del LLM local) y produce, en un solo comando:

  1. resultados/FASE13_RESULTADOS.md  — informe con el ranking AMPLIADO
     (los 7 modelos originales + control 4,600 + ModernBERT + LLM local),
     listo para leer o pegar.
  2. presentacion/fase13_ranking.png  — gráfico de barras del ranking
     ampliado, listo para una lámina o para el sitio.
  3. Bloque LaTeX (impreso en consola) para actualizar la tabla del paper.

Uso:  python fase13_integrar_resultados.py
"""
import io
import json
import sys
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

F13 = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios\fase13")
RAIZ = Path(r"T:\MIMIC\PLN_SP")

# ------------------------- cargar artefactos -------------------------------
final = F13 / "modernbert_final.json"
prog = F13 / "modernbert_progreso.json"
fuente = final if final.exists() else prog
assert fuente.exists(), "aún no hay resultados de ModernBERT"
mb = json.loads(fuente.read_text(encoding="utf-8"))
estado = "FINAL (2 épocas)" if fuente == final else \
    f"PARCIAL (época {mb.get('epoca_completada', '?')})"

llm = json.loads((F13 / "llm_local_vs_experto.json").read_text(
    encoding="utf-8")) if (F13 / "llm_local_vs_experto.json").exists() else None

# ranking original (fase 11) + nuevos
RANKING = [
    ("TF-IDF + LinearSVC (texto completo)", 0.7149, 0.4592, 0.5443, "48 s"),
    ("TF-IDF + LinearSVC sin balanceo (completo)", 0.7109, 0.3909, 0.5132, "47 s"),
    ("Bio_ClinicalBERT (ft, ponderado, 256 tok)", 0.5429, 0.3541, 0.3252, "4.0 h"),
    ("TF-IDF + LinearSVC (truncado 1,150 car.)", 0.5746, 0.3301, 0.3148, "6 s"),
    ("TF-IDF sin balanceo (truncado 1,150 car.)", 0.5890, 0.2747, 0.2951, "5 s"),
    ("Bio_ClinicalBERT (fine-tuning, 256 tok)", 0.6072, 0.2487, 0.3438, "2.9 h"),
    ("BioBERT (fine-tuning)", 0.5971, 0.2097, 0.3182, "2.9 h"),
]
for nombre, r in mb["resultados"].items():
    tiempo = (f"{r['minutos_acumulados']/60:.1f} h"
              if "minutos_acumulados" in r else f"{r.get('segundos', 0):.0f} s")
    RANKING.append((nombre, r["exactitud"], r["f1_macro"],
                    r["kappa"], tiempo))
RANKING.sort(key=lambda t: -t[2])

# ------------------------- 1) informe markdown -----------------------------
md = [f"# Fase 13 — resultados ({estado})", ""]
md.append(f"Generado a partir de `{fuente.name}` "
          f"({mb.get('generado', '')}).")
md.append("")
md.append("## Ranking ampliado (misma partición, semilla 42)")
md.append("")
md.append("| # | Modelo | Exactitud | F1-macro | Kappa | Tiempo |")
md.append("|---|---|---|---|---|---|")
for i, (n, ex, f1, k, t) in enumerate(RANKING, 1):
    marca = " ⭐" if "ModernBERT" in n else ""
    md.append(f"| {i} | {n}{marca} | {ex:.4f} | **{f1:.4f}** | {k:.4f} | {t} |")
md.append("")
if llm:
    md.append("## LLM generativo local (contra consenso experto, no comparable "
              "con el ranking)")
    md.append("")
    md.append(f"- {llm['modelo']} en zero-shot, 100 % local (Ollama): "
              f"sensibilidad {llm['sensibilidad']:.3f} · especificidad "
              f"{llm['especificidad']:.3f} · kappa {llm['kappa']:.3f} "
              f"sobre {llm['n_consenso']} casos — dijo SÍ a todo: sin ajuste "
              "no discrimina.")
    md.append("")
md.append("## Lectura")
mb_f1 = max(r["f1_macro"] for n, r in mb["resultados"].items()
            if "ModernBERT" in n)
ctl = next((r["f1_macro"] for n, r in mb["resultados"].items()
            if "TF-IDF" in n), None)
md.append("")
md.append(f"- ModernBERT alcanza **F1-macro {mb_f1:.4f}** con ventana de "
          "1,024 tokens (4× la de la fase 11).")
md.append(f"- Frente al Bio_ClinicalBERT de 256 tokens (0.3541): "
          f"{'SUPERA' if mb_f1 > 0.3541 else 'no supera'} al transformer "
          "clínico anterior.")
if ctl:
    md.append(f"- Frente al control léxico de su MISMA ventana ({ctl:.4f}): "
              f"{'lo supera — la arquitectura ya aporta a igual ventana'
                 if mb_f1 > ctl else
                 'aún por debajo — a igual ventana el léxico sigue delante'}.")
md.append(f"- Frente al campeón de texto completo (0.4592): "
          f"{'LO SUPERA — titular para el paper'
             if mb_f1 > 0.4592 else
             'por debajo — consistente con que el texto completo sigue siendo la ventaja decisiva'}.")

out_md = RAIZ / "resultados" / "FASE13_RESULTADOS.md"
out_md.write_text("\n".join(md), encoding="utf-8")
print(f"[OK] {out_md}")

# ------------------------- 2) grafico de barras ----------------------------
GRANATE, AZUL, GRIS, VERDE = "#7B1522", "#2E5F7F", "#B4B2A9", "#1D6F54"
nombres = [n for n, *_ in RANKING]
f1s = [f1 for _, _, f1, _, _ in RANKING]
colores = [VERDE if "ModernBERT" in n else
           (GRANATE if "texto completo" in n and "sin" not in n else
            (AZUL if "BERT" in n else GRIS)) for n in nombres]

fig, ax = plt.subplots(figsize=(11, 0.62 * len(RANKING) + 1.6))
y = range(len(RANKING))[::-1]
ax.barh(list(y), f1s, color=colores, height=0.62)
for yi, f1 in zip(y, f1s):
    ax.text(f1 + 0.004, yi, f"{f1:.3f}", va="center", fontsize=10,
            fontweight="bold")
ax.set_yticks(list(y))
ax.set_yticklabels(nombres, fontsize=9.5)
ax.set_xlabel("F1-macro (misma partición, semilla 42)", fontsize=11)
ax.set_title(f"Ranking ampliado con la fase 13 — {estado}",
             fontsize=13, color=GRANATE, fontweight="bold", pad=12)
ax.set_xlim(0, max(f1s) * 1.14)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
out_png = RAIZ / "presentacion" / "fase13_ranking.png"
fig.savefig(out_png, dpi=300, bbox_inches="tight")
print(f"[OK] {out_png}")

# ------------------------- 3) bloque LaTeX ---------------------------------
print("\n----- filas LaTeX para la tabla del paper -----")
for n, r in mb["resultados"].items():
    print(f"{n} & {r['exactitud']:.4f} & {r['f1_macro']:.4f} & "
          f"{r['kappa']:.4f} \\\\")
print("------------------------------------------------")
