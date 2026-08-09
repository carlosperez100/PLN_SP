# PLN_SP — Procesamiento de Lenguaje Natural aplicado a la Seguridad del Paciente

**Trabajo final del curso MIA-10 · Procesamiento del Lenguaje Natural**
Maestría en Inteligencia Artificial — Universidad Nacional de Ingeniería (UNI)
Docente: Dr. Wester Zela Moraya · Autor: **Carlos Pérez Pérez**

> Repositorio **exclusivo del curso de PLN**. Reúne el código, los resultados y la
> explicación de la parte de procesamiento de lenguaje natural del proyecto
> *Detección Automática de Eventos Adversos Hospitalarios en Notas Clínicas*.

**🌐 Reporte en línea (sitio web): https://carlosperez100.github.io/PLN_SP/**

---

## 🎯 Qué hace este trabajo

Construye y audita un canal de PLN que **detecta eventos adversos en notas
clínicas** (MIMIC-IV, 70,000 notas de modelado sobre 331,793 procesadas) y los
clasifica según el Anexo 02 GG-ESSALUD-2021, comparando **7 modelos**: TF-IDF
(LogReg / LinearSVC, con y sin balanceo, completo y truncado) frente a
**Bio_ClinicalBERT y BioBERT con ajuste fino en GPU**.

### Cifras vigentes (fase 9 — tras corregir los 7 modos de fallo)

| Métrica del detector final | Valor | IC 95 % |
|---|---|---|
| Sensibilidad | **0.762** | [0.751, 0.773] |
| Especificidad | **0.770** | [0.759, 0.781] |
| AUC | **0.843** | [0.836, 0.849] |
| VPP a prevalencia real (20.12 %) | **0.455** | — |

| Ranking (misma partición, semilla 42) | F1-macro | Tiempo |
|---|---|---|
| ★ TF-IDF + LinearSVC (texto completo) | **0.459** | 48 s |
| Bio_ClinicalBERT (*fine-tuning*, ponderado) | 0.354 | 4.0 h |
| BioBERT (*fine-tuning*) | 0.210 | 2.9 h |

**Hallazgo:** la hipótesis inicial se **refutó** — el transformer clínico no
superó al modelo léxico, y la causa está medida: su ventana de 256 tokens cubre
solo el **9 %** del documento (truncar el TF-IDF a esa misma ventana lo degrada
28 % de F1-macro). Contra **juicio experto** (163 casos anotados, 78 por
duplicado): sensibilidad **0.945** sobre el consenso, **0.914 [0.849–0.953]**
en el análisis ampliado. Transferencia al **español con etiqueta de oro**
(corpus ERSP): exactitud 0.862 (tipo) · 0.846 (naturaleza) · 0.726 (severidad)
· 0.761 (código de evento, 41 clases).

> ⚠️ Las cifras preliminares publicadas antes del 27-jul (exactitud 0.731,
> F1-macro 0.515 sobre 14,853 notas) fueron **invalidadas por la auditoría**
> del pipeline y se conservan solo como registro histórico más abajo.

---

## 🔬 Ampliación del 27 de julio de 2026

Una auditoría del pipeline encontró **cuatro defectos** en la construcción del
corpus y los corrigió. El detalle completo, con el código, los comandos y la
salida literal de consola, está en [`bitacora/`](bitacora/).

### Los defectos y su efecto medido

| Defecto | Efecto | Estado |
|---|---|---|
| Muestreo no declarado: solo se examinaba el **9%** del corpus | 301,793 epicrisis sin revisar | Corregido — 331,793 procesadas |
| `re.DOTALL` hacía que `.*` cruzara la epicrisis entera | Detección del **48.8%** frente al ~9% de la literatura | Corregido — **−63.7%** de detecciones |
| Los códigos CIE-10 del mapeo llevaban punto (`A04.7`) y MIMIC no (`A047`) | El Tier A operaba al **1.5%** de su capacidad | Corregido — **factor 267×** |
| Ausencia de clase negativa en el entrenamiento | El sistema no podía abstenerse | Corregido — abstención 6/6 |

### La firma del bug del comodín

Al acotar la ventana del patrón, **solo cambian los patrones que contienen
`.*`**; los demás quedan idénticos hasta la última detección. Eso demuestra que
no era un problema de especificidad sino de **alcance del comodín**:

```
patrones con  .*  :  42,330  →   6,735   (−84.1%)
patrones sin  .*  :  13,189  →  13,189   ( 0.0%)
```

### Etiqueta no circular

El hallazgo metodológico central. Los códigos CIE-10 los asigna un codificador
clínico humano leyendo la historia, de forma **independiente del texto** de la
epicrisis. Reentrenando el mismo modelo sobre la misma fuente y cambiando solo
la etiqueta:

```
Etiqueta regex (circular)     F1-macro = 0.515
Etiqueta CIE-10 causal        F1-macro = 0.526   IC95 [0.498–0.555]
```

La comparación **no es pareja** (8 clases frente a 6) y el delta no es
concluyente. Lo que sí puede afirmarse: *un modelo léxico recupera del texto,
con F1-macro 0.526, una etiqueta que no proviene del texto*. Es evidencia de
aprendizaje real, no de circularidad.

### Escalabilidad entre géneros documentales

¿Sirve el mismo modelo para una queja, un reporte de incidente o una evolución
médica? Se midió truncando el texto:

| Longitud | F1-macro |
|---|---|
| 120 caracteres *(mediana de un reporte de incidente)* | 0.213 |
| 500 caracteres | 0.420 |
| 2,000 caracteres *(≈512 tokens)* | 0.433 |
| Completo *(~10,000)* | **0.526** |

