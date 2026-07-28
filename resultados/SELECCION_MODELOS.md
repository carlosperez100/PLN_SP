# Criterio y metodología de selección del modelo de PLN

**Trabajo final MIA-10 · Procesamiento del Lenguaje Natural · Dr. Wester Zela Moraya**
Autor: Carlos Pérez Pérez · Maestría en IA, UNI · julio 2026

> Responde a la observación del curso: *no basta con decir qué modelo se usó; hay que
> justificar con qué criterio, con qué metodología y con qué métricas se eligió.*

---

## 1. El error que este documento evita

Elegir un modelo porque aparece en un blog, en un foro o porque «es el que todos usan»
no es una decisión metodológica: es una coincidencia. Peor todavía es justificarlo con
el ranking equivocado. Los rankings generalistas de LLM puntúan **razonamiento y
conocimiento** (MMLU, GPQA, IFEval); esta tarea es **clasificación multietiqueta de
documentos**. Un modelo puede liderar el primer tipo de ranking y ser inservible aquí.

De hecho, el *Open LLM Leaderboard* de Hugging Face —el ranking que más se cita en
clase— fue **archivado y ya no se actualiza**: sus autores lo retiraron porque la
saturación de los benchmarks y la contaminación de datos lo habían vuelto obsoleto, y
advirtieron del riesgo de «*hill climbing*» en direcciones irrelevantes
([HF, Open LLM Leaderboard v1 · archive](https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive)).
Citarlo hoy como criterio de selección sería un error verificable.

## 2. Definición formal de la tarea (paso previo obligatorio)

Antes de mirar cualquier ranking hay que fijar la tarea, porque la tarea determina la
métrica y la métrica determina el ranking pertinente:

| Elemento | Valor en este trabajo |
|---|---|
| Tipo de tarea | Clasificación **multietiqueta** de documentos, y ∈ {0,1}¹² |
| Unidad de análisis | La epicrisis (nota de alta), no el evento |
| Etiquetas | 12 naturalezas del Anexo 02, Directiva GG-ESSALUD-2021 |
| Corpus | MIMIC-IV-Note v2.2 — 14 853 epicrisis, 12 785 pacientes |
| Idioma | Inglés clínico (etapa actual); español en el OE5 |
| Métrica primaria | **F1-macro** (clases desbalanceadas → el F1-ponderado infla) |
| Métricas secundarias | F1-micro, kappa de Cohen, F1 por etiqueta |
| Métricas **no** aplicables | BLEU, ROUGE, METEOR (miden generación), perplejidad, MMLU |

**Consecuencia:** el ranking pertinente es uno de **clasificación**, no de generación
ni de razonamiento.

## 3. Instrumentos de ranking utilizados (y por qué cada uno)

