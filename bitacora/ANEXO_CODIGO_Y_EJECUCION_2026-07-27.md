# Anexo — Código, ejecución y salidas reales

**Tesis MIA-303 · Detección automatizada de eventos adversos hospitalarios**
**Carlos Pérez Pérez · Maestría en Inteligencia Artificial, UNI**
**Sesión del 26–27 de julio de 2026**

> Documento complementario de la bitácora, destinado a la revisión del código.
> Para cada experimento se incluye: el objetivo, el fragmento de código que
> toma la decisión metodológica, el comando exacto con que se ejecutó, la
> **salida literal de consola** —copiada del log, sin editar— y la lectura del
> resultado. Todo es reproducible desde los archivos indicados.

---

## 1. Entorno de ejecución

| | |
|---|---|
| Equipo | HP Victus 16 · 12 hilos · 15.6 GB RAM |
| GPU | NVIDIA GeForce GTX 1650, 4 GB (Turing, sin Tensor Cores) |
| Sistema | Windows 11 |
| Intérprete | Python 3.13 · entorno aislado `T:\MIMIC\.venv-gpu` |
| Librerías | scikit-learn, pandas, pyarrow, numpy · torch 2.13.0+cu126, transformers |
| Datos | MIMIC-IV-Note v2.2 + MIMIC-IV hosp v3.1 (acceso credencializado PhysioNet) |
| Ubicación | `T:\MIMIC\` (disco NVMe dedicado; ver §7) |

El entorno se creó aislado y **no** sobre la instalación base de Anaconda, para
no comprometer el único intérprete sano del equipo:

```bash
"C:\ProgramData\Anaconda3\python.exe" -m venv T:\MIMIC\.venv-gpu
T:\MIMIC\.venv-gpu\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126
T:\MIMIC\.venv-gpu\Scripts\python.exe -m pip install transformers accelerate sentence-transformers chromadb pandas pyarrow scikit-learn duckdb
```

Verificación de la GPU:

```
torch 2.13.0+cu126 | numpy 2.5.1 | cuda True
```

---

## 2. Mapa de los scripts

Todos en `T:\MIMIC\tesis\04_pipeline_codigo\`, salvo el último.

| Script | Qué resuelve | Duración real |
|---|---|---|
| `fase3_v2_tier_a_corregido.py` | Bug de formato en los códigos CIE-10 | 22 min |
| `fase3_v2_corpus_completo.py` | Corpus completo + ablación de la ventana del patrón | 17 h 23 min *(interrumpido)* |
| `fase3_v2_reanudar.py` | Reanudación desde el checkpoint | 32 min |
| `fase4_v2_etiqueta_a1.py` | OE2 con etiqueta no circular + curva de escalabilidad | 2 h 46 min |
| `fase4_v3_umbral_calibrado.py` | Calibración de umbrales *(intento fallido)* | 8 min |
| `fase4_v4_clase_negativa.py` | Detector binario con clase negativa | 19 min |
| `fase4_v5_punto_operacion.py` | Elección del punto de operación | 2 min |
| `05_prototipo_app/motor_v2.py` | Cadena texto → detección → GEMSES → responsable | — |

---

## 3. Experimento 1 — el bug del punto en los códigos CIE-10

### Objetivo

El Tier A (códigos CIE-10) aportaba solo 229 notas al corpus, el 1.5%.
Averiguar por qué.

### El diagnóstico, en una comparación

```python
# El mapeo guarda los codigos CON punto:
['A04.7', 'A41.0', 'A41.5', 'A41.8', 'A41.9', 'B44.1', 'B95', 'B96.5']
# con punto: 201 de 223

