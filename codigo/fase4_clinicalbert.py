# -*- coding: utf-8 -*-
"""
FASE 4 (OE2) - ClinicalBERT como extractor de caracteristicas (feasibility).

En CPU no es viable el fine-tuning completo de ClinicalBERT sobre 14.8k notas,
asi que se demuestra la FACTIBILIDAD del tercer modelo del OE2 usando
Bio_ClinicalBERT congelado (mean-pooling de embeddings) + cabezal LogReg, sobre
una submuestra estratificada. Se compara en el MISMO split contra TF-IDF+LinearSVC
para una comparacion justa.

Salida: datos_intermedios/fase4/fase4_clinicalbert.json

Requiere: transformers, torch (CPU ok), y descarga del modelo
emilyalsentzer/Bio_ClinicalBERT (~440MB) desde HuggingFace (necesita internet
la primera vez; luego queda en cache).
"""
import os, json, time, sys
from pathlib import Path
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, cohen_kappa_score

BASE = Path(r"C:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios/fase4")
DATASET = BASE / "fase4_dataset.parquet"
MODELO = "emilyalsentzer/Bio_ClinicalBERT"
N_SUB = 2500          # submuestra estratificada (CPU)
MAX_LEN = 256
BATCH = 16
SEED = 42


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def metricas(y, pred):
    return {
        "accuracy": round(accuracy_score(y, pred), 4),
        "f1_weighted": round(f1_score(y, pred, average="weighted"), 4),
        "f1_macro": round(f1_score(y, pred, average="macro"), 4),
        "cohen_kappa": round(cohen_kappa_score(y, pred), 4),
    }


def embeddings(textos, tok, model, torch):
    outs = []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(textos), BATCH):
            lote = textos[i:i + BATCH]
            enc = tok(lote, padding=True, truncation=True, max_length=MAX_LEN,
                      return_tensors="pt")
            hs = model(**enc).last_hidden_state           # [B, T, H]
            mask = enc["attention_mask"].unsqueeze(-1).float()
            mean = (hs * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            outs.append(mean.cpu().numpy())
            if (i // BATCH) % 10 == 0:
                log(f"  embed {min(i + BATCH, len(textos))}/{len(textos)}")
    return np.vstack(outs)


def main():
    t0 = time.time()
    df = pd.read_parquet(DATASET)
    # submuestra estratificada
    frac = min(1.0, N_SUB / len(df))
    sub = (df.groupby("naturaleza", group_keys=False)
             .apply(lambda g: g.sample(max(1, int(round(len(g) * frac))),
                                       random_state=SEED)))
    sub = sub.reset_index(drop=True)
    log(f"Submuestra: {len(sub)} notas, {sub['naturaleza'].nunique()} clases")

    Xtr_txt, Xte_txt, ytr, yte = train_test_split(
        sub["text"].tolist(), sub["naturaleza"].tolist(),
        test_size=0.2, random_state=SEED, stratify=sub["naturaleza"])
    log(f"Split: train={len(ytr)} test={len(yte)}")

    resultados = {}

    # --- Modelo baseline en el MISMO split ---
    vec = TfidfVectorizer(max_features=30000, ngram_range=(1, 2), min_df=3,
                          sublinear_tf=True, stop_words="english")
    Xtr = vec.fit_transform(Xtr_txt); Xte = vec.transform(Xte_txt)
    svc = LinearSVC(class_weight="balanced"); svc.fit(Xtr, ytr)
    resultados["TF-IDF+LinearSVC (submuestra)"] = metricas(yte, svc.predict(Xte))
    log(f"TF-IDF+LinearSVC: {resultados['TF-IDF+LinearSVC (submuestra)']}")

    # --- ClinicalBERT feature extractor ---
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        log(f"Cargando {MODELO} ...")
        tok = AutoTokenizer.from_pretrained(MODELO)
        model = AutoModel.from_pretrained(MODELO)
        torch.set_num_threads(max(1, os.cpu_count() - 1))
        log("Extrayendo embeddings de train ...")
        Etr = embeddings(Xtr_txt, tok, model, torch)
        log("Extrayendo embeddings de test ...")
        Ete = embeddings(Xte_txt, tok, model, torch)
        head = LogisticRegression(max_iter=2000, class_weight="balanced", n_jobs=-1)
        head.fit(Etr, ytr)
        resultados["ClinicalBERT(frozen)+LogReg"] = metricas(yte, head.predict(Ete))
        log(f"ClinicalBERT+LogReg: {resultados['ClinicalBERT(frozen)+LogReg']}")
    except Exception as e:
        resultados["ClinicalBERT(frozen)+LogReg"] = {"error": str(e)[:300]}
        log(f"ClinicalBERT FALLO: {e}")

    salida = {
        "modelo_bert": MODELO,
        "n_submuestra": len(sub),
        "max_len": MAX_LEN,
        "nota": "ClinicalBERT como extractor congelado (no fine-tuning) por CPU; "
                "demostracion de factibilidad para el piloto.",
        "resultados": resultados,
        "segundos": round(time.time() - t0, 1),
    }
    (BASE / "fase4_clinicalbert.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==== FASE 4 - ClinicalBERT vs baseline (mismo split, submuestra) ====")
    for n, r in resultados.items():
        if "error" in r:
            print(f"{n:<34} ERROR: {r['error'][:80]}")
        else:
            print(f"{n:<34} acc={r['accuracy']} f1w={r['f1_weighted']} "
                  f"f1m={r['f1_macro']} kappa={r['cohen_kappa']}")
    print(f"\nTotal {salida['segundos']}s -> {BASE / 'fase4_clinicalbert.json'}")


if __name__ == "__main__":
    main()
