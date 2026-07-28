# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 4 v3 — UMBRAL DE DECISION CALIBRADO POR CLASE
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
PROBLEMA QUE CORRIGE

  El modelo de la Fase 4 v2 (etiqueta A1) usa el umbral por defecto de
  LinearSVC: se predice positivo cuando la distancia al hiperplano es >= 0.
  Con `class_weight="balanced"` y clases muy desbalanceadas eso produce:

    - FALSOS POSITIVOS ABSURDOS. Un texto de un solo caracter (".") dispara
      la clase "Procedimiento". En un sistema que escala alertas a un
      responsable institucional eso es inadmisible.
    - CLASES MUERTAS. "Sistema/Organizacion" obtiene F1 = 0.000 (n=66) y
      "Medicacion" recall 0.150 (6 de 40): el umbral fijo nunca las alcanza.

DISENO DEL EXPERIMENTO — SIN FUGA

  Ajustar umbrales mirando el conjunto de prueba seria fuga metodologica.
  Por eso se parte en TRES, siempre agrupando por paciente:

      train_fit (64%)  ->  entrena el clasificador
      val       (16%)  ->  BUSCA el umbral optimo por clase
      test      (20%)  ->  evalua, una sola vez, sin tocar

  Para cada clase se recorre la rejilla de umbrales sobre la distancia al
  hiperplano y se elige el que maximiza F1 de esa clase EN VALIDACION.

  Se reporta ademas el rechazo de textos vacios o triviales, que es el
  fallo que motivo este experimento.

SALIDAS (datos_intermedios/fase4_v3/):
  resultados_umbral.json     antes y despues, global y por clase
  umbrales.json              umbral elegido por clase (lo consume motor_v2)
  modelo_a1_calibrado.pkl    modelo + umbrales, listo para el prototipo

USO:
  python fase4_v3_umbral_calibrado.py
