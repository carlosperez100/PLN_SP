# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 3 v2 — CORPUS COMPLETO + ABLACION DE VENTANA DE PATRON
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
Corrige dos defectos de `fase3_corpus_expansion.py` detectados el 26-jul-2026:

  (1) MUESTREO NO DECLARADO
      El original examinaba `ORDER BY RANDOM() LIMIT 30000` (9.04% del corpus)
      en Tier B y `LIMIT 50000` registros en Tier A. Aqui se procesan las
      331,793 epicrisis completas, sin tope.

  (2) BUG DE ALCANCE DEL REGEX
      El original compila con re.DOTALL, de modo que un `.*` atraviesa la
      epicrisis entera (p. ej. "blood glucose" en la pagina 1 e "insulin" en
      la pagina 5 disparan hipoglicemia_insulina). Resultado: tasa de
      deteccion 48.8%, frente al ~9% de incidencia que reporta la literatura
      (de Vries et al., 2008).

Se ejecutan DOS variantes sobre el MISMO corpus, en una sola pasada:

  LAXO     — identico al original: re.DOTALL activo, `.*` sin acotar.
  ACOTADO  — sin re.DOTALL y cada `.*` limitado a `.{0,100}` (ventana de
             100 caracteres). El patron ya no cruza parrafos.

La comparacion entre ambas es el experimento de ablacion reportable:
"sensibilidad de la deteccion a la ventana del patron".

SALIDAS (en datos_intermedios/fase3_v2/):
  candidatos_laxo.csv        detecciones con regex sin acotar
  candidatos_acotado.csv     detecciones con ventana de 100 caracteres
  comparacion.json           metricas de ambas variantes, lado a lado
  por_patron.csv             aporte de cada patron en cada variante
  progreso.json              checkpoint (permite reanudar tras un corte)

USO:
  python fase3_v2_corpus_completo.py
