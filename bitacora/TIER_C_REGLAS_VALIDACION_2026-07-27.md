# Conjunto final de reglas de validación por dato estructurado (MIMIC-IV v3.1)
### Salida de la síntesis post-refutación — versión implementable

---

## 0. Resumen ejecutivo

De las **73 reglas** propuestas en las seis familias, tras la revisión adversarial:

| Situación | N.º | %
|---|---|---|
| Sobreviven sin cambios sustantivos | 6 | 8 % |
| Sobreviven **con las correcciones del revisor aplicadas** | 41 | 56 % |
| Degradadas a *modificador de gravedad* o *señal débil* (no deciden el veredicto) | 11 | 15 % |
| **Descartadas** (constructo inválido, evidencia nula o daño neto) | 15 | 21 % |

Tres correcciones son **transversales y obligatorias**; sin ellas ninguna regla es publicable:

1. **El reloj no es criterio de atribución.** Sustituir toda ventana `admittime + 24/48 h` por una ventana anclada en el **hecho causal** (primera administración intrahospitalaria del fármaco, fecha del procedimiento, primer registro documentado). Las ventanas fijas descartan entre el 25 % y el 46 % de los eventos verdaderos y no separan POA de adquirido.
2. **Ausencia de dato ≠ dato negativo.** Toda regla de descarte lleva una **precondición de evaluabilidad** explícita; si no se cumple, la salida es `INDETERMINADO`, nunca `DESCARTA`.
3. **El denominador de las métricas es el subconjunto marcado por el texto**, no las 546 028 admisiones. Las cotas de especificidad publicadas (0,986–0,999) están calculadas sobre la cohorte completa y son inválidas: medido en las 331 793 epicrisis reales, la tasa de disparo de la regla nuclear metabólica es del 14,1 % entre los texto-positivos frente al 1,34 % global — **diez veces mayor**.

---

## 1. Marco común (obligatorio, coste de implementación ≈ 0)

### 1.1 Cuatro estados de salida (no dos)

```
CONFIRMADO            el hallazgo fisiológico existe Y la atribución al proceso asistencial se sostiene
ATRIBUCION_DISTINTA   el hallazgo existe pero la causa etiquetada por el texto queda descartada
DESCARTADO            existe dato suficiente y contradice el hallazgo
INDETERMINADO         no hay dato suficiente para pronunciarse (se reporta, no se computa)
```

### 1.2 Reglas de precedencia (resuelven las contradicciones detectadas)

```
P1  Evaluabilidad manda: si falla la precondición → INDETERMINADO (bloquea DESCARTADO).
P2  Un descarte de EXPOSICIÓN nunca produce DESCARTADO si el hallazgo fisiológico
    está confirmado → produce ATRIBUCION_DISTINTA.
    (Resuelve las 1 484 admisiones que R-MET-01 confirmaba y R-MET-08 descartaba,
     47 de ellas dentro del corpus de texto.)
P3  Un descarte FISIOLÓGICO (p. ej. nadir glucémico ≥70) tiene precedencia sobre
    cualquier confirmación de exposición.
P4  Los modificadores de gravedad (rescate, reintubación, transfusión masiva,
    lactato, reversión) NUNCA alteran el veredicto; solo estratifican.
P5  Una lista única canónica de itemids por concepto, compartida entre la regla
    que confirma y la que descarta (obligatorio para catéter central y vía aérea).
```

### 1.3 Regla de higiene de itemids (aplicable a todo el sistema)

- **Verificar por VOLUMEN, no por existencia en el diccionario.** Con cero filas confirmadas: `52027`, `51676`, `228388`, `52157`, `52105`, `51695`, `52165` (PTT Control), `225803`, `225809`, `225955`, `51002`, `52642`, `225478`, `230172`, `230174`, `229996`, ICD-10 `N1411`/`N1419`. `52569` existe pero **todas** sus filas tienen `hadm_id` nulo → aporta cero bajo el filtro estándar.
- **Prohibido como evidencia de evento**: todo itemid con `d_items.category = 'Alarms'` (contienen el umbral configurado en el monitor, no un disparo) y todo itemid cuyo dominio observado sea >95 % un único valor (p. ej. `229878`, 100 % «Yes»).
- **Prohibido umbralizar úlceras por `valuenum`**: está vacío en todo el vocabulario nuevo (228813-228822). Mapear por texto normalizado (ojo al doble espacio en la variante «Partial thickness skin loss…», 460 registros).
- Declarar siempre `fuente:itemid` (un itemid de `chartevents` bajo `tabla='labevents'` devuelve vacío silenciosamente: pasa en R-MET-02, R-MET-04, R-MET-12).

### 1.4 Restricción estructural de cobertura (limita toda la mitad ICU del sistema)

`chartevents`, `procedureevents`, `inputevents`, `outputevents`, `datetimeevents` **solo existen dentro de la estancia UCI**: 85 242 de 546 028 admisiones (15,6 %). Además, el 13,1 % de las admisiones con UCI inician la UCI >48 h después de `admittime` y el 61,3 % siguen hospitalizadas >48 h tras salir (mediana 70,3 h). Consecuencia operativa:

> Fuera de UCI, ninguna regla de módulo ICU puede DESCARTAR. Solo puede CONFIRMAR.

Antes de diseñar nada más: **medir qué fracción del corpus de epicrisis corresponde a admisiones con estancia en UCI**. Si es baja, la arquitectura de dos niveles no es viable y hay que reportarlo.

---

## 2. Catálogo final ordenado por relación valor/coste

Coste = bytes a recorrer × complejidad de *join*. Referencia de tamaños reales verificados en `T:\MIMIC_full`:
`procedures_icd` 7,7 MB · `admissions` 20 MB · `procedureevents` 24 MB · `diagnoses_icd` 34 MB · `outputevents` 49 MB · `datetimeevents` 63 MB · **`microbiologyevents` 112 MB** · `inputevents` 401 MB · `prescriptions` 606 MB · `emar_detail` 748 MB · `emar` 811 MB · **`labevents` 2,5 GB** (filtrable por itemid en una pasada) · **`chartevents` 3,5 GB**.