# MIMIC-IV los guarda SIN punto:
['A021', 'A031', 'A045', 'A047', 'A0471', 'A0472', 'A048', 'A049']
# con punto: 0 de 200,000
```

El `JOIN d.icd_code = c.icd_code` del script original solo podía acertar con
los 22 códigos de tres caracteres, y de esos coincidían cuatro.

### El código que lo corrige

```python
def cargar_mapping():
    """codigo_sin_punto -> (naturaleza, evento, severidad, estrato, original)"""
    mapping = {}
    with open(PATH_MAPPING, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            orig = (row.get("codigo_icd10") or "").strip()
            if not orig:
                continue
            clave = orig.replace(".", "").upper()          # <-- EL ARREGLO
            estrato = "A1" if clave.startswith(PREFIJOS_CAUSALES) else "A2"
            mapping[clave] = (...)
    return mapping
```

La coincidencia se hace **por prefijo**, no por igualdad, porque MIMIC usa
códigos más específicos que el mapeo (`A047` → `A0471`, `A0472`), que es la
jerarquía normal de CIE-10:

```python
for p in prefijos:
    m = cod10.str.startswith(p)
```

### La estratificación A1 / A2

Al corregir el formato apareció un segundo problema: los códigos que más
aportan son **condiciones**, no eventos adversos. `diagnoses_icd` de MIMIC-IV
**no trae bandera de present-on-admission**, así que una neumonía puede ser el
motivo de ingreso y no un daño causado por la atención. Por eso se separan:

```python
# Familias CIE-10 cuya semantica imputa el dano a la atencion sanitaria
PREFIJOS_CAUSALES = (
    "T80", "T81", "T82", "T83", "T84", "T85", "T86", "T88",   # complicaciones de la atencion
    "Y63", "Y65", "Y83", "Y84",                                # errores e incidentes asistenciales
    "W00", "W01", "W06", "W07", "W08", "W10", "W13", "W18", "W19",  # caidas
    "L89",                                                     # ulcera por presion
)
```

### Comando

```bash
python fase3_v2_tier_a_corregido.py
```

### Salida real

```
[23:00:34] [+0:00:00] Mapeo: 223 codigos unicos - A1 causal 73 - A2 condiciones 150
[23:00:34] [+0:00:00] Indexando diagnoses_icd.csv.gz por prefijo ...
[23:23:06] [+0:22:31] 6,364,488 diagnosticos - 545,497 hospitalizaciones
[23:23:06] [+0:22:31] metodo ORIGINAL (con punto): 411 hospitalizaciones
[23:23:06] [+0:22:31] metodo CORREGIDO (prefijo) : 109,714 hospitalizaciones
[23:23:06] [+0:22:31] Recorriendo epicrisis (solo columnas de id, sin texto) ...

========================================================================
TIER A CORREGIDO - antes y despues
========================================================================
Hospitalizaciones, metodo original  :      411
Hospitalizaciones, metodo corregido :  109,714   (266.9x)
------------------------------------------------------------------------
A1 causal explicito :  18,989 notas  (24,400 detecciones, 6 naturalezas)
A2 condiciones      :  53,375 notas  (87,460 detecciones, 7 naturalezas)
------------------------------------------------------------------------

A1 - top naturalezas:
naturaleza
Procedimiento           8667
Cuidado del paciente    7550
Dispositivo             2994
Infeccion nosocomial    2417
Sistema/Organizacion     288
Medicacion               209
```

### Lectura

**411 → 109,714 hospitalizaciones: factor 267×.** El Tier A nunca falló
conceptualmente; falló por un punto.

El estrato A1 cubre **35,618 hospitalizaciones, el 6.53% del total**, cifra
compatible con el ~9% de incidencia de la literatura (de Vries et al., 2008) —
algo por debajo, que es justamente el subregistro documentado de la
codificación administrativa. Esa concordancia es la validación externa de que
A1 mide lo que dice medir.

**A1 aporta 18,989 notas, más que el corpus completo anterior (14,853), y es
casi disjunto de él**: la intersección es de 1,196 notas, el 6.3%.

---

## 4. Experimento 2 — ablación de la ventana del patrón

### Objetivo

Los patrones del Tier B se compilaban con `re.DOTALL`, lo que permite que un
comodín `.*` atraviese la epicrisis entera. Medir cuánto cambia la detección
al acotarlo.

### El código de la corrección

```python
def acotar(patron: str, n: int = VENTANA_PATRON) -> str:
    return patron.replace(".*", ".{0," + str(n) + "}")

def compilar_variantes():
    """Dos versiones del mismo conjunto de patrones, para comparar."""
    variantes = {"laxo": {}, "acotado": {}}
    for clave, val in TIER_B_PATRONES.items():
        nat, ev, sev, rx = val[0], val[1], val[2], val[-1]
        variantes["laxo"][clave]    = (nat, ev, sev, re.compile(rx, re.I | re.DOTALL))
        variantes["acotado"][clave] = (nat, ev, sev, re.compile(acotar(rx), re.I))
    return variantes
```

Una sola lectura del `.gz` alimenta ambas variantes, de modo que la
comparación es exacta: mismas notas, mismo orden, misma negación.

### Comando

```bash
python fase3_v2_corpus_completo.py     # murio al 78.4%
python fase3_v2_reanudar.py            # completo el resto
```

### Salida real de la reanudación

```
[17:07:11] [+0:00:00] Checkpoint: 260,000 epicrisis ya procesadas (78.4%)
[17:07:11] [+0:00:00] Conteos previos - laxo 203,152 - acotado 73,998
[17:07:11] [+0:00:00] Faltan 71,793 epicrisis
[17:07:13] [+0:00:01] Saltando los primeros 260,000 registros del .gz ...
[17:07:35] [+0:00:24]   saltadas 240,000/260,000
[17:16:14] [+0:09:03] 280,000/331,793 ( 84.4%) | nuevas: laxo 16,316 - acotado  6,049 | ETA 0:23:28
[17:34:21] [+0:27:10] 320,000/331,793 ( 96.4%) | nuevas: laxo 46,523 - acotado 16,740 | ETA 0:05:20
[17:39:37] [+0:32:26] 331,793/331,793 (100.0%) | nuevas: laxo 55,519 - acotado 19,924 | ETA 0:00:00

========================================================================
ABLACION DE LA VENTANA DEL PATRON - RESULTADO SOBRE EL CORPUS COMPLETO
========================================================================
Epicrisis procesadas : 331,793 de 331,793 (100.0%)
------------------------------------------------------------------------
  Variante LAXA (re.DOTALL, original) :  258,671 detecciones
  Variante ACOTADA (ventana 100 car.) :   93,922 detecciones
  Reduccion al acotar                 :  164,749 (63.7%)
------------------------------------------------------------------------
Total 0:32:26
```

### La verificación que confirma el diagnóstico

Si la hipótesis es correcta —el problema es el alcance del comodín y no la
especificidad de los patrones—, entonces los patrones **sin** `.*` no deben
cambiar en absoluto. Se comprobó separándolos:

```python
tb = ast.literal_eval(...)                      # los 35 patrones originales
tiene_wild = {k: ('.*' in v[-1]) for k, v in tb.items()}
df['tiene_.*'] = [tiene_wild.get(i, False) for i in df.index]
df['cambio_%'] = (100 * (df.acotado - df.laxo) / df.laxo).round(1)
```

Salida real:

```
=== patrones CON .* (afectados) ===
                           laxo  acotado  cambio_%
hipoglicemia_insulina      9382       96     -99.0
falla_dispositivo          5263       63     -98.8
quemadura_paciente         3433       61     -98.2
complicacion_anestesia     1242       50     -96.0
infeccion_cateter_central  1011       58     -94.3
hemorragia_postoperatoria  1020      121     -88.1
anticoagulacion_excesiva   6145     1016     -83.5
neumonia_ventilador        2187      481     -78.0
infeccion_sitio_qx         8376     2515     -70.0

=== patrones SIN .* (no deberian cambiar) ===
                           laxo  acotado  cambio_%
infeccion_clostridium      4337     4337       0.0
bacteriemia                3645     3645       0.0
infeccion_mrsa             3299     3299       0.0
ulcera_presion              973      973       0.0
reaccion_transfusional      207      207       0.0
error_medicacion_dosis      185      185       0.0

resumen: con .* -> 42330 a 6735
         sin .* -> 13189 a 13189
```

### Lectura

**Cero variación en los patrones sin comodín. Ni una detección de diferencia.**
Eso demuestra que no se trataba de una baja especificidad general de los
patrones, sino de un **defecto de alcance**. Los construidos con alternativas
literales siempre midieron bien.

El caso extremo: `hipoglicemia_insulina` pasó de 9,382 detecciones a 96. Las
9,286 restantes eran notas donde «blood glucose», «low» e «insulin» aparecían
en párrafos distintos, sin relación entre sí.

---

## 5. Experimento 3 — OE2 con etiqueta no circular

### Objetivo

La auditoría previa mostró que el 99% de las etiquetas son subcadena del
texto: la etiqueta la produce el mismo regex que se aplica al texto. Reentrenar
el **mismo modelo** sobre la **misma fuente**, cambiando **una sola variable**:
la etiqueta.

### El código: control de fuga y robustez entre géneros

```python
def construir_vectorizador():
    """
    Palabra + caracter. Los n-gramas de CARACTER son la pieza que da
    robustez entre generos documentales (queja / reporte / epicrisis /
    evolucion): no dependen de la segmentacion en palabras ni del registro.
    """
    return FeatureUnion([
        ("palabra",  TfidfVectorizer(max_features=60000, ngram_range=(1, 2), ...)),
        ("caracter", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), ...)),
    ])

