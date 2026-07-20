"""
=============================================================================
  FASE 3 — EXPANSIÓN DEL CORPUS
  Detección de 188 eventos adversos (Tiers A+B+C) en MIMIC-IV
  Meta: 300+ notas etiquetadas, cobertura de 12 naturalezas
=============================================================================
Autor: Carlos Pérez Pérez — MIA-303 UNI 2026

SALIDAS:
  corpus_fase3_candidatos.csv   → notas con al menos 1 evento detectado
  corpus_fase3_muestra300.csv   → muestra estratificada 300+ notas
  corpus_fase3_estadisticas.csv → resumen por naturaleza y tier
  corpus_fase3_anotacion.csv    → plantilla para anotación experta

USO:
  python fase3_corpus_expansion.py
=============================================================================
"""

import re
import gzip
import json
import csv
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import duckdb
import pandas as pd

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
PATH_DISCHARGE = Path(r"C:\MIMIC\note\note\discharge.csv.gz")
PATH_DIAGNOSES = Path(r"C:\MIMIC\mimiciv\hosp\diagnoses_icd.csv.gz")
PATH_ADMISSIONS= Path(r"C:\MIMIC\mimiciv\hosp\admissions.csv.gz")
PATH_PHARMACY  = Path(r"C:\MIMIC\mimiciv\hosp\pharmacy.csv.gz")
PATH_MAPPING   = Path(r"C:\MIMIC\tesis\04_pipeline_codigo\eventos_adversos_icd10_v2.csv")
PATH_SALIDAS   = Path(r"C:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")

SEMILLA        = 42
MUESTRA_TARGET = 350   # notas para la muestra estratificada (>300)
NOTAS_PREVIEW  = 5     # notas a mostrar en consola para verificación

random.seed(SEMILLA)
PATH_SALIDAS.mkdir(parents=True, exist_ok=True)

def log(msg, nivel="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{nivel:<5}] {msg}")