### NIVEL 1 — Alto valor, coste bajo (implementar primero)

| # | ID | Evento / función | Dir. | Fuente | Coste |
|---|---|---|---|---|---|
| 1 | **R-MET-02c** | Descarte por nadir glucémico ≥70 mg/dL **con criterio de densidad** | descarta | labevents (50931, 50809) | bajo |
| 2 | **R-INF-01c** | Bacteriemia nosocomial confirmada por hemocultivo (patógeno especiado, RIT 14 d) | confirma | microbiologyevents | muy bajo |
| 3 | **R-REN-01c** | LRA KDIGO con clasificación POA / adquirida / indeterminada | confirma+clasifica | labevents (50912) + admissions | bajo |
| 4 | **R-INF-03c** | Contaminación por comensal cutáneo (LCBI-2 no cumplido) | descarta | microbiologyevents | muy bajo |
| 5 | **R-INF-16c** | Urocultivo no elegible (MIXED BACTERIAL FLORA, ≥3 especies, levadura, no especiado) | descarta | microbiologyevents | muy bajo |
| 6 | **R-INF-07c** | Colonización por MRSA (hallazgo solo en muestra de vigilancia) | descarta | microbiologyevents | muy bajo |
| 7 | **R-INF-18c** | Bacteriemia secundaria probable (mismo germen en otro sitio ±2 d) → sale del proxy CLABSI | descarta (del numerador) | microbiologyevents | muy bajo |
| 8 | **R-HEM-01c** | INR ≥5,0 con warfarina administrada y sin marcador de fallo hepático | confirma | labevents (51237, 50885, 51214) + emar | bajo-medio |
| 9 | **R-HEM-02c** | Anticoagulación excesiva **adquirida** (basal ≤2,5 → pico ≥5,0 tras 72 h) | confirma | labevents (51237) | bajo |
| 10 | **R-INF-08c** | *C. difficile*: toxina = confirmado / PCR + tratamiento = probable / PCR sola = indeterminado | escalonado | microbiologyevents | muy bajo |
| 11 | **R-REN-11c** | Exclusión de diálisis **crónica** (solo por episodio anterior; ERC-5 sin diálisis NO se excluye) | gobierno | diagnoses_icd + procedures_icd | trivial |
| 12 | **R-DIS-19c** | MINS: troponina T >1,5 ng/mL con curva ≥20 %, **excluyendo cirugía cardíaca** | confirma | labevents (51003) + services | bajo |
| 13 | **R-REN-04c** | LRA estadio 3 / inicio de TRR (lista de itemids depurada, **sin 224270**) | confirma | procedureevents + procedures_icd | bajo |
| 14 | **R-DIS-12c** | Reapertura quirúrgica: ICD-9 5412/3403/0123/0302/0602/3941 (**sin 3998**) + ICD-10 `0WJ*0ZZ/0DJ*0ZZ/0FJ*0ZZ` con procedimiento índice previo | confirma (circular) | procedures_icd | trivial |
| 15 | **R-DIS-06c** | Prohibición de itemids de alarma y de campos degenerados | gobierno | d_items | trivial |
| 16 | **R-CUI-01c** | Caída documentada por enfermería (225474) anclada a `icustays` | confirma | procedureevents | trivial |
| 17 | **R-CUI-06c** | Extubación no planificada (225468 / 225477) | confirma | procedureevents | trivial |
| 18 | **R-DIS-16c** | Hiperamilasemia/hiperlipasemia tardía post-CPRE (**CPRE ampliada a códigos terapéuticos**, ≥ día +2) | confirma parcial | labevents (50956, 50867) + procedures_icd | bajo |
| 19 | **R-DIS-15c** | Punción/laceración accidental abdominopélvica (PSI 15 corregido) + conjunto ampliado declarado aparte | confirma (circular) | diagnoses_icd | trivial |

### NIVEL 2 — Valor alto/medio, coste medio (requiere emar / prescriptions / inputevents)

| # | ID | Evento / función | Dir. | Fuente | Coste |
|---|---|---|---|---|---|
| 20 | **R-MET-01c+03c** | Hipoglicemia <54 mg/dL **posterior a administración intrahospitalaria de insulina** (regla conjunta) | confirma | labevents + emar ∪ inputevents ∪ prescriptions | medio |
| 21 | **R-MET-08c** | Cero exposición a insulina por **cuatro** vías → `ATRIBUCION_DISTINTA` | atribución | prescriptions ∪ emar ∪ inputevents ∪ chartevents 228236 | medio |
| 22 | **R-MET-05c** | CMS816v4 **fiel** (sin recorte de 24 h) + variante «atribuible al hospital» | confirma | labevents + emar ∪ inputevents | medio |
| 23 | **R-HEM-03c** | Descarte de sangrado *por anticoagulante* (INR<1,5 ∧ PTT<45 ∧ cero anticoagulante/antiagregante/fibrinolítico **administrado**) | descarta | labevents + emar | medio |
| 24 | **R-HEM-04c** | Reversión farmacológica: INR ≥4,5 + fitomenadiona (**cualquier vía**) o CCP en 0-24 h | confirma | labevents + emar | medio |
| 25 | **R-INF-02c** | Descarte de bacteriemia **condicionado** (≥1 hemocultivo procesado ∧ sin ATB sistémico 72 h antes ∧ sin shock con vasopresor) | descarta | microbiologyevents + emar + inputevents | medio |
| 26 | **R-INF-09c** | Soporte terapéutico ICD: vancomicina **oral/rectal** o fidaxomicina ≥3 días (**metronidazol eliminado**) | confirma | emar | medio |
| 27 | **R-DIS-08c** | Naloxona/flumazenil con **iatrogenia demostrada** (opioide administrado antes; excluye T40.x/F11.x; excluye perfusión) | confirma | emar + emar_detail + diagnoses_icd | medio |
| 28 | **R-HEM-08c** | Sangrado mayor ISTH: caída ≥2 g/dL ∧ nadir <8 o caída ≥20 % ∧ **≥1 corroboración objetiva** | confirma | labevents + inputevents + procedures_icd | medio |
| 29 | **R-REN-07c** | LRA asociada a vancomicina (valle **inferido por timing**; excluye sellos/oral; declara causa competitiva) | confirma parcial | labevents (51009, 50912) + emar | medio |
| 30 | **R-MET-06c** | Rescate con dextrosa (emar ∪ inputevents 220952/220950) → **gravedad**, no etiología | gravedad | emar + inputevents | medio |
| 31 | **R-HEM-05c** | Heparina no fraccionada: PTT >100 s (o >2,5× `ref_range_upper`) **confirmado en 2 determinaciones**, con perfusión IV real («Heparin Sodium» 25 000 UNIT, excluidos flush/dwell/priming/HD/CRRT/IABP/Impella) | confirma | labevents + prescriptions + emar | medio-alto |
| 32 | **R-HEM-14c** | Hemorragia mayor con soporte transfusional (≥1750 mL/24 h) y transfusión masiva (≥3500 mL) | gravedad | inputevents | medio |
| 33 | **R-REN-09c** | LRA con exposición concurrente a nefrotóxicos (**3 subfamilias separadas**; IECA/ARA-II solo si Δ>30 % o K⁺>5,5 o suspensión) | confirma parcial | labevents + emar | medio |

