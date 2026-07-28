# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 4 v2 — OE2 CON ETIQUETA A1 (NO CIRCULAR)
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
PREGUNTA QUE RESPONDE ESTE EXPERIMENTO

  El OE2 actual reporta acc 0.731 / F1-macro 0.515 con LinearSVC. Pero la
  auditoria mostro que el 99% de las etiquetas son subcadena del texto: la
  etiqueta viene del mismo regex que se aplico al texto. Ese 0.731 mide, en
  buena parte, consistencia con la regla — no deteccion de eventos.

  Aqui se reentrena el MISMO modelo sobre la MISMA fuente (epicrisis de
  MIMIC-IV), cambiando UNA sola cosa: la etiqueta.

    Etiqueta ANTERIOR : Tier B — regex sobre el propio texto  (circular)
    Etiqueta NUEVA    : Tier A1 — codigos ICD-10 de semantica causal
                        (T80-T88, Y63/Y65/Y83/Y84, W00-W19, L89), asignados
                        por un codificador clinico humano de forma
                        INDEPENDIENTE del texto de la epicrisis.

  La caida de rendimiento entre ambas es la MEDIDA DIRECTA de cuanto del
  0.731 era circularidad. Ese numero no existe hoy en la literatura del
  trabajo y es el aporte metodologico mas fuerte de la tesis.

DISENO

  - Split POR PACIENTE (subject_id), nunca por nota: evita fuga.
  - Multietiqueta con Binary Relevance (15.1% de las notas tienen mas de
    una naturaleza), coherente con la decision ya fijada en el documento.
  - Metrica primaria F1-macro con IC bootstrap; se reporta tambien micro.
  - Modelo: TF-IDF (palabra + caracter) + LinearSVC, la mejor config del OE2.

ESCALABILIDAD (requisito del objetivo general de la tesis)

  El sistema debe aceptar CUALQUIER texto clinico —queja, reporte de
  incidente, epicrisis, evolucion medica— y no solo epicrisis. Por eso el
  vectorizador se entrena con `sublinear_tf` y n-gramas de CARACTER ademas
  de palabra: los n-gramas de caracter son robustos a cambios de registro,
  abreviaturas y errores de tipeo, que es justo lo que distingue una queja
  de una epicrisis. Ademas se mide explicitamente el efecto de la LONGITUD
  del texto (ver `evaluar_por_longitud`), truncando las epicrisis a 120,
  500 y 2000 caracteres para estimar como se degradaria el detector frente
  a textos cortos tipo ERSP. Sin esa medicion no se puede afirmar que el
  pipeline escala a otros generos documentales.

SALIDAS (datos_intermedios/fase4_v2/):
  dataset_a1.parquet          notas + texto + etiquetas A1 (reutilizable)
  resultados_a1.json          metricas, IC bootstrap y comparacion
  modelo_a1.pkl               vectorizador + clasificador entrenados
  por_longitud.csv            degradacion segun longitud del texto

USO:
  python fase4_v2_etiqueta_a1.py
