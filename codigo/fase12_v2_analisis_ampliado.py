# -*- coding: utf-8 -*-
"""Fase 12 v2 — sistema contra juicio experto usando TODOS los casos anotados.

POR QUE EXISTE. La fase 12 original usaba solo los 78 casos anotados bajo el
codebook v2 (posteriores al 28-jul) y, de ellos, los 68 con consenso de ambos
evaluadores. Pero el anotador A completo 163 veredictos: los otros 85 son el
piloto anotado bajo el protocolo v1. Este script JUNTA TODO el juicio experto
disponible, sin ocultar la heterogeneidad: cada caso queda etiquetado con su
procedencia (consenso doble / solo A piloto / solo A v2) y los desacuerdos
A-B se excluyen declarados, no se promedian.

TRES REFERENCIAS, DE LA MAS ESTRICTA A LA MAS AMPLIA:
  R1 Consenso doble (v2)ii      la original, reproducida como control.
  R2 Mejor juicio disponible    consenso donde hay dos anotadores; veredicto
                                de A donde solo hay uno. Desacuerdos y
                                no-determinables fuera. ESTA es la principal
                                del analisis ampliado.
  R3 Anotador A completo        los 163 veredictos de A, ambos protocolos.
                                Cota de robustez (hereda el sesgo de A).

Uso:  python fase12_v2_analisis_ampliado.py
Salida: datos_intermedios/fase12/sistema_vs_experto_AMPLIADO.json
"""
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

D = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
OUT = D / "fase12"
CODEBOOK_V2_DESDE = "2026-07-28"


def log(m=""):
    print(m, flush=True)


