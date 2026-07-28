<!-- GENERADO por codigo/seleccion_modelos.py — no editar a mano -->

## Tabla 1. Etapa 1 — filtros duros de admisibilidad

| Filtro | Restricción |
|---|---|
| **F1** | Tarea: debe resolver clasificación multietiqueta supervisada de documentos. |
| **F2** | Idioma: debe operar sobre el corpus disponible (MIMIC-IV-Note, inglés clínico). |
| **F3** | Cómputo: entrenable e inferible en CPU, con huella <= 2.5 GB (RAM libre del VPS). |
| **F4** | DUA de PhysioNet: el texto clínico no puede salir hacia terceros sin vía de cumplimiento. |
| **F5** | Licencia: pesos y código de uso libre (restricción de proyecto). |

## Tabla 2. Candidatos descartados en la Etapa 1

| Candidato | Filtro | Motivo |
|---|:---:|---|
| LLM generativo vía API pública (OpenAI / ChatGPT) | **F4** | PhysioNet prohíbe expresamente enviar datos MIMIC por APIs de terceros como OpenAI o pegarlos en ChatGPT. |
| LLM cloud con vía de cumplimiento (Azure OpenAI opt-out, Vertex AI, Bedrock) | **F5** | Admisible bajo condiciones documentadas por PhysioNet, pero de pago y con reproducibilidad dependiente del proveedor. Queda como ruta habilitada para el piloto. |
| LLM local de 7B+ parámetros (Llama, Qwen, Mistral) | **F3** | Excede la RAM libre del VPS (~2.5 GB) y exige GPU para inferencia útil. |
| Bio_ClinicalBERT con fine-tuning completo | **F3** | 8-12 h por época en CPU. Se reserva al piloto, con GPU. |
| bsc-bio-ehr-es / BETO / MarIA (roberta-large-bne) | **F2** | Modelos de español; el corpus de esta etapa es inglés clínico. Son los candidatos del OE5 (transferencia a EsSalud). |

## Tabla 3. Etapa 2 — matriz de decisión ponderada

| Criterio | Peso | TF-IDF (palabra+char) + LinearSVC | TF-IDF + Regresión Logística | Bio_ClinicalBERT congelado + LogReg |
|---|:---:|:---:|:---:|:---:|
| C1 — Correspondencia con la tarea (clasificación multietiqueta) | 0.20 | 4 | 4 | 2 |
| C2 — Ajuste al dominio clínico | 0.10 | 2 | 2 | 4 |
| C3 — Transferibilidad al español (OE5) | 0.15 | 3 | 3 | 1 |
| C4 — Viabilidad de cómputo (CPU, <= 2.5 GB) | 0.15 | 4 | 4 | 2 |
| C5 — Cumplimiento del DUA (procesamiento 100 % local) | 0.15 | 4 | 4 | 4 |
| C6 — Interpretabilidad / auditabilidad clínica | 0.10 | 4 | 4 | 2 |
| C7 — Desempeño empírico en el corpus (F1-macro, CV 5-fold) *(posterior)* | 0.15 | 4 | 3 | 1 |
| **Puntaje a priori (C1–C6)** | 0.85 | **3.59** | **3.59** | **2.41** |
| **Puntaje final (C1–C7)** | 1.00 | **3.65** | **3.50** | **2.20** |
| **Puntaje final normalizado** | | 91.2 % | 87.5 % | 55.0 % |

**Modelo seleccionado: TF-IDF (palabra+char) + LinearSVC** (puntaje 3.65/4.00 = 91.2 %).

Escala 0–4: 0 no cumple · 1 deficiente · 2 aceptable · 3 bueno · 4 óptimo.


## Tabla 4. Justificación de cada puntaje

| Candidato | Criterio | Justificación |
|---|:---:|---|
| TF-IDF (palabra+char) + LinearSVC | C1 | Clasificador supervisado nativo; multietiqueta vía Binary Relevance. |
| TF-IDF (palabra+char) + LinearSVC | C2 | Sin conocimiento clínico previo: lo induce del propio corpus. |
| TF-IDF (palabra+char) + LinearSVC | C3 | Agnóstico al idioma; se reentrena en español sin cambiar arquitectura. |
| TF-IDF (palabra+char) + LinearSVC | C4 | Entrena en segundos; el modelo serializado pesa pocos MB. |
| TF-IDF (palabra+char) + LinearSVC | C5 | Todo el procesamiento ocurre en la máquina del investigador. |
| TF-IDF (palabra+char) + LinearSVC | C6 | Coeficientes por n-grama -> evidencia legible por el auditor clínico. |
| TF-IDF (palabra+char) + LinearSVC | C7 | F1-macro 0.515; kappa 0.581; exactitud 0.731 +/- 0.007 (mejor medido). |
| TF-IDF + Regresión Logística | C1 | Igual que el anterior: misma familia de representación y tarea. |
| TF-IDF + Regresión Logística | C2 | Sin conocimiento clínico previo. |
| TF-IDF + Regresión Logística | C3 | Agnóstico al idioma. |
| TF-IDF + Regresión Logística | C4 | Coste despreciable en CPU. |
| TF-IDF + Regresión Logística | C5 | Procesamiento local. |
| TF-IDF + Regresión Logística | C6 | Coeficientes con lectura probabilística directa. |
| TF-IDF + Regresión Logística | C7 | F1-macro 0.466; kappa 0.474; exactitud 0.628 +/- 0.009. |
| Bio_ClinicalBERT congelado + LogReg | C1 | Se usa como extractor de rasgos, no ajustado a esta tarea. |
| Bio_ClinicalBERT congelado + LogReg | C2 | Preentrenado sobre notas clínicas de MIMIC: máximo ajuste de dominio. |
| Bio_ClinicalBERT congelado + LogReg | C3 | Monolingüe inglés; no transfiere a español. |
| Bio_ClinicalBERT congelado + LogReg | C4 | Inferencia CPU factible pero lenta; ~440 MB de pesos. |
| Bio_ClinicalBERT congelado + LogReg | C5 | Pesos descargables: se ejecuta en local. |
| Bio_ClinicalBERT congelado + LogReg | C6 | Embeddings opacos; exigiría SHAP/LIME para justificar un caso. |
| Bio_ClinicalBERT congelado + LogReg | C7 | F1-macro 0.190; kappa 0.180; exactitud 0.380 (peor medido). |