# =============================================================================
# TIER B — PATRONES DE TEXTO (75 eventos)
# Mapeo: patrón regex → (naturaleza, evento_gemses, nivel_severidad)
# =============================================================================
TIER_B_PATRONES = {
    # ── INFECCIÓN ──────────────────────────────────────────────────────────
    "infeccion_cateter_central": (
        "Infección", "Infección asociada a catéter venoso central", "Alto",
        r"central\s+(?:line|venous\s+catheter|line[-\s]associated).*infect|"
        r"CLABSI|central\s+line\s+infection|catheter[-\s]related\s+bloodstream",
    ),
    "infeccion_sitio_qx": (
        "Infección", "Infección del sitio operatorio", "Alto",
        r"surgical\s+site\s+infect|wound\s+infect|SSI\b|"
        r"incision.*infect|operative\s+site.*infect",
    ),
    "neumonia_ventilador": (
        "Infección", "Neumonía asociada a ventilador mecánico", "Muy alto",
        r"ventilator[-\s]associated\s+pneumonia|VAP\b|"
        r"pneumonia.*(?:mechanical\s+ventilation|intubat)",
    ),
    "bacteriemia": (
        "Infección", "Bacteriemia/Septicemia nosocomial", "Muy alto",
        r"bacteremia|septicemia|bloodstream\s+infect|positive\s+blood\s+cultur",
    ),
    "itu_cateter": (
        "Infección", "Infección urinaria asociada a catéter", "Medio",
        r"catheter[-\s]associated\s+(?:urinary|UTI)|CAUTI\b|"
        r"urinary\s+catheter.*infect",
    ),
    "infeccion_clostridium": (
        "Infección", "Infección por Clostridioides difficile", "Alto",
        r"C\.?\s*difficile|Clostridium\s+difficile|CDI\b|C\.\s*diff\b",
    ),
    "infeccion_mrsa": (
        "Infección", "Infección por MRSA", "Muy alto",
        r"MRSA\b|methicillin[-\s]resistant\s+Staphylococcus\s+aureus",
    ),
    # ── MEDICACIÓN ─────────────────────────────────────────────────────────
    "reaccion_adversa_medicamento": (
        "Medicación", "Reacción adversa a medicamento (RAM)", "Alto",
        r"adverse\s+(?:drug\s+)?reaction|drug\s+reaction|ADR\b|"
        r"adverse\s+effect.*(?:medication|drug|antibiotic)",
    ),
    "error_medicacion_dosis": (
        "Medicación", "Error de medicación — dosis incorrecta", "Alto",
        r"(?:wrong|incorrect|erroneous)\s+dose|dose\s+error|"
        r"overdose\s+(?:of|due\s+to)|medication\s+error",
    ),
    "sobredosis_inadvertida": (
        "Medicación", "Sobredosis inadvertida", "Muy alto",
        r"accidental\s+overdose|inadvertent\s+(?:overdose|overdosing)|"
        r"unintentional\s+(?:overdose|poisoning)",
    ),
    "omision_medicamento": (
        "Medicación", "Omisión de medicamento prescrito", "Medio",
        r"missed\s+(?:dose|medication)|medication\s+(?:not\s+given|withheld)|"
        r"omitted\s+(?:dose|medication)",
    ),
    "interaccion_medicamentosa": (
        "Medicación", "Interacción medicamentosa significativa", "Alto",
        r"drug[-\s]drug\s+interaction|drug\s+interaction|"
        r"contraindicated.*(?:combination|medication|drug)",
    ),
    "hipoglicemia_insulina": (
        "Medicación", "Hipoglicemia por insulina", "Alto",
        r"hypoglycemia.*insulin|insulin[-\s]induced\s+hypoglycemia|"
        r"blood\s+glucose.*low.*insulin",
    ),
    "anticoagulacion_excesiva": (
        "Medicación", "Anticoagulación excesiva / sangrado por anticoagulante", "Muy alto",
        r"over[-\s]anticoagulat|supratherapeutic.*(?:INR|anticoagulat)|"
        r"anticoagulant.*bleed|warfarin.*hemorrhage|heparin.*bleed",
    ),
    # ── PROCEDIMIENTO ──────────────────────────────────────────────────────
    "complicacion_anestesia": (
        "Procedimiento", "Complicación anestésica", "Alto",
        r"anesthesia.*complicat|anesthetic\s+complicat|"
        r"intraoperative.*complicat.*anesth",
    ),
    "perforacion_visceral": (
        "Procedimiento", "Perforación visceral durante procedimiento", "Muy alto",
        r"visceral\s+perforation|bowel\s+perforation|colonic\s+perforation|"
        r"perforation.*(?:during|intraoperative|complication)",
    ),
    "hemorragia_postoperatoria": (
        "Procedimiento", "Hemorragia post-operatoria", "Alto",
        r"postoperative\s+bleed|post[-\s]?op.*hemorrhage|"
        r"surgical\s+(?:bleed|hemorrhage)|intraoperative\s+blood\s+loss",
    ),
    "fistula_postoperatoria": (
        "Procedimiento", "Fístula post-operatoria", "Alto",
        r"anastomotic\s+(?:leak|fistula)|post[-\s]?operative\s+fistula|"
        r"fistula.*(?:after\s+surgery|postoperative)",
    ),
    "reintervencion_qx": (
        "Procedimiento", "Reintervención quirúrgica no programada", "Alto",
        r"return\s+to\s+(?:OR|operating\s+room)|re[-\s]operation|"
        r"unplanned\s+(?:reoperation|surgical\s+return|return\s+to\s+OR)",
    ),
    "cirugia_sitio_incorrecto": (
        "Procedimiento", "Cirugía en sitio incorrecto", "Muy alto",
        r"wrong[-\s]site\s+surgery|wrong\s+(?:site|side|patient|procedure)",
    ),
    "lesion_nerviosa_qx": (
        "Procedimiento", "Lesión nerviosa quirúrgica", "Alto",
        r"nerve\s+(?:injury|damage|lesion).*(?:during|intraoperative|surgical)|"
        r"iatrogenic\s+nerve\s+(?:injury|damage)",
    ),
    # ── CUIDADO DEL PACIENTE ───────────────────────────────────────────────
    "ulcera_presion": (
        "Cuidado del paciente", "Úlcera por presión / escara", "Alto",
        r"pressure\s+(?:ulcer|injury|sore|wound)|decubitus\s+ulcer|"
        r"stage\s+(?:II|III|IV|2|3|4)\s+pressure|bedsore",
    ),
    "caida_paciente": (
        "Cuidado del paciente", "Caída del paciente", "Alto",
        r"patient\s+fall|fell\s+(?:from|out\s+of)|fall\s+from\s+(?:bed|chair|stretcher)|"
        r"accidental\s+fall.*patient",
    ),
    "extubacion_no_planificada": (
        "Cuidado del paciente", "Extubación no planificada", "Muy alto",
        r"unplanned\s+extubat|accidental\s+extubat|self[-\s]extubat|"
        r"inadvertent\s+extubat",
    ),
    "retiro_accidental_sondas": (
        "Cuidado del paciente", "Retiro accidental de sondas/tubos", "Alto",
        r"accidental\s+(?:removal|dislodgement|displacement)\s+of\s+"
        r"(?:tube|catheter|line|drain|NGT|nasogastric)|"
        r"self[-\s]removal.*(?:tube|catheter)",
    ),
    "quemadura_paciente": (
        "Cuidado del paciente", "Quemadura del paciente en hospitalización", "Alto",
        r"burn.*(?:patient|during\s+hospitalization|hospital)|"
        r"thermal\s+injury.*patient",
    ),
    "contencion_inadecuada": (
        "Cuidado del paciente", "Contención física inadecuada", "Medio",
        r"restraint.*(?:injury|complicat|incorrect)|"
        r"improper\s+restraint|physical\s+restraint.*adverse",
    ),
    # ── SANGRE / HEMODERIVADOS ─────────────────────────────────────────────
    "reaccion_transfusional": (
        "Sangre/Hemoderivados", "Reacción transfusional aguda", "Muy alto",
        r"transfusion\s+(?:reaction|complicat)|"
        r"acute\s+hemolytic\s+transfusion|TRALI\b|TACO\b|"
        r"allergic\s+transfusion\s+reaction",
    ),
    "transfusion_grupo_incorrecto": (
        "Sangre/Hemoderivados", "Transfusión de sangre grupo incorrecto", "Muy alto",
        r"wrong\s+blood\s+type|ABO\s+incompatib|incompatible\s+(?:blood|transfusion)|"
        r"blood\s+group\s+mismatch",
    ),
    "infeccion_transfusional": (
        "Sangre/Hemoderivados", "Infección transmitida por transfusión", "Muy alto",
        r"transfusion[-\s]transmitted\s+(?:infect|disease)|"
        r"blood[-\s]borne\s+(?:infect|pathogen).*transfus",
    ),
    # ── DIAGNÓSTICO ────────────────────────────────────────────────────────
    "error_diagnostico": (
        "Diagnóstico", "Error en el diagnóstico", "Alto",
        r"diagnostic\s+error|misdiagnos|missed\s+diagnosis|"
        r"incorrect\s+diagnosis|wrong\s+diagnosis|delayed\s+diagnosis",
    ),
    "retraso_diagnostico": (
        "Diagnóstico", "Retraso en el diagnóstico", "Alto",
        r"delay(?:ed)?\s+(?:in\s+)?diagnosis|diagnosis\s+delay|"
        r"late\s+diagnosis|delayed\s+recognition",
    ),
    # ── HISTORIA CLÍNICA ───────────────────────────────────────────────────
    "documentacion_incompleta": (
        "Historia Clínica", "Documentación clínica incompleta/incorrecta", "Medio",
        r"incomplete\s+(?:documentation|record|chart|note)|"
        r"missing\s+(?:documentation|information\s+in\s+chart)|"
        r"documentation\s+(?:error|deficien)",
    ),
    # ── DISPOSITIVO MÉDICO ─────────────────────────────────────────────────
    "falla_dispositivo": (
        "Dispositivo médico", "Falla o mal funcionamiento de dispositivo", "Alto",
        r"device\s+(?:failure|malfunction|defect)|equipment\s+(?:failure|malfunction)|"
        r"pump\s+(?:failure|malfunction)|monitor.*(?:failure|malfunct)",
    ),
    "infeccion_protesis": (
        "Dispositivo médico", "Infección de prótesis/implante", "Muy alto",
        r"prosthetic\s+(?:joint\s+)?infect|implant\s+infect|"
        r"periprosthetic\s+infect|infected\s+(?:prosthesis|implant)",
    ),
}

