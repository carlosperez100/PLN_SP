# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 3 v2 — TIER A CORREGIDO (bug de formato ICD-10)
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
BUG DETECTADO (26-jul-2026):

  El mapeo `eventos_adversos_icd10_v2.csv` guarda los codigos CON punto
  (A04.7, T81.4, Y83.8 — 201 de 223), mientras que MIMIC-IV los almacena
  SIN punto (A047, T814, Y838 — 0 de 6,364,488 registros tienen punto).

  El `JOIN d.icd_code = c.icd_code` del script original solo podia acertar
  con los 22 codigos de 3 caracteres, y de esos coincidian 4.

  Efecto medido:  411 hospitalizaciones detectadas.
  Con el arreglo: 109,714 hospitalizaciones.  Factor 267x.

  El Tier A nunca fallo conceptualmente: fallo por un punto.

SEGUNDO HALLAZGO — no todos los codigos sirven como etiqueta:

  Al arreglar el formato, los codigos que mas aportan resultan ser
  CONDICIONES y no EVENTOS ADVERSOS: N17.9 insuficiencia renal aguda
  (35,884), J18.9 neumonia (9,415), A41.9 sepsis (7,770). Esas pueden ser
  el MOTIVO DE INGRESO, no un dano causado por la atencion, y
  `diagnoses_icd` de MIMIC-IV **no trae bandera de present-on-admission**,
  asi que no hay forma de distinguirlas.

  Por eso el Tier A se parte en dos estratos:

    A1 — SEMANTICA CAUSAL EXPLICITA. Codigos que por definicion imputan el
         dano a la atencion sanitaria:
           T80-T88  complicaciones de la atencion medica y quirurgica
           Y63,Y65  errores en la asistencia / incidentes en la atencion
           Y83,Y84  complicaciones de procedimientos
           W00-W19  caidas
           L89      ulcera por presion
         Medido: 35,618 hospitalizaciones = 6.53% del total.
         Compatible con el ~9% de incidencia de la literatura
         (de Vries et al., 2008) — algo por debajo, que es justamente el
         subregistro documentado de la codificacion administrativa.

    A2 — CONDICIONES. El resto. Se conservan marcadas pero NO deben usarse
         como etiqueta positiva sin verificacion, por el problema de POA.
         Medido: 97,876 hospitalizaciones = 17.94%.

POR QUE ESTO IMPORTA MAS QUE EL ARREGLO DEL REGEX:

  Los codigos ICD-10 los asigna un codificador clinico humano leyendo la
  historia, con criterio propio y de forma independiente del texto de la
  epicrisis. Una etiqueta derivada de A1 NO es circular respecto del texto,
  al contrario que la del Tier B (99% de las etiquetas son subcadena de la
  nota). Es la unica fuente de etiquetas del pipeline que ataca de raiz la
  amenaza de validez principal del OE2.

SALIDAS (en datos_intermedios/fase3_v2/):
  candidatos_tier_a_corregido.csv    detecciones nota x codigo, con estrato
  tier_a_resumen.json                cifras del antes y el despues

USO:
  python fase3_v2_tier_a_corregido.py
