# Fase 4 (OE2) — Resultados preliminares del piloto NLP

**Tarea:** clasificar la *naturaleza* del evento adverso (8 clases del Anexo 02
con soporte suficiente) a partir del texto de la nota de alta de MIMIC-IV.
**Etiqueta:** supervisión débil derivada del pipeline Fase 3 (Tier A ICD-10 +
Tier B patrones de texto). **No hay anotación humana todavía** (las 350 notas del
*gold standard* siguen pendientes).

> Estas cifras son de una **prueba de concepto**. Por la circularidad de la
> etiqueta (ver Limitaciones) miden **consistencia con la regla débil**, no
> validez clínica. El número clínicamente válido se obtendrá contra el *gold*
> humano en el piloto.

## 1. Comparación de modelos (OE2)

Dataset: 14 853 notas · 12 785 pacientes · 8 clases. Split estratificado 80/20,
semilla 42. TF-IDF palabra (1–2), 30 000 features, `class_weight="balanced"`.

| Modelo | Accuracy | F1-ponderado | F1-macro | Kappa |
|---|---|---|---|---|
| **TF-IDF + LinearSVC** | **0.71** | **0.71** | 0.46 | **0.55** |
| TF-IDF + LogReg | 0.62 | 0.64 | 0.45 | 0.46 |
| ClinicalBERT (congelado) + LogReg¹ | 0.38 | 0.43 | 0.19 | 0.18 |

¹ Bio_ClinicalBERT como extractor de rasgos (sin *fine-tuning*, por CPU) sobre
submuestra estratificada de 2 499 notas, evaluado en el mismo split que su baseline
(TF-IDF+LinearSVC = 0.65 acc en esa submuestra).

**Lectura:** en una tarea cuyo objetivo se define por patrones léxicos, el modelo
léxico (TF-IDF) domina. ClinicalBERT congelado capta semántica pero no reproduce
los disparadores exactos que definen la etiqueta; requeriría *fine-tuning* (GPU)
para competir. Esto se propone como trabajo del piloto.

## 2. Robustez (validación cruzada 5-fold, split por nota)

| Modelo | Accuracy (media ± desv) | F1-ponderado | F1-macro | Kappa |
|---|---|---|---|---|
| LogReg | 0.628 ± 0.009 | 0.650 ± 0.009 | 0.466 | 0.474 |
| LinearSVC | 0.719 ± 0.009 | 0.717 ± 0.009 | 0.499 | 0.561 |
| **LinearSVC + char n-gramas** | **0.731 ± 0.007** | **0.729 ± 0.007** | **0.515** | **0.581** |

La baja varianza (±0.01) indica que las cifras son estables ante el remuestreo.
Añadir char n-gramas (3–5, `char_wb`) a la config de palabra mejora todas las
métricas (+1.3 pts de accuracy, +1.6 de F1-macro), coherente con la morfología y
las abreviaturas del texto clínico. **LinearSVC + char es la mejor configuración.**

## 3. Análisis de sensibilidad: fuga por paciente

La auditoría metodológica señaló que el split por nota permite que notas de un
mismo paciente caigan en train y test (24.0 % de las notas están expuestas).
Se rehízo el experimento con **split a nivel de paciente** (`GroupShuffleSplit`
por `subject_id`):

| Métrica | Split por nota (con fuga) | Split por paciente (honesto) | Δ |
|---|---|---|---|
| Accuracy | 0.7075 | 0.7252 | +0.018 |
| F1-ponderado | 0.7057 | 0.7234 | +0.018 |
| F1-macro | 0.4638 | 0.4919 | +0.028 |
| Kappa | 0.5451 | 0.5701 | +0.025 |

CV agrupada por paciente (5-fold, `StratifiedGroupKFold`):
**accuracy 0.714 ± 0.004 · F1-macro 0.492 ± 0.018 · kappa 0.555 ± 0.006.**

**Hallazgo clave:** corregir la fuga por paciente **no degradó** el desempeño
(varió < 2 puntos, dentro del ruido). Es decir, la fuga por paciente **no era la
amenaza dominante**. La limitación que sí sostiene el resultado es la
**circularidad** de la etiqueta débil, que es *invariante al split*: ninguna
partición la corrige, solo la anotación humana independiente.

## 4. Cuantificación de la circularidad (experimento de enmascaramiento)

Para medir cuánto del desempeño depende de los disparadores léxicos que generaron
la etiqueta, se reentrenó tras **enmascarar los 35 patrones Tier B**
(`re.sub` → ` __MASK__ `) sobre el texto. Split por paciente, misma semilla.

| Métrica | A: texto original | B: disparadores enmascarados | Caída A→B |
|---|---|---|---|
| Accuracy | 0.7252 | 0.7117 | **0.0135** |
| F1-ponderado | 0.7234 | 0.7100 | 0.0134 |
| F1-macro | 0.4919 | 0.4859 | 0.0060 |
| Kappa | 0.5701 | 0.5486 | 0.0215 |

