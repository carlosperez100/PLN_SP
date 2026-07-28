# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 4 v5 — ELECCION DEL PUNTO DE OPERACION
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
PREGUNTA

  El detector binario de la Fase 4 v4 usa el umbral por defecto (margen >= 0)
  y alcanza sensibilidad 0.907, especificidad 0.917 y un VPP corregido a
  prevalencia real de 0.433. Ese umbral es ARBITRARIO: es donde LinearSVC
  coloca el hiperplano, no una decision de diseño.

  ¿Que punto de operacion conviene a un sistema de tamizaje que escala
  alertas a un responsable institucional?

POR QUE LA ESPECIFICIDAD ES LA UNICA PALANCA

  Con prevalencia p = 6.53%, el valor predictivo positivo es

      VPP = (sens · p) / (sens · p + (1 - esp) · (1 - p))

  El termino de falsos positivos, (1 - esp)(1 - p), va multiplicado por
  0.9347, mientras que el de verdaderos positivos va multiplicado por 0.0653.
  El error en la clase mayoritaria pesa catorce veces mas.

  Consecuencia, calculada en este mismo script: con la especificidad fija,
  pasar de sensibilidad 0.907 a 1.000 —deteccion perfecta— sube el VPP de
  0.433 a solo 0.457. En cambio subir la especificidad de 0.917 a 0.970 lo
  lleva a 0.679. A prevalencia baja, un punto de especificidad vale del orden
  de diez puntos de sensibilidad.

  Es el principio clasico del cribado poblacional y explica por que un
  detector con AUC 0.973 puede seguir emitiendo mas falsas alarmas que
  aciertos si se opera en el umbral equivocado.

QUE HACE ESTE SCRIPT

  1. Recarga el detector y el conjunto de prueba de la Fase 4 v4, con el
     MISMO split por paciente (misma semilla), para no reentrenar nada.
  2. Barre el umbral sobre el margen de decision y, en cada punto, calcula
     sensibilidad, especificidad, VPP corregido por prevalencia y la carga
     operativa proyectada sobre los 515,493 egresos de EsSalud en 2025.
  3. Selecciona el punto recomendado con un criterio EXPLICITO y declarado:
     el mayor VPP que conserve una deteccion superior a la notificacion
     actual de EsSalud (14,275 eventos/año). Es decir: mejorar la precision
     sin renunciar a superar el sistema vigente.

SALIDAS (datos_intermedios/fase4_v5/):
  curva_operacion.csv        un punto por umbral, con todas las metricas
  punto_operacion.json       punto recomendado y criterio de seleccion

USO:
  python fase4_v5_punto_operacion.py
