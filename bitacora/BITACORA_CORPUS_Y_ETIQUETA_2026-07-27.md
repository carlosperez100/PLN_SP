# Bitácora — Corrección del corpus y de la etiqueta

**Tesis MIA-303 · Detección automatizada de eventos adversos hospitalarios**
**Carlos Pérez Pérez · Maestría en Inteligencia Artificial, UNI**
**Sesión de trabajo: 26–27 de julio de 2026**

> Documento para revisión docente. Registra, en orden cronológico, los
> defectos encontrados en el pipeline, las correcciones aplicadas, los
> resultados medidos y —sobre todo— **los intentos que no funcionaron y qué
> se aprendió de ellos**. Todas las cifras se verificaron contra el código y
> los datos, no contra documentación previa.

---

## 0. Punto de partida

El OE2 reportaba, sobre 14,853 epicrisis de MIMIC-IV y 8 clases:

| Modelo | Exactitud | F1-macro | Kappa |
|---|---|---|---|
| TF-IDF + LinearSVC | 0.731 | 0.515 | 0.581 |
| TF-IDF + LogReg | 0.628 | 0.466 | 0.474 |
| Bio_ClinicalBERT congelado + LogReg | 0.380 | 0.190 | 0.180 |

La auditoría previa había señalado una amenaza de validez sin cuantificar:
**el 99% de las etiquetas son subcadena del texto**, porque la etiqueta la
produce el mismo regex que se aplica al texto. No se podía distinguir si el
modelo aprendía o repetía la regla.

---

## 1. Defecto 1 — el corpus era una muestra no declarada

**Hallazgo.** El corpus de 14,853 notas no proviene de las 331,793 epicrisis
de MIMIC-IV-Note v2.2, sino de dos topes codificados en la Fase 3:

| Paso | Notas | Origen |
|---|---|---|
| Universo disponible | **331,793** (145,914 pacientes) | verificado leyendo `discharge.csv.gz` completo |
| Tier B examinó | **30,000** = 9.04% | `ORDER BY RANDOM() LIMIT 30000` |
| Tier A, tope de registros | 50,000 | `LIMIT 50000` |
| Corpus resultante | 14,863 → **14,853** | tras `MIN_CLASE = 30` |

**Consecuencia.** El 91% del corpus nunca se examinó, y el documento no lo
declaraba. Es una limitación de validez externa que debe explicitarse.

**Corrección.** `fase3_v2_corpus_completo.py` procesa las 331,793 sin tope.

---

## 2. Defecto 2 — bug de alcance en las expresiones regulares

**Hallazgo.** Los 35 patrones del Tier B se compilan con `re.DOTALL`, de modo
que un comodín `.*` **atraviesa la epicrisis entera**. Ejemplo real:

```python
r"blood\s+glucose.*low.*insulin"      # hipoglicemia por insulina
```

Basta con que «blood glucose» aparezca en la primera página e «insulin» en la
quinta —situación habitual en cualquier nota de cuidados intensivos— para que
la nota se marque como hipoglicemia. Ese patrón marcaba 3,819 notas.

**Efecto medido.** Tasa de detección del **48.8%** de las epicrisis. La
literatura reporta una incidencia cercana al **9%** (de Vries et al., 2008):
el detector estaba **5.4 veces por encima**.

**Corrección.** Sin `re.DOTALL` y cada `.*` acotado a `.{0,100}`.

**Resultado sobre 2,000 epicrisis reales (prueba de humo):**

| Variante | Notas marcadas | Tasa |
|---|---|---|
| Laxa (original) | 1,084 / 2,000 | 54.2% |
| Acotada (ventana de 100 caracteres) | 483 / 2,000 | **24.1%** |

Acotar elimina el **55%** de las marcas. La comparación entre ambas variantes
sobre el corpus completo constituye un **experimento de ablación** reportable:
*sensibilidad de la detección a la ventana del patrón*.

**RESULTADO FINAL sobre el corpus completo — 331,793 epicrisis (100%):**