### NIVEL 3 — Valor medio, coste alto (una sola pasada por `chartevents`)

| # | ID | Evento / función | Dir. | Coste |
|---|---|---|---|---|
| 34 | **R-MET-04c** | Glucometría POC <54 (225664, 226537; **220621 reclasificado como laboratorio recharteado**) | confirma | alto |
| 35 | **R-CUI-09c** | Retiro no planificado de línea: **unión** procedureevents (225821/225476) ∪ chartevents `*Discontinued` con `value LIKE 'Unplanned%'` → 2 282 eventos frente a 282 | confirma | alto |
| 36 | **R-INF-13c** | NAV → sustituir por **VAE/PVAP de NHSN** (PEEP 220339, FiO₂ 223835, T.ª, leucocitos, ATB nuevo ≥4 d, cultivo elegible) | confirma | alto |
| 37 | **R-CUI-02c** | HAPU con **línea base negativa** 224026='Intact' + estadio ≥II por texto + UCI precoz | confirma | alto |
| 38 | **R-INF-15c** | ITU asociada a sonda (organismo elegible + sonda `229351` >2 días + **signo clínico**) — sin umbral de UFC | confirma | alto |
| 39 | **R-HEM-10c** | RTFNH: `T_post ≥38 °C` y `T_post − T_pre_última ≥1 °C` (**no el mínimo**), extendido a plaquetas y plasma | confirma | alto |
| 40 | **R-DIS-01c** | Extravasación **Grade ≥3** (7 itemids verificados) con inserción previa (224566/224276/224277/224275/224274/229468) | confirma | alto |
| 41 | **R-INF-10c/12c** | Proxy de CLABSI con **lista canónica única** (sin Impella 228169 ni ECMO 229515; con MAC 229526 y Sheath 225789) | confirma/descarta | alto |
| 42 | **R-CUI-08c** | Descarte de extubación por imposibilidad física con **inventario ampliado de vía aérea en chartevents** (error residual 0,24 % frente al 11,9 % declarado) | descarta | alto |
| 43 | **R-REN-05c** | Oliguria: Σ(salidas − irrigante 227488) / (peso × **horas reales**), estadios 1/2/3 separados | confirma | alto |

### NIVEL 4 — Conservadas pero **no operativas** (se publican como límite de alcance)

`R-MET-10c` sulfonilureas (n=48) · `R-HEM-06c` anti-Xa HBPM (cobertura 0,30 %) · `R-HEM-11c` hemólisis (score ≥2/3, **nunca descarta**) · `R-HEM-12c` TACO exploratorio (≥3/4) · `R-HEM-13c` fenotipo 4Ts (**jamás «HIT confirmada»**; enriquecimiento medido ≈1,01×, es decir nulo) · `R-CUI-05c` Braden (~500 admisiones) · `R-DIS-04c` fuga aérea (reubicada a complicación quirúrgica torácica).

---

## 3. Reglas DESCARTADAS y motivo

