# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - Validacion cruzada robusta de los baselines sklearn.

Reutiliza el dataset ya construido (fase4_dataset.parquet) para NO releer
discharge.csv.gz. Evalua con StratifiedKFold (5 folds) y reporta media +/- desv.
de accuracy, F1-ponderado, F1-macro y kappa de Cohen para:
  - LogReg  (TF-IDF palabra 1-2)
  - LinearSVC (TF-IDF palabra 1-2)
  - LinearSVC (TF-IDF palabra 1-2 + char_wb 3-5)   <- config reforzada

Salida: datos_intermedios/fase4/fase4_crossval.json
"""
import os, json, time
from pathlib import Path
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (accuracy_score, f1_score, cohen_kappa_score)

BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios/fase4")
DATASET = BASE / "fase4_dataset.parquet"
N_SPLITS = 5
SEED = 42


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def vectorizar(train_txt, test_txt, char=False):
    w = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=3,
                        sublinear_tf=True, stop_words="english")
    Xtr = w.fit_transform(train_txt); Xte = w.transform(test_txt)
    if char:
        c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                            max_features=20000, min_df=3, sublinear_tf=True)
        Xtr = hstack([Xtr, c.fit_transform(train_txt)]).tocsr()
        Xte = hstack([Xte, c.transform(test_txt)]).tocsr()
    return Xtr, Xte


CONFIGS = {
    "LogReg": dict(clf=lambda: LogisticRegression(max_iter=1000,
                   class_weight="balanced", n_jobs=-1), char=False),
    "LinearSVC": dict(clf=lambda: LinearSVC(class_weight="balanced"), char=False),
    "LinearSVC+char": dict(clf=lambda: LinearSVC(class_weight="balanced"), char=True),
}


def cv_config(nombre, cfg, X_txt, y):
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    met = {"accuracy": [], "f1_weighted": [], "f1_macro": [], "cohen_kappa": []}
    for i, (tr, te) in enumerate(skf.split(X_txt, y), 1):
        Xtr, Xte = vectorizar(X_txt.iloc[tr], X_txt.iloc[te], char=cfg["char"])
        clf = cfg["clf"](); clf.fit(Xtr, y.iloc[tr]); pred = clf.predict(Xte)
        yte = y.iloc[te]
        met["accuracy"].append(accuracy_score(yte, pred))
        met["f1_weighted"].append(f1_score(yte, pred, average="weighted"))
        met["f1_macro"].append(f1_score(yte, pred, average="macro"))
        met["cohen_kappa"].append(cohen_kappa_score(yte, pred))
        log(f"  {nombre} fold {i}/{N_SPLITS}: acc={met['accuracy'][-1]:.3f}")
    resumen = {k: {"media": round(float(np.mean(v)), 4),
                   "desv": round(float(np.std(v)), 4)} for k, v in met.items()}
    log(f"{nombre}: f1w={resumen['f1_weighted']['media']}"
        f"+/-{resumen['f1_weighted']['desv']} kappa={resumen['cohen_kappa']['media']}")
    return resumen


def main():
    t0 = time.time()
    df = pd.read_parquet(DATASET)
    log(f"Dataset: {len(df)} notas, {df['naturaleza'].nunique()} clases")
    salida = {"n_notas": len(df), "n_splits": N_SPLITS, "configs": {}}
    for nombre, cfg in CONFIGS.items():
        salida["configs"][nombre] = cv_config(nombre, cfg, df["text"], df["naturaleza"])
    salida["segundos"] = round(time.time() - t0, 1)
    (BASE / "fase4_crossval.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== VALIDACION CRUZADA 5-FOLD (media +/- desv) ====")
    print(f"{'config':<16}{'acc':>14}{'f1_w':>14}{'f1_m':>14}{'kappa':>14}")
    for n, r in salida["configs"].items():
        print(f"{n:<16}"
              f"{r['accuracy']['media']:.3f}+-{r['accuracy']['desv']:.3f}  "
              f"{r['f1_weighted']['media']:.3f}+-{r['f1_weighted']['desv']:.3f}  "
              f"{r['f1_macro']['media']:.3f}+-{r['f1_macro']['desv']:.3f}  "
              f"{r['cohen_kappa']['media']:.3f}+-{r['cohen_kappa']['desv']:.3f}")
    print(f"\nTotal {salida['segundos']}s -> {BASE / 'fase4_crossval.json'}")


if __name__ == "__main__":
    main()
