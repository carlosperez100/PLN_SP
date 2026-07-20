# PLN_SP — Procesamiento de Lenguaje Natural aplicado a la Seguridad del Paciente

**Trabajo final del curso MIA-10 · Procesamiento del Lenguaje Natural**
Maestría en Inteligencia Artificial — Universidad Nacional de Ingeniería (UNI)
Docente: Dr. Wester Zela Moraya · Autor: **Carlos Pérez Pérez**

> Repositorio **exclusivo del curso de PLN**. Reúne el código, los resultados y la
> explicación de la parte de procesamiento de lenguaje natural del proyecto
> *Detección Automática de Eventos Adversos Hospitalarios en Epicrisis*.

**🌐 Reporte en línea (sitio web): https://carlosperez100.github.io/PLN_SP/**

---

## 🎯 Qué hace este trabajo

Compara, sobre **14,853 epicrisis reales** de MIMIC-IV (12,785 pacientes), tres
enfoques de PLN para clasificar la **naturaleza del evento adverso** (8 clases del
Anexo 02 GG-ESSALUD-2021):

- **Modelo léxico clásico** — TF-IDF + Regresión Logística / LinearSVC
- **Transformer clínico** — Bio_ClinicalBERT (congelado, como extractor de rasgos)

### Resultado principal

| Modelo | Exactitud (CV 5-fold) | F1-macro | Kappa |
|---|---|---|---|
| TF-IDF + Regresión Logística | 0.628 | 0.466 | 0.474 |
| **★ TF-IDF + LinearSVC (palabra + char)** | **0.731** | **0.515** | **0.581** |
| Bio_ClinicalBERT congelado + LogReg | 0.38 | 0.19 | 0.18 |

**Hallazgo:** en una tarea definida por patrones léxicos, el modelo clásico superó
al transformer clínico sin *fine-tuning*. La hipótesis inicial se **refutó**. La
métrica honesta es el F1-macro (~0.51); la etiqueta débil tiene circularidad
estructural, por lo que las cifras miden consistencia con la regla, no validez
clínica (ver [`resultados/`](resultados/)).

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
├── resultados/        # Informe de métricas y auditoría (sin datos de pacientes)
│   ├── RESULTADOS_FASE4.md
│   └── fase4_limitaciones_DRAFT.md
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