| Regla | Motivo del descarte |
|---|---|
| **R-MET-07** «Sobredosis inadvertida de insulina» | Fallo de validez de constructo: la firma `<40 mg/dL + insulina + rescate` no distingue el **error de dosificación** de la reacción adversa a una dosis correcta (dieta absoluta, fracaso renal, hepatopatía). Duplica el evento de R-MET-05 e infla el recuento. VPP publicado 0,993 con sensibilidad real estimada <0,30. → Se reconvierte en **nivel 3 de gravedad** del evento «hipoglicemia por insulina». |
| **R-MET-09** dose_due vs dose_given | Hallazgo negativo **verificado**: 0 coincidencias en 87 371 064 filas de `emar_detail`; además 14 240 `dose_val_rx` en formato rango («0-10»). Se conserva como **declaración de no viabilidad**, no como regla. |
| **R-MET-11** sobredosis de fármacos no hipoglucemiantes | No existe módulo de notificación de incidentes ni bandera de error; la intención («inadvertida») no está en ningún campo. |
| **R-CUI-12** descarte de caída por ICD | Dispara sobre **31 300 admisiones** (dos órdenes de magnitud más que toda la población confirmable) con un error medido del **12,3 %**, y su cláusula exculpatoria (`Y92.23x`) es estructuralmente imposible en el 53,3 % de la base (era ICD-9). Solo admisible reconvertida en **conjunción positiva de evidencia de caída comunitaria** o como reponderación probabilística, nunca como filtro binario. |
| **R-CUI-11** caída confirmada por ICD | Refutada empíricamente: de 1 560 admisiones, el 82,8 % tiene registro de urgencias y el 46,4 % un diagnóstico principal traumático (S/T) → la caída ocurrió **antes** de llegar. Sobrevive únicamente la versión endurecida (143 admisiones) como **señal débil de estratificación**. |
| **R-DIS-10** reintervención por ≥2 «OR Received» | VPP medido **0,194**: añadirla empeora el conjunto. Solo sobrevive como **modificador** con dedup a 6 h (no 24 h: entre 6 y 24 h hay 379 pares que son el retorno urgente a quirófano) y con criterio concurrente obligatorio. |
| **R-DIS-13** repetición del mismo código de procedimiento | Descarte correcto y confirmado: los códigos dominantes son drenajes, accesos vasculares, endoscopias y ventilación protocolizados. |
| **R-DIS-09** dantroleno (hipertermia maligna) | 987 filas / 95 admisiones, con brazo de ensayo clínico («dantrolene / placebo») y predominio de forma oral para espasticidad. Inutilizable. |
| **R-DIS-07** complicación anestésica intraoperatoria | Cero registros de `225478 Operation`, `230172`, `230174`, `229996`; 12 y 1 registro de isoflurano/sevoflurano. **MIMIC-IV no instrumenta el periodo intraoperatorio.** |
| **R-REN-13** nefritis intersticial (eosinofiluria) | 7 274 determinaciones, **todas sin `valuenum`**; sensibilidad 30,8 % / especificidad 68,2 % en la literatura. |
| **R-REN-14** nefropatía por contraste codificada | `N1411` y `N1419` con 0 registros. No sirve como patrón de oro; solo como marco de muestreo (`N141`, 1 007 admisiones). |
| **R-HEM-12 (TRALI)** | No separable de TACO ni del SDRA con dato estructurado. |
| **R-CUI-10** retiro accidental de sonda enteral/vesical | 0 itemids de desplazamiento/salida accidental en los 4 095 de `d_items`; `229352`/`229353` radicalmente asimétricos (376 782 vs 2 589 filas). |
| **R-DIS-17** perforación por imagen | `221214`, `225459`, `225457` son `param_type='Processes'`: registran que el estudio se hizo, nunca su resultado. |
| **R-INF-05** lactato como confirmador | Degradada a **apoyo de gravedad** con vasopresor concurrente (Sepsis-3). Como confirmador aislado inyecta falsos positivos (isquemia mesentérica, convulsión, metformina, shock cardiogénico). |

---

## 4. Pseudocódigo de las tres reglas de mayor valor/coste

> **Estrategia de E/S obligatoria:** una única pasada por cada archivo grande extrayendo de golpe **todos** los itemids de **todas** las reglas, materializando `parquet` intermedios. `labevents` (2,5 GB) se recorre **una vez** con ~30 itemids; `chartevents` (3,5 GB) **una vez** con ~60 itemids. Nunca una pasada por regla.
>
> Lista mínima para la pasada de `labevents`: `50931, 50809, 50912, 52546, 51006, 51237, 51275, 51228, 51229, 51222, 50811, 51265, 51301, 50813, 50885, 50884, 51214, 50954, 50935, 51003, 51009, 50929, 50997, 50865, 50910, 50911, 50956, 50867, 50963, 50971`.

---

### 4.1 R-MET-02c — Descarte por control glucémico documentado (mayor palanca de especificidad)

**Objetivo:** eliminar falsos positivos del patrón textual `hypoglycemia.*insulin` (7 466 admisiones) demostrando que el paciente **nunca** estuvo hipoglucémico y que el muestreo fue suficiente para afirmarlo.

```python
# ---------- ENTRADAS ----------
# hosp/admissions.csv.gz : subject_id, hadm_id, admittime, dischtime
# hosp/labevents.csv.gz  : subject_id, hadm_id, itemid, charttime, valuenum, valueuom
# (opcional NIVEL 3) icu/chartevents.csv.gz : hadm_id, itemid, charttime, valuenum
# exposición a insulina: tabla intermedia INSULIN_ADM (ver R-MET-01c)

ADM = read_csv("hosp/admissions.csv.gz",
               usecols=["subject_id","hadm_id","admittime","dischtime"],
               parse_dates=["admittime","dischtime"])
ADM["los_h"] = (ADM.dischtime - ADM.admittime).total_seconds()/3600

GLU_LAB_ITEMIDS = {50931, 50809}      # 52569 EXCLUIDO: 100 % hadm_id nulo -> aporta 0
GLU_POC_ITEMIDS = {225664, 226537}    # 220621 = laboratorio recharteado, NO POC
PLAUSIBLE = lambda v: 5.0 <= v <= 1000.0   # 172 valores <=0 y 413 >1000 en 225664

glu = []
for chunk in read_csv("hosp/labevents.csv.gz", chunksize=5_000_000,
                      usecols=["subject_id","hadm_id","itemid","charttime",
                               "valuenum","valueuom"]):
    c = chunk[chunk.itemid.isin(GLU_LAB_ITEMIDS)]
    c = c[c.hadm_id.notna() & c.valuenum.notna()]
    c = c[c.valuenum.map(PLAUSIBLE)]
    # verificado: 100 % de la glucosa de sangre está en mg/dL (un único valueuom nulo)
    glu.append(c[["hadm_id","charttime","valuenum"]])
GLU = concat(glu)                      # ~3,9 M filas
GLU["src"] = "lab"

# --- (opcional) POC de UCI: solo si ya se hizo la pasada de chartevents ---
# GLU_POC: mismas columnas, src="poc"; aporta +20,6 % de admisiones con <54
# GLU = concat([GLU, GLU_POC])

# ---------- AGREGACIÓN POR ADMISIÓN ----------
AGG = GLU.groupby("hadm_id").agg(n_glu=("valuenum","size"),
                                 min_glu=("valuenum","min")).reset_index()
AGG = AGG.merge(ADM[["hadm_id","admittime","dischtime","los_h"]], on="hadm_id")

# ---------- CRITERIO DE DENSIDAD (sustituye a COUNT>=3, que es arbitrario) ----------
# D1: al menos 1 glucosa por cada 24 h de estancia
AGG["dens_estancia_ok"] = AGG.n_glu >= ceil(AGG.los_h / 24.0)

# D2: si hubo insulina, >=3 glucosas en las 24 h siguientes a CADA administración
#     INSULIN_ADM(hadm_id, t_adm) = emar U inputevents U prescriptions
def dens_insulina_ok(hadm):
    adms = INSULIN_ADM[INSULIN_ADM.hadm_id == hadm].t_adm
    if len(adms) == 0: return True                      # sin insulina, no aplica
    g = GLU[GLU.hadm_id == hadm].charttime
    return all( ((g > t) & (g <= t + 24h)).sum() >= 3 for t in adms )

AGG["dens_insulina_ok"] = AGG.hadm_id.map(dens_insulina_ok)

# ---------- VEREDICTO ----------
def veredicto(r):
    if r.n_glu == 0:                                   return "INDETERMINADO"   # 138 676 hadm (25,4 %)
    if not (r.dens_estancia_ok and r.dens_insulina_ok):return "INDETERMINADO"
    if r.min_glu >= 70.0:                              return "DESCARTADO"      # ~225 000 hadm
    if 54.0 <= r.min_glu < 70.0:                       return "INDETERMINADO"   # 26 529 hadm, ADA nivel 1
    return "PASA_A_R-MET-01c"                                                    # min_glu < 54

AGG["estado"] = AGG.apply(veredicto, axis=1)
```

