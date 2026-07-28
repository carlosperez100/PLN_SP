# -*- coding: utf-8 -*-
"""
Selección justificada del modelo de PLN — trabajo final MIA-10.

Implementa el procedimiento de decisión en dos etapas descrito en
`resultados/SELECCION_MODELOS.md`:

  Etapa 1 — filtros duros de admisibilidad (no se puntúa lo inadmisible).
  Etapa 2 — puntuación multicriterio ponderada de los candidatos admisibles.

Emite las tablas en Markdown y LaTeX para que la sección del paper sea
regenerable y no escrita a mano.

    python codigo/seleccion_modelos.py
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_MD = RAIZ / "resultados" / "tablas_seleccion_modelos.md"
SALIDA_TEX = RAIZ / "resultados" / "tablas_seleccion_modelos.tex"

# --------------------------------------------------------------------------
# Etapa 1 — filtros duros de admisibilidad
# --------------------------------------------------------------------------
# Cada filtro es una restricción del problema, no una preferencia. Un candidato
# que no lo pasa queda fuera del espacio de búsqueda y no se puntúa.

FILTROS = {
    "F1": "Tarea: debe resolver clasificación multietiqueta supervisada de documentos.",
    "F2": "Idioma: debe operar sobre el corpus disponible (MIMIC-IV-Note, inglés clínico).",
    "F3": "Cómputo: entrenable e inferible en CPU, con huella <= 2.5 GB (RAM libre del VPS).",
    "F4": "DUA de PhysioNet: el texto clínico no puede salir hacia terceros sin vía de cumplimiento.",
    "F5": "Licencia: pesos y código de uso libre (restricción de proyecto).",
}

DESCARTADOS = [
    # (candidato, filtro que no pasa, motivo verificable)
    ("LLM generativo vía API pública (OpenAI / ChatGPT)", "F4",
     "PhysioNet prohíbe expresamente enviar datos MIMIC por APIs de terceros "
     "como OpenAI o pegarlos en ChatGPT."),
    ("LLM cloud con vía de cumplimiento (Azure OpenAI opt-out, Vertex AI, Bedrock)", "F5",
     "Admisible bajo condiciones documentadas por PhysioNet, pero de pago y con "
     "reproducibilidad dependiente del proveedor. Queda como ruta habilitada para el piloto."),
    ("LLM local de 7B+ parámetros (Llama, Qwen, Mistral)", "F3",
     "Excede la RAM libre del VPS (~2.5 GB) y exige GPU para inferencia útil."),
    ("Bio_ClinicalBERT con fine-tuning completo", "F3",
     "8-12 h por época en CPU. Se reserva al piloto, con GPU."),
    ("bsc-bio-ehr-es / BETO / MarIA (roberta-large-bne)", "F2",
     "Modelos de español; el corpus de esta etapa es inglés clínico. Son los "
     "candidatos del OE5 (transferencia a EsSalud)."),
]

# --------------------------------------------------------------------------
# Etapa 2 — puntuación multicriterio de los candidatos admisibles
# --------------------------------------------------------------------------
# C1-C6 son criterios *a priori*: se pueden puntuar antes de correr nada.
# C7 es el único criterio posterior (depende de la corrida).

CRITERIOS = [
    ("C1", "Correspondencia con la tarea (clasificación multietiqueta)", 0.20, "a priori"),
    ("C2", "Ajuste al dominio clínico",                                  0.10, "a priori"),
    ("C3", "Transferibilidad al español (OE5)",                          0.15, "a priori"),
    ("C4", "Viabilidad de cómputo (CPU, <= 2.5 GB)",                     0.15, "a priori"),
    ("C5", "Cumplimiento del DUA (procesamiento 100 % local)",           0.15, "a priori"),
    ("C6", "Interpretabilidad / auditabilidad clínica",                  0.10, "a priori"),
    ("C7", "Desempeño empírico en el corpus (F1-macro, CV 5-fold)",      0.15, "posterior"),
]

# Escala 0-4: 0 = no cumple, 1 = deficiente, 2 = aceptable, 3 = bueno, 4 = óptimo.
CANDIDATOS = [
    {
        "nombre": "TF-IDF (palabra+char) + LinearSVC",
        "notas": {"C1": 4, "C2": 2, "C3": 3, "C4": 4, "C5": 4, "C6": 4, "C7": 4},
        "f1_macro": 0.515,
        "just": {
            "C1": "Clasificador supervisado nativo; multietiqueta vía Binary Relevance.",
            "C2": "Sin conocimiento clínico previo: lo induce del propio corpus.",
            "C3": "Agnóstico al idioma; se reentrena en español sin cambiar arquitectura.",
            "C4": "Entrena en segundos; el modelo serializado pesa pocos MB.",
            "C5": "Todo el procesamiento ocurre en la máquina del investigador.",
            "C6": "Coeficientes por n-grama -> evidencia legible por el auditor clínico.",
            "C7": "F1-macro 0.515; kappa 0.581; exactitud 0.731 +/- 0.007 (mejor medido).",
        },
    },
    {
        "nombre": "TF-IDF + Regresión Logística",
        "notas": {"C1": 4, "C2": 2, "C3": 3, "C4": 4, "C5": 4, "C6": 4, "C7": 3},
        "f1_macro": 0.466,
        "just": {
            "C1": "Igual que el anterior: misma familia de representación y tarea.",
            "C2": "Sin conocimiento clínico previo.",
            "C3": "Agnóstico al idioma.",
            "C4": "Coste despreciable en CPU.",
            "C5": "Procesamiento local.",
            "C6": "Coeficientes con lectura probabilística directa.",
            "C7": "F1-macro 0.466; kappa 0.474; exactitud 0.628 +/- 0.009.",
        },
    },
    {
        "nombre": "Bio_ClinicalBERT congelado + LogReg",
        "notas": {"C1": 2, "C2": 4, "C3": 1, "C4": 2, "C5": 4, "C6": 2, "C7": 1},
        "f1_macro": 0.190,
        "just": {
            "C1": "Se usa como extractor de rasgos, no ajustado a esta tarea.",
            "C2": "Preentrenado sobre notas clínicas de MIMIC: máximo ajuste de dominio.",
            "C3": "Monolingüe inglés; no transfiere a español.",
            "C4": "Inferencia CPU factible pero lenta; ~440 MB de pesos.",
            "C5": "Pesos descargables: se ejecuta en local.",
            "C6": "Embeddings opacos; exigiría SHAP/LIME para justificar un caso.",
            "C7": "F1-macro 0.190; kappa 0.180; exactitud 0.380 (peor medido).",
        },
    },
]

MAX_NOTA = 4.0


def puntuar(cand, solo_a_priori=False):
    """Suma ponderada. Si solo_a_priori, excluye C7 y renormaliza los pesos."""
    criterios = [c for c in CRITERIOS if not (solo_a_priori and c[3] == "posterior")]
    peso_total = sum(c[2] for c in criterios)
    bruto = sum(cand["notas"][c[0]] * c[2] for c in criterios)
    return bruto / peso_total


def main():
    for c in CANDIDATOS:
        c["score_final"] = puntuar(c)
        c["score_priori"] = puntuar(c, solo_a_priori=True)

    ganador = max(CANDIDATOS, key=lambda c: c["score_final"])

    md = []
    md.append("<!-- GENERADO por codigo/seleccion_modelos.py — no editar a mano -->\n")
    md.append("## Tabla 1. Etapa 1 — filtros duros de admisibilidad\n")
    md.append("| Filtro | Restricción |")
    md.append("|---|---|")
    for k, v in FILTROS.items():
        md.append(f"| **{k}** | {v} |")
    md.append("\n## Tabla 2. Candidatos descartados en la Etapa 1\n")
    md.append("| Candidato | Filtro | Motivo |")
    md.append("|---|:---:|---|")
    for nombre, filtro, motivo in DESCARTADOS:
        md.append(f"| {nombre} | **{filtro}** | {motivo} |")

    md.append("\n## Tabla 3. Etapa 2 — matriz de decisión ponderada\n")
    cab = "| Criterio | Peso | " + " | ".join(c["nombre"] for c in CANDIDATOS) + " |"
    md.append(cab)
    md.append("|---|:---:|" + ":---:|" * len(CANDIDATOS))
    for cid, desc, peso, tipo in CRITERIOS:
        marca = " *(posterior)*" if tipo == "posterior" else ""
        fila = f"| {cid} — {desc}{marca} | {peso:.2f} | "
        fila += " | ".join(str(c["notas"][cid]) for c in CANDIDATOS) + " |"
        md.append(fila)
    md.append("| **Puntaje a priori (C1–C6)** | 0.85 | " +
              " | ".join(f"**{c['score_priori']:.2f}**" for c in CANDIDATOS) + " |")
    md.append("| **Puntaje final (C1–C7)** | 1.00 | " +
              " | ".join(f"**{c['score_final']:.2f}**" for c in CANDIDATOS) + " |")
    md.append("| **Puntaje final normalizado** | | " +
              " | ".join(f"{100 * c['score_final'] / MAX_NOTA:.1f} %" for c in CANDIDATOS) + " |")
    md.append(f"\n**Modelo seleccionado: {ganador['nombre']}** "
              f"(puntaje {ganador['score_final']:.2f}/4.00 = "
              f"{100 * ganador['score_final'] / MAX_NOTA:.1f} %).\n")
    md.append("Escala 0–4: 0 no cumple · 1 deficiente · 2 aceptable · 3 bueno · 4 óptimo.\n")

    md.append("\n## Tabla 4. Justificación de cada puntaje\n")
    md.append("| Candidato | Criterio | Justificación |")
    md.append("|---|:---:|---|")
    for c in CANDIDATOS:
        for cid, _, _, _ in CRITERIOS:
            md.append(f"| {c['nombre']} | {cid} | {c['just'][cid]} |")

    SALIDA_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    # ---- LaTeX (solo la matriz de decisión, que es la que va al paper) ----
    tex = [r"% GENERADO por codigo/seleccion_modelos.py -- no editar a mano",
           r"\begin{table}[htbp]", r"\centering",
           r"\caption{Matriz de decisi\'on ponderada para la selecci\'on del modelo de PLN.}",
           r"\label{tab:seleccion-modelos}",
           r"\begin{tabular}{@{}p{0.34\linewidth}c" + "c" * len(CANDIDATOS) + r"@{}}",
           r"\toprule",
           r"Criterio & Peso & " + " & ".join(f"M{i + 1}" for i in range(len(CANDIDATOS))) + r" \\",
           r"\midrule"]
    for cid, desc, peso, tipo in CRITERIOS:
        d = desc.replace("%", r"\%").replace("<=", r"$\leq$")
        tex.append(f"{cid} -- {d} & {peso:.2f} & " +
                   " & ".join(str(c['notas'][cid]) for c in CANDIDATOS) + r" \\")
    tex.append(r"\midrule")
    tex.append(r"\textbf{Puntaje final} & 1.00 & " +
               " & ".join(f"\\textbf{{{c['score_final']:.2f}}}" for c in CANDIDATOS) + r" \\")
    tex += [r"\bottomrule", r"\end{tabular}", r"\\[2pt]", r"\footnotesize"]
    tex.append("M1: " + "; ".join(f"M{i + 1}: {c['nombre']}" for i, c in enumerate(CANDIDATOS))
               .replace("M1: ", "", 1) + ". Escala 0--4.")
    tex += [r"\end{table}"]
    SALIDA_TEX.write_text("\n".join(tex) + "\n", encoding="utf-8")

    print("Etapa 1: %d candidatos descartados por filtro duro." % len(DESCARTADOS))
    print("Etapa 2: puntajes (a priori C1-C6 / final C1-C7):")
    for c in CANDIDATOS:
        print("  %-38s  %.2f / %.2f  (%.1f%%)" % (
            c["nombre"][:38], c["score_priori"], c["score_final"],
            100 * c["score_final"] / MAX_NOTA))
    print("SELECCIONADO:", ganador["nombre"])
    print("Escrito:", SALIDA_MD)
    print("Escrito:", SALIDA_TEX)


if __name__ == "__main__":
    main()