# Division POR PACIENTE, nunca por nota: evita que el mismo paciente
# aparezca en entrenamiento y prueba.
gss = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SEED)
tr, te = next(gss.split(txt, Y, groups=df["subject_id"]))
```

Intervalo de confianza por remuestreo, no asintótico:

```python
def ic_bootstrap(y_true, y_pred, n=200, seed=SEED):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, y_true.shape[0], y_true.shape[0])
        vals.append(f1_score(y_true[idx], y_pred[idx], average="macro", zero_division=0))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))
```

### Comando

```bash
python fase4_v2_etiqueta_a1.py
```

### Salida real

```
[09:39:48] A1: 18,989 notas - 14,005 pacientes
[09:40:24] Texto recuperado para 18,989/18,989 notas
[09:40:25] Multietiqueta: 15.1% de las notas

=== Modelo principal: etiqueta A1, texto completo ===
A1 texto completo      F1-macro 0.526 [0.498-0.555] - F1-micro 0.769 - exact-match 0.634 - train 15,288 / test 3,701

=== Escalabilidad: degradacion segun longitud del texto ===
truncado a 120 caracteres  F1-macro 0.214 [0.204-0.221] - F1-micro 0.277
truncado a 500 caracteres  F1-macro 0.420 [0.402-0.441] - F1-micro 0.666
truncado a 2000 caracteres F1-macro 0.433 [0.418-0.459] - F1-micro 0.703
truncado a completo        F1-macro 0.526 [0.498-0.555] - F1-micro 0.769
```

### Lectura, con su límite

```
Etiqueta regex (circular)     F1-macro = 0.515
Etiqueta A1  (no circular)    F1-macro = 0.526   IC95 [0.498-0.555]
```

**La comparación no es pareja y no debe presentarse como tal**: 0.515 era sobre
14,853 notas y 8 clases; 0.526 es sobre 18,989 notas y 6 clases, y un menor
número de clases infla el F1-macro. El delta de +0.011 no es concluyente.

Lo que sí puede afirmarse: *un modelo léxico recupera del texto, con F1-macro
0.526, una etiqueta que no proviene del texto sino de un codificador clínico
humano*. Eso es evidencia de aprendizaje real. La afirmación inversa —que el
0.515 anterior no era circular— **no** se sostiene.

**La curva de escalabilidad** responde al requisito de que el sistema acepte
cualquier texto: a 120 caracteres, la mediana de un reporte de incidente, el
F1 cae un 60%. El pipeline **no transfiere directamente** a géneros breves.

Y un hallazgo lateral: entre 500 y 2,000 caracteres apenas hay mejora (0.420 →
0.433), pero de 2,000 al texto completo salta a 0.526. **Truncar a 512 tokens
cuesta ~18% del F1-macro**, lo que sustenta con medición propia la necesidad de
segmentación por fragmentos o modelo de contexto largo.

---

## 6. Experimento 4 — el intento que falló, y por qué se conserva

### Objetivo

El modelo disparaba una detección ante un texto de un solo carácter. Se
intentó corregir calibrando el umbral por clase.

### El código, con la precaución metodológica

Ajustar umbrales mirando el conjunto de prueba sería fuga. Se partió en tres,
**agrupando siempre por paciente**, y se verificó por aserción:

```python
idx_tr, idx_te  = split_por_paciente(df, Y, 0.20, SEED)
idx_fit, idx_val = split_por_paciente(sub_tr, Ytr_full, 0.20, SEED + 1)