| Variante | Detecciones | Notas negadas por NegEx |
|---|---|---|
| Laxa (`re.DOTALL`, original) | **258,671** | 30,130 |
| Acotada (ventana de 100 caracteres) | **93,922** | 26,613 |
| **Reducción** | **164,749** | **63.7%** |

La reducción se mantuvo entre el 63% y el 64% en todos los puntos de control
del recorrido, de modo que no depende del tramo del corpus examinado.

### La firma del bug, patrón por patrón

La evidencia decisiva es que el efecto **solo alcanza a los patrones que
contienen un comodín `.*`**. Los que no lo tienen quedan idénticos, hasta la
última detección:

**Patrones CON `.*` — se desploman**

| Patrón | Laxo | Acotado | Cambio |
|---|---|---|---|
| `hipoglicemia_insulina` | 9,382 | 96 | **−99.0%** |
| `falla_dispositivo` | 5,263 | 63 | **−98.8%** |
| `quemadura_paciente` | 3,433 | 61 | −98.2% |
| `complicacion_anestesia` | 1,242 | 50 | −96.0% |
| `infeccion_cateter_central` | 1,011 | 58 | −94.3% |
| `hemorragia_postoperatoria` | 1,020 | 121 | −88.1% |
| `anticoagulacion_excesiva` | 6,145 | 1,016 | −83.5% |
| `neumonia_ventilador` | 2,187 | 481 | −78.0% |
| `infeccion_sitio_qx` | 8,376 | 2,515 | −70.0% |

**Patrones SIN `.*` — sin variación alguna**

| Patrón | Laxo | Acotado | Cambio |
|---|---|---|---|
| `infeccion_clostridium` | 4,337 | 4,337 | 0.0% |
| `bacteriemia` | 3,645 | 3,645 | 0.0% |
| `infeccion_mrsa` | 3,299 | 3,299 | 0.0% |
| `ulcera_presion` | 973 | 973 | 0.0% |
| `reaccion_transfusional` | 207 | 207 | 0.0% |
| `error_medicacion_dosis` | 185 | 185 | 0.0% |

**Agregado sobre el tramo con filas persistidas:**

```
patrones con  .*  :  42,330  →   6,735   (−84.1%)
patrones sin  .*  :  13,189  →  13,189   ( 0.0%)
```

Esta separación limpia es la prueba de que el problema **no era una baja
especificidad general de los patrones**, sino un **defecto de alcance del
comodín**: `re.DOTALL` permitía que `.*` cruzara la epicrisis completa. Los
patrones construidos con alternativas literales nunca estuvieron afectados y
siguen midiendo lo mismo.

El caso extremo es `hipoglicemia_insulina`: de 9,382 detecciones a 96. Las
9,286 restantes eran notas en las que «blood glucose», «low» e «insulin»
aparecían en párrafos distintos del documento, sin relación entre sí.

> **Dificultades de ejecución, para el registro.** La corrida completa
> (331,793 notas × 35 patrones × 2 variantes) resultó mucho más lenta de lo
> estimado: unos 9 minutos por bloque de 20,000 notas, y bastante más al
> competir con los entrenamientos. Se interrumpió **dos veces**: la laptop se
> suspendió durante la noche (salto del bloque 2 a las 23:40 al bloque 4 a las
> 09:21) y el **27-jul a las 16:27 un cierre iniciado por el sistema (evento
> 1074 de Windows) mató el proceso al 78.4%**, tras 17 h 23 min.
>
> Al revisar el script para relanzarlo se descubrió que **la reanudación
> anunciada en su documentación no estaba implementada**: escribía
> `progreso.json` en cada bloque pero nunca lo leía, y las filas de detección
> se acumulaban solo en memoria. Relanzarlo habría significado empezar de cero
> (unas 20 horas) y las filas del primer tramo se habían perdido.
>
> Se escribió `fase3_v2_reanudar.py`, que sí lee el checkpoint, salta el tramo
> hecho —24 segundos— y **persiste las filas en disco en cada bloque**. La
> reanudación completó las 71,793 epicrisis restantes en **32 minutos**.
>
> **Limitación derivada, que debe declararse.** Los conteos de la ablación
> cubren las 331,793 epicrisis y son válidos: provienen del mismo código
> determinista sobre el mismo corpus. En cambio las filas a nivel de nota solo
> existen para el tramo reanudado de 71,793 epicrisis. Las comparaciones por
> patrón de las tablas anteriores se calculan sobre ese tramo, que es una
> muestra del 21.6% del corpus. Para disponer del corpus de candidatos
> completo a nivel de fila habría que rehacer la corrida entera.