Se enmascaró al menos un disparador en el **64.1 %** de las notas (media 1.58
por nota). Pese a ello, el desempeño **apenas cayó 1.35 puntos** de accuracy.

**Interpretación (matiz importante):** el modelo **no** es un mero reproductor de
las regex — al quitar el disparador literal, se apoya en el **contexto léxico
co-ocurrente** y sostiene la predicción. Esto refina el hallazgo de la auditoría:
la circularidad es **estructural** (la etiqueta se deriva del texto, por lo que las
cifras no pueden citarse como validez clínica), pero **empíricamente el modelo
aprendió más que el disparador**: capturó la huella léxica distribuida de cada
tipo de evento. La caída de 1.35 puntos es la dependencia "dura" del disparador;
el residual es contexto que sigue sin validarse contra verdad clínica. Solo la
anotación humana de las 350 notas resuelve si esa huella coincide con el juicio
experto.

## 5. Reformulación multi-etiqueta (OneVsRest)

El baseline mono-clase toma la naturaleza *moda* por nota, pero el **30.9 % de las
notas tienen más de una naturaleza** (media 1.39 etiquetas/nota). Se replanteó la
tarea como **multi-etiqueta** (cada nota puede pertenecer a varias naturalezas),
con TF-IDF + `OneVsRest(LinearSVC)` y split por paciente.

| Métrica multi-etiqueta | Valor |
|---|---|
| F1-micro | 0.751 |
| F1-macro | 0.557 |
| F1-ponderado | 0.748 |
| F1-samples | 0.719 |
| Hamming loss | 0.084 |
| Exact-match (subset accuracy) | 0.511 |

F1 por etiqueta: Infección 0.82 · Medicación 0.81 · Dispositivo 0.62 ·
Procedimiento 0.61 · Cuidado 0.60 · Sistema/Org. 0.57 ·
Infección nosocomial 0.33 · Sangre/Hemoderivados 0.10.

**Lecturas:** (1) el *exact-match* de solo 0.51 confirma que la tarea es
genuinamente multi-etiqueta y que el número mono-clase (0.71) la sobre-simplificaba.
(2) Al no penalizar las co-ocurrencias, el **F1-macro sube a 0.557** (vs 0.499
mono-clase): el encuadre multi-etiqueta es más justo con las naturalezas
co-presentes. (3) El cuello de botella persistente son las **clases minoritarias**
(Sangre 0.10, Infección nosocomial 0.33) — un problema de escasez de datos, no de
formulación, que solo se resuelve con más ejemplos anotados.

## 6. Limitaciones y amenazas a la validez

Ver [`fase4_limitaciones_DRAFT.md`](fase4_limitaciones_DRAFT.md) (auditoría
adversarial: 26 hallazgos confirmados). Las principales:

1. **Circularidad etiqueta→texto** (estructural): 99 % de las etiquetas se
   derivan de patrones sobre el mismo texto. El experimento §4 muestra que la
   dependencia del disparador literal es baja (−1.35 pts al enmascararlo), pero
   la circularidad estructural persiste vía contexto, por lo que las cifras miden
   consistencia con la regla débil, no exactitud clínica.
2. **Sin *gold* humano** (crítica): las 350 notas siguen sin anotar; toda cifra
   mide consistencia con la regla, no exactitud clínica.
3. **Colapso multi-etiqueta→moda** (alta): 30.9 % de notas tienen varias
   naturalezas; tomar la moda es parcialmente arbitrario. Replantear como
   multi-etiqueta.
4. **F1-macro (0.46–0.49) es la métrica honesta**, no el F1-ponderado (0.71),
   por el desbalance; clases minoritarias (n=6, n=9 en test) sin poder
   estadístico.
5. **Validez externa** (crítica): entrenado en inglés (MIMIC), el objetivo es
   EsSalud en español → transferibilidad por demostrar (Fase 6, BETO).

## 7. Correcciones para el piloto

- Split por paciente (ya implementado) y CV agrupada como estándar.
- Anotar las 350 notas → *gold* humano; medir contra él, no contra la regla.
- Enmascarado de disparadores ya cuantificado (§4): entrenar sobre texto
  enmascarado para forzar aprendizaje por contexto, no por *trigger*.
- Reformulación multi-etiqueta ya evaluada (§5); adoptarla como formulación
  principal del piloto en vez del colapso a moda.
- Reportar F1-macro con intervalos de confianza; *fine-tuning* de ClinicalBERT con GPU.

---
*Generado por el pipeline Fase 4: `fase4_entrenar_baseline.py`,
`fase4_crossval.py`, `fase4_clinicalbert.py`, `fase4_split_paciente.py`.
Modelo/dataset no versionados (DUA MIMIC).*