# =============================================================================
# PASO 1 — CARGAR MAPEO ICD-10 (TIER A)
# =============================================================================
def cargar_mapping_tier_a(path: Path) -> dict:
    """Carga el CSV de mapeo ICD-10 y retorna dict {icd10_code: evento_info}"""
    mapping = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get('codigo_icd10', '').strip()
            if code:
                mapping[code] = {
                    'naturaleza': row.get('naturaleza_oms', row.get('categoria_anexo02_essalud', '')),
                    'evento': row.get('evento_anexo02', row.get('descripcion_es', '')),
                    'severidad': row.get('severidad_base', 'Medio'),
                    'tier': 'A',
                }
    log(f"Mapeo Tier A cargado: {len(mapping)} códigos ICD-10")
    return mapping

# =============================================================================
# PASO 2 — CONSTRUIR BASE EN DUCKDB
# =============================================================================
def construir_base_duckdb(con) -> None:
    """Crea tablas en DuckDB desde los CSV.gz de MIMIC-IV"""
    log("Cargando discharge notes en DuckDB (puede tardar 1-2 min)...")
    con.execute(f"""
        CREATE OR REPLACE TABLE notas AS
        SELECT note_id, subject_id, hadm_id, charttime, text
        FROM read_csv_auto('{PATH_DISCHARGE}', compression='gzip',
                           ignore_errors=true)
        WHERE note_id IS NOT NULL AND text IS NOT NULL AND length(text) > 100
    """)
    n_notas = con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
    log(f"Notas cargadas: {n_notas:,}")

    log("Cargando diagnoses_icd...")
    con.execute(f"""
        CREATE OR REPLACE TABLE diagnoses AS
        SELECT subject_id, hadm_id, icd_code, icd_version
        FROM read_csv_auto('{PATH_DIAGNOSES}', compression='gzip',
                           ignore_errors=true)
    """)
    n_dx = con.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0]
    log(f"Diagnósticos cargados: {n_dx:,}")

    log("Cargando admissions...")
    con.execute(f"""
        CREATE OR REPLACE TABLE admissions AS
        SELECT subject_id, hadm_id, admittime, dischtime,
               hospital_expire_flag, discharge_location
        FROM read_csv_auto('{PATH_ADMISSIONS}', compression='gzip',
                           ignore_errors=true)
    """)
    log("Tablas DuckDB listas.")