p_fit, p_val, p_te = set(...), set(...), set(...)
assert not (p_fit & p_val) and not (p_fit & p_te) and not (p_val & p_te), \
    "FUGA: hay pacientes compartidos entre particiones"

# El umbral se busca SOBRE VALIDACION; la prueba se evalua una sola vez.
for j, c in enumerate(clases):
    for t in REJILLA:
        f1 = f1_score(Yval[:, j], (Dval[:, j] >= t).astype(int), zero_division=0)
```

### Salida real

```
BASE (umbral 0)        F1-macro 0.517
  Cuidado del paciente     umbral -0.10  (F1 en val 0.861)
  Dispositivo              umbral -0.10  (F1 en val 0.586)
  Infeccion nosocomial     umbral -0.15  (F1 en val 0.641)
  Medicacion               umbral -0.30  (F1 en val 0.473)
  Procedimiento            umbral -0.30  (F1 en val 0.800)
  Sistema/Organizacion     umbral -0.50  (F1 en val 0.175)
CALIBRADO              F1-macro 0.547  (delta +0.030)

  «.                                 » base=1 calibrado=2
  «                                  » base=0 calibrado=2
  «ok                                » base=0 calibrado=2
  «Paciente estable, sin novedad.    » base=0 calibrado=1
```

### Lectura

El F1-macro mejoró (+0.030) y se rescató una clase que estaba en cero. **Pero
el objetivo original empeoró**: todos los umbrales óptimos resultaron
negativos, porque al maximizar F1 por clase el criterio se vuelve *más*
permisivo. Ganar recall en clases minoritarias y rechazar texto vacío son
objetivos en tensión.

**El diagnóstico es lo valioso.** El corpus A1 contiene únicamente epicrisis
que tienen al menos un evento codificado: **el modelo nunca vio un ejemplo
negativo**. No aprendió «¿hay un evento?» sino «¿de qué naturaleza es el evento
que sé que hay?». Ningún umbral puede corregirlo, porque la clase «sin evento»
no existe en el espacio de salida.

Se conserva el experimento porque el fallo condujo al defecto de diseño real.

---

## 7. Experimento 5 — detector con clase negativa

### El código: definición de los negativos

```python
# Negativo = hospitalizacion SIN NINGUN codigo del mapeo, ni A1 ni A2.
# Se excluyen los A2 a proposito: son ambiguos (pueden ser motivo de
# ingreso) y usarlos como negativos introduciria ruido de etiqueta.
ch = ch[~ch["hadm_id"].isin(hadm_con_codigo)]