def wilson(exitos, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = exitos / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    semi = (z / den) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (round(max(0.0, centro - semi), 4), round(min(1.0, centro + semi), 4))


def evaluar(nombre, sub):
    """sub: DataFrame con columnas ref (0/1) y pred (0/1)."""
    vp = int(((sub.pred == 1) & (sub.ref == 1)).sum())
    fp = int(((sub.pred == 1) & (sub.ref == 0)).sum())
    fn = int(((sub.pred == 0) & (sub.ref == 1)).sum())
    vn = int(((sub.pred == 0) & (sub.ref == 0)).sum())
    n = vp + fp + fn + vn
    sens = vp / (vp + fn) if (vp + fn) else float("nan")
    esp = vn / (vn + fp) if (vn + fp) else float("nan")
    vpp = vp / (vp + fp) if (vp + fp) else float("nan")
    vpn = vn / (vn + fn) if (vn + fn) else float("nan")
    kappa = (cohen_kappa_score(sub.ref, sub.pred)
             if sub.ref.nunique() > 1 else float("nan"))
    log(f"\n--- {nombre} (n={n}) ---")
    log(f"  matriz: VP={vp} FP={fp} FN={fn} VN={vn}")
    for etq, val, ex, tot in [("sens", sens, vp, vp + fn),
                              ("esp", esp, vn, vn + fp),
                              ("vpp", vpp, vp, vp + fp),
                              ("vpn", vpn, vn, vn + fn)]:
        lo, hi = wilson(ex, tot)
        log(f"  {etq:<5} {val:.4f}  IC95 [{lo:.3f}, {hi:.3f}]  (n={tot})")
    log(f"  kappa {kappa:.4f}")
    return {"n": n, "matriz": {"vp": vp, "fp": fp, "fn": fn, "vn": vn},
            "sensibilidad": round(float(sens), 4),
            "sensibilidad_ic95": list(wilson(vp, vp + fn)),
            "especificidad": round(float(esp), 4),
            "especificidad_ic95": list(wilson(vn, vn + fp)),
            "vpp": round(float(vpp), 4), "vpp_ic95": list(wilson(vp, vp + fp)),
            "vpn": round(float(vpn), 4), "vpn_ic95": list(wilson(vn, vn + fn)),
            "kappa": round(float(kappa), 4)}


log("=" * 70)
log("  FASE 12 v2 — analisis ampliado: TODO el juicio experto disponible")
log("=" * 70)

# --- 1. anotaciones de A (los dos protocolos) -------------------------------
a = pd.read_csv(D / "fase6_revision/anotaciones.csv", dtype=str).fillna("")
a = a[a.es_evento_adverso.str.strip() != ""].copy()
a["protocolo"] = np.where(a.revisado_en.str[:10] > CODEBOOK_V2_DESDE,
                          "codebook_v2", "piloto_v1")
log(f"\nanotador A: {len(a)} veredictos "
    f"({(a.protocolo == 'piloto_v1').sum()} piloto v1 + "
    f"{(a.protocolo == 'codebook_v2').sum()} codebook v2)")

# --- 2. anotaciones de B (solo la tanda valida) ------------------------------
bdf = pd.read_csv(D / "fase6_revision_b/anotaciones.csv", dtype=str).fillna("")
bdf = bdf[bdf.es_evento_adverso.str.strip() != ""][
    ["id_ciego", "es_evento_adverso"]].rename(
        columns={"es_evento_adverso": "juicio_b"})
log(f"anotador B: {len(bdf)} veredictos validos (la tanda anulada NO entra)")

# --- 3. texto y prediccion del sistema ---------------------------------------
muestra = pd.read_csv(D / "fase6_revision/muestra_ciega.csv")
d = a.merge(muestra[["id_ciego", "text"]], on="id_ciego", how="inner")
log(f"casos con texto recuperado: {len(d)} de {len(a)}")

with open(D / "fase9_final/modelo_final.pkl", "rb") as f:
    M = pickle.load(f)
vec, clf = M["deteccion"]["vectorizador"], M["deteccion"]["clasificador"]
d["pred"] = (clf.decision_function(vec.transform(d.text)) >= 0).astype(int)

d = d.merge(bdf, on="id_ciego", how="left")
d["juicio_a"] = d.es_evento_adverso

# --- 4. construir las tres referencias ---------------------------------------
resultados = {}

# R1: consenso doble (la original, como control de reproduccion)
doble = d[d.juicio_b.notna() & (d.juicio_b != "")]
conc = doble[(doble.juicio_a == doble.juicio_b)
             & doble.juicio_a.isin(["SI", "NO"])].copy()
conc["ref"] = (conc.juicio_a == "SI").astype(int)
resultados["R1_consenso_doble"] = evaluar(
    "R1 · consenso doble (codebook v2) — la referencia original", conc)

# R2: mejor juicio disponible
#   - donde hay dos anotadores: solo el consenso (desacuerdos FUERA, declarados)
#   - donde solo esta A (piloto v1): su veredicto
solo_a = d[d.juicio_b.isna() | (d.juicio_b == "")]
solo_a_ok = solo_a[solo_a.juicio_a.isin(["SI", "NO"])].copy()
solo_a_ok["ref"] = (solo_a_ok.juicio_a == "SI").astype(int)
mejor = pd.concat([conc, solo_a_ok], ignore_index=True)
n_desac = int((doble.juicio_a != doble.juicio_b).sum())
resultados["R2_mejor_juicio"] = evaluar(
    "R2 · mejor juicio disponible (consenso + solo-A) — ANALISIS AMPLIADO",
    mejor)
resultados["R2_mejor_juicio"]["composicion"] = {
    "consenso_doble": int(len(conc)),
    "solo_A_piloto_v1": int((solo_a_ok.protocolo == "piloto_v1").sum()),
    "solo_A_codebook_v2": int((solo_a_ok.protocolo == "codebook_v2").sum()),
    "desacuerdos_excluidos": n_desac,
    "no_determinables_excluidos": int(
        (d.juicio_a == "NO_DETERMINABLE").sum()),
}

# R3: anotador A completo (cota de robustez)
a_todo = d[d.juicio_a.isin(["SI", "NO"])].copy()
a_todo["ref"] = (a_todo.juicio_a == "SI").astype(int)
resultados["R3_anotador_A_completo"] = evaluar(
    "R3 · anotador A completo (ambos protocolos) — cota de robustez", a_todo)

# subregistro con la referencia ampliada: casos que los codigos declararon
# negativos (estrato DESCARTADO en la muestra) que el experto confirma
if "estrato" in muestra.columns:
    est = muestra[["id_ciego", "estrato"]]
    m2 = mejor.merge(est, on="id_ciego", how="left")
    desc = m2[m2.estrato == "DESCARTADO"]
    if len(desc):
        confirmados = int((desc.ref == 1).sum())
        lo, hi = wilson(confirmados, len(desc))
        resultados["subregistro_ampliado"] = {
            "casos_descartados_por_codigos": int(len(desc)),
            "confirmados_reales_por_experto": confirmados,
            "proporcion": round(confirmados / len(desc), 4),
            "ic95": [lo, hi]}
        log(f"\nSUBREGISTRO (ampliado): {confirmados}/{len(desc)} casos "
            f"declarados negativos por los codigos son reales para el "
            f"experto = {confirmados/len(desc):.1%} IC95 [{lo:.3f}, {hi:.3f}]")

salida = {
    "generado": datetime.now().isoformat(timespec="seconds"),
    "proposito": ("analisis AMPLIADO juntando todo el juicio experto: "
                  "163 veredictos de A (85 piloto v1 + 78 codebook v2) y "
                  "78 de B; tres referencias de rigor decreciente"),
    "nota_metodologica": (
        "R1 es la referencia mas estricta (solo consenso doble bajo el "
        "codebook v2). R2 agrega los casos con un solo anotador usando su "
        "veredicto (piloto v1 incluido) y excluye los 10 desacuerdos A-B "
        "declarandolos zona ambigua. R3 usa a A como unica referencia en "
        "todos sus casos: hereda su sesgo individual y por eso es cota, no "
        "resultado principal. La mezcla de protocolos v1/v2 en R2 y R3 se "
        "declara como limitacion."),
    "resultados": resultados,
}
(OUT / "sistema_vs_experto_AMPLIADO.json").write_text(
    json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
log(f"\n[OK] {OUT / 'sistema_vs_experto_AMPLIADO.json'}")