**Notas de implementación**
- El rendimiento **real** de esta regla es 225 269 admisiones (41,3 %) con la cláusula de recuento aplicada, **no** 374 401 (68,6 %) como se publicó. Publicar la cifra correcta.
- Excluir del bloqueo del descarte las glucosas bajas **anteriores a la primera administración intrahospitalaria de insulina** (2 503 admisiones): son comunitarias y no deben impedir descartar el evento hospitalario.
- La unión con R-MET-08c (cero exposición a insulina) alcanza 484 959 admisiones (88,8 %), no el 71,2 % declarado (una unión no puede ser menor que su mayor término).

---

### 4.2 R-INF-01c / 02c / 03c — Bacteriemia nosocomial (mejor relación valor/coste del sistema: 112 MB)

```python
# ---------- ENTRADAS ----------
# hosp/microbiologyevents.csv.gz : micro_specimen_id, subject_id, hadm_id, chartdate,
#                                  charttime, spec_itemid, test_itemid, org_itemid,
#                                  org_name, ab_itemid, ab_name, interpretation
# hosp/admissions.csv.gz         : subject_id, hadm_id, admittime, dischtime,
#                                  admission_location, edregtime

MB = read_csv("hosp/microbiologyevents.csv.gz",
              usecols=["micro_specimen_id","subject_id","hadm_id","charttime",
                       "chartdate","spec_itemid","test_itemid","org_itemid",
                       "org_name"], parse_dates=["charttime","chartdate"])

# 1) Espécimen: sangre clínica. Excluir post-mortem (70016) y stem cell (70060).
MB = MB[MB.spec_itemid.isin({70011, 70012})]

# 2) Prueba: NO restringir a 90201 (pierde candidemia y anaerobios)
MB = MB[MB.test_itemid.isin({90201, 90258, 90117, 90265, 90264, 90167})]

# 3) UNA FILA POR AISLAMIENTO (microbiologyevents tiene una fila por antibiótico)
MB = MB.drop_duplicates(subset=["micro_specimen_id","org_itemid"])

# 4) Resultados administrativos
MB = MB[MB.org_name.notna()]
MB = MB[~MB.org_name.str.upper().isin({"CANCELLED","NEGATIVE","NO GROWTH"})]

# 5) CLASIFICACIÓN DEL ORGANISMO — por REGEX, no por igualdad exacta
COMENSAL = r"(STAPHYLOCOCC|MICROCOCC|CORYNEBACTER|PROPIONIBACTER|CUTIBACTER|" \
           r"BACILLUS(?!.*ANTHRACIS)|VIRIDANS|LACTOBACILL)"
NO_ESPECIADO = r"(GRAM POSITIVE|GRAM NEGATIVE|COCCUS\(COCCI\)|ROD\(S\))"
def clasifica(n):
    u = n.upper()
    if re.search(NO_ESPECIADO, u):                       return "NO_ELEGIBLE"
    if "STAPH AUREUS" in u or "LUGDUNENSIS" in u:        return "PATOGENO"
    if re.search(COMENSAL, u):                           return "COMENSAL"
    return "PATOGENO"                                    # incluye Candida spp.
MB["clase"] = MB.org_name.map(clasifica)

# 6) JOIN CON LA ADMISIÓN (55,87 % de las filas tiene hadm_id NULO)
ADM = read_csv("hosp/admissions.csv.gz",
               usecols=["subject_id","hadm_id","admittime","dischtime",
                        "admission_location","edregtime"], parse_dates=[...])
MB = MB.merge(ADM, on="subject_id", suffixes=("","_adm"))
MB = MB[(MB.charttime >= MB.admittime) & (MB.charttime <= MB.dischtime)]
# EXIGIR ASIGNACIÓN UNÍVOCA (hospitalizaciones solapadas/contiguas del mismo paciente)
cnt = MB.groupby(["micro_specimen_id","org_itemid"]).hadm_id.nunique()
MB = MB[MB.set_index(["micro_specimen_id","org_itemid"]).index.map(cnt) == 1]

# 7) VENTANA (proxy CONSERVADOR del «día 3» calendario de NHSN — declararlo así)
MB["nosocomial"] = MB.charttime > MB.admittime + 48h

# 8) VENTANA DE INFECCIÓN REPETIDA (RIT): 1 evento por (hadm, género-especie) / 14 d
MB = MB.sort_values("charttime")
MB["evento_nuevo"] = MB.groupby(["hadm_id","org_name"]).charttime \
                       .transform(lambda s: s.diff().fillna(pd.Timedelta("999d")) > 14d)

# ---------- VEREDICTOS ----------
# C1) CONFIRMA: >=1 aislamiento PATOGENO, nosocomial, evento_nuevo
# C2) LCBI-2  : solo COMENSAL -> exige >=2 micro_specimen_id con charttime DISTINTO,
#               separados <=1 día calendario, mismo género-especie,
#               MÁS >=1 signo sistémico en ±1 día:
#                 chartevents 223762 > 38.0 C  o  223761 > 100.4 F
#                 o PAM 220052 < 65  o  inicio de vasopresor en inputevents
#                 (221906 norepi, 221749 fenilef, 222315 vasopresina,
#                  221289 epi, 221662 dopamina)
#               Si no se cumple -> CONTAMINACION (descarta la etiqueta de bacteriemia)
# C3) NO_ELEGIBLE -> nunca confirma (NHSN no acepta tinción de Gram como patógeno)
# C4) <=48 h -> NO borrar: reetiquetar
#         admission_location LIKE 'TRANSFER FROM%'  -> IAAS_ATENCION_PREVIA
#         alta previa del mismo subject_id <30 d    -> IAAS_ATENCION_PREVIA
#         resto                                     -> POA_COMUNITARIA
# D1) DESCARTE (R-INF-02c) SOLO SI:
#         existe >=1 hemocultivo PROCESADO (no CANCELLED) en la ventana
#      Y  ninguno aporta organismo elegible
#      Y  no hubo antibiótico sistémico en las 72 h previas a la 1ª extracción
#      Y  no hay shock séptico con vasopresor
#     en cualquier otro caso -> INDETERMINADO
# E1) EXCLUSIÓN R-INF-18c: si el mismo género-especie aparece en cultivo de otro
#     sitio (orina, vía aérea baja, herida/tejido, líquido estéril, bilis) en
#     [-2 d, +2 d] -> BSI_SECUNDARIA_PROBABLE (sale del numerador del proxy CLABSI)
```