# Ningun paciente puede estar en ambos lados
neg = neg[~neg["subject_id"].isin(pac_pos)]
```

### El código: corrección por prevalencia

```python
def vpp_corregido(sens, esp, prev=PREV_REAL):
    """Valor predictivo positivo a prevalencia real (Bayes)."""
    num = sens * prev
    den = num + (1 - esp) * (1 - prev)
    return num / den if den else 0.0
```

### Comando y salida real

```bash
python fase4_v4_clase_negativa.py
```

```
[18:05:21] Positivos: 18,989
[18:05:56] Negativos: 37,978
[18:05:56]   descartados 4,414 negativos de pacientes que ya son positivos
[18:05:59] Dataset binario: 52,553 notas (36.1% positivas)
[18:05:59] train 42,109 - test 10,444 (sin pacientes compartidos)
[18:24:35] Sensibilidad 0.907 - Especificidad 0.917 - Precision 0.856 - F1 0.881 - AUC 0.973
[18:24:35] VPP corregido a prevalencia real (6.53%): 0.433

Prueba de abstencion ante textos triviales:
  «.                                             » margen -1.71 -> se abstiene
  «                                              » margen -0.99 -> se abstiene
  «ok                                            » margen -0.67 -> se abstiene
  «Paciente estable, sin novedad.                » margen -0.84 -> se abstiene
  «Routine follow up visit. Vital signs stable. N» margen -1.31 -> se abstiene
  «Patient admitted for elective knee replacement» margen -0.67 -> se abstiene