=============================================================================
"""
import json
import time
import pickle
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

BASE       = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
A1_CSV     = BASE / "fase3_v2" / "candidatos_tier_a_corregido.csv"
DISCHARGE  = Path(r"T:\MIMIC\note\note\discharge.csv.gz")
OUT        = BASE / "fase4_v2"
OUT.mkdir(parents=True, exist_ok=True)

SEED        = 42
TEST_SIZE   = 0.20
N_BOOTSTRAP = 200
LONGITUDES  = [120, 500, 2000, None]   # None = texto completo

T0 = time.time()


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] [+{timedelta(seconds=int(time.time()-T0))}] {m}",
          flush=True)


# =============================================================================
# 1 — DATASET
# =============================================================================
def construir_dataset() -> pd.DataFrame:
    destino = OUT / "dataset_a1.parquet"
    if destino.exists():
        log(f"Reutilizando {destino.name}")
        return pd.read_parquet(destino)

    log("Cargando etiquetas A1 ...")
    a = pd.read_csv(A1_CSV)
    a1 = a[a["estrato"] == "A1"]
    etiquetas = (a1.groupby("note_id")["naturaleza"]
                   .agg(lambda s: sorted(set(s))))
    subj = a1.groupby("note_id")["subject_id"].first()
    log(f"A1: {len(etiquetas):,} notas · {a1['subject_id'].nunique():,} pacientes")

    log("Recuperando el texto de discharge.csv.gz ...")
    objetivo = set(etiquetas.index)
    trozos = []
    for ch in pd.read_csv(DISCHARGE, usecols=["note_id", "text"],
                          chunksize=20000, encoding="utf-8"):
        hit = ch[ch["note_id"].isin(objetivo)]
        if len(hit):
            trozos.append(hit)
    textos = pd.concat(trozos, ignore_index=True)
    log(f"Texto recuperado para {len(textos):,}/{len(objetivo):,} notas")

    df = textos.copy()
    df["subject_id"] = df["note_id"].map(subj)
    df["labels"] = df["note_id"].map(etiquetas)
    df = df.dropna(subset=["text", "labels", "subject_id"])
    df = df[df["text"].str.strip().str.len() > 0].reset_index(drop=True)
    df.to_parquet(destino)
    log(f"Dataset guardado: {len(df):,} notas -> {destino.name}")
    return df


# =============================================================================
# 2 — MODELO
# =============================================================================
def construir_vectorizador():
    """
    Palabra + caracter. Los n-gramas de CARACTER son la pieza que da
    robustez entre generos documentales (queja / reporte / epicrisis /
    evolucion): no dependen de la segmentacion en palabras ni del registro.
    """
    return FeatureUnion([
        ("palabra", TfidfVectorizer(max_features=60000, ngram_range=(1, 2),
                                    min_df=3, sublinear_tf=True,
                                    strip_accents="unicode",
                                    lowercase=True)),
        ("caracter", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                     max_features=60000, min_df=3,
                                     sublinear_tf=True,
                                     strip_accents="unicode",
                                     lowercase=True)),
    ])


def ic_bootstrap(y_true, y_pred, n=N_BOOTSTRAP, seed=SEED):
    rng = np.random.default_rng(seed)
    N = y_true.shape[0]
    vals = []
    for _ in range(n):
        idx = rng.integers(0, N, N)
        vals.append(f1_score(y_true[idx], y_pred[idx],
                             average="macro", zero_division=0))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def entrenar_y_evaluar(df, truncar=None, etiqueta=""):
    txt = df["text"] if truncar is None else df["text"].str[:truncar]

    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform(df["labels"])

    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SEED)
    tr, te = next(gss.split(txt, Y, groups=df["subject_id"]))

    vec = construir_vectorizador()
    Xtr = vec.fit_transform(txt.iloc[tr])
    Xte = vec.transform(txt.iloc[te])

    clf = OneVsRestClassifier(
        LinearSVC(class_weight="balanced", random_state=SEED), n_jobs=-1)
    clf.fit(Xtr, Y[tr])
    pred = clf.predict(Xte)

    f1ma = f1_score(Y[te], pred, average="macro", zero_division=0)
    f1mi = f1_score(Y[te], pred, average="micro", zero_division=0)
    lo, hi = ic_bootstrap(Y[te], pred)
    exact = float((pred == Y[te]).all(axis=1).mean())

    log(f"{etiqueta:<22} F1-macro {f1ma:.3f} [{lo:.3f}–{hi:.3f}] · "
        f"F1-micro {f1mi:.3f} · exact-match {exact:.3f} · "
        f"train {len(tr):,} / test {len(te):,}")

    return {
        "f1_macro": round(f1ma, 4),
        "f1_macro_ic95": [round(lo, 4), round(hi, 4)],
        "f1_micro": round(f1mi, 4),
        "exact_match": round(exact, 4),
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "clases": list(mlb.classes_),
    }, (vec, clf, mlb, Y[te], pred)


# =============================================================================
# 3 — MAIN
# =============================================================================
def main():
    df = construir_dataset()
    log(f"Dataset: {len(df):,} notas · {df['subject_id'].nunique():,} pacientes")
    log(f"Multietiqueta: {(df['labels'].str.len()>1).mean():.1%} de las notas")

    log("")
    log("=== Modelo principal: etiqueta A1, texto completo ===")
    principal, art = entrenar_y_evaluar(df, None, "A1 texto completo")
    vec, clf, mlb, Yte, pred = art

    with open(OUT / "modelo_a1.pkl", "wb") as f:
        pickle.dump({"vectorizador": vec, "clasificador": clf,
                     "binarizador": mlb}, f)

    rep = classification_report(Yte, pred, target_names=mlb.classes_,
                                zero_division=0, output_dict=True)

    log("")
    log("=== Escalabilidad: degradacion segun longitud del texto ===")
    log("(simula queja / reporte corto / evolucion frente a epicrisis)")
    por_long = []
    for L in LONGITUDES:
        nombre = "completo" if L is None else f"{L} caracteres"
        r, _ = entrenar_y_evaluar(df, L, f"truncado a {nombre}")
        por_long.append({"longitud": nombre,
                         "caracteres": L or -1,
                         "f1_macro": r["f1_macro"],
                         "f1_macro_lo": r["f1_macro_ic95"][0],
                         "f1_macro_hi": r["f1_macro_ic95"][1],
                         "f1_micro": r["f1_micro"]})
    pd.DataFrame(por_long).to_csv(OUT / "por_longitud.csv", index=False,
                                  encoding="utf-8")

    F1_REGEX = 0.515          # F1-macro del OE2 con etiqueta Tier B (regex)
    ACC_REGEX = 0.731
    delta = principal["f1_macro"] - F1_REGEX

    resultados = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "experimento": "OE2 con etiqueta A1 no circular (ICD-10 causal)",
        "dataset": {
            "notas": len(df),
            "pacientes": int(df["subject_id"].nunique()),
            "multietiqueta_pct": round(100*(df["labels"].str.len()>1).mean(), 1),
            "clases": list(mlb.classes_),
        },
        "modelo_principal": principal,
        "por_clase": {k: v for k, v in rep.items()
                      if k in list(mlb.classes_)},
        "comparacion_con_etiqueta_regex": {
            "f1_macro_regex_circular": F1_REGEX,
            "accuracy_regex_circular": ACC_REGEX,
            "f1_macro_a1_no_circular": principal["f1_macro"],
            "delta_f1_macro": round(delta, 4),
            "lectura": (
                "La diferencia estima cuanto del rendimiento anterior dependia "
                "de que la etiqueta viniera del mismo regex aplicado al texto. "
                "Una caida grande NO invalida el trabajo: cuantifica la "
                "circularidad, que es lo que la auditoria pedia medir."),
        },
        "escalabilidad_por_longitud": por_long,
        "nota_escalabilidad": (
            "El detector se entrena sobre epicrisis largas. La curva por "
            "longitud estima su comportamiento ante textos cortos (quejas, "
            "reportes de incidente, evoluciones). Es el sustento empirico de "
            "que el pipeline admite otros generos documentales."),
    }
    (OUT / "resultados_a1.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 74)
    print("OE2 CON ETIQUETA A1 (NO CIRCULAR) — RESULTADO")
    print("=" * 74)
    print(f"Notas {len(df):,} · pacientes {df['subject_id'].nunique():,} · "
          f"{len(mlb.classes_)} naturalezas · split POR PACIENTE")
    print("-" * 74)
    print(f"  Etiqueta regex (circular)   F1-macro = {F1_REGEX:.3f}")
    print(f"  Etiqueta A1  (no circular)  F1-macro = {principal['f1_macro']:.3f}  "
          f"IC95 [{principal['f1_macro_ic95'][0]:.3f}–{principal['f1_macro_ic95'][1]:.3f}]")
    print(f"  Delta                                = {delta:+.3f}")
    print("-" * 74)
    print("Degradacion por longitud del texto (escalabilidad):")
    for r in por_long:
        print(f"  {r['longitud']:<16} F1-macro {r['f1_macro']:.3f}")
    print("-" * 74)
    print(f"Total {timedelta(seconds=int(time.time()-T0))} -> {OUT}")
    print("=" * 74)


if __name__ == "__main__":
    main()
