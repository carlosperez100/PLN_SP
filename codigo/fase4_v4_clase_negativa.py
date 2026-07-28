# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 4 v4 — DETECTOR CON CLASE NEGATIVA
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
EL DEFECTO QUE CORRIGE

  El corpus A1 contiene UNICAMENTE epicrisis que tienen al menos un evento
  adverso codificado. El modelo nunca vio un ejemplo negativo, de modo que
  no aprendio «¿hay un evento?» sino «¿de que naturaleza es el evento que
  ya se que hay?».

  Consecuencia medida en la Fase 4 v3: un texto de un solo caracter (".")
  dispara una deteccion, y calibrar umbrales lo EMPEORA, porque al maximizar
  F1 por clase el criterio se vuelve mas permisivo. Ningun umbral puede
  arreglarlo: la clase «sin evento» no existe en el espacio de salida.

  Para el objetivo general de la tesis —texto → deteccion → priorizacion →
  responsable— esto es bloqueante: el sistema debe poder ABSTENERSE antes de
  escalar una alerta a un responsable institucional.

DISENO EN DOS ETAPAS

  Etapa 1  DETECTOR BINARIO   ¿esta epicrisis contiene un evento adverso?
  Etapa 2  CLASIFICADOR       ¿de que naturaleza?  (solo sobre positivos)

  Es la unica formulacion que refleja la decision real del sistema y la que
  permite medir la abstencion.

DEFINICION DE LOS NEGATIVOS

  Negativo = epicrisis cuya hospitalizacion NO tiene NINGUN codigo del mapeo,
  ni del estrato A1 (causal) ni del A2 (condiciones). Se excluyen los A2 a
  proposito: son ambiguos —pueden ser motivo de ingreso— y usarlos como
  negativos introduciria ruido de etiqueta.

  Universo: 545,497 hospitalizaciones, de las cuales 109,714 tienen algun
  codigo. Quedan ~435,783 candidatas a negativo; se muestrean al azar con
  semilla fija.

PROPORCION Y PREVALENCIA

  Se entrena con razon 1:2 (un positivo por cada dos negativos) para que el
  entrenamiento sea abordable, PERO la prevalencia real de A1 es del 6.53%.
  Entrenar y evaluar a 1:2 sobreestima la precision que el sistema tendria
  en produccion.

  Por eso se reporta ADEMAS la precision corregida a prevalencia real
  mediante el teorema de Bayes:

      VPP = (sens · prev) / (sens · prev + (1 - esp) · (1 - prev))

  Esa cifra —y no la del conjunto de prueba— es la que hay que citar cuando
  se hable de desplegar el sistema sobre el flujo real de epicrisis.

SALIDAS (datos_intermedios/fase4_v4/):
  dataset_binario.parquet    positivos + negativos con texto (reutilizable)
  resultados_binario.json    metricas, correccion por prevalencia, abstencion
  detector_binario.pkl       modelo de la etapa 1

USO:
  python fase4_v4_clase_negativa.py
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
from sklearn.pipeline import FeatureUnion
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (f1_score, precision_score, recall_score,
                             confusion_matrix, roc_auc_score)

BASE      = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
A1_CSV    = BASE / "fase3_v2" / "candidatos_tier_a_corregido.csv"
DATASET_POS = BASE / "fase4_v2" / "dataset_a1.parquet"
DISCHARGE = Path(r"T:\MIMIC\note\note\discharge.csv.gz")
DIAGNOSES = Path(r"T:\MIMIC\mimiciv\hosp\diagnoses_icd.csv.gz")
OUT       = BASE / "fase4_v4"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
RAZON_NEG = 2          # negativos por cada positivo
PREV_REAL = 0.0653     # prevalencia medida del estrato A1
TEST_SIZE = 0.20

T0 = time.time()


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] [+{timedelta(seconds=int(time.time()-T0))}] {m}",
          flush=True)