| Instrumento | Qué aporta | Por qué es el pertinente |
|---|---|---|
| [**MTEB / MMTEB Leaderboard**](https://huggingface.co/spaces/mteb/leaderboard) | Pestaña **Classification** y vista multilingüe (MMTEB: 131 tareas, 250+ idiomas, agregación por conteo de Borda) | Es el único ranking masivo de Hugging Face que puntúa **explícitamente clasificación** y permite filtrar por idioma. Sirve para priorizar candidatos de tipo *encoder*/embedding. |
| [**IberBench**](https://arxiv.org/abs/2504.16921) (arXiv:2504.16921) | 101 datasets, 22 categorías de tarea, español y variedades ibero-americanas | Instrumento de referencia para el **OE5** (transferencia a español/EsSalud). Su hallazgo es directamente relevante: los LLM rinden **peor en tareas de interés industrial** que en tareas fundamentales. |
| [**JAMIA 2024 — encoders clínicos en español**](https://doi.org/10.1093/jamia/ocae054) | Comparación revisada por pares de BETO, MarIA, XLM-R, mDeBERTa, bsc-bio-ehr-es y variantes Galén sobre 12 corpus clínicos, con **micro-F1** | Evidencia de dominio revisada por pares, no un blog. Es la referencia que fija la expectativa realista para el OE5. |
| ❌ *Open LLM Leaderboard* | — | **Archivado**; métricas de razonamiento, no de clasificación. Se documenta su exclusión. |

## 4. Procedimiento de decisión en dos etapas

El procedimiento está implementado en [`codigo/seleccion_modelos.py`](../codigo/seleccion_modelos.py)
y las tablas se regeneran con `python codigo/seleccion_modelos.py`, de modo que la
decisión es **reproducible y auditable**, no una afirmación del autor.

### Etapa 1 — filtros duros de admisibilidad

Un filtro duro es una **restricción del problema**, no una preferencia. Lo que no lo
pasa sale del espacio de búsqueda y no se puntúa. Esto es lo que impide que la
comparación degenere en «probemos lo que esté de moda».

| Filtro | Restricción |
|---|---|
| **F1** Tarea | Debe resolver clasificación multietiqueta supervisada de documentos. |
| **F2** Idioma | Debe operar sobre el corpus disponible (MIMIC-IV-Note, inglés clínico). |
| **F3** Cómputo | Entrenable e inferible en CPU, huella ≤ 2.5 GB (RAM libre del servidor de despliegue). |
| **F4** DUA | El texto clínico no puede salir hacia terceros sin una vía de cumplimiento documentada. |
| **F5** Licencia | Pesos y código de uso libre. |

#### El filtro F4 es el más importante, y es el que casi nadie aplica

PhysioNet —la entidad que custodia MIMIC— publicó una norma explícita: el *Credentialed
Data Use Agreement* **prohíbe compartir los datos con terceros, lo que incluye
enviarlos por APIs como las de OpenAI o pegarlos en plataformas en línea como ChatGPT**
([PhysioNet — Responsible use of MIMIC data with online services like GPT](https://physionet.org/news/post/gpt-responsible-use/);
ampliado en [Use of MIMIC Data with LLMs and Online Services](https://physionet.org/news/post/llm-responsible-use/)).

Existen vías de cumplimiento, y PhysioNet las nombra: **Azure OpenAI** con
renuncia (*opt-out*) documentada a la revisión humana, **Amazon Bedrock** con copia
aislada del modelo base, **Gemini vía Vertex AI** y **Claude**, en tanto no entrenen
con los *prompts* ni hagan revisión humana rutinaria. La regla operativa es:
*solo servicios que no usen los datos para entrenamiento ni revisión humana.*

Por eso, en este trabajo, **usar un LLM en la nube no es una decisión de rendimiento
sino de cumplimiento normativo**, y se resuelve antes de comparar métricas.

#### Candidatos descartados en la Etapa 1

| Candidato | Filtro | Motivo |
|---|:---:|---|
| LLM generativo vía API pública (OpenAI / ChatGPT) | **F4** | Prohibido expresamente por PhysioNet para datos MIMIC. |
| LLM cloud con vía de cumplimiento (Azure OpenAI *opt-out*, Vertex AI, Bedrock) | **F5** | Admisible bajo condiciones documentadas, pero de pago y con reproducibilidad dependiente del proveedor. **Queda como ruta habilitada para el piloto.** |
| LLM local de 7B+ parámetros (Llama, Qwen, Mistral) | **F3** | Excede la RAM libre del servidor (~2.5 GB) y exige GPU. |
| Bio_ClinicalBERT con *fine-tuning* completo | **F3** | 8–12 h por época en CPU. Se reserva al piloto, con GPU. |
| `bsc-bio-ehr-es` / BETO / MarIA | **F2** | Modelos de español; el corpus de esta etapa es inglés. Son los candidatos del **OE5**. |

### Etapa 2 — matriz de decisión ponderada

Siete criterios, pesos que suman 1.00, escala 0–4
(0 no cumple · 1 deficiente · 2 aceptable · 3 bueno · 4 óptimo).
**C1–C6 son *a priori*** (puntuables antes de correr nada); **C7 es el único
posterior**. Separarlos permite comprobar si el marco de decisión *predijo* el
resultado, en lugar de racionalizarlo después.

| Criterio | Peso | LinearSVC | LogReg | ClinicalBERT congelado |
|---|:---:|:---:|:---:|:---:|
| C1 Correspondencia con la tarea | 0.20 | 4 | 4 | 2 |
| C2 Ajuste al dominio clínico | 0.10 | 2 | 2 | 4 |
| C3 Transferibilidad al español (OE5) | 0.15 | 3 | 3 | 1 |
| C4 Viabilidad de cómputo (CPU, ≤2.5 GB) | 0.15 | 4 | 4 | 2 |
| C5 Cumplimiento del DUA (100 % local) | 0.15 | 4 | 4 | 4 |
| C6 Interpretabilidad / auditabilidad | 0.10 | 4 | 4 | 2 |
| C7 Desempeño empírico *(posterior)* | 0.15 | 4 | 3 | 1 |
| **Puntaje a priori (C1–C6)** | 0.85 | **3.59** | **3.59** | **2.41** |
| **Puntaje final (C1–C7)** | 1.00 | **3.65** | **3.50** | **2.20** |
| **Normalizado** | | **91.2 %** | 87.5 % | 55.0 % |

**Modelo seleccionado: TF-IDF (palabra + carácter) + LinearSVC** — 3.65/4.00 (91.2 %).

Tablas completas, con la justificación de cada puntaje, en
[`tablas_seleccion_modelos.md`](tablas_seleccion_modelos.md); versión LaTeX para el
paper en [`tablas_seleccion_modelos.tex`](tablas_seleccion_modelos.tex).

## 5. El resultado clave: el marco predijo el hallazgo contraintuitivo

El puntaje **a priori** ya separaba a la familia léxica (3.59) del transformer clínico
congelado (2.41), **antes de ejecutar un solo experimento**. La corrida lo confirmó:

| Modelo | Exactitud (CV 5-fold) | F1-macro | Kappa |
|---|---|---|---|
| TF-IDF + Regresión Logística | 0.628 ± 0.009 | 0.466 | 0.474 |
| **★ TF-IDF + LinearSVC (palabra + char)** | **0.731 ± 0.007** | **0.515** | **0.581** |
| Bio_ClinicalBERT congelado + LogReg | 0.380 | 0.190 | 0.180 |

La hipótesis inicial —«ClinicalBERT ≥ 75 %, será el mejor»— quedó **refutada**. Y no
es una anomalía local: García Subies *et al.* (JAMIA, 2024), al comparar encoders sobre
12 corpus clínicos en español, llegaron al mismo tipo de conclusión —**los mejores
modelos no fueron los clínicos sino los de propósito general**, y las adaptaciones de
dominio rindieron **por debajo** de sus modelos base cuando el corpus de especialización
no era suficientemente grande y limpio
([doi:10.1093/jamia/ocae054](https://doi.org/10.1093/jamia/ocae054)).

Es decir: el resultado «raro» de este trabajo está **corroborado por literatura
revisada por pares**. Eso convierte una aparente debilidad en un aporte.

## 6. Aporte metodológico del trabajo

1. Un **procedimiento de selección en dos etapas** (filtros duros → puntuación
   ponderada) que hace explícito y reproducible lo que normalmente queda implícito.
2. La incorporación del **cumplimiento del DUA como criterio de primer orden**, con
   la norma de PhysioNet citada. En datos clínicos credencializados, la restricción
   legal precede a la métrica: un modelo con mejor F1 pero que exige exportar el texto
   es **inadmisible**, no «una alternativa a considerar».
3. La **separación entre criterios a priori y posteriores**, que permite falsar el
   marco de decisión en lugar de usarlo para justificar lo ya hecho.
4. Evidencia empírica de que, en una tarea definida por patrones léxicos, **un modelo
   clásico interpretable y desplegable en CPU domina a un transformer clínico sin
   *fine-tuning*** — con el respaldo independiente de JAMIA 2024.

## 7. Límite honesto de este análisis

La etiqueta de esta etapa es **débil** (reglas Tier A/ICD-10 + Tier B/regex + NegEx),
no anotación humana. Por tanto las cifras miden **consistencia con la regla**, no
validez clínica; hay circularidad estructural. El experimento de enmascaramiento de los
35 disparadores Tier B (que solo baja la exactitud 1.35 puntos) demuestra que el modelo
**no es un reproductor de la regex** y usa contexto léxico, pero no elimina la
circularidad. La métrica honesta es el **F1-macro (~0.51)**, no el F1-ponderado (~0.73).
El cierre de este flanco es la anotación *gold* y el *fine-tuning* con GPU, ambos
previstos para el piloto. Detalle en
[`fase4_limitaciones_DRAFT.md`](fase4_limitaciones_DRAFT.md).

---

## Referencias verificadas

1. García Subies, G., Barbero Jiménez, Á., & Martínez Fernández, P. (2024). A comparative
   analysis of Spanish Clinical encoder-based models on NER and classification tasks.
   *Journal of the American Medical Informatics Association*, 31(9), 2137–2146.
   https://doi.org/10.1093/jamia/ocae054
2. González, J. Á., Borrego Obrador, I., Romo Herrero, Á., Sarvazyan, A. M.,
   Chinea-Ríos, M., Basile, A., & Franco-Salvador, M. (2025). *IberBench: LLM Evaluation
   on Iberian Languages*. arXiv:2504.16921. https://arxiv.org/abs/2504.16921
3. PhysioNet. *Responsible use of MIMIC data with online services like GPT.*
   https://physionet.org/news/post/gpt-responsible-use/
4. PhysioNet. *Use of MIMIC Data with Large Language Models and Online Services.*
   https://physionet.org/news/post/llm-responsible-use/
5. MTEB / MMTEB Leaderboard (Hugging Face). https://huggingface.co/spaces/mteb/leaderboard
6. Hugging Face. *Open LLM Leaderboard v1 — archive* (ranking retirado).
   https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive
7. Alsentzer, E. *et al.* Bio_ClinicalBERT. https://huggingface.co/emilyalsentzer/Bio_ClinicalBERT
8. PlanTL-GOB-ES. `bsc-bio-ehr-es` — RoBERTa biomédico-clínico en español.
   https://huggingface.co/PlanTL-GOB-ES/bsc-bio-ehr-es
9. MIMIC-IV-Note v2.2 (PhysioNet). https://physionet.org/content/mimic-iv-note/2.2/