# =============================================================================
# PASO 3 — DETECCIÓN TIER A (ICD-10)
# =============================================================================
def detectar_tier_a(con, mapping_tier_a: dict) -> pd.DataFrame:
    """
    Une notas con diagnoses, filtra los hadm_id que tienen ICD-10
    de eventos adversos, retorna DataFrame con nota + evento detectado.
    """
    log("Detectando Tier A (ICD-10 matching)...")
    codigos = list(mapping_tier_a.keys())
    # DuckDB: filtrar diagnoses por códigos conocidos
    # Construimos tabla temporal de códigos
    rows_codigo = [(c,) for c in codigos]
    con.execute("CREATE OR REPLACE TABLE codigos_tier_a (icd_code VARCHAR)")
    con.executemany("INSERT INTO codigos_tier_a VALUES (?)", rows_codigo)

    df_tier_a = con.execute("""
        SELECT DISTINCT
            n.note_id,
            n.subject_id,
            n.hadm_id,
            n.text,
            d.icd_code
        FROM notas n
        JOIN diagnoses d ON n.hadm_id = d.hadm_id
        JOIN codigos_tier_a c ON d.icd_code = c.icd_code
        WHERE length(n.text) > 200
        LIMIT 50000
    """).df()

    # Agregar metadata del evento
    df_tier_a['naturaleza']  = df_tier_a['icd_code'].map(lambda x: mapping_tier_a.get(x, {}).get('naturaleza', ''))
    df_tier_a['evento']      = df_tier_a['icd_code'].map(lambda x: mapping_tier_a.get(x, {}).get('evento', ''))
    df_tier_a['severidad']   = df_tier_a['icd_code'].map(lambda x: mapping_tier_a.get(x, {}).get('severidad', 'Medio'))
    df_tier_a['tier']        = 'A'
    df_tier_a['patron_match']= df_tier_a['icd_code']

    log(f"Tier A: {len(df_tier_a):,} registros (nota × evento)")
    return df_tier_a