---

## 3. Defecto 3 — el Tier A fallaba por un punto

Este es el hallazgo de mayor impacto de la sesión.

**Hallazgo.** El mapeo `eventos_adversos_icd10_v2.csv` almacena los códigos
**con punto** (`A04.7`, `T81.4`, `Y83.8` — 201 de 223), mientras que MIMIC-IV
los almacena **sin punto** (`A047`, `T814`). Ninguno de los 6,364,488
registros de diagnósticos de MIMIC contiene un punto.

El `JOIN d.icd_code = c.icd_code` solo podía acertar con los 22 códigos de
tres caracteres, y de esos coincidían cuatro.

| Método | Hospitalizaciones detectadas |
|---|---|
| Original (comparación literal) | **411** |
| Corregido (sin punto + coincidencia por prefijo) | **109,714** |
| | **factor 267×** |

Se usa coincidencia por prefijo porque MIMIC emplea códigos más específicos
que el mapeo (`A047` → `A0471`, `A0472`), que es la jerarquía normal de
CIE-10.

**Segundo hallazgo, derivado del primero.** Al corregir el formato, los
códigos que más aportan resultan ser **condiciones** y no eventos adversos:
N17.9 insuficiencia renal aguda (35,884), J18.9 neumonía (9,415), A41.9
sepsis (7,770). Esas pueden ser el **motivo de ingreso**, no un daño causado
por la atención — y `diagnoses_icd` de MIMIC-IV **no incluye bandera de
present-on-admission**, por lo que no es posible distinguirlas.

**Decisión metodológica.** El Tier A se estratifica en dos:

| Estrato | Definición | Hospitalizaciones | % de 545,497 | Uso |
|---|---|---|---|---|
| **A1** | Semántica causal explícita: T80–T88 (complicaciones de la atención médica y quirúrgica), Y63/Y65/Y83/Y84 (errores e incidentes asistenciales), W00–W19 (caídas), L89 (úlcera por presión) — 73 códigos | **35,618** | **6.53%** | **Apto como etiqueta** |
| A2 | El resto — 150 códigos | 97,876 | 17.94% | No apto sin verificación de POA |

El **6.53%** de A1 es compatible con el ~9% de la literatura, ligeramente por
debajo, que es justamente el subregistro documentado de la codificación
administrativa frente a la revisión de historias.

**Por qué esto importa más que la corrección del regex.** Los códigos CIE-10
los asigna un **codificador clínico humano** leyendo la historia, de forma
**independiente del texto de la epicrisis**. Una etiqueta derivada de A1
**no es circular** respecto del texto. Es la única fuente del pipeline que
ataca de raíz la amenaza de validez principal del OE2.

**Resultado de A1 sobre el corpus completo:**

| | Notas | Detecciones | Naturalezas |
|---|---|---|---|
| A1 (apto) | **18,989** | 24,400 | 6 |
| A2 (no apto) | 53,375 | 87,460 | 7 |
| Tier A original, para comparar | 229 | — | — |

A1 por sí solo es **mayor que el corpus completo anterior** (14,853). Y es
**casi disjunto** de él: la intersección es de 1,196 notas, el **6.3% de A1**;
hay 17,793 notas que el pipeline nunca había visto.

**A1 es complementario, no redundante** — cubre precisamente las clases donde
el detector léxico estaba ciego:

| Naturaleza | A1 (CIE-10) | Tier B (regex) |
|---|---|---|
| Procedimiento | **8,667** | 1,643 |
| Cuidado del paciente | **7,550** | 2,097 |
| Dispositivo | **2,994** | 0 |
| Infección nosocomial | **2,417** | 173 |
| Medicación | 209 | 6,536 |
| Infección | 0 | 7,754 |

