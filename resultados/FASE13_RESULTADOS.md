# Fase 13 — resultados (PARCIAL (época 1))

Generado a partir de `modernbert_progreso.json` (2026-08-17T10:28:57).

## Ranking ampliado (misma partición, semilla 42)

| # | Modelo | Exactitud | F1-macro | Kappa | Tiempo |
|---|---|---|---|---|---|
| 1 | TF-IDF + LinearSVC (texto completo) | 0.7149 | **0.4592** | 0.5443 | 48 s |
| 2 | TF-IDF + LinearSVC sin balanceo (completo) | 0.7109 | **0.3909** | 0.5132 | 47 s |
| 3 | TF-IDF + LinearSVC (truncado a 4600 car.) | 0.6510 | **0.3880** | 0.4340 | 23 s |
| 4 | BioClinical ModernBERT (ft, 1024 tokens) — época 1 ⭐ | 0.6489 | **0.3583** | 0.4405 | 11.4 h |
| 5 | Bio_ClinicalBERT (ft, ponderado, 256 tok) | 0.5429 | **0.3541** | 0.3252 | 4.0 h |
| 6 | TF-IDF + LinearSVC (truncado 1,150 car.) | 0.5746 | **0.3301** | 0.3148 | 6 s |
| 7 | TF-IDF sin balanceo (truncado 1,150 car.) | 0.5890 | **0.2747** | 0.2951 | 5 s |
| 8 | Bio_ClinicalBERT (fine-tuning, 256 tok) | 0.6072 | **0.2487** | 0.3438 | 2.9 h |
| 9 | BioBERT (fine-tuning) | 0.5971 | **0.2097** | 0.3182 | 2.9 h |

## LLM generativo local (contra consenso experto, no comparable con el ranking)

- llama3.2:3b en zero-shot, 100 % local (Ollama): sensibilidad 1.000 · especificidad 0.000 · kappa 0.000 sobre 68 casos — dijo SÍ a todo: sin ajuste no discrimina.

## Lectura

- ModernBERT alcanza **F1-macro 0.3583** con ventana de 1,024 tokens (4× la de la fase 11).
- Frente al Bio_ClinicalBERT de 256 tokens (0.3541): SUPERA al transformer clínico anterior.
- Frente al control léxico de su MISMA ventana (0.3880): aún por debajo — a igual ventana el léxico sigue delante.
- Frente al campeón de texto completo (0.4592): por debajo — consistente con que el texto completo sigue siendo la ventaja decisiva.