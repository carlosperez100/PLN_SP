# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - Correccion metodologica: split a nivel de PACIENTE.

Responde a la auditoria adversarial (hallazgos criticos confirmados):
  - Fuga por paciente: el split original era por note_id, no por subject_id.
  - Lectura latin-1 de un CSV UTF-8 -> mojibake en etiquetas (corregido a UTF-8).
  - Metrica titular F1-ponderado ocultaba el F1-macro honesto -> se reportan ambos.
  - Sin matriz de confusion -> se calcula y guarda.

Compara el split por NOTA (con fuga, "antes") vs el split por PACIENTE (honesto,
"despues") como analisis de sensibilidad, y ademas hace validacion cruzada
agrupada por paciente (StratifiedGroupKFold) para intervalos.

Reutiliza el texto de fase4_dataset.parquet (no relee discharge.csv.gz) y
rejunta subject_id + naturaleza limpia desde corpus_fase3_candidatos.csv (UTF-8).

Salida: datos_intermedios/fase4/fase4_split_paciente.json  (+ matriz de confusion)

NOTA DE VALIDEZ: la etiqueta sigue siendo supervision debil (regex Tier A/B sobre
la misma nota). Estas metricas miden CONSISTENCIA con esa etiqueta, no acuerdo con
un gold humano. La correccion del split elimina la fuga por paciente pero NO la
circularidad etiqueta->texto (ver seccion de limitaciones de la tesis).
"""
import os, json, time
from collections import Counter
from pathlib import Path
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit, train_test_split, StratifiedGroupKFold
from sklearn.metrics import (accuracy_score, f1_score, cohen_kappa_score,
                             classification_report, confusion_matrix)

BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios")
CANDIDATOS = BASE / "corpus_fase3_candidatos.csv"
PARQUET = BASE / "fase4" / "fase4_dataset.parquet"
OUT = BASE / "fase4"
MIN_CLASE = 30
SEED = 42


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def metricas(y, pred):
    return {
        "accuracy": round(accuracy_score(y, pred), 4),
        "f1_weighted": round(f1_score(y, pred, average="weighted"), 4),
        "f1_macro": round(f1_score(y, pred, average="macro"), 4),
        "cohen_kappa": round(cohen_kappa_score(y, pred), 4),
    }


def vec_fit_eval(Xtr_txt, Xte_txt, ytr, yte):
    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=3,
                          sublinear_tf=True, stop_words="english")
    Xtr = vec.fit_transform(Xtr_txt)
    Xte = vec.transform(Xte_txt)
    svc = LinearSVC(class_weight="balanced")
    svc.fit(Xtr, ytr)
    pred = svc.predict(Xte)
    return metricas(yte, pred), pred


def main():
    t0 = time.time()
    # Texto (parquet) + etiqueta limpia y subject_id (candidatos UTF-8)
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
    log(f"Dataset: {len(df)} notas, {df['subject_id'].nunique()} pacientes, "
        f"{df['naturaleza'].nunique()} clases (UTF-8 limpio)")
    # cuantificar exposicion a fuga: notas de pacientes con >1 nota
    notas_por_pac = df.groupby("subject_id").size()
    multi = notas_por_pac[notas_por_pac > 1].index
    pct_exp = round(100 * df["subject_id"].isin(multi).mean(), 1)
    log(f"Notas de pacientes con >1 nota (expuestas a fuga): {pct_exp}%")

    salida = {"n_notas": len(df), "n_pacientes": int(df['subject_id'].nunique()),
              "n_clases": int(df['naturaleza'].nunique()),
              "pct_notas_expuestas_fuga": pct_exp, "seed": SEED}

    # ---- ANTES: split por NOTA (con fuga) ----
    Xtr, Xte, ytr, yte = train_test_split(
        df["text"], df["naturaleza"], test_size=0.2,
        random_state=SEED, stratify=df["naturaleza"])
    m_nota, _ = vec_fit_eval(Xtr, Xte, ytr, yte)
    log(f"ANTES (split por nota): {m_nota}")
    salida["split_por_nota_con_fuga"] = m_nota

    # ---- DESPUES: split por PACIENTE (honesto) ----
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    tr, te = next(gss.split(df["text"], df["naturaleza"], groups=df["subject_id"]))
    m_pac, pred_pac = vec_fit_eval(df["text"].iloc[tr], df["text"].iloc[te],
                                   df["naturaleza"].iloc[tr], df["naturaleza"].iloc[te])
    log(f"DESPUES (split por paciente): {m_pac}")
    salida["split_por_paciente_honesto"] = m_pac
    salida["caida_por_correccion"] = {
        k: round(m_nota[k] - m_pac[k], 4) for k in m_nota}

    # matriz de confusion (antes ausente)
    yte_pac = df["naturaleza"].iloc[te]
    clases = sorted(df["naturaleza"].unique())
    cm = confusion_matrix(yte_pac, pred_pac, labels=clases)
    rep = classification_report(yte_pac, pred_pac, labels=clases, zero_division=0)
    (OUT / "fase4_confusion_paciente.txt").write_text(
        "Clases: " + " | ".join(clases) + "\n\n" + np.array2string(cm) +
        "\n\n" + rep, encoding="utf-8")

    # ---- CV agrupada por paciente (intervalos) ----
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    accs, f1w, f1m, kaps = [], [], [], []
    for i, (a, b) in enumerate(sgkf.split(df["text"], df["naturaleza"],
                                          groups=df["subject_id"]), 1):
        m, _ = vec_fit_eval(df["text"].iloc[a], df["text"].iloc[b],
                            df["naturaleza"].iloc[a], df["naturaleza"].iloc[b])
        accs.append(m["accuracy"]); f1w.append(m["f1_weighted"])
        f1m.append(m["f1_macro"]); kaps.append(m["cohen_kappa"])
        log(f"  CV-paciente fold {i}/5: acc={m['accuracy']} f1m={m['f1_macro']}")
    salida["cv_agrupada_paciente_5fold"] = {
        "accuracy": {"media": round(float(np.mean(accs)), 4), "desv": round(float(np.std(accs)), 4)},
        "f1_weighted": {"media": round(float(np.mean(f1w)), 4), "desv": round(float(np.std(f1w)), 4)},
        "f1_macro": {"media": round(float(np.mean(f1m)), 4), "desv": round(float(np.std(f1m)), 4)},
        "cohen_kappa": {"media": round(float(np.mean(kaps)), 4), "desv": round(float(np.std(kaps)), 4)},
    }
    salida["segundos"] = round(time.time() - t0, 1)
    (OUT / "fase4_split_paciente.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== FASE 4 - CORRECCION SPLIT POR PACIENTE ====")
    print(f"{'metrica':<14}{'nota(fuga)':>12}{'paciente':>12}{'caida':>10}")
    for k in ["accuracy", "f1_weighted", "f1_macro", "cohen_kappa"]:
        print(f"{k:<14}{m_nota[k]:>12}{m_pac[k]:>12}{salida['caida_por_correccion'][k]:>10}")
    cv = salida["cv_agrupada_paciente_5fold"]
    print(f"\nCV por paciente 5-fold: acc={cv['accuracy']['media']}+-{cv['accuracy']['desv']} "
          f"f1_macro={cv['f1_macro']['media']}+-{cv['f1_macro']['desv']} "
          f"kappa={cv['cohen_kappa']['media']}+-{cv['cohen_kappa']['desv']}")
    print(f"Notas expuestas a fuga: {pct_exp}%  |  total {salida['segundos']}s")


if __name__ == "__main__":
    main()