> **Advertencia para la redacción.** Una concordancia del 6.3% entre dos
> detectores del mismo fenómeno implica baja precisión en al menos uno de
> ellos. Debe reportarse como **concordancia entre fuentes de etiqueta**,
> con su kappa, y no asumir que la unión constituye «el corpus verdadero».

---

## 4. Experimento principal — OE2 con etiqueta no circular

Se reentrena el **mismo modelo** sobre la **misma fuente**, cambiando **una
sola variable**: la etiqueta. División **por paciente**, multietiqueta con
Binary Relevance, F1-macro con intervalo de confianza bootstrap (200
remuestreos).

**Resultado (18,989 notas · 14,005 pacientes · 6 naturalezas):**

```
Etiqueta regex  (circular)     F1-macro = 0.515
Etiqueta A1  (no circular)     F1-macro = 0.526   IC95 [0.498 – 0.555]
                               F1-micro = 0.769
                               exact-match = 0.634
```

**Lectura correcta, y sus límites.** La comparación **no es pareja**: 0.515
era sobre 14,853 notas y **8 clases**; 0.526 es sobre 18,989 notas y **6
clases**, y un menor número de clases infla el F1-macro. El delta de +0.011
**no es concluyente y no debe presentarse como tal**.

Lo que sí puede afirmarse:

> Un modelo léxico recupera del texto, con F1-macro 0.526, una etiqueta que
> **no proviene del texto**, sino de un codificador clínico humano. Eso es
> evidencia de aprendizaje real, no de circularidad.

La afirmación inversa **no** se sostiene: esto no demuestra que el 0.515
anterior no fuera circular. Demuestra que es posible alcanzar un desempeño
comparable **sin** circularidad.

**Desempeño por clase:**

| Naturaleza | F1 | Precisión | Recall | n |
|---|---|---|---|---|
| Cuidado del paciente | **0.870** | 0.883 | 0.858 | 1,464 |
| Procedimiento | **0.797** | 0.784 | 0.810 | 1,715 |
| Infección nosocomial | 0.634 | 0.618 | 0.651 | 455 |
| Dispositivo | 0.598 | 0.626 | 0.571 | 555 |
| Medicación | 0.255 | 0.857 | 0.150 | 40 |
| Sistema/Organización | **0.000** | 0.000 | 0.000 | 66 |

Las dos clases mayoritarias alcanzan cifras publicables. El F1-macro queda en
0.526 pese a un F1-micro de 0.769 porque las clases minoritarias lo arrastran.

---

## 5. Escalabilidad entre géneros documentales

El objetivo general exige que el sistema acepte **cualquier texto** —queja,
reporte de incidente, epicrisis o evolución médica—. Para sustentarlo con
evidencia y no por declaración, se evaluó el mismo modelo truncando el texto:

| Longitud del texto | F1-macro |
|---|---|
| 120 caracteres *(mediana de los reportes ERSP)* | **0.213** |
| 500 caracteres | 0.420 |
| 2,000 caracteres *(≈512 tokens)* | 0.433 |
| Completo *(~10,000 caracteres)* | **0.526** |

**Conclusión.** Un modelo entrenado sobre epicrisis **pierde el 60% del
F1-macro** ante un texto de 120 caracteres. El pipeline **no transfiere de
forma directa** a géneros documentales breves: se requiere un modelo
entrenado sobre el género de destino.

**Hallazgo adicional, relevante para una observación de la evaluadora.** Entre
500 y 2,000 caracteres apenas hay mejora (0.420 → 0.433), pero del truncado a
2,000 al texto completo se salta a 0.526. Es decir, **truncar a 512 tokens
cuesta alrededor del 18% del F1-macro**, porque la información discriminante
está distribuida a lo largo de todo el documento. Esto sustenta con una
medición propia —y no solo con cita bibliográfica— la necesidad de
segmentación por fragmentos o de un modelo de contexto largo.

---

## 6. Intento fallido — calibración del umbral de decisión