def construir_dataset():
    destino = OUT / "dataset_binario.parquet"
    if destino.exists():
        log(f"Reutilizando {destino.name}")
        return pd.read_parquet(destino)

    log("Cargando positivos (A1) ...")
    pos = pd.read_parquet(DATASET_POS)[["note_id", "subject_id", "text"]]
    pos["y"] = 1
    log(f"Positivos: {len(pos):,}")

    log("Identificando hospitalizaciones SIN ningun codigo del mapeo ...")
    a = pd.read_csv(A1_CSV, usecols=["hadm_id"])
    hadm_con_codigo = set(a["hadm_id"].unique())
    # tambien las de estrato A2: el CSV ya trae ambos estratos
    log(f"  hospitalizaciones con algun codigo: {len(hadm_con_codigo):,}")

    n_obj = len(pos) * RAZON_NEG
    log(f"Muestreando {n_obj:,} epicrisis negativas del .gz ...")
    rng = np.random.default_rng(SEED)
    trozos = []
    recogidos = 0
    for ch in pd.read_csv(DISCHARGE,
                          usecols=["note_id", "subject_id", "hadm_id", "text"],
                          chunksize=20000, encoding="utf-8"):
        ch = ch[~ch["hadm_id"].isin(hadm_con_codigo)]
        ch = ch[ch["text"].notna() & (ch["text"].str.len() > 100)]
        if not len(ch):
            continue
        # muestreo proporcional para no sesgar hacia el inicio del archivo
        k = min(len(ch), max(1, int(n_obj / 16)))
        ch = ch.sample(n=k, random_state=int(rng.integers(0, 1 << 31)))
        trozos.append(ch[["note_id", "subject_id", "text"]])
        recogidos += len(ch)
        if recogidos >= n_obj:
            break
    neg = pd.concat(trozos, ignore_index=True).head(n_obj)
    neg["y"] = 0
    log(f"Negativos: {len(neg):,}")

    # ningun paciente puede estar en ambos lados
    pac_pos = set(pos["subject_id"])
    antes = len(neg)
    neg = neg[~neg["subject_id"].isin(pac_pos)]
    log(f"  descartados {antes-len(neg):,} negativos de pacientes que ya son positivos")

    df = pd.concat([pos, neg], ignore_index=True)
    df = df.dropna(subset=["text", "subject_id"]).reset_index(drop=True)
    df.to_parquet(destino)
    log(f"Dataset binario: {len(df):,} notas ({df['y'].mean():.1%} positivas)")
    return df


def vectorizador():
    return FeatureUnion([
        ("palabra", TfidfVectorizer(max_features=60000, ngram_range=(1, 2),
                                    min_df=3, sublinear_tf=True,
                                    strip_accents="unicode", lowercase=True)),
        ("caracter", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     max_features=40000, min_df=3,
                                     sublinear_tf=True,
                                     strip_accents="unicode", lowercase=True)),
    ])


def vpp_corregido(sens, esp, prev=PREV_REAL):
    """Valor predictivo positivo a prevalencia real (Bayes)."""
    num = sens * prev
    den = num + (1 - esp) * (1 - prev)
    return num / den if den else 0.0


