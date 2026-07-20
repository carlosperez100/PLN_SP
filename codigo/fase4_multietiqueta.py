# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - Reformulacion MULTI-ETIQUETA.

Responde al hallazgo de la auditoria: el 30.9% de las notas tienen mas de una
naturaleza, y el baseline mono-clase (moda) descarta esa informacion. Aqui la
tarea se plantea como corresponde: cada nota puede pertenecer a VARIAS naturalezas
simultaneamente (multi-label), usando el CONJUNTO de naturalezas detectadas por
nota como objetivo.

Modelo: TF-IDF (palabra 1-2) + OneVsRestClassifier(LinearSVC), split por PACIENTE.
Metricas propias de multi-etiqueta: F1-micro/macro/weighted/samples, Hamming loss,
exact-match (subset accuracy) y F1 por etiqueta.

Salida: datos_intermedios/fase4/fase4_multietiqueta.json (+ reporte por etiqueta)
"""
import os, json, time
from pathlib import Path
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (f1_score, hamming_loss, accuracy_score,
                             classification_report)

BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios")
CANDIDATOS = BASE / "corpus_fase3_candidatos.csv"
PARQUET = BASE / "fase4" / "fase4_dataset.parquet"
OUT = BASE / "fase4"
MIN_CLASE = 30
SEED = 42


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def main():
    t0 = time.time()
    df = pd.read_parquet(PARQUET)[["note_id", "text"]]
    cand = pd.read_csv(CANDIDATOS, encoding="utf-8")

    # etiquetas validas (>= MIN_CLASE detecciones)
    vc = cand["naturaleza"].value_counts()
    validas = set(vc[vc >= MIN_CLASE].index)
    subj = cand.groupby("note_id")["subject_id"].first()
    # conjunto de naturalezas por nota (solo las validas)
    conj = (cand[cand["naturaleza"].isin(validas)]
            .groupby("note_id")["naturaleza"].agg(lambda s: sorted(set(s))))

    df["subject_id"] = df["note_id"].map(subj)
    df["labels"] = df["note_id"].map(conj)
    df = df.dropna(subset=["text", "subject_id", "labels"])
    df = df[df["labels"].map(len) > 0].reset_index(drop=True)

    n_multi = df["labels"].map(len)
    pct_multi = round(100 * (n_multi > 1).mean(), 1)
    log(f"Dataset: {len(df)} notas | {pct_multi}% multi-naturaleza | "
        f"media {round(float(n_multi.mean()), 2)} etiquetas/nota")

    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform(df["labels"])
    log(f"Etiquetas ({len(mlb.classes_)}): {list(mlb.classes_)}")

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr, te = next(gss.split(df["text"], Y, groups=df["subject_id"]))

    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=3,
                          sublinear_tf=True, stop_words="english")
    Xtr = vec.fit_transform(df["text"].iloc[tr])
    Xte = vec.transform(df["text"].iloc[te])
    Ytr, Yte = Y[tr], Y[te]

    clf = OneVsRestClassifier(LinearSVC(class_weight="balanced"), n_jobs=-1)
    clf.fit(Xtr, Ytr)
    pred = clf.predict(Xte)

    met = {
        "f1_micro": round(f1_score(Yte, pred, average="micro", zero_division=0), 4),
        "f1_macro": round(f1_score(Yte, pred, average="macro", zero_division=0), 4),
        "f1_weighted": round(f1_score(Yte, pred, average="weighted", zero_division=0), 4),
        "f1_samples": round(f1_score(Yte, pred, average="samples", zero_division=0), 4),
        "hamming_loss": round(hamming_loss(Yte, pred), 4),
        "exact_match_subset_acc": round(accuracy_score(Yte, pred), 4),
    }
    log(f"Multi-etiqueta: {met}")

    # F1 por etiqueta
    f1_por_etq = f1_score(Yte, pred, average=None, zero_division=0)
    por_etiqueta = {c: round(float(f), 4) for c, f in zip(mlb.classes_, f1_por_etq)}

    rep = classification_report(Yte, pred, target_names=list(mlb.classes_),
                                zero_division=0)
    (OUT / "fase4_multietiqueta_reporte.txt").write_text(rep, encoding="utf-8")

    salida = {
        "n_notas": len(df),
        "pct_multi_naturaleza": pct_multi,
        "media_etiquetas_por_nota": round(float(n_multi.mean()), 2),
        "n_etiquetas": len(mlb.classes_),
        "etiquetas": list(mlb.classes_),
        "split": "por paciente (GroupShuffleSplit, seed 42)",
        "modelo": "TF-IDF(1-2) + OneVsRest(LinearSVC)",
        "metricas": met,
        "f1_por_etiqueta": por_etiqueta,
        "nota_interpretacion": ("El exact-match bajo confirma que la tarea real es "
                                "multi-etiqueta: el baseline mono-clase (0.71 acc) "
                                "sobre-simplificaba. F1-micro/samples son las cifras "
                                "comparables; siguen midiendo consistencia con la "
                                "etiqueta debil, no validez clinica."),
        "segundos": round(time.time() - t0, 1),
    }
    (OUT / "fase4_multietiqueta.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== FASE 4 - MULTI-ETIQUETA (OneVsRest LinearSVC, split paciente) ====")
    for k, v in met.items():
        print(f"  {k:<24} {v}")
    print("\n  F1 por etiqueta:")
    for c, f in sorted(por_etiqueta.items(), key=lambda x: -x[1]):
        print(f"    {c:<24} {f}")
    print(f"\n{pct_multi}% notas multi-naturaleza | total {salida['segundos']}s")


if __name__ == "__main__":
    main()