**Motivación.** El modelo con umbral por defecto producía falsos positivos
inadmisibles: un texto de un solo carácter (`.`) disparaba la clase
«Procedimiento». En un sistema que escala alertas a un responsable
institucional, eso no es aceptable. Además, «Sistema/Organización» tenía
F1 = 0.000 y «Medicación» recall = 0.150.

**Diseño, cuidando la fuga.** Ajustar umbrales mirando el conjunto de prueba
sería fuga metodológica. Se partió en tres, **agrupando siempre por
paciente** y verificando por aserción que ningún paciente cruzara
particiones: `train_fit` · `val` · `test` = 12,208 · 3,080 · 3,701. El umbral
por clase se buscó **sobre validación**, y la prueba se evaluó una sola vez.

**Resultado cuantitativo — mejora:**

| | F1-macro |
|---|---|
| Umbral fijo en 0 | 0.517 |
| Umbral calibrado por clase | **0.547** (+0.030) |

| Naturaleza | Umbral | F1 antes | F1 después | Recall antes | Recall después |
|---|---|---|---|---|---|
| Cuidado del paciente | −0.10 | 0.869 | 0.871 | 0.861 | 0.884 |
| Procedimiento | −0.30 | 0.792 | 0.800 | 0.803 | **0.896** |
| Infección nosocomial | −0.15 | 0.632 | 0.631 | 0.637 | **0.717** |
| Dispositivo | −0.10 | 0.592 | 0.592 | 0.564 | 0.613 |
| Medicación | −0.30 | 0.217 | **0.286** | 0.125 | 0.200 |
| Sistema/Organización | −0.50 | **0.000** | **0.103** | 0.000 | 0.106 |

Se rescató la clase muerta y mejoró el recall en todas.

**Pero el objetivo original NO se cumplió — empeoró:**

| Texto de prueba | Umbral fijo | Calibrado |
|---|---|---|
| `.` | 1 detección | **2** |
| *(vacío)* | 0 | **2** |
| `ok` | 0 | **2** |
| `Paciente estable, sin novedad.` | 0 | **1** |

Todos los umbrales óptimos resultaron **negativos** (−0.10 a −0.50): al
maximizar F1 por clase, el criterio se vuelve **más permisivo**, no menos.
Ganar recall en las clases minoritarias y rechazar textos vacíos son
**objetivos en tensión**, y la calibración por F1 resuelve el primero
sacrificando el segundo.

**Diagnóstico de la causa raíz — y es un defecto de diseño, no de ajuste.**
El corpus A1 contiene **únicamente notas que tienen al menos un evento
adverso codificado**. El modelo **nunca vio un ejemplo negativo**. Por tanto
no aprendió *«¿hay un evento?»* sino *«¿de qué naturaleza es el evento que
sé que hay?»*. Ningún umbral puede corregir eso: la clase «sin evento» no
existe en el espacio de salida.

**Implicación para el objetivo general.** La cadena
`texto → detección → priorización → responsable` requiere una decisión previa
de **detectar o abstenerse**, y el OE2 tal como está formulado no la modela.
Corregirlo exige reconstruir el conjunto de entrenamiento incorporando un
muestreo de epicrisis **sin** código de evento adverso como clase negativa.

---

## 6 bis. Corrección — detector con clase negativa explícita

Se reformuló la tarea en **dos etapas**, que es la única manera de reflejar la
decisión real del sistema:

```
Etapa 1  DETECTOR BINARIO   ¿esta epicrisis contiene un evento adverso?
Etapa 2  CLASIFICADOR       ¿de qué naturaleza?  (solo sobre positivos)
```

**Definición de los negativos.** Epicrisis cuya hospitalización **no tiene
ningún código del mapeo**, ni del estrato A1 ni del A2. Se excluyeron
deliberadamente las A2: son condiciones ambiguas —insuficiencia renal,
neumonía, sepsis— que pueden ser el motivo de ingreso, y usarlas como
negativas habría inyectado ruido de etiqueta justo en los casos difíciles.
Se descartaron además 4,414 negativos pertenecientes a pacientes que ya
figuraban entre los positivos.

**Dataset:** 52,553 epicrisis — 18,989 con evento y 33,564 sin evento.
División por paciente, verificada por aserción: train 42,109 · test 10,444.