**Advertencia obligatoria en la tesis:** el evento medido por R-INF-10c no es CLABSI sino **«bacteriemia nosocomial en portador de catéter venoso central»**; sin poder descartar bacteriemia secundaria de forma completa, la etiqueta CLABSI no es sostenible.

---

### 4.3 R-REN-01c — LRA con clasificación POA / adquirida / indeterminada

**Corrige tres errores graves simultáneos:** exclusión de la diálisis aguda (borra el evento más grave), corte de 48 h (destruye el 46 % de los positivos propios) y pérdida de la creatinina de urgencias (57,8 % de las admisiones la tienen y difiere ≥0,3 mg/dL de la primera intrahospitalaria en el 15,1 %).

```python
# ---------- ENTRADAS ----------
# hosp/labevents.csv.gz : subject_id, hadm_id, itemid, charttime, valuenum
# hosp/admissions.csv.gz, hosp/diagnoses_icd.csv.gz, hosp/procedures_icd.csv.gz
# icu/procedureevents.csv.gz (TRR)

CR_ITEMID = 50912          # SOLO química. 52024 = gasómetro (0,35 %, otro método
                           # analítico; contamina un umbral de 0,3 mg/dL)
# 52546 se conserva SOLO para el basal ambulatorio (1 273 filas, hadm_id nulo)

cr = []
for chunk in read_csv("hosp/labevents.csv.gz", chunksize=5_000_000,
                      usecols=["subject_id","hadm_id","itemid","charttime","valuenum"]):
    c = chunk[chunk.itemid.isin({50912, 52546})]
    c = c[c.valuenum.between(0.1, 30.0)]      # plausibilidad
    cr.append(c)                              # NO filtrar hadm_id: los nulos son
CR = concat(cr)                               # urgencias y ambulatorio, y son clave

ADM = read_csv("hosp/admissions.csv.gz", usecols=["subject_id","hadm_id",
               "admittime","dischtime"], parse_dates=[...])

# ---------- 1) EXCLUSIÓN: SOLO DIÁLISIS CRÓNICA, Y SOLO POR EPISODIO ANTERIOR ----------
ERT_DX  = {"N186","5856","Z992"}                 # NO excluir N185/5855 (ERC-5 sin diálisis:
ERT_PCS = {"3995","5498","5A1D00Z","5A1D60Z",    # 1 610 admisiones que SÍ pueden sufrir LRA)
           "5A1D70Z","5A1D80Z","5A1D90Z"}
# excluir hadm_i si el mismo subject_id tiene ERT_DX o ERT_PCS en un episodio con
# admittime ESTRICTAMENTE ANTERIOR. El episodio en que se inicia la diálisis y
# aparece por primera vez el código -> INDETERMINADO (no excluir, no confirmar).

# ---------- 2) ANCLAJES ----------
# t0 = primera creatinina del EPISODIO ASISTENCIAL:
#      min( charttime de CR con hadm_id = h ,
#           charttime de CR con hadm_id NULO del mismo subject_id
#                dentro de [admittime - 24 h, admittime] )      <-- urgencias
# basal_amb = MEDIANA de CR con hadm_id NULO del mismo subject_id
#             en [admittime - 365 d, admittime - 7 d]
#             (reportar análisis de sensibilidad con media y mínimo: Siew/Matheny
#              muestran que el resultado depende de esta elección)

# ---------- 3) CLASIFICACIÓN (tres estados, NO exclusión mutua) ----------
# PRESENTE_AL_INGRESO : cr(t0) >= 1.5 * basal_amb
# ADQUIRIDA           : EXISTE t > t0 con
#                         cr(t) - min(cr en [t-48 h, t]) >= 0.3      (criterio absoluto)
#                       O cr(t) >= 1.5 * min(cr en [max(t0, t-7 d), t])  (relativo)
#                       -- SE EVALÚA AUNQUE EL PACIENTE INGRESE YA CON LRA:
#                          LRA sobre LRA es un evento adverso.
# INDETERMINADA       : <2 determinaciones útiles y sin basal ambulatorio
# EVALUABLE_SOLO_LRA  : 1 determinación + basal ambulatorio (permite afirmar POA,
#                       NUNCA adquirida)

# ---------- 4) ESTADIO 3 (R-REN-04c) ----------
# cr >= 4.0 con ascenso agudo previo
# O cr >= 3.0 * basal                       <-- criterio KDIGO ausente en la regla original
# O inicio de TRR: procedureevents itemid IN (225441, 225802, 225805)   [+225436 apoyo]
#                  ELIMINADO 224270 'Dialysis Catheter' (es la COLOCACIÓN DE UN
#                  CATÉTER, no una sesión: 4 044 admisiones de falso positivo)
#   O ICD 3995/5498/5A1D* en ESTE episodio, sin diálisis crónica previa
```