# =============================================================================
# PASO 4 — DETECCIÓN TIER B (PATRONES DE TEXTO)
# =============================================================================
def detectar_tier_b(con) -> pd.DataFrame:
    """
    Aplica patrones regex sobre texto de notas.
    Carga muestra de notas y aplica todos los patrones.
    """
    log("Cargando muestra de notas para Tier B (texto libre)...")
    df_notas = con.execute("""
        SELECT note_id, subject_id, hadm_id, text
        FROM notas
        ORDER BY RANDOM()
        LIMIT 30000
    """).df()

    log(f"Aplicando {len(TIER_B_PATRONES)} patrones Tier B sobre {len(df_notas):,} notas...")
    resultados = []
    for key, (naturaleza, evento, severidad, patron) in TIER_B_PATRONES.items():
        regex = re.compile(patron, re.IGNORECASE | re.DOTALL)
        mask = df_notas['text'].str.contains(regex, regex=True, na=False)
        matches = df_notas[mask].copy()
        if len(matches) > 0:
            matches['naturaleza']   = naturaleza
            matches['evento']       = evento
            matches['severidad']    = severidad
            matches['tier']         = 'B'
            matches['patron_match'] = key
            matches['icd_code']     = ''
            resultados.append(matches)
            log(f"  {key:<40s}: {len(matches):>5,} notas")

    if resultados:
        df_tier_b = pd.concat(resultados, ignore_index=True)
    else:
        df_tier_b = pd.DataFrame()

    log(f"Tier B total: {len(df_tier_b):,} registros (nota × evento)")
    return df_tier_b

# =============================================================================
# PASO 5 — NEGACIÓN SIMPLE (NegEx lite)
# =============================================================================
NEGEX_PREFIJOS = re.compile(
    r"(?:no|without|deny|denies|denied|absent|negative\s+for|"
    r"not\s+consistent\s+with|ruled?\s+out|r/o|unremarkable\s+for)\s+",
    re.IGNORECASE
)

def filtrar_negaciones(df: pd.DataFrame, ventana_chars: int = 60) -> pd.DataFrame:
    """
    Descarta filas donde el patrón aparece precedido de expresión negadora
    en una ventana de <ventana_chars> caracteres.
    Heurística simple (NegEx lite) para reducir falsos positivos.
    """
    if df.empty or 'patron_match' not in df.columns:
        return df

    def esta_negado(row):
        if row['tier'] != 'B':
            return False
        patron_info = TIER_B_PATRONES.get(row['patron_match'])
        if not patron_info:
            return False
        patron_re = re.compile(patron_info[3], re.IGNORECASE | re.DOTALL)
        texto = row['text']
        for m in patron_re.finditer(texto):
            inicio = max(0, m.start() - ventana_chars)
            contexto = texto[inicio:m.start()]
            if NEGEX_PREFIJOS.search(contexto):
                return True
        return False

    mask_negado = df.apply(esta_negado, axis=1)
    n_antes = len(df)
    df = df[~mask_negado].copy()
    log(f"NegEx: eliminados {mask_negado.sum():,} registros negados "
        f"({n_antes:,} -> {len(df):,})")
    return df