**Resultado:**

| Métrica | Valor |
|---|---|
| Sensibilidad (recall) | **0.907** |
| Especificidad | **0.917** |
| Precisión en el conjunto de prueba | 0.856 |
| F1 | 0.881 |
| AUC | **0.973** |

**Prueba de abstención — el fallo que motivó todo esto:**

| Texto | Margen | Decisión |
|---|---|---|
| `.` | −1.71 | se abstiene |
| *(vacío)* | −0.99 | se abstiene |
| `ok` | −0.67 | se abstiene |
| «Paciente estable, sin novedad.» | −0.84 | se abstiene |
| «Routine follow up visit. Vital signs stable…» | −1.31 | se abstiene |
| «Elective knee replacement. Uneventful postoperative course…» | −0.67 | se abstiene |

**6 de 6.** El sistema ya puede abstenerse. El defecto queda cerrado, y se
confirma que la causa era la ausencia de clase negativa y no el umbral.

### La cifra honesta: corrección por prevalencia

El conjunto de prueba tiene 36.1% de positivos **por construcción**, pero la
prevalencia real del estrato A1 es del **6.53%**. Evaluar sin corregir
sobreestima la precisión que el sistema tendría en producción. Aplicando el
teorema de Bayes:

```
VPP = (sens · prev) / (sens · prev + (1 − esp) · (1 − prev))
    = (0.907 · 0.0653) / (0.907 · 0.0653 + 0.083 · 0.9347)
    = 0.433
```

| | Precisión |
|---|---|
| En el conjunto de prueba (36.1% positivos) | 0.856 |
| **A prevalencia real (6.53%)** | **0.433** |

**Es esta segunda cifra la que corresponde citar** al hablar de despliegue: de
cada 100 alertas emitidas sobre el flujo real de epicrisis, unas 43 serían
correctas.

**Lectura correcta de ese 0.433.** No es un mal resultado: es el propio de una
herramienta de **tamizaje**, no de diagnóstico. La salida va a un revisor
humano, no a una acción automática. Lo que no sería defendible es citar el
0.856 como si fuera el desempeño en producción.

### Proyección sobre EsSalud

Aplicando la sensibilidad y la especificidad medidas a los 515,493 egresos
hospitalarios de EsSalud en 2025:

| | Casos/año |
|---|---|
| Eventos adversos esperados (6.53%) | 33,662 |
| Notificados actualmente | 14,275 — el **42%** de los esperados |
| **Alertas que emitiría el detector** | **70,523** (≈193/día) |
| — de ellas, correctas | 30,531 |
| — falsas alarmas | 39,992 |

El sistema **duplicaría con creces la detección actual**: 30,531 eventos
verdaderos frente a los 14,275 que hoy se notifican, **2.1 veces más**.

El coste es explícito y debe declararse: unas 40,000 falsas alarmas al año,
alrededor de 110 diarias en toda la institución, que requieren revisión
humana. Dimensionar esa carga es parte del diseño de implantación y no puede
omitirse al proponer el despliegue.

---

## 7. Cadena completa de punta a punta

Se implementó `05_prototipo_app/motor_v2.py`, que integra el objetivo general:

```
texto (cualquier género) → detección → priorización GEMSES → responsable
```

Diferencias respecto de la versión anterior:

1. Corrige el bug de `re.DOTALL` (ventana acotada a 100 caracteres).
2. Añade el modelo A1 como **segunda señal independiente del léxico**.
3. Armoniza los vocabularios de naturaleza, que diferían entre el mapeo CIE-10
   («Dispositivo», «Medicacion») y los patrones («Dispositivo médico»,
   «Medicación»).
4. Define **concordancia como nivel de confianza**: si ambos detectores
   coinciden en la naturaleza, confianza Alta; si solo uno, Media.

**Prueba con cuatro géneros distintos.** La úlcera por presión de una
evolución médica fue detectada por **ambos** detectores de forma
independiente (confianza Alta). En cambio, **ni la queja ni el reporte de
incidente redactados en español fueron detectados por el detector léxico**,
porque los 35 patrones están escritos en inglés. Confirma con datos la
necesidad del OE5.