Abstencion ante textos triviales: 6/6
```

### Lectura

El defecto queda cerrado: **6 de 6**, con margen holgado. Se confirma que la
causa era la ausencia de clase negativa y no el umbral.

**La cifra que corresponde citar es 0.433, no 0.856.** El conjunto de prueba
tiene 36.1% de positivos por construcción, pero la prevalencia real es 6.53%.
De cada 100 alertas sobre el flujo real, unas 43 serían correctas. No es un mal
resultado: es el propio de una herramienta de **tamizaje**, cuya salida va a un
revisor humano y no a una acción automática.

---

## 8. Experimento 6 — punto de operación, y un criterio que salió mal

### El principio

```python
# Con prevalencia p = 6.53%:
#   VPP = (sens·p) / (sens·p + (1-esp)·(1-p))
# El termino de falsos positivos va multiplicado por 0.9347 y el de
# verdaderos positivos por 0.0653: el error en la clase mayoritaria pesa
# catorce veces mas.
```

Salida real de la demostración numérica:

```
   sens 0.907 - esp 0.917 fija -> VPP 0.433
   sens 0.950 - esp 0.917 fija -> VPP 0.444
   sens 0.990 - esp 0.917 fija -> VPP 0.455
   sens 1.000 - esp 0.917 fija -> VPP 0.457     <- deteccion perfecta
   sens 0.907 fija - esp 0.950 -> VPP 0.559
   sens 0.907 fija - esp 0.970 -> VPP 0.679
   sens 0.907 fija - esp 0.980 -> VPP 0.760
```

**Aunque la sensibilidad fuera perfecta, el VPP subiría de 0.433 a 0.457.** A
prevalencia baja, un punto de especificidad vale del orden de diez de
sensibilidad. Es el principio clásico del cribado poblacional.

### La curva de operación

```
 umbral    sens     esp  VPP real  alertas/ano   /dia  captados  vs hoy
------------------------------------------------------------------------------------
    0.0   0.907   0.917     0.433       70,429    193    30,526   2.14x
    0.3   0.821   0.955     0.558       49,503    136    27,628   1.94x
    0.6   0.705   0.977     0.680       34,911     96    23,724   1.66x
    0.9   0.555   0.991     0.804       23,238     64    18,678   1.31x
    1.2   0.381   0.997     0.887       14,465     40    12,827   0.90x
    1.5   0.237   0.998     0.910        8,747     24     7,963   0.56x