=============================================================================
"""
import json
import pickle
import time
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.pipeline import FeatureUnion
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import f1_score, classification_report

BASE = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
DATASET = BASE / "fase4_v2" / "dataset_a1.parquet"
OUT = BASE / "fase4_v3"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
REJILLA = np.arange(-1.5, 1.51, 0.05)

T0 = time.time()


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] [+{timedelta(seconds=int(time.time()-T0))}] {m}",
          flush=True)


def vectorizador():
    return FeatureUnion([
        ("palabra", TfidfVectorizer(max_features=60000, ngram_range=(1, 2),
                                    min_df=3, sublinear_tf=True,
                                    strip_accents="unicode", lowercase=True)),
        ("caracter", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     max_features=60000, min_df=3,
                                     sublinear_tf=True,
                                     strip_accents="unicode", lowercase=True)),
    ])


def split_por_paciente(df, Y, test_size, seed):
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    return next(gss.split(df["text"], Y, groups=df["subject_id"]))


def main():
    log("Cargando dataset A1 ...")
    df = pd.read_parquet(DATASET)
    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform(df["labels"])
    clases = list(mlb.classes_)
    log(f"{len(df):,} notas · {df['subject_id'].nunique():,} pacientes · "
        f"{len(clases)} clases")

    # --- particion en tres, por paciente ---
    idx_tr, idx_te = split_por_paciente(df, Y, 0.20, SEED)
    sub_tr = df.iloc[idx_tr].reset_index(drop=True)
    Ytr_full = Y[idx_tr]
    idx_fit, idx_val = split_por_paciente(sub_tr, Ytr_full, 0.20, SEED + 1)

    txt_fit = sub_tr["text"].iloc[idx_fit]
    txt_val = sub_tr["text"].iloc[idx_val]
    txt_te = df["text"].iloc[idx_te]
    Yfit, Yval, Yte = Ytr_full[idx_fit], Ytr_full[idx_val], Y[idx_te]

    # verificacion de que ningun paciente cruza particiones
    p_fit = set(sub_tr["subject_id"].iloc[idx_fit])
    p_val = set(sub_tr["subject_id"].iloc[idx_val])
    p_te = set(df["subject_id"].iloc[idx_te])
    assert not (p_fit & p_val) and not (p_fit & p_te) and not (p_val & p_te), \
        "FUGA: hay pacientes compartidos entre particiones"
    log(f"train_fit {len(txt_fit):,} · val {len(txt_val):,} · test {len(txt_te):,} "
        f"(sin pacientes compartidos)")

    log("Entrenando ...")
    vec = vectorizador()
    Xfit = vec.fit_transform(txt_fit)
    Xval = vec.transform(txt_val)
    Xte = vec.transform(txt_te)
    clf = OneVsRestClassifier(
        LinearSVC(class_weight="balanced", random_state=SEED), n_jobs=-1)
    clf.fit(Xfit, Yfit)

    Dval = clf.decision_function(Xval)
    Dte = clf.decision_function(Xte)

    # --- linea base: umbral fijo en 0 ---
    pred_base = (Dte >= 0).astype(int)
    f1_base = f1_score(Yte, pred_base, average="macro", zero_division=0)
    rep_base = classification_report(Yte, pred_base, target_names=clases,
                                     zero_division=0, output_dict=True)
    log(f"BASE (umbral 0)        F1-macro {f1_base:.3f}")

    # --- busqueda del umbral por clase, EN VALIDACION ---
    log("Calibrando umbrales sobre validacion ...")
    umbrales = {}
    for j, c in enumerate(clases):
        mejor_t, mejor_f1 = 0.0, -1.0
        for t in REJILLA:
            f1 = f1_score(Yval[:, j], (Dval[:, j] >= t).astype(int),
                          zero_division=0)
            if f1 > mejor_f1:
                mejor_f1, mejor_t = f1, float(t)
        umbrales[c] = round(mejor_t, 3)
        log(f"  {c:<24} umbral {mejor_t:+.2f}  (F1 en val {mejor_f1:.3f})")

    T = np.array([umbrales[c] for c in clases])
    pred_cal = (Dte >= T).astype(int)
    f1_cal = f1_score(Yte, pred_cal, average="macro", zero_division=0)
    rep_cal = classification_report(Yte, pred_cal, target_names=clases,
                                    zero_division=0, output_dict=True)
    log(f"CALIBRADO              F1-macro {f1_cal:.3f}  "
        f"(delta {f1_cal-f1_base:+.3f})")

    # --- prueba de rechazo de textos triviales ---
    triviales = [".", "", "   ", "ok", "Paciente estable, sin novedad.",
                 "Routine visit. No complaints. Continue medications."]
    Dtriv = clf.decision_function(vec.transform([t if t.strip() else " "
                                                 for t in triviales]))
    rechazo = []
    for t, fila in zip(triviales, Dtriv):
        base = [clases[j] for j, v in enumerate(fila >= 0) if v]
        cal = [clases[j] for j, v in enumerate(fila >= T) if v]
        rechazo.append({"texto": t[:48], "umbral_0": base, "calibrado": cal})
        log(f"  «{t[:34]:<34}» base={len(base)} calibrado={len(cal)}")

    resultados = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "experimento": "umbral de decision calibrado por clase, sin fuga",
        "particion": {"train_fit": len(txt_fit), "val": len(txt_val),
                      "test": len(txt_te), "agrupado_por": "subject_id"},
        "f1_macro_umbral_fijo": round(f1_base, 4),
        "f1_macro_calibrado": round(f1_cal, 4),
        "delta": round(f1_cal - f1_base, 4),
        "umbrales": umbrales,
        "por_clase": {
            c: {
                "f1_antes": round(rep_base[c]["f1-score"], 4),
                "f1_despues": round(rep_cal[c]["f1-score"], 4),
                "recall_antes": round(rep_base[c]["recall"], 4),
                "recall_despues": round(rep_cal[c]["recall"], 4),
                "precision_antes": round(rep_base[c]["precision"], 4),
                "precision_despues": round(rep_cal[c]["precision"], 4),
                "n": int(rep_base[c]["support"]),
            } for c in clases
        },
        "rechazo_textos_triviales": rechazo,
    }
    (OUT / "resultados_umbral.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "umbrales.json").write_text(
        json.dumps(umbrales, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(OUT / "modelo_a1_calibrado.pkl", "wb") as f:
        pickle.dump({"vectorizador": vec, "clasificador": clf,
                     "binarizador": mlb, "umbrales": umbrales}, f)

    print("\n" + "=" * 72)
    print("UMBRAL CALIBRADO — ANTES Y DESPUES")
    print("=" * 72)
    print(f"F1-macro umbral fijo (0) : {f1_base:.3f}")
    print(f"F1-macro calibrado       : {f1_cal:.3f}   ({f1_cal-f1_base:+.3f})")
    print("-" * 72)
    print(f"{'clase':<24} {'umbral':>7} {'F1 antes':>9} {'F1 desp':>8} "
          f"{'rec antes':>10} {'rec desp':>9}")
    for c in clases:
        v = resultados["por_clase"][c]
        print(f"{c:<24} {umbrales[c]:>+7.2f} {v['f1_antes']:>9.3f} "
              f"{v['f1_despues']:>8.3f} {v['recall_antes']:>10.3f} "
              f"{v['recall_despues']:>9.3f}")
    print("-" * 72)
    print(f"Total {timedelta(seconds=int(time.time()-T0))} -> {OUT}")
    print("=" * 72)


if __name__ == "__main__":
    main()