**Defecto pendiente en la priorización (OE3).** Con pocos eventos únicos, las
bandas Verde/Amarillo/Rojo salen invertidas: una úlcera por presión (severidad
Alto, impacto 6) quedó **Verde** mientras que un evento de severidad Media
quedó **Rojo**. La causa es que las bandas se calculan por percentiles P25/P75
de la distribución observada, y con n pequeño los percentiles son degenerados.
En producción esto significaría escalar a Dirección un evento leve mientras un
evento grave permanece en el Servicio. Requiere un **n mínimo** o un **corte
absoluto de respaldo**.

---

## 8. Recurso nuevo — base ERSP de EsSalud

Se incorporó una base de **8,799 eventos adversos reales de EsSalud**,
clasificados uno por uno por el autor.

| | Corpus MIMIC | **Base ERSP** |
|---|---|---|
| Casos | 14,853 | 8,799 |
| Idioma | Inglés | **Español** |
| Etiqueta | Regex (circular) | **Juicio experto humano** |
| Naturalezas | 8 de 12 | **12 de 12** |
| Eventos distintos | 40 | **154 de los 231** del Anexo 02 |
| Origen | Hospital de Boston | **EsSalud** |

Supera en 25 veces la muestra de 350 notas previstas para validación experta,
que continuaba en 0/350.

**Decisión de diseño adoptada.** MIMIC permanece como corpus principal y ERSP
entra como validación externa, **con alcance acotado**: entre ambos corpus
cambian simultáneamente el idioma, el género documental (epicrisis de ~10,000
caracteres frente a reportes de ~120) y la calidad de la etiqueta. Por eso
ERSP **no puede funcionar como conjunto de prueba retenido** del modelo
entrenado en MIMIC —una caída de desempeño no sería atribuible—, pero sí como:

1. validación externa de la **operacionalización del Anexo 02**;
2. estimación de la **distribución poblacional real** (en EsSalud predomina
   Cuidado del Paciente con 37% y Gestión de la Organización con 21%, esta
   última inexistente en el corpus MIMIC);
3. corpus de transferencia para ejecutar el **OE5**, que hasta ahora era solo
   un protocolo documentado;
4. base para medir **kappa inter-anotador real** con un segundo experto.

> **Restricción legal.** La base contiene datos personales: DNI, edad, sexo y
> centro asistencial en columnas propias, y en el texto libre 45 descripciones
> con DNI de ocho dígitos, 187 con referencias a historia clínica, 312 con
> fechas y alrededor de 3,971 con nombres propios. Bajo la Ley 29733 no puede
> publicarse ni versionarse sin anonimizar. Se almacenó en
> `_datos_trabajo/ERSP/`, verificado como ignorado por git, y se añadió
> `*.xlsx` al `.gitignore` porque la extensión no estaba cubierta.
>
> **Cola larga en las etiquetas.** De los 154 códigos de evento, solo 47
> tienen 30 casos o más y 25 aparecen una sola vez. La clasificación a 154
> clases no es viable; a nivel de las 12 naturalezas sí.

---

## 9. Resumen para revisión docente

**Defectos encontrados y corregidos**

| # | Defecto | Efecto medido | Estado |
|---|---|---|---|
| 1 | Muestreo no declarado (9% del corpus) | 301,793 epicrisis sin examinar | **Corregido; 331,793 procesadas (100%)** |
| 2 | `re.DOTALL` en los patrones | Detección 48.8% frente a ~9% esperado | **Corregido; −63.7% (258,671 → 93,922)** |
| 3 | Códigos CIE-10 con punto | Tier A al 1.5% de su capacidad | **Corregido; factor 267×** |
| 4 | Vocabularios de naturaleza divergentes | Clases duplicadas al unir tiers | Corregido en `motor_v2` |
| 5 | **Ausencia de clase negativa** | El sistema no podía abstenerse | **Corregido; abstención 6/6, AUC 0.973** |

**Defectos identificados y aún abiertos**