**Cobertura real (recalculada sobre el archivo completo):** 415 830 admisiones (76,2 %) con ≥1 creatinina y 320 677 (58,7 %) con ≥2. Incorporar la creatinina de urgencias **reduce** la zona de indeterminación.

---

## 5. Ganancia de especificidad esperable — cálculo explícito y cotas

### 5.1 Punto de partida

Con `p = 0,0653`, `sens = 0,907`, `esp = 0,917`:

```
TP = 0,907 × 0,0653          = 0,05923
FP = (1 − 0,917) × 0,9347    = 0,07758
VPP = 0,05923 / 0,13681      = 0,433     ✔ reproduce el valor publicado
```

### 5.2 Modelo del validador

El validador estructurado no cambia el clasificador: **elimina falsos positivos** del conjunto de texto-positivos, con dos parámetros y una restricción:

- `c` = **cobertura**: fracción de texto-positivos sobre los que la regla es evaluable.
- `q` = **poder de descarte** dentro del subconjunto evaluable.
- `e` = **erosión**: fracción de verdaderos positivos descartados por error.

```
f_FP = c · q              esp' = 1 − (1 − 0,917)·(1 − f_FP)
sens' = 0,907 · (1 − e)   VPP' = sens'·p / (sens'·p + (1 − esp')·(1 − p))
```

### 5.3 Anclajes empíricos disponibles (medidos, no supuestos)

| Familia | Cobertura medida | Observación |
|---|---|---|
| Metabólico | 74,6 % con ≥1 glucosa; **63,9 % de los texto-positivos decidibles** (14,1 % confirmados + 50,3 % descartados; 36,1 % indeterminados) | tras exigir densidad, el descarte cae de 68,6 % a 41,3 % global |
| Renal | 76,2 % con ≥1 creatinina; 58,7 % con ≥2 | 39,2 % de estancias <48 h, faltante **no aleatorio** |
| Hemorragia | 50 % sin ningún INR, 52 % sin PTT; 41 % sin dos Hb | el subconjunto texto-positivo está **enriquecido** en anticoagulados → el poder de descarte real es menor que el global |
| Infección | microbiología solo si se solicitó; `procedureevents`/`chartevents` solo en 15,6 % (UCI) | |
| Cuidado físico / dispositivos | 15,6 % (UCI) | fuera de UCI **no puede descartar** |

### 5.4 Escenarios (conservadores)

| Escenario | c·q (f_FP) | e | esp' | VPP' |
|---|---|---|---|---|
| **Solo Nivel 1** (labevents + microbiología + ICD) | 0,20 | 0,03 | **0,934** | **0,481** |
| **Conservador** (Niveles 1+2) | 0,275 | 0,05 | **0,940** | **0,500** |
| **Central** (Niveles 1+2 bien calibrados) | 0,40 | 0,07 | **0,950** | **0,542** |
| **Optimista** (Niveles 1+2+3, con la pasada completa de chartevents) | 0,55 | 0,10 | **0,963** | **0,604** |

### 5.5 Lo que NO se puede prometer

Alcanzar el objetivo implícito del planteamiento (esp = 0,970 → VPP 0,679) exige **eliminar el 63,9 % de todos los falsos positivos**:

```
(1 − 0,970) / (1 − 0,917) = 0,030 / 0,083 = 0,361 de FP supervivientes  →  f_FP = 0,639
```

Con cobertura máxima realista `c ≈ 0,60`, eso requeriría `q ≈ 1,00`: descarte perfecto dentro del subconjunto evaluable. **No es defendible con la evidencia disponible.** La afirmación honesta es:

> **esp 0,917 → 0,934–0,963 (punto central 0,950); VPP 0,433 → 0,48–0,60 (punto central 0,54).** Intervalo dominado por la incertidumbre en la cobertura, no por la del umbral.

### 5.6 Cuatro advertencias que deben figurar junto a cualquier cifra

1. **Sesgo de selección por indeterminación.** Reportar el VPP solo sobre el subconjunto decidible lo **infla** por construcción. Publicar siempre tres cifras: VPP global, VPP del subconjunto decidible, y % del corpus en cada estado.
2. **`p = 0,0653` es la prevalencia de CUALQUIER evento adverso.** Aplicada a un evento único con prevalencia estructurada del 1,34 % (hipoglicemia por insulina) o del 0,046 % (la mal llamada «sobredosis»), sobreestima gravemente el VPP. Cada regla debe reportar su VPP contra la prevalencia **de su propio evento**.
3. **Sesgo de espectro en el estrato UCI.** La prevalencia de evento adverso en UCI es muy superior al 6,53 %; el VPP subirá en ese estrato **aunque la especificidad de la regla no mejore en absoluto**. Atribuir esa subida al validador sería un error inferencial.
4. **Inconsistencia aritmética pendiente de resolver.** Con VPP de texto 0,433 sobre 7 466 texto-positivos habría ~3 233 eventos verdaderos; con sensibilidad de regla 0,5-0,7 se esperarían ~1 940 disparos verdaderos, pero solo hay **1 056 disparos totales**. O la sensibilidad real de la regla es ≤0,33 o el VPP del texto está sobreestimado. **Hay que resolverlo antes de publicar**, con revisión manual ciega de una submuestra estratificada (≥100 casos, con κ).

---

## 6. Eventos NO validables con dato estructurado (resultado, no fracaso)

Esta lista **acota el alcance del sistema** y debe ir en la sección de limitaciones con su evidencia:

### 6.1 No validables por ausencia estructural del dato