# =============================================================================
# PASO 6 — MUESTREO ESTRATIFICADO
# =============================================================================
def muestrear_estratificado(df: pd.DataFrame, n_target: int = 350) -> pd.DataFrame:
    """
    Selecciona notas únicas (1 nota = 1 fila), estratificado por naturaleza.
    Prioriza notas con múltiples eventos detectados.
    """
    # Primero colapsar: una fila por nota con lista de eventos
    df_nota = (df.groupby(['note_id', 'subject_id', 'hadm_id', 'text'])
                 .agg(
                     naturalezas=('naturaleza', lambda x: '|'.join(sorted(set(x)))),
                     eventos=('evento', lambda x: '|'.join(sorted(set(x)))),
                     tiers=('tier', lambda x: '|'.join(sorted(set(x)))),
                     n_eventos=('evento', 'nunique'),
                 ).reset_index())

    n_total = len(df_nota)
    log(f"Notas únicas con al menos 1 evento: {n_total:,}")

    if n_total <= n_target:
        log(f"Menos notas que el target ({n_total} < {n_target}) — tomando todas")
        return df_nota

    # Estratificar por naturaleza principal (primera)
    df_nota['nat_principal'] = df_nota['naturalezas'].str.split('|').str[0]
    naturalezas = df_nota['nat_principal'].value_counts()
    n_nat = len(naturalezas)
    por_nat = max(n_target // n_nat, 5)

    muestras = []
    for nat, grupo in df_nota.groupby('nat_principal'):
        # Priorizar notas con más eventos (más informativas para validación)
        grupo_ordenado = grupo.sort_values('n_eventos', ascending=False)
        k = min(por_nat, len(grupo_ordenado))
        muestras.append(grupo_ordenado.head(k))

    df_muestra = pd.concat(muestras, ignore_index=True)
    # Completar hasta n_target si es necesario
    if len(df_muestra) < n_target:
        ya = set(df_muestra['note_id'])
        resto = df_nota[~df_nota['note_id'].isin(ya)].sample(
            min(n_target - len(df_muestra), len(df_nota) - len(ya)),
            random_state=SEMILLA)
        df_muestra = pd.concat([df_muestra, resto], ignore_index=True)

    log(f"Muestra estratificada: {len(df_muestra):,} notas")
    return df_muestra

# =============================================================================
# PASO 7 — PLANTILLA DE ANOTACIÓN
# =============================================================================
def crear_plantilla_anotacion(df_muestra: pd.DataFrame) -> pd.DataFrame:
    """
    Genera plantilla CSV para anotación experta.
    Columnas: note_id, texto_primeros_500, eventos_detectados,
              tiers, ANOTACION_EXPERTO (vacío), CORRECTO_S_N (vacío), NOTAS_ANOTADOR
    """
    df_anot = df_muestra.copy()
    df_anot['texto_primeros_500'] = df_anot['text'].str[:500]
    df_anot['ANOTACION_EXPERTO'] = ''   # el anotador llena esto
    df_anot['CORRECTO_S_N']      = ''   # S=sí, N=no, P=parcial
    df_anot['NOTAS_ANOTADOR']    = ''

    cols_out = [
        'note_id', 'hadm_id',
        'naturalezas', 'eventos', 'tiers', 'n_eventos',
        'texto_primeros_500',
        'ANOTACION_EXPERTO', 'CORRECTO_S_N', 'NOTAS_ANOTADOR',
    ]
    return df_anot[cols_out]

# =============================================================================
# MAIN
# =============================================================================
def main():
    log("=" * 60)
    log("FASE 3 — EXPANSIÓN DEL CORPUS GEMSES × MIMIC-IV")
    log("=" * 60)

    # Verificar archivos
    for p, lbl in [
        (PATH_DISCHARGE,  "discharge.csv.gz"),
        (PATH_DIAGNOSES,  "diagnoses_icd.csv.gz"),
        (PATH_ADMISSIONS, "admissions.csv.gz"),
        (PATH_MAPPING,    "eventos_adversos_icd10_v2.csv"),
    ]:
        if not p.exists():
            log(f"FALTA: {p}", "ERROR")
            return
        log(f"OK: {lbl} ({p.stat().st_size/1e6:.0f} MB)")

    # Cargar mapeo Tier A
    mapping_tier_a = cargar_mapping_tier_a(PATH_MAPPING)

    # DuckDB en memoria
    con = duckdb.connect()
    construir_base_duckdb(con)

    # Detección
    df_a = detectar_tier_a(con, mapping_tier_a)
    df_b = detectar_tier_b(con)

    # Combinar
    log("Combinando Tier A + Tier B...")
    dfs = [df for df in [df_a, df_b] if not df.empty]
    if not dfs:
        log("Sin eventos detectados — revisa los archivos de datos.", "ERROR")
        return

    cols_comunes = ['note_id', 'subject_id', 'hadm_id', 'text',
                    'naturaleza', 'evento', 'severidad', 'tier', 'patron_match']
    partes = []
    for df in dfs:
        for c in cols_comunes:
            if c not in df.columns:
                df[c] = ''
        partes.append(df[cols_comunes])

    df_todos = pd.concat(partes, ignore_index=True)
    log(f"Total candidatos (Tier A + B): {len(df_todos):,} registros")

    # Filtrar negaciones (solo Tier B)
    df_todos = filtrar_negaciones(df_todos)

    # Guardar candidatos completos
    out_cand = PATH_SALIDAS / "corpus_fase3_candidatos.csv"
    df_todos.drop(columns=['text']).to_csv(out_cand, index=False, encoding='utf-8')
    log(f"Guardado: {out_cand}")

    # Estadísticas por naturaleza
    stats = (df_todos.groupby(['naturaleza', 'tier'])
             .agg(n_registros=('note_id', 'count'),
                  n_notas=('note_id', 'nunique'),
                  n_eventos=('evento', 'nunique'))
             .reset_index()
             .sort_values('n_notas', ascending=False))
    out_stats = PATH_SALIDAS / "corpus_fase3_estadisticas.csv"
    stats.to_csv(out_stats, index=False, encoding='utf-8')
    log(f"Guardado: {out_stats}")
    print("\n" + stats.to_string(index=False) + "\n")

    # Muestreo estratificado
    df_muestra = muestrear_estratificado(df_todos, n_target=MUESTRA_TARGET)
    out_muestra = PATH_SALIDAS / "corpus_fase3_muestra300.csv"
    df_muestra.drop(columns=['text'], errors='ignore').to_csv(
        out_muestra, index=False, encoding='utf-8')
    log(f"Guardado: {out_muestra} ({len(df_muestra)} notas)")

    # Plantilla anotación (con texto visible)
    df_anot = crear_plantilla_anotacion(df_muestra)
    out_anot = PATH_SALIDAS / "corpus_fase3_anotacion.csv"
    df_anot.to_csv(out_anot, index=False, encoding='utf-8')
    log(f"Guardado: {out_anot}")

    # Resumen final
    log("=" * 60)
    log(f"RESUMEN FASE 3")
    log(f"  Notas candidatas totales : {df_todos['note_id'].nunique():>8,}")
    log(f"  Naturalezas cubiertas    : {df_todos['naturaleza'].nunique():>8}")
    log(f"  Eventos únicos detectados: {df_todos['evento'].nunique():>8}")
    log(f"  Muestra para anotación   : {len(df_muestra):>8,} notas")
    log(f"  Tier A (ICD-10)          : {(df_todos['tier']=='A').sum():>8,}")
    log(f"  Tier B (texto)           : {(df_todos['tier']=='B').sum():>8,}")
    log("=" * 60)
    log("Siguiente paso: abrir corpus_fase3_anotacion.csv y anotar columna CORRECTO_S_N")
    log("Meta: precision >= 75% en todas las naturalezas (hoy: Medicacion y Cuidado <50%)")
    log("=" * 60)

    con.close()

if __name__ == "__main__":
    main()