```

### El criterio automático dio una respuesta degenerada

Se codificó así:

```python
# Criterio: maximizar VPP sujeto a captar mas eventos que los que EsSalud
# notifica hoy. Sin esa restriccion el optimo trivial es un umbral altisimo
# que casi no emite alertas: precision perfecta y utilidad nula.
viables = curva[curva["eventos_captados_ano"] > NOTIFICADOS_HOY]
rec = viables.loc[viables["vpp_prevalencia_real"].idxmax()]
```

Y eligió **umbral +1.1**: VPP 0.869, pero captando 14,609 eventos, apenas
**1.02×** lo que EsSalud ya notifica.

**Ese resultado hay que rechazarlo, y conviene explicar por qué.** El
optimizador se pegó al borde de la restricción: maximizó la precisión
entregando el mínimo de detección permitido. Un sistema así tendría una
precisión excelente y **no reduciría el subregistro en absoluto** — que es el
problema que motiva toda la tesis.

El fallo no está en el código sino en el criterio: fue mal especificado. La
restricción «captar más que hoy» es demasiado débil cuando el objetivo real es
*reducir el subregistro de forma significativa*.

### El punto defendible

Con una restricción coherente con el objetivo de la tesis —captar al menos
1.5× lo que se notifica hoy— el punto es **umbral +0.6**:

| | Umbral 0.0 | **Umbral +0.6** |
|---|---|---|
| Sensibilidad | 0.907 | 0.705 |
| Especificidad | 0.917 | **0.977** |
| **VPP a prevalencia real** | 0.433 | **0.680** |
| Alertas/año | 70,429 | **34,911** |
| Alertas/día | 193 | **96** |
| Eventos captados | 30,526 | 23,724 |
| Frente a la notificación actual | 2.14× | **1.66×** |

Sube la precisión de 43 a 68 aciertos por cada 100 alertas, **reduce la carga
de revisión a la mitad** y sigue detectando un 66% más de eventos que el
sistema vigente.

La elección final es una decisión institucional, no estadística: depende de
cuánta carga de revisión pueda absorber la organización. Lo que sí es técnico
es presentar la curva completa para que esa decisión se tome informada.

---

## 9. Una advertencia sobre el VPP: es un suelo, no el valor verdadero

Los falsos positivos se cuentan contra códigos CIE-10. Pero la premisa central
de esta tesis es que **la codificación administrativa subregistra los eventos
adversos** — de hecho el estrato A1 mide 6.53% frente al ~9% de la literatura.

Entonces, cuando el modelo marca una epicrisis sin código, hay dos
posibilidades: se equivocó, **o detectó un evento real que nadie codificó**.

Si una fracción de los ~40,000 falsos positivos anuales fueran eventos
verdaderos no codificados, la especificidad real sería mayor y el VPP también.

**Cómo se comprueba:** revisión experta de una muestra aleatoria de falsos
positivos. Ahí es donde la muestra de oro de 350 notas cobra sentido, y ya no
como validación genérica sino respondiendo una pregunta precisa. Si el 30% de
los falsos positivos resultaran eventos reales, el VPP subiría de 0.433 a cerca
de 0.60 **sin tocar el modelo**, y de paso se mediría el subregistro de la
codificación, que es la tesis misma. Un experimento, dos resultados.

---

## 10. Cronología real de ejecución, con las interrupciones

| Momento | Suceso |
|---|---|
| 26-jul 22:51 | Arranca la ablación sobre las 331,793 epicrisis |
| 26-jul 23:23 | Termina el Tier A corregido (22 min) |
| 26-jul 23:40 → 27-jul 09:21 | **La laptop se suspende.** El trabajo salta del bloque 2 al 4 |
| 27-jul 09:39 | Arranca el OE2 con etiqueta A1 |
| 27-jul 12:25 | Termina (2 h 46 min; lento por competir con la ablación) |
| 27-jul 16:27 | **Cierre iniciado por el sistema (evento 1074).** Muere la ablación al 78.4%, tras 17 h 23 min |
| 27-jul 17:07 | Reanudación desde el checkpoint |
| 27-jul 17:39 | Ablación completa al 100% (32 min) |
| 27-jul 18:24 | Detector con clase negativa |
| 27-jul 18:43 | Curva de operación |

**Sobre la reanudación.** Al ir a relanzar el proceso muerto se descubrió que
el script escribía `progreso.json` en cada bloque pero **nunca lo leía**: la
reanudación anunciada en su documentación no estaba implementada. Peor, las
filas de detección se acumulaban solo en memoria. Relanzarlo habría costado
unas 20 horas.

Se escribió `fase3_v2_reanudar.py`, que sí lee el checkpoint, salta el tramo
hecho en 24 segundos y **persiste las filas en disco en cada bloque**:

```python
# checkpoint en CADA bloque: un nuevo corte ya no pierde nada
f_lax.flush(); f_aco.flush(); f_ta.flush()
ruta_prog.write_text(json.dumps({
    "notas_vistas": total_vistas,
    "laxo": conteo_previo["laxo"] + nuevos["laxo"],
    "acotado": conteo_previo["acotado"] + nuevos["acotado"],
}, indent=2), encoding="utf-8")
```

Las 71,793 epicrisis restantes se completaron en 32 minutos.

**Limitación derivada, que debe declararse:** los conteos de la ablación cubren
las 331,793 epicrisis y son válidos, porque provienen del mismo código
determinista sobre el mismo corpus. Pero las filas a nivel de nota solo existen
para el tramo reanudado (21.6% del corpus); las del primer tramo se perdieron.
Las comparaciones patrón por patrón de la §4 se calculan sobre ese tramo.

### Sobre la infraestructura

El SSD del equipo registra **7,278 errores de bloque defectuoso en siete días**.
Se instaló un NVMe adicional de 1 TB y se migró la totalidad del proyecto
—48,016 archivos, verificados uno a uno— a la unidad nueva. Fue necesario
actualizar 27 scripts con rutas absolutas escritas a mano; sin ese paso nada
habría vuelto a ejecutarse.

---

## 11. Cómo reproducir

```bash
# 1. Corregir el Tier A y estratificar A1/A2
python fase3_v2_tier_a_corregido.py