**No transfiere directamente**: pierde el 60% del F1 ante un texto breve. Y de
paso: truncar a 512 tokens cuesta ~18% del F1-macro, lo que sustenta con
medición propia la necesidad de segmentación por fragmentos.

### Detector con capacidad de abstención

Reformulado en dos etapas —¿hay evento? y ¿de qué naturaleza?— con 33,564
epicrisis **sin** evento como clase negativa:

| Métrica | Valor |
|---|---|
| Sensibilidad | 0.907 |
| Especificidad | 0.917 |
| AUC | **0.973** |
| Precisión en el conjunto de prueba | 0.856 |
| **Precisión a prevalencia real (6.53%)** | **0.433** |

**La cifra que corresponde citar es 0.433, no 0.856.** El conjunto de prueba
tiene 36% de positivos por construcción; la prevalencia real es 6.53%. Corregido
por Bayes, de cada 100 alertas sobre el flujo real unas 43 serían correctas. Es
el desempeño propio de una herramienta de **tamizaje**, cuya salida va a un
revisor humano.

La curva completa de puntos de operación está en
[`resultados/metricas/curva_operacion.md`](resultados/metricas/curva_operacion.md).
A prevalencia baja la especificidad domina: con sensibilidad perfecta el VPP
solo subiría a 0.457, mientras que una especificidad de 0.977 lo lleva a 0.680.

### Lo que no funcionó, y se conserva

`fase4_v3_umbral_calibrado.py` documenta un **intento fallido**: calibrar
umbrales mejoró el F1-macro (+0.030) pero **empeoró** los falsos positivos que
pretendía corregir. El diagnóstico reveló un defecto de diseño más profundo —no
existía clase negativa— que ningún umbral podía arreglar. Se conserva porque el
fallo condujo al hallazgo.

---

## 📂 Estructura

```
PLN_SP/
├── codigo/            # Los scripts de Python que se corrieron
│   ├── fase3_corpus_expansion.py      # Corpus: Tier A (ICD-10) + Tier B (regex) + NegEx
│   ├── fase4_entrenar_baseline.py     # OE2: TF-IDF + LogReg vs LinearSVC
│   ├── fase4_crossval.py              # Validación cruzada 5-fold
│   ├── fase4_clinicalbert.py          # Bio_ClinicalBERT (transformer)
│   ├── fase4_split_paciente.py        # Split por paciente (sin fuga)
│   ├── fase4_circularidad.py          # Experimento de enmascaramiento
│   └── fase4_multietiqueta.py         # Reformulación multi-etiqueta
├── bitacora/          # Auditoría del 27-jul-2026: proceso, código y ejecución
│   ├── BITACORA_CORPUS_Y_ETIQUETA_2026-07-27.md   # los 4 defectos y sus correcciones
│   ├── ANEXO_CODIGO_Y_EJECUCION_2026-07-27.md     # código + comandos + salida real
│   ├── TIER_C_REGLAS_VALIDACION_2026-07-27.md     # reglas con datos estructurados
│   └── logs/                                       # registros de ejecución sin editar
├── resultados/        # Informe de métricas y auditoría (sin datos de pacientes)
│   ├── RESULTADOS_FASE4.md
│   ├── fase4_limitaciones_DRAFT.md
│   └── metricas/                                   # métricas en JSON + curva de operación
├── presentacion/      # Lámina de resultados
│   └── slide_resultados_OE2_PLN.png
└── docs/              # Explicación navegable (HTML)
    └── index.html
```

---

## ▶️ Cómo se corrió

```bash
# Entorno: Anaconda 3 (Python 3.13) — 100% software libre
# Librerías: scikit-learn 1.7.2 · torch 2.12.1 (CPU) · transformers 5.13.0 · pandas · nltk · gensim

set KMP_DUPLICATE_LIB_OK=TRUE          # Windows: evita conflicto de OpenMP

python codigo/fase3_corpus_expansion.py    # 1) construir el corpus
python codigo/fase4_entrenar_baseline.py   # 2) TF-IDF + LogReg vs LinearSVC
python codigo/fase4_crossval.py            #    validación cruzada 5-fold
python codigo/fase4_clinicalbert.py        #    Bio_ClinicalBERT
python codigo/fase4_split_paciente.py      #    split por paciente
python codigo/fase4_circularidad.py        #    enmascaramiento de disparadores
python codigo/fase4_multietiqueta.py       #    multi-etiqueta
```

---

## 🔒 Sobre los datos (importante)

El **código es 100% público y leíble**. Lo que **NO** se versiona aquí es el texto
clínico ni los modelos entrenados sobre él (`*.csv`, `*.parquet`, `*.pkl`), porque
el **Data Use Agreement (DUA) de MIMIC-IV lo prohíbe**. Para *re-ejecutar* el
pipeline se requiere acceso credencializado a MIMIC-IV
([PhysioNet](https://physionet.org/content/mimic-iv-note/2.2/) — curso CITI + firma
del DUA). Es la misma barrera ética que protege los datos de pacientes.

## 🔗 Enlaces útiles

- Dataset: [MIMIC-IV-Note v2.2 (PhysioNet)](https://physionet.org/content/mimic-iv-note/2.2/)
- Modelo: [Bio_ClinicalBERT (Hugging Face)](https://huggingface.co/emilyalsentzer/Bio_ClinicalBERT)
- Taxonomía: Anexo N.° 02, Directiva GG-ESSALUD-2021 (231 eventos / 12 naturalezas)

---

*Curso MIA-10 Procesamiento del Lenguaje Natural · Maestría en IA · UNI · 2026.*