=============================================================================
"""
import re
import csv
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

# Los 35 patrones y el NegEx se toman del script original para que haya UNA
# sola fuente de verdad. No se importa el modulo (arrastraria duckdb, que este
# script no necesita): se extraen las dos asignaciones con ast y se evaluan.
import ast

_ORIGINAL = Path(__file__).parent / "fase3_corpus_expansion.py"


def _extraer_del_original(*nombres):
    arbol = ast.parse(_ORIGINAL.read_text(encoding="utf-8"))
    quiero = set(nombres)
    ns = {"re": re}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign):
            for t in nodo.targets:
                if isinstance(t, ast.Name) and t.id in quiero:
                    exec(compile(ast.Module([nodo], []), "<original>", "exec"),
                         ns)
    faltan = quiero - set(ns)
    if faltan:
        raise RuntimeError(f"No se hallaron en el original: {faltan}")
    return [ns[n] for n in nombres]


TIER_B_PATRONES, NEGEX_PREFIJOS = _extraer_del_original(
    "TIER_B_PATRONES", "NEGEX_PREFIJOS")

# =============================================================================
# CONFIGURACION
# =============================================================================
PATH_DISCHARGE = Path(r"T:\MIMIC\note\note\discharge.csv.gz")
PATH_DIAGNOSES = Path(r"T:\MIMIC\mimiciv\hosp\diagnoses_icd.csv.gz")
PATH_MAPPING   = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\eventos_adversos_icd10_v2.csv")
PATH_SALIDAS   = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios\fase3_v2")

CHUNK          = 20000   # notas por bloque; ~200 MB de RAM por bloque
VENTANA_NEGEX  = 60      # caracteres antes del match para buscar negacion
VENTANA_PATRON = 100     # caracteres maximos que puede saltar un `.*` acotado
MIN_LEN_TEXTO  = 100     # mismo filtro que el original

PATH_SALIDAS.mkdir(parents=True, exist_ok=True)

T0 = time.time()


def log(msg, nivel="INFO"):
    el = timedelta(seconds=int(time.time() - T0))
    print(f"[{datetime.now():%H:%M:%S}] [+{el}] [{nivel:<5}] {msg}", flush=True)


# =============================================================================
# COMPILACION DE LAS DOS VARIANTES
# =============================================================================
def acotar(patron: str, n: int = VENTANA_PATRON) -> str:
    """Sustituye cada comodin `.*` por una ventana de n caracteres."""
    return patron.replace(".*", ".{0," + str(n) + "}")


def compilar_variantes():
    """
    Devuelve {variante: {clave: (naturaleza, evento, severidad, regex_compilado)}}

    LAXO    = re.IGNORECASE | re.DOTALL, patron intacto   (reproduce el original)
    ACOTADO = re.IGNORECASE            , `.*` -> `.{0,100}`
    """
    laxo, acotado = {}, {}
    for clave, (nat, ev, sev, patron) in TIER_B_PATRONES.items():
        laxo[clave] = (nat, ev, sev,
                       re.compile(patron, re.IGNORECASE | re.DOTALL))
        acotado[clave] = (nat, ev, sev,
                          re.compile(acotar(patron), re.IGNORECASE))
    return {"laxo": laxo, "acotado": acotado}


# =============================================================================
# TIER A — sin LIMIT
# =============================================================================
def cargar_mapping_tier_a() -> dict:
    mapping = {}
    with open(PATH_MAPPING, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("codigo_icd10") or "").strip()
            if code:
                mapping[code] = {
                    "naturaleza": row.get("naturaleza_oms")
                                  or row.get("categoria_anexo02_essalud", ""),
                    "evento": row.get("evento_anexo02")
                              or row.get("descripcion_es", ""),
                    "severidad": row.get("severidad_base", "Medio"),
                }
    log(f"Tier A: {len(mapping)} codigos ICD-10 en el mapeo")
    return mapping


def indexar_diagnosticos(mapping: dict) -> dict:
    """hadm_id -> lista de codigos ICD-10 de evento adverso. SIN tope."""
    log("Indexando diagnoses_icd.csv.gz (sin LIMIT) ...")
    codigos = set(mapping)
    por_hadm = defaultdict(list)
    n = 0
    for ch in pd.read_csv(PATH_DIAGNOSES, usecols=["hadm_id", "icd_code"],
                          chunksize=500000):
        n += len(ch)
        hit = ch[ch["icd_code"].isin(codigos)]
        for h, c in zip(hit["hadm_id"], hit["icd_code"]):
            por_hadm[h].append(c)
    log(f"Tier A: {n:,} diagnosticos leidos -> "
        f"{len(por_hadm):,} hospitalizaciones con codigo de evento adverso")
    return dict(por_hadm)


# =============================================================================
# NEGEX
# =============================================================================
def esta_negado(texto: str, regex, ventana: int = VENTANA_NEGEX) -> bool:
    for m in regex.finditer(texto):
        ini = max(0, m.start() - ventana)
        if NEGEX_PREFIJOS.search(texto[ini:m.start()]):
            return True
    return False


# =============================================================================
# PASADA PRINCIPAL — una sola lectura del .gz para ambas variantes
# =============================================================================
def procesar():
    mapping = cargar_mapping_tier_a()
    dx_por_hadm = indexar_diagnosticos(mapping)
    variantes = compilar_variantes()

    detecciones = {"laxo": [], "acotado": []}
    tier_a_filas = []
    notas_vistas = 0
    notas_validas = 0
    negados = {"laxo": 0, "acotado": 0}
    por_patron = {"laxo": defaultdict(int), "acotado": defaultdict(int)}

    log(f"Recorriendo las 331,793 epicrisis en bloques de {CHUNK:,} ...")
    log("(una sola lectura del .gz alimenta las DOS variantes)")

    for i, ch in enumerate(pd.read_csv(
            PATH_DISCHARGE,
            usecols=["note_id", "subject_id", "hadm_id", "text"],
            chunksize=CHUNK, encoding="utf-8")):

        notas_vistas += len(ch)
        ch = ch[ch["text"].notna()]
        ch = ch[ch["text"].str.len() > MIN_LEN_TEXTO]
        notas_validas += len(ch)

        # ---------- Tier A (sin tope) ----------
        m_a = ch["hadm_id"].isin(dx_por_hadm)
        for nid, sid, hid in zip(ch.loc[m_a, "note_id"],
                                 ch.loc[m_a, "subject_id"],
                                 ch.loc[m_a, "hadm_id"]):
            for code in dx_por_hadm[hid]:
                info = mapping[code]
                tier_a_filas.append((nid, sid, hid, info["naturaleza"],
                                     info["evento"], info["severidad"],
                                     "A", code))

        # ---------- Tier B, ambas variantes ----------
        for nombre, patrones in variantes.items():
            for clave, (nat, ev, sev, rx) in patrones.items():
                mask = ch["text"].str.contains(rx, regex=True, na=False)
                if not mask.any():
                    continue
                sub = ch[mask]
                for nid, sid, hid, txt in zip(sub["note_id"], sub["subject_id"],
                                              sub["hadm_id"], sub["text"]):
                    if esta_negado(txt, rx):
                        negados[nombre] += 1
                        continue
                    detecciones[nombre].append(
                        (nid, sid, hid, nat, ev, sev, "B", clave))
                    por_patron[nombre][clave] += 1

        if i % 2 == 0:
            frac = notas_vistas / 331793
            eta = (time.time() - T0) / max(frac, 1e-9) * (1 - frac)
            log(f"bloque {i:>3} | {notas_vistas:>7,}/331,793 ({frac:6.1%}) | "
                f"laxo {len(detecciones['laxo']):>7,} | "
                f"acotado {len(detecciones['acotado']):>7,} | "
                f"ETA {timedelta(seconds=int(eta))}")
            (PATH_SALIDAS / "progreso.json").write_text(json.dumps({
                "notas_vistas": notas_vistas,
                "laxo": len(detecciones["laxo"]),
                "acotado": len(detecciones["acotado"]),
                "segundos": round(time.time() - T0, 1),
            }, indent=2), encoding="utf-8")

    return (detecciones, tier_a_filas, notas_vistas, notas_validas,
            negados, por_patron)


# =============================================================================
# SALIDAS
# =============================================================================
COLS = ["note_id", "subject_id", "hadm_id", "naturaleza", "evento",
        "severidad", "tier", "patron_match"]


def main():
    (detecciones, tier_a_filas, notas_vistas, notas_validas,
     negados, por_patron) = procesar()

    df_a = pd.DataFrame(tier_a_filas, columns=COLS)
    log(f"Tier A: {len(df_a):,} detecciones sobre "
        f"{df_a['note_id'].nunique():,} notas unicas")

    resumen = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "corpus": {
            "epicrisis_leidas": notas_vistas,
            "epicrisis_validas": notas_validas,
            "muestreo": "NINGUNO — corpus completo (el original usaba LIMIT 30000)",
        },
        "tier_a": {
            "detecciones": len(df_a),
            "notas_unicas": int(df_a["note_id"].nunique()),
            "aporte_pct_del_corpus": round(
                100 * df_a["note_id"].nunique() / max(notas_validas, 1), 3),
        },
        "variantes": {},
    }

    for nombre in ("laxo", "acotado"):
        df_b = pd.DataFrame(detecciones[nombre], columns=COLS)
        df = pd.concat([df_a, df_b], ignore_index=True)
        n_unicas = int(df["note_id"].nunique())
        tasa = 100 * n_unicas / max(notas_validas, 1)

        salida = PATH_SALIDAS / f"candidatos_{nombre}.csv"
        df.to_csv(salida, index=False, encoding="utf-8")

        resumen["variantes"][nombre] = {
            "detecciones_tier_b": len(df_b),
            "negados_descartados": negados[nombre],
            "notas_unicas_totales": n_unicas,
            "tasa_deteccion_pct": round(tasa, 2),
            "razon_vs_literatura_9pct": round(tasa / 9.0, 2),
            "naturalezas_cubiertas": int(df["naturaleza"].nunique()),
            "archivo": str(salida),
        }
        log(f"{nombre.upper():<8} -> {n_unicas:,} notas unicas | "
            f"tasa {tasa:.2f}% | {len(df_b):,} detecciones Tier B")

    lax = resumen["variantes"]["laxo"]["notas_unicas_totales"]
    aco = resumen["variantes"]["acotado"]["notas_unicas_totales"]
    resumen["ablacion"] = {
        "reduccion_notas": lax - aco,
        "reduccion_pct": round(100 * (lax - aco) / max(lax, 1), 2),
        "interpretacion": (
            "Cuanto mayor la reduccion, mas dependia la deteccion de que el "
            "comodin `.*` cruzara la epicrisis completa. La variante ACOTADA "
            "exige que los terminos del patron esten a menos de "
            f"{VENTANA_PATRON} caracteres."),
    }

    (PATH_SALIDAS / "comparacion.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    filas = []
    for clave in TIER_B_PATRONES:
        filas.append({
            "patron": clave,
            "naturaleza": TIER_B_PATRONES[clave][0],
            "laxo": por_patron["laxo"].get(clave, 0),
            "acotado": por_patron["acotado"].get(clave, 0),
        })
    dfp = pd.DataFrame(filas)
    dfp["reduccion_pct"] = (100 * (dfp["laxo"] - dfp["acotado"])
                            / dfp["laxo"].replace(0, pd.NA)).round(1)
    dfp = dfp.sort_values("laxo", ascending=False)
    dfp.to_csv(PATH_SALIDAS / "por_patron.csv", index=False, encoding="utf-8")

    print("\n" + "=" * 74)
    print("FASE 3 v2 — ABLACION DE VENTANA DE PATRON (corpus completo)")
    print("=" * 74)
    print(f"Epicrisis procesadas : {notas_validas:,} "
          f"(el original examinaba 30,000 = 9.04%)")
    print(f"Tier A               : {resumen['tier_a']['notas_unicas']:,} notas "
          f"({resumen['tier_a']['aporte_pct_del_corpus']}% del corpus)")
    print("-" * 74)
    for nombre in ("laxo", "acotado"):
        v = resumen["variantes"][nombre]
        print(f"{nombre.upper():<8} notas={v['notas_unicas_totales']:>8,}  "
              f"tasa={v['tasa_deteccion_pct']:>6.2f}%  "
              f"({v['razon_vs_literatura_9pct']}x la literatura)  "
              f"naturalezas={v['naturalezas_cubiertas']}")
    print("-" * 74)
    print(f"Reduccion al acotar  : {resumen['ablacion']['reduccion_notas']:,} "
          f"notas ({resumen['ablacion']['reduccion_pct']}%)")
    print(f"Total                : {timedelta(seconds=int(time.time() - T0))}")
    print(f"Salidas en           : {PATH_SALIDAS}")
    print("=" * 74)
    print("\nTop 10 patrones por reduccion absoluta:")
    print(dfp.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