| Evento | Evidencia de la imposibilidad |
|---|---|
| **Error de medicación / dosis incorrecta** | `dose_due` y `dose_given` **no coexisten en ninguna** de las 87 371 064 filas de `emar_detail`. Además 14 240 `dose_val_rx` en formato rango («0-10»). El registro es **autoconfirmatorio por diseño**. |
| **Sobredosis inadvertida (cualquier fármaco)** | La intención («inadvertida») no está en ningún campo; no hay módulo de notificación de incidentes. |
| **Complicación anestésica intraoperatoria** | 0 registros de `225478 Operation`, `230172`, `230174`, `229996`; 12 y 1 registro de isoflurano/sevoflurano. Sin módulo perioperatorio. |
| **Hipertermia maligna** | Dantroleno: 987 filas / 95 admisiones, con brazo de ensayo clínico y predominio oral (espasticidad). |
| **Reacción hemolítica transfusional aguda** | No existe itemid de Coombs ni de pruebas cruzadas en los 1 650 de `d_labitems`; `52157` y `52105` con **cero filas**. Solo score exploratorio ≥2/3, que nunca descarta. |
| **TRALI** | No separable de TACO ni del SDRA con dato estructurado. |
| **Nefritis intersticial aguda por fármacos** | 7 274 determinaciones de eosinófilos en orina, **todas sin `valuenum`**. |
| **Trombocitopenia inducida por heparina (confirmada)** | Sin anti-PF4 ni SRA en `d_labitems`. Solo «fenotipo 4Ts», con enriquecimiento medido ≈1,01× (nulo). |
| **Retiro accidental de sonda enteral / vesical** | 0 itemids de desplazamiento o salida accidental en 4 095 de `d_items`; `229352`/`229353` asimétricos 376 782 : 2 589. |
| **Perforación visceral por hallazgo de imagen** | Los itemids de imagen son `param_type='Processes'`: registran que el estudio se hizo, nunca el resultado. El hallazgo vive **solo en texto libre**. |
| **Nefropatía por contraste como etiqueta de referencia** | `N1411` y `N1419` con 0 registros (código creado en oct-2020). |
| **Sobredosis de opiáceos/benzodiacepinas por marcador objetivo** | No hay nivel sérico de rutina: solo el **antídoto** como sustituto indirecto. Distinguir de digoxina, litio, vancomicina, gentamicina, que **sí** tienen nivel medible. |

### 6.2 No validables por límite de cobertura (el dato existe, pero no donde hace falta)

- **Todo evento en las 460 786 admisiones sin estancia en UCI**, para cualquier regla basada en `chartevents`, `procedureevents`, `inputevents`, `outputevents` o `datetimeevents` (84,4 % de la base).
- **Glucometría capilar de hospitalización general y de urgencias**: no existe en MIMIC-IV en ninguna tabla. R-MET-04c mide **UCI, no hospital**.
- **Úlcera por presión aparecida antes del ingreso a UCI o después del alta de UCI** (61,3 % de las admisiones con UCI siguen hospitalizadas >48 h tras salir, mediana 70,3 h).
- **Caídas fuera de UCI**: la única fuente clínica (`225474`) es de UCI; la administrativa es circular y está dominada por caídas comunitarias (82,8 % con paso por urgencias, 46,4 % con diagnóstico principal traumático).
- **Extravasación/infiltración fuera de UCI.**
- **Transfusión fuera de UCI**: solo 19 709 admisiones (3,6 %) tienen algún hemoderivado en `inputevents`; en planta la transfusión no existe como registro fechado.
- **Ventilación iniciada en quirófano, urgencias u otro centro**: 6 389 admisiones con vía aérea documentada solo en `chartevents`, sin ninguna fila en `procedureevents`.

### 6.3 Validables solo parcialmente (se detecta el sustituto, no el evento)

| Evento etiquetado | Lo que realmente mide la regla |
|---|---|
| CLABSI | Bacteriemia nosocomial **en portador** de catéter venoso central |
| CAUTI | ITU asociada a sonda **sin umbral de UFC** (`quantity` no nulo en 182 de 3 988 224 filas = 0,005 %) |
| NAV | **PVAP** del algoritmo VAE de NHSN (sin criterio radiológico) |
| Pancreatitis post-CPRE | **Hiperamilasemia/hiperlipasemia tardía** post-CPRE (el criterio clínico de Cotton —dolor nuevo, prolongación del ingreso— no es verificable) |
| Sobredosis de insulina | **Hipoglicemia severa asociada a medicamento hipoglucemiante** (el numerador CMS admite antidiabéticos orales) |
| Daño renal por fármaco | **LRA con exposición concurrente a nefrotóxicos** (con polifarmacia la atribución a un fármaco no es posible) |
| HAPU | Lesión por presión **documentada en UCI con línea base negativa**, ~2 000 admisiones (no 5 053) |

### 6.4 Eventos ausentes del catálogo que MIMIC-IV sí permitiría aproximar

**Infección de sitio quirúrgico** (una de las IAAS más frecuentes y notificable en el Anexo 02 GG-ESSALUD-2021) y **candidemia** como evento propio. Ambos son huecos de cobertura, no limitaciones del dato: `procedures_icd` con fecha, `services` quirúrgicos y cultivos de herida/tejido/absceso están disponibles, y la candidemia se recupera sin más que ampliar `test_itemid` en R-INF-01c.

---

## 7. Limitación transversal que condiciona toda la tesis

`diagnoses_icd` **no tiene fecha ni bandera de present-on-admission** (columnas verificadas: `subject_id, hadm_id, seq_num, icd_code, icd_version`) y la codificación responde a la facturación. Consecuencias que deben declararse una sola vez y aplicar a **todas** las familias:

1. Ningún código diagnóstico puede usarse como **patrón de oro**; solo como marco de muestreo estratificado para la revisión manual, que es el único patrón de referencia legítimo.
2. La discriminación POA/adquirido debe hacerse **siempre** por orden temporal frente a un anclaje causal (primera administración, fecha de procedimiento, primera determinación del episodio incluida la de urgencias), nunca por código.
3. Los códigos de procedimiento asignados por un codificador **que leyó la epicrisis** (PSI 15, reapertura quirúrgica, revisión de dispositivo) son **parcialmente circulares** respecto al detector de texto y su concordancia no es evidencia de validez externa. Deben reportarse como tales.