=============================================================================
"""
import json
import pickle
import time
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import confusion_matrix

BASE = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
MODELO = BASE / "fase4_v4" / "detector_binario.pkl"
DATASET = BASE / "fase4_v4" / "dataset_binario.parquet"
OUT = BASE / "fase4_v5"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
TEST_SIZE = 0.20
PREV_REAL = 0.0653                # prevalencia medida del estrato A1
EGRESOS_ESSALUD = 515_493         # EsSalud 2025
NOTIFICADOS_HOY = 14_275          # EsSalud 2025
UMBRALES = np.round(np.arange(-0.6, 2.41, 0.1), 2)

T0 = time.time()


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] [+{timedelta(seconds=int(time.time()-T0))}] {m}",
          flush=True)


def vpp(sens, esp, prev=PREV_REAL):
    """Valor predictivo positivo corregido a prevalencia real (Bayes)."""
    num = sens * prev
    den = num + (1 - esp) * (1 - prev)
    return num / den if den else 0.0


def main():
    log("Cargando detector y dataset de la Fase 4 v4 ...")
    with open(MODELO, "rb") as f:
        m = pickle.load(f)
    df = pd.read_parquet(DATASET)

    # mismo split por paciente que en v4: misma semilla, mismo test_size
    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SEED)
    _, te = next(gss.split(df["text"], df["y"], groups=df["subject_id"]))
    X = m["vectorizador"].transform(df["text"].iloc[te])
    y = df["y"].iloc[te].values
    dec = m["clasificador"].decision_function(X)
    log(f"Conjunto de prueba: {len(y):,} epicrisis ({y.mean():.1%} positivas)")

    # --- demostracion numerica de cual es la palanca ---
    log("")
    log("Sensibilidad del VPP a cada metrica (prevalencia 6.53%):")
    for s in (0.907, 0.95, 0.99, 1.00):
        log(f"   sens {s:.3f} · esp 0.917 fija -> VPP {vpp(s, 0.917):.3f}")
    for e in (0.95, 0.97, 0.98):
        log(f"   sens 0.907 fija · esp {e:.3f} -> VPP {vpp(0.907, e):.3f}")

    # --- barrido del umbral ---
    log("")
    log("Barriendo el umbral de decision ...")
    reales = EGRESOS_ESSALUD * PREV_REAL
    filas = []
    for t in UMBRALES:
        pred = (dec >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        esp = tn / (tn + fp) if (tn + fp) else 0.0
        v = vpp(sens, esp)
        captados = reales * sens
        falsas = (EGRESOS_ESSALUD - reales) * (1 - esp)
        filas.append({
            "umbral": float(t),
            "sensibilidad": round(sens, 4),
            "especificidad": round(esp, 4),
            "vpp_prevalencia_real": round(v, 4),
            "alertas_ano": int(round(captados + falsas)),
            "alertas_dia": int(round((captados + falsas) / 365)),
            "eventos_captados_ano": int(round(captados)),
            "falsas_alarmas_ano": int(round(falsas)),
            "veces_vs_notificacion_actual": round(captados / NOTIFICADOS_HOY, 2),
        })
    curva = pd.DataFrame(filas)
    curva.to_csv(OUT / "curva_operacion.csv", index=False, encoding="utf-8")

    # --- seleccion con criterio explicito ---
    # Criterio: maximizar VPP sujeto a captar mas eventos que los que EsSalud
    # notifica hoy. Sin esa restriccion el optimo trivial es un umbral altisimo
    # que casi no emite alertas: precision perfecta y utilidad nula.
    viables = curva[curva["eventos_captados_ano"] > NOTIFICADOS_HOY]
    rec = viables.loc[viables["vpp_prevalencia_real"].idxmax()]

    actual = curva[curva["umbral"] == 0.0].iloc[0]

    resultado = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "criterio_de_seleccion": (
            "maximizar el VPP corregido por prevalencia sujeto a captar mas "
            f"eventos que los {NOTIFICADOS_HOY:,} que EsSalud notifica hoy. La "
            "restriccion es necesaria: sin ella el optimo es un umbral muy alto "
            "con precision casi perfecta y utilidad nula."),
        "prevalencia_usada": PREV_REAL,
        "punto_actual_umbral_0": actual.to_dict(),
        "punto_recomendado": rec.to_dict(),
        "mejora": {
            "vpp": round(rec["vpp_prevalencia_real"] - actual["vpp_prevalencia_real"], 4),
            "reduccion_falsas_alarmas_ano": int(actual["falsas_alarmas_ano"]
                                                - rec["falsas_alarmas_ano"]),
            "coste_eventos_no_captados": int(actual["eventos_captados_ano"]
                                             - rec["eventos_captados_ano"]),
        },
        "nota_sobre_el_suelo": (
            "El VPP calculado es un SUELO, no el valor verdadero. Los falsos "
            "positivos se cuentan contra codigos CIE-10, y la premisa de esta "
            "tesis es que la codificacion administrativa subregistra los "
            "eventos adversos. Parte de esos falsos positivos pueden ser "
            "eventos reales nunca codificados. Cuantificarlo exige revision "
            "experta de una muestra de falsos positivos."),
    }
    (OUT / "punto_operacion.json").write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 84)
    print("CURVA DE OPERACION DEL DETECTOR")
    print("=" * 84)
    print(f"{'umbral':>7} {'sens':>7} {'esp':>7} {'VPP real':>9} "
          f"{'alertas/ano':>12} {'/dia':>6} {'captados':>9} {'vs hoy':>7}")
    print("-" * 84)
    for _, r in curva[curva["umbral"].isin(
            [0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8])].iterrows():
        print(f"{r['umbral']:>7.1f} {r['sensibilidad']:>7.3f} "
              f"{r['especificidad']:>7.3f} {r['vpp_prevalencia_real']:>9.3f} "
              f"{r['alertas_ano']:>12,} {r['alertas_dia']:>6,} "
              f"{r['eventos_captados_ano']:>9,} "
              f"{r['veces_vs_notificacion_actual']:>6.2f}x")
    print("-" * 84)
    print(f"PUNTO RECOMENDADO: umbral {rec['umbral']:+.1f}")
    print(f"  VPP {actual['vpp_prevalencia_real']:.3f} -> "
          f"{rec['vpp_prevalencia_real']:.3f}  "
          f"(+{rec['vpp_prevalencia_real']-actual['vpp_prevalencia_real']:.3f})")
    print(f"  Falsas alarmas: {int(actual['falsas_alarmas_ano']):,} -> "
          f"{int(rec['falsas_alarmas_ano']):,} al ano")
    print(f"  Eventos captados: {int(rec['eventos_captados_ano']):,} "
          f"({rec['veces_vs_notificacion_actual']:.2f}x lo que se notifica hoy)")
    print(f"\nTotal {timedelta(seconds=int(time.time()-T0))} -> {OUT}")
    print("=" * 84)


if __name__ == "__main__":
    main()