=============================================================================
"""
import csv
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

PATH_DISCHARGE = Path(r"T:\MIMIC\note\note\discharge.csv.gz")
PATH_DIAGNOSES = Path(r"T:\MIMIC\mimiciv\hosp\diagnoses_icd.csv.gz")
PATH_MAPPING   = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\eventos_adversos_icd10_v2.csv")
PATH_SALIDAS   = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios\fase3_v2")
PATH_SALIDAS.mkdir(parents=True, exist_ok=True)

# Familias ICD-10 cuya semantica imputa el dano a la atencion sanitaria.
PREFIJOS_CAUSALES = (
    "T80", "T81", "T82", "T83", "T84", "T85", "T86", "T88",   # complicaciones de la atencion
    "Y63", "Y65", "Y83", "Y84",                                # errores e incidentes asistenciales
    "W00", "W01", "W06", "W07", "W08", "W10", "W13", "W18", "W19",  # caidas
    "L89",                                                     # ulcera por presion
)

T0 = time.time()


def log(msg):
    el = timedelta(seconds=int(time.time() - T0))
    print(f"[{datetime.now():%H:%M:%S}] [+{el}] {msg}", flush=True)


def cargar_mapping():
    """codigo_sin_punto -> (naturaleza, evento, severidad, estrato, codigo_original)"""
    mapping = {}
    with open(PATH_MAPPING, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            orig = (row.get("codigo_icd10") or "").strip()
            if not orig:
                continue
            clave = orig.replace(".", "").upper()          # <-- EL ARREGLO
            estrato = "A1" if clave.startswith(PREFIJOS_CAUSALES) else "A2"
            mapping[clave] = (
                row.get("naturaleza_oms") or row.get("categoria_anexo02_essalud", ""),
                row.get("evento_anexo02") or row.get("descripcion_es", ""),
                row.get("severidad_base", "Medio"),
                estrato,
                orig,
            )
    a1 = sum(1 for v in mapping.values() if v[3] == "A1")
    log(f"Mapeo: {len(mapping)} codigos unicos — A1 causal {a1} · A2 condiciones {len(mapping)-a1}")
    return mapping


def indexar(mapping):
    """hadm_id -> lista de claves del mapeo, por coincidencia de PREFIJO."""
    prefijos = tuple(sorted(mapping))
    por_hadm = defaultdict(set)
    hadm_totales = set()
    exacto_viejo = set()
    con_punto = {k for k in (v[4] for v in mapping.values())}
    n = 0
    log("Indexando diagnoses_icd.csv.gz por prefijo ...")
    for ch in pd.read_csv(PATH_DIAGNOSES,
                          usecols=["hadm_id", "icd_code", "icd_version"],
                          chunksize=500000):
        n += len(ch)
        hadm_totales.update(ch["hadm_id"])
        cod = ch["icd_code"].astype(str).str.strip().str.upper()
        # reproduccion del metodo original, para el antes/despues
        exacto_viejo.update(ch.loc[cod.isin(con_punto), "hadm_id"])
        sub = ch[(ch["icd_version"] == 10)]
        cod10 = cod[sub.index]
        for p in prefijos:
            m = cod10.str.startswith(p)
            if m.any():
                for h in sub.loc[m, "hadm_id"]:
                    por_hadm[h].add(p)
    log(f"{n:,} diagnosticos · {len(hadm_totales):,} hospitalizaciones")
    log(f"metodo ORIGINAL (con punto): {len(exacto_viejo):,} hospitalizaciones")
    log(f"metodo CORREGIDO (prefijo) : {len(por_hadm):,} hospitalizaciones")
    return dict(por_hadm), len(hadm_totales), len(exacto_viejo)


def main():
    mapping = cargar_mapping()
    por_hadm, n_hadm, n_viejo = indexar(mapping)

    log("Recorriendo epicrisis (solo columnas de id, sin texto) ...")
    filas = []
    n_notas = 0
    for ch in pd.read_csv(PATH_DISCHARGE,
                          usecols=["note_id", "subject_id", "hadm_id"],
                          chunksize=50000, encoding="utf-8"):
        n_notas += len(ch)
        hit = ch[ch["hadm_id"].isin(por_hadm)]
        for nid, sid, hid in zip(hit["note_id"], hit["subject_id"], hit["hadm_id"]):
            for clave in por_hadm[hid]:
                nat, ev, sev, estrato, orig = mapping[clave]
                filas.append((nid, sid, hid, nat, ev, sev, estrato, orig))

    df = pd.DataFrame(filas, columns=["note_id", "subject_id", "hadm_id",
                                      "naturaleza", "evento", "severidad",
                                      "estrato", "icd_code"])
    salida = PATH_SALIDAS / "candidatos_tier_a_corregido.csv"
    df.to_csv(salida, index=False, encoding="utf-8")

    a1 = df[df["estrato"] == "A1"]
    a2 = df[df["estrato"] == "A2"]

    resumen = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "bug": {
            "descripcion": "el mapeo usa codigos CON punto (A04.7) y MIMIC-IV los guarda SIN punto (A047)",
            "hadm_metodo_original": n_viejo,
            "hadm_metodo_corregido": len(por_hadm),
            "factor": round(len(por_hadm) / max(n_viejo, 1), 1),
        },
        "corpus": {
            "epicrisis_leidas": n_notas,
            "hospitalizaciones_totales": n_hadm,
        },
        "estratos": {
            "A1_causal_explicito": {
                "notas": int(a1["note_id"].nunique()),
                "detecciones": len(a1),
                "naturalezas": int(a1["naturaleza"].nunique()),
                "uso": "APTO como etiqueta: semantica causal, asignado por codificador humano, NO circular respecto del texto",
            },
            "A2_condiciones": {
                "notas": int(a2["note_id"].nunique()),
                "detecciones": len(a2),
                "naturalezas": int(a2["naturaleza"].nunique()),
                "uso": "NO apto como etiqueta positiva sin verificacion: puede ser motivo de ingreso y MIMIC-IV no trae bandera present-on-admission",
            },
        },
        "archivo": str(salida),
    }
    (PATH_SALIDAS / "tier_a_resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 72)
    print("TIER A CORREGIDO — antes y despues")
    print("=" * 72)
    print(f"Hospitalizaciones, metodo original  : {n_viejo:>8,}")
    print(f"Hospitalizaciones, metodo corregido : {len(por_hadm):>8,}"
          f"   ({resumen['bug']['factor']}x)")
    print("-" * 72)
    print(f"A1 causal explicito : {a1['note_id'].nunique():>7,} notas  "
          f"({len(a1):,} detecciones, {a1['naturaleza'].nunique()} naturalezas)")
    print(f"A2 condiciones      : {a2['note_id'].nunique():>7,} notas  "
          f"({len(a2):,} detecciones, {a2['naturaleza'].nunique()} naturalezas)")
    print("-" * 72)
    print(f"Total {timedelta(seconds=int(time.time() - T0))} -> {salida}")
    print("=" * 72)
    if len(a1):
        print("\nA1 — top naturalezas:")
        print(a1.groupby("naturaleza")["note_id"].nunique()
                .sort_values(ascending=False).head(10).to_string())


if __name__ == "__main__":
    main()