# 2. Ablacion de la ventana del patron sobre el corpus completo
python fase3_v2_corpus_completo.py
python fase3_v2_reanudar.py          # solo si el anterior se interrumpe

# 3. OE2 con etiqueta no circular + curva de escalabilidad
python fase4_v2_etiqueta_a1.py

# 4. Calibracion de umbrales (intento fallido, se conserva)
python fase4_v3_umbral_calibrado.py

# 5. Detector con clase negativa
python fase4_v4_clase_negativa.py

# 6. Punto de operacion
python fase4_v5_punto_operacion.py

# 7. Cadena completa de punta a punta
cd ../05_prototipo_app && python motor_v2.py
```

Todas las semillas están fijadas en 42. Los scripts reutilizan los `.parquet`
intermedios si ya existen, de modo que una segunda ejecución no repite la parte
cara.

### Dónde están las salidas

| Carpeta | Contenido |
|---|---|
| `datos_intermedios/fase3_v2/` | Tier A corregido, ablación, filas por variante |
| `datos_intermedios/fase4_v2/` | Dataset A1, modelo, métricas, curva por longitud |
| `datos_intermedios/fase4_v3/` | Umbrales calibrados, métricas antes y después |
| `datos_intermedios/fase4_v4/` | Dataset binario, detector, prueba de abstención |
| `datos_intermedios/fase4_v5/` | Curva de operación, punto recomendado |

Los datos y modelos **no** están bajo control de versiones, por el acuerdo de
uso de MIMIC-IV y por la Ley 29733 en el caso de la base ERSP de EsSalud.

---

*Anexo cerrado el 27 de julio de 2026.*