def main():
    df = construir_dataset()

    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SEED)
    tr, te = next(gss.split(df["text"], df["y"], groups=df["subject_id"]))
    assert not (set(df["subject_id"].iloc[tr]) & set(df["subject_id"].iloc[te])), \
        "FUGA: pacientes compartidos entre particiones"
    log(f"train {len(tr):,} · test {len(te):,} (sin pacientes compartidos)")

    log("Entrenando detector binario ...")
    vec = vectorizador()
    Xtr = vec.fit_transform(df["text"].iloc[tr])
    Xte = vec.transform(df["text"].iloc[te])
    ytr, yte = df["y"].iloc[tr].values, df["y"].iloc[te].values

    clf = LinearSVC(class_weight="balanced", random_state=SEED)
    clf.fit(Xtr, ytr)
    dec = clf.decision_function(Xte)
    pred = (dec >= 0).astype(int)

    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
    sens = tp / (tp + fn) if (tp + fn) else 0.0
    esp = tn / (tn + fp) if (tn + fp) else 0.0
    prec = precision_score(yte, pred, zero_division=0)
    f1 = f1_score(yte, pred, zero_division=0)
    auc = roc_auc_score(yte, dec)
    vpp_real = vpp_corregido(sens, esp)

    log(f"Sensibilidad {sens:.3f} · Especificidad {esp:.3f} · "
        f"Precision {prec:.3f} · F1 {f1:.3f} · AUC {auc:.3f}")
    log(f"VPP corregido a prevalencia real ({PREV_REAL:.2%}): {vpp_real:.3f}")

    # --- la prueba que motivo todo esto ---
    log("")
    log("Prueba de abstencion ante textos triviales:")
    triviales = [".", "   ", "ok",
                 "Paciente estable, sin novedad.",
                 "Routine follow up visit. Vital signs stable. No acute distress.",
                 "Patient admitted for elective knee replacement. Uneventful "
                 "postoperative course. Discharged home in stable condition."]
    dtriv = clf.decision_function(vec.transform([t if t.strip() else " "
                                                 for t in triviales]))
    abstiene = []
    for t, d in zip(triviales, dtriv):
        detecta = bool(d >= 0)
        abstiene.append({"texto": t[:60], "margen": round(float(d), 3),
                         "detecta_evento": detecta})
        log(f"  «{t[:46]:<46}» margen {d:+.2f} -> "
            f"{'DETECTA' if detecta else 'se abstiene'}")

    with open(OUT / "detector_binario.pkl", "wb") as f:
        pickle.dump({"vectorizador": vec, "clasificador": clf}, f)

    resultados = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "experimento": "detector binario con clase negativa explicita",
        "dataset": {
            "total": len(df),
            "positivos": int(df["y"].sum()),
            "negativos": int((df["y"] == 0).sum()),
            "razon_entrenamiento": f"1:{RAZON_NEG}",
            "prevalencia_entrenamiento": round(float(df["y"].mean()), 4),
            "prevalencia_real_A1": PREV_REAL,
        },
        "metricas_conjunto_prueba": {
            "sensibilidad": round(sens, 4),
            "especificidad": round(esp, 4),
            "precision": round(prec, 4),
            "f1": round(f1, 4),
            "auc": round(auc, 4),
            "matriz": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
        },
        "correccion_por_prevalencia": {
            "vpp_en_prueba": round(prec, 4),
            "vpp_a_prevalencia_real": round(vpp_real, 4),
            "lectura": (
                "El conjunto de prueba tiene 33% de positivos por construccion, "
                "pero la prevalencia real del estrato A1 es 6.53%. El VPP "
                "corregido por Bayes es la cifra que corresponde citar al "
                "hablar de despliegue sobre el flujo real de epicrisis: de "
                "cada 100 alertas emitidas, solo esa fraccion seria correcta."),
        },
        "prueba_abstencion": abstiene,
    }
    (OUT / "resultados_binario.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 74)
    print("DETECTOR BINARIO CON CLASE NEGATIVA — RESULTADO")
    print("=" * 74)
    print(f"Dataset: {len(df):,} epicrisis "
          f"({int(df['y'].sum()):,} con evento · {int((df['y']==0).sum()):,} sin evento)")
    print("-" * 74)
    print(f"  Sensibilidad (recall)          : {sens:.3f}")
    print(f"  Especificidad                  : {esp:.3f}")
    print(f"  Precision en el conjunto prueba: {prec:.3f}")
    print(f"  F1                             : {f1:.3f}")
    print(f"  AUC                            : {auc:.3f}")
    print("-" * 74)
    print(f"  VPP a prevalencia real ({PREV_REAL:.2%})  : {vpp_real:.3f}"
          f"   <- cifra de despliegue")
    print("-" * 74)
    n_abs = sum(1 for a in abstiene if not a["detecta_evento"])
    print(f"Abstencion ante textos triviales: {n_abs}/{len(abstiene)}")
    print(f"\nTotal {timedelta(seconds=int(time.time()-T0))} -> {OUT}")
    print("=" * 74)


if __name__ == "__main__":
    main()