| # | Defecto | Por qué importa |
|---|---|---|
| 6 | Bandas GEMSES degeneradas con n pequeño | Prioriza al revés: evento grave en Verde, leve en Rojo |
| 7 | Detector léxico monolingüe inglés | No detecta quejas ni reportes en español |
| 8 | Muestra de oro sin anotar | 0/350; ERSP la supera pero requiere anonimización y autorización |

**Aportes metodológicos de esta sesión**

1. Primera medición de la **detección con etiqueta no circular**: F1-macro
   0.526, IC95 [0.498–0.555].
2. **Curva de degradación por longitud** del texto, que cuantifica la
   transferencia entre géneros documentales y el costo de truncar a 512
   tokens (≈18% de F1-macro).
3. **Estratificación A1/A2** del Tier A con justificación clínica y validación
   contra la incidencia de la literatura (6.53% frente a ~9%).
4. Documentación de un **intento fallido** —la calibración de umbrales— cuyo
   diagnóstico reveló un defecto de diseño más profundo que el que se
   pretendía corregir.
5. **Ablación de la ventana del patrón sobre el corpus completo** (331,793
   epicrisis), con la separación limpia entre patrones con y sin comodín que
   demuestra que se trataba de un defecto de alcance y no de especificidad.
6. **Detector con clase negativa y capacidad de abstención** (AUC 0.973,
   sensibilidad 0.907), con la **precisión corregida por prevalencia real**
   —0.433 frente al 0.856 del conjunto de prueba— y la proyección de carga
   operativa sobre EsSalud. Es la cifra que corresponde citar al proponer un
   despliegue, y rara vez se reporta en trabajos de este tipo.

---

## 10. Archivos generados

| Archivo | Contenido |
|---|---|
| `04_pipeline_codigo/fase3_v2_corpus_completo.py` | Corpus completo + ablación de ventana del patrón |
| `04_pipeline_codigo/fase3_v2_reanudar.py` | Reanudación tras el corte, con persistencia por bloque |
| `04_pipeline_codigo/fase3_v2_tier_a_corregido.py` | Tier A con el arreglo del punto y la estratificación A1/A2 |
| `04_pipeline_codigo/fase4_v2_etiqueta_a1.py` | OE2 con etiqueta no circular + curva de escalabilidad |
| `04_pipeline_codigo/fase4_v3_umbral_calibrado.py` | Calibración de umbrales sin fuga (intento fallido, documentado) |
| `04_pipeline_codigo/fase4_v4_clase_negativa.py` | Detector binario con clase negativa y corrección por prevalencia |
| `05_prototipo_app/motor_v2.py` | Cadena texto → detección → GEMSES → responsable |
| `datos_intermedios/fase3_v2/` | Candidatos por variante, comparación y aporte por patrón |
| `datos_intermedios/fase4_v2/` | Dataset A1, modelo, métricas y curva por longitud |
| `datos_intermedios/fase4_v3/` | Umbrales, métricas antes y después, modelo calibrado |
| `datos_intermedios/fase4_v4/` | Dataset binario, detector, métricas y prueba de abstención |

Los datos y modelos permanecen fuera del control de versiones por el acuerdo
de uso de MIMIC-IV y por la Ley 29733 en el caso de la base ERSP.

---

## 11. Nota sobre la infraestructura

Durante esta sesión se detectó que el SSD del equipo registra **7,278 errores
de bloque defectuoso en siete días**, y el sistema se cerró por su cuenta una
vez, matando 17 horas de cómputo. Se instaló un disco NVMe adicional de 1 TB
y **la totalidad del proyecto —tesis y PLN_SP, 48,016 archivos— se migró a la
unidad nueva**, verificando la integridad archivo por archivo. Fue necesario
actualizar 27 scripts que tenían rutas absolutas escritas a mano; sin ese
paso nada habría vuelto a ejecutarse.

Se deja constancia porque explica los tiempos de esta sesión y porque
cualquier corrida futura debe lanzarse desde la unidad nueva.

---

*Bitácora cerrada el 27 de julio de 2026, con la ablación completada sobre las
331,793 epicrisis del corpus.*
