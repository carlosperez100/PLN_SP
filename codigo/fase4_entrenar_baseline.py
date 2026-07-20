# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - Entrenamiento y comparacion de modelos NLP.

Baseline sklearn: TF-IDF + LogisticRegression  vs  TF-IDF + LinearSVC.
Etiqueta debil (weak supervision): 'naturaleza' del evento adverso, derivada
del pipeline Tier A/B de la Fase 3. Se toma la naturaleza PRIMARIA (mas
frecuente) por nota como target multiclase.

Texto clinico: MIMIC-IV-Note discharge.csv.gz (unido por note_id).

Salidas (en datos_intermedios/fase4/):
  - fase4_resultados.json          metricas de cada modelo
  - fase4_reporte_<modelo>.txt     classification_report por modelo
  - fase4_dataset.parquet          dataset unido (texto + label) para reuso
  - fase4_mejor_modelo.pkl         vectorizador + mejor modelo

Uso:
  set KMP_DUPLICATE_LIB_OK=TRUE
  python fase4_entrenar_baseline.py
"""
import os, json, pickle, time
from pathlib import Path
from collections import Counter

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, f1_score, cohen_kappa_score,
                             classification_report, confusion_matrix)

# ---- Rutas ----
BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios")
CANDIDATOS = BASE / "corpus_fase3_candidatos.csv"
DISCHARGE = Path(r"C:/MIMIC/note/note/discharge.csv.gz")
OUT = BASE / "fase4"
OUT.mkdir(exist_ok=True)

MIN_CLASE = 30          # descartar naturalezas con < 30 notas
RANDOM_STATE = 42
TEST_SIZE = 0.20


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cargar_etiquetas():
    """note_id -> naturaleza primaria (mas frecuente entre sus detecciones)."""
    df = pd.read_csv(CANDIDATOS, encoding="latin-1")
    log(f"Candidatos: {len(df)} detecciones, {df['note_id'].nunique()} notas unicas")
    # naturaleza primaria por nota = moda
    prim = (df.groupby("note_id")["naturaleza"]
              .agg(lambda s: Counter(s).most_common(1)[0][0]))
    return prim  # Series indexada por note_id


def cargar_texto(note_ids):
    """Stream de discharge.csv.gz; devuelve dict note_id -> text para los ids pedidos."""
    objetivo = set(note_ids)
    textos = {}
    total = 0
    for chunk in pd.read_csv(DISCHARGE, usecols=["note_id", "text"],
                             chunksize=20000, encoding="utf-8"):
        total += len(chunk)
        hit = chunk[chunk["note_id"].isin(objetivo)]
        for nid, txt in zip(hit["note_id"], hit["text"]):
            textos[nid] = txt
        if len(textos) >= len(objetivo):
            break
    log(f"Discharge: leidas ~{total} notas, recuperadas {len(textos)}/{len(objetivo)}")
    return textos


def construir_dataset():
    prim = cargar_etiquetas()
    textos = cargar_texto(prim.index.tolist())
    df = pd.DataFrame({"note_id": list(textos.keys()),
                       "text": list(textos.values())})
    df["naturaleza"] = df["note_id"].map(prim)
    df = df.dropna(subset=["text", "naturaleza"])
    df = df[df["text"].str.strip().str.len() > 0]
    # filtrar clases raras
    vc = df["naturaleza"].value_counts()
    keep = vc[vc >= MIN_CLASE].index
    excluidas = vc[vc < MIN_CLASE]
    if len(excluidas):
        log(f"Clases excluidas (<{MIN_CLASE}): {dict(excluidas)}")
    df = df[df["naturaleza"].isin(keep)].reset_index(drop=True)
    log(f"Dataset final: {len(df)} notas, {df['naturaleza'].nunique()} clases")
    log(f"Distribucion:\n{df['naturaleza'].value_counts()}")
    return df


def evaluar(nombre, modelo, Xtr, ytr, Xte, yte):
    t0 = time.time()
    modelo.fit(Xtr, ytr)
    pred = modelo.predict(Xte)
    m = {
        "modelo": nombre,
        "accuracy": round(accuracy_score(yte, pred), 4),
        "f1_weighted": round(f1_score(yte, pred, average="weighted"), 4),
        "f1_macro": round(f1_score(yte, pred, average="macro"), 4),
        "cohen_kappa": round(cohen_kappa_score(yte, pred), 4),
        "segundos": round(time.time() - t0, 1),
    }
    log(f"{nombre}: acc={m['accuracy']} f1w={m['f1_weighted']} "
        f"kappa={m['cohen_kappa']} ({m['segundos']}s)")
    rep = classification_report(yte, pred, zero_division=0)
    (OUT / f"fase4_reporte_{nombre}.txt").write_text(rep, encoding="utf-8")
    return m, modelo


def main():
    t0 = time.time()
    df = construir_dataset()
    df.to_parquet(OUT / "fase4_dataset.parquet")

    Xtr_txt, Xte_txt, ytr, yte = train_test_split(
        df["text"], df["naturaleza"], test_size=TEST_SIZE,
        random_state=RANDOM_STATE, stratify=df["naturaleza"])
    log(f"Split: train={len(ytr)} test={len(yte)}")

    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2),
                          min_df=3, sublinear_tf=True, stop_words="english")
    Xtr = vec.fit_transform(Xtr_txt)
    Xte = vec.transform(Xte_txt)
    log(f"TF-IDF: {Xtr.shape[1]} features")

    modelos = {
        "LogReg": LogisticRegression(max_iter=1000, class_weight="balanced",
                                     n_jobs=-1),
        "LinearSVC": LinearSVC(class_weight="balanced"),
    }
    resultados, fit_models = [], {}
    for nombre, mdl in modelos.items():
        m, fitted = evaluar(nombre, mdl, Xtr, ytr, Xte, yte)
        resultados.append(m)
        fit_models[nombre] = fitted

    resultados.sort(key=lambda r: r["f1_weighted"], reverse=True)
    mejor = resultados[0]["modelo"]
    with open(OUT / "fase4_mejor_modelo.pkl", "wb") as f:
        pickle.dump({"vectorizer": vec, "modelo": fit_models[mejor],
                     "nombre": mejor, "clases": sorted(df["naturaleza"].unique())}, f)

    salida = {
        "n_notas": len(df),
        "n_clases": int(df["naturaleza"].nunique()),
        "clases": df["naturaleza"].value_counts().to_dict(),
        "min_clase": MIN_CLASE,
        "test_size": TEST_SIZE,
        "resultados": resultados,
        "mejor_modelo": mejor,
        "segundos_total": round(time.time() - t0, 1),
    }
    (OUT / "fase4_resultados.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== COMPARACION FASE 4 (baseline sklearn) ====")
    print(f"{'modelo':<12}{'acc':>8}{'f1_w':>8}{'f1_m':>8}{'kappa':>8}")
    for r in resultados:
        print(f"{r['modelo']:<12}{r['accuracy']:>8}{r['f1_weighted']:>8}"
              f"{r['f1_macro']:>8}{r['cohen_kappa']:>8}")
    print(f"\nMejor: {mejor}  |  total {salida['segundos_total']}s")
    print(f"Salidas en: {OUT}")


if __name__ == "__main__":
    main()
