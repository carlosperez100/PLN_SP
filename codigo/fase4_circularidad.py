# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - Experimento de circularidad: enmascarar los disparadores.

Cuantifica el hallazgo critico de la auditoria: como la etiqueta 'naturaleza'
proviene de regex (Tier B) sobre el mismo texto, un TF-IDF re-aprende esas regex.
Aqui MEDIMOS cuanto del desempeno se debe a los disparadores exactos:

  Condicion A (original): texto tal cual  -> TF-IDF + LinearSVC
  Condicion B (enmascarado): se reemplazan por " __MASK__ " todos los tramos que
    disparan los patrones Tier B (TIER_B_PATRONES) -> TF-IDF + LinearSVC

La CAIDA A->B es la magnitud de la circularidad atribuible al trigger literal.
El desempeno residual en B mide cuanto aporta el CONTEXTO (co-ocurrencias), no el
disparador. Ambas condiciones usan split por PACIENTE (sin fuga).

Nota: la caida es una COTA INFERIOR de la circularidad (el modelo aun puede
apoyarse en tokens de contexto correlacionados con el trigger).

Salida: datos_intermedios/fase4/fase4_circularidad.json
"""
import os, re, json, time
from collections import Counter
from pathlib import Path
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, cohen_kappa_score

import ast

def _cargar_tier_b():
    """Extrae el dict TIER_B_PATRONES del codigo fuente sin importar el modulo
    (evita la dependencia duckdb que este importa en su cabecera)."""
    src = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/fase3_corpus_expansion.py").read_text(encoding="utf-8")
    arbol = ast.parse(src)
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign):
            for tg in nodo.targets:
                if getattr(tg, "id", "") == "TIER_B_PATRONES":
                    return ast.literal_eval(nodo.value)
    raise RuntimeError("No se encontro TIER_B_PATRONES")

TIER_B_PATRONES = _cargar_tier_b()

BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios")
CANDIDATOS = BASE / "corpus_fase3_candidatos.csv"
PARQUET = BASE / "fase4" / "fase4_dataset.parquet"
OUT = BASE / "fase4"
MIN_CLASE = 30
SEED = 42


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# Ultimo elemento de cada tupla = regex del patron
REGEXES = []
for k, v in TIER_B_PATRONES.items():
    patron = v[-1] if isinstance(v, (tuple, list)) else v
    if isinstance(patron, str) and patron:
        try:
            REGEXES.append(re.compile(patron, re.IGNORECASE))
        except re.error:
            pass


def enmascarar(texto):
    n = 0
    for rx in REGEXES:
        texto, k = rx.subn(" __MASK__ ", texto)
        n += k
    return texto, n


def metricas(y, pred):
    return {
        "accuracy": round(accuracy_score(y, pred), 4),
        "f1_weighted": round(f1_score(y, pred, average="weighted"), 4),
        "f1_macro": round(f1_score(y, pred, average="macro"), 4),
        "cohen_kappa": round(cohen_kappa_score(y, pred), 4),
    }


def entrenar(Xtr_txt, Xte_txt, ytr, yte):
    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=3,
                          sublinear_tf=True, stop_words="english")
    Xtr = vec.fit_transform(Xtr_txt); Xte = vec.transform(Xte_txt)
    svc = LinearSVC(class_weight="balanced"); svc.fit(Xtr, ytr)
    return metricas(yte, svc.predict(Xte))


def main():
    t0 = time.time()
    log(f"Patrones Tier B compilados: {len(REGEXES)}")
    df = pd.read_parquet(PARQUET)[["note_id", "text"]]
    cand = pd.read_csv(CANDIDATOS, encoding="utf-8")
    subj = cand.groupby("note_id")["subject_id"].first()
    nat = (cand.groupby("note_id")["naturaleza"]
               .agg(lambda s: Counter(s).most_common(1)[0][0]))
    df["subject_id"] = df["note_id"].map(subj)
    df["naturaleza"] = df["note_id"].map(nat)
    df = df.dropna(subset=["text", "naturaleza", "subject_id"])
    vc = df["naturaleza"].value_counts()
    df = df[df["naturaleza"].isin(vc[vc >= MIN_CLASE].index)].reset_index(drop=True)
    log(f"Dataset: {len(df)} notas, {df['naturaleza'].nunique()} clases")

    log("Enmascarando disparadores ...")
    masked, nmask = [], []
    for t in df["text"]:
        mt, k = enmascarar(t)
        masked.append(mt); nmask.append(k)
    df["text_masked"] = masked
    pct_con_mask = round(100 * (np.array(nmask) > 0).mean(), 1)
    log(f"Notas con >=1 disparador enmascarado: {pct_con_mask}% | "
        f"media {round(float(np.mean(nmask)), 2)} masks/nota")

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr, te = next(gss.split(df["text"], df["naturaleza"], groups=df["subject_id"]))
    ytr, yte = df["naturaleza"].iloc[tr], df["naturaleza"].iloc[te]

    m_orig = entrenar(df["text"].iloc[tr], df["text"].iloc[te], ytr, yte)
    log(f"A original:    {m_orig}")
    m_mask = entrenar(df["text_masked"].iloc[tr], df["text_masked"].iloc[te], ytr, yte)
    log(f"B enmascarado: {m_mask}")

    caida = {k: round(m_orig[k] - m_mask[k], 4) for k in m_orig}
    salida = {
        "n_notas": len(df), "n_patrones_tierB": len(REGEXES),
        "pct_notas_con_disparador": pct_con_mask,
        "media_masks_por_nota": round(float(np.mean(nmask)), 2),
        "split": "por paciente (GroupShuffleSplit, seed 42)",
        "A_original": m_orig, "B_enmascarado": m_mask, "caida_A_menos_B": caida,
        "interpretacion": ("La caida A->B es la cota inferior de la circularidad "
                           "atribuible al disparador literal; el residual en B es "
                           "el aporte del contexto."),
        "segundos": round(time.time() - t0, 1),
    }
    (OUT / "fase4_circularidad.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== FASE 4 - CIRCULARIDAD (original vs disparadores enmascarados) ====")
    print(f"{'metrica':<14}{'A original':>12}{'B enmascar.':>12}{'caida':>10}")
    for k in ["accuracy", "f1_weighted", "f1_macro", "cohen_kappa"]:
        print(f"{k:<14}{m_orig[k]:>12}{m_mask[k]:>12}{caida[k]:>10}")
    print(f"\nDisparadores enmascarados en {pct_con_mask}% de notas | total {salida['segundos']}s")


if __name__ == "__main__":
    main()
