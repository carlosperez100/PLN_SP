He verificado el código y los artefactos: el split usa `train_test_split` sin `groups` (líneas 124-126), `subject_id` no entra al `DataFrame` (líneas 80-97), la etiqueta es la moda de detecciones regex (líneas 57-59), el `f1_weighted` es el criterio de selección (línea 146), la matriz de confusión se importa pero nunca se usa (línea 35), y las cifras del JSON/reporte coinciden. La redacción es fiel.

Aquí está la subsección lista para pegar.

---

## Amenazas a la validez y limitaciones

En esta subsección exponemos, con la mayor transparencia posible, las limitaciones metodológicas que afectan la interpretación de los resultados del OE2. Consideramos que reconocerlas de forma explícita es parte del rigor exigible a una tesis de maestría, y que ninguna de ellas invalida el pipeline como prueba de concepto, pero todas condicionan la lectura de las cifras reportadas (exactitud 0.71, F1-ponderado 0.71, F1-macro 0.46 y kappa de Cohen 0.55). Las ordenamos de mayor a menor gravedad.

### Circularidad de la etiqueta: el modelo reaprende las reglas que generaron su propio objetivo

La limitación más seria de nuestro diseño es que la variable objetivo no proviene de anotación humana, sino del propio pipeline de la Fase 3. De las 23.556 detecciones que sustentan las etiquetas, 23.327 (99 por ciento) fueron generadas por patrones de texto (expresiones regulares del Tier B) aplicados sobre la misma nota clínica que después vectorizamos con TF-IDF. Es decir, la etiqueta es, por construcción, una función cerrada del texto de entrada: primero derivamos la naturaleza del evento a partir de subcadenas presentes en la nota (términos como *MRSA*, *bacteremia*, *hypoglycemia*, *medication error*) y luego pedimos a un clasificador de n-gramas que prediga esa misma etiqueta a partir de ese mismo texto. En consecuencia, el modelo no aproxima una verdad clínica latente sino que reimplementa de forma aproximada un banco conocido de reglas.

Esta circularidad explica el patrón observado a nivel de clase: las dos categorías que sostienen las métricas globales (Infección, con F1 de 0.79, y Medicación, con F1 de 0.72) son precisamente las que se etiquetan de manera íntegra por texto, mientras que las categorías que dependen de códigos ICD-10 y no de un disparador léxico rinden mucho peor. Alto donde existe un patrón de texto que copiar, bajo donde no lo hay: esa es la firma esperable del *target leakage*, no la de un aprendizaje clínico genuino.

La implicación directa es que las cifras del OE2 no deben leerse como capacidad de clasificar la naturaleza real de un evento adverso, sino como la fidelidad con que un modelo lineal reproduce la heurística de la Fase 3. El kappa de 0.55 mide concordancia con esa etiqueta débil, no con el juicio de un experto; y su interpretación en la escala de Landis y Koch como "acuerdo moderado" resulta engañosa, porque el supuesto de independencia entre observadores que sustenta ese estadístico está violado (el "anotador" que generó la etiqueta y el clasificador miran el mismo texto con la misma familia de rasgos léxicos). El techo real del experimento es la propia definición de las reglas.

### Ausencia de un patrón de oro anotado por expertos

De forma consistente con lo anterior, verificamos que en ningún punto del pipeline de la Fase 4 se emplea anotación humana. Las columnas previstas para la revisión clínica en la Fase 3 (ANOTACION_EXPERTO, CORRECTO_S_N, NOTAS_ANOTADOR) se crearon vacías y nunca se diligenciaron, y el script de entrenamiento ni siquiera abre el archivo de anotación. El propio código reconoce que la heurística tiene precisión inferior al 50 por ciento en algunas naturalezas (Medicación y Cuidado) y fija como meta pendiente alcanzar el 75 por ciento. Sin una referencia humana independiente, cualquier afirmación del tipo "el modelo clasifica la naturaleza con 71 por ciento de acierto" carece de sustento: un modelo puede alcanzar ese valor reproduciendo fielmente etiquetas que son parcialmente incorrectas.

### Fuga de datos por paciente en la partición

El segundo problema estructural es que la partición de entrenamiento y prueba se realiza a nivel de nota (note_id) y no de paciente (subject_id). Como MIMIC-IV contiene varias notas por paciente, notas de un mismo paciente terminan repartidas entre entrenamiento y prueba. Al reproducir la partición exacta del script (semilla 42, 20 por ciento de prueba), constatamos que 606 de las 2.971 notas de prueba (20,4 por ciento) pertenecen a un paciente que también aparece en entrenamiento, y que 552 pacientes se encuentran simultáneamente a ambos lados del corte. Dado que las notas de alta de un mismo paciente comparten antecedentes, medicación crónica y frases de plantilla, el modelo puede memorizar rasgos idiosincráticos del paciente y reencontrarlos en prueba, lo que infla las métricas.

La información necesaria para evitar esta fuga estaba disponible (subject_id figura en el corpus fuente), de modo que se trata de una decisión corregible y no de una limitación de los datos. Su efecto es real pero acotado: como el 76 por ciento restante de las notas corresponde a pacientes con una sola nota, la caída esperada al corregir la partición es moderada (unos pocos puntos), no un colapso. Conviene subrayar que la validación cruzada implementada tampoco corrige esta fuga, porque baraja notas y no pacientes; por tanto su baja varianza entre pliegues transmite una falsa sensación de robustez.

### Métricas titulares sin cuantificación de la incertidumbre y sin verdadera validación cruzada

Las cifras principales provienen de una única partición con semilla fija, sin intervalos de confianza ni prueba de significancia. La afirmación de que LinearSVC es el "mejor modelo" se sostiene en el ordenamiento de dos valores puntuales, sin una prueba pareada (por ejemplo, McNemar sobre las predicciones del mismo conjunto de prueba) que respalde la superioridad. Además, aunque el script de validación cruzada existe, verificamos que no llegó a completarse: no se generó su archivo de salida y el registro de ejecución muestra que se abortó tras el tercer pliegue del primer modelo (3 de 15 pliegues). En consecuencia, las cifras del OE2 no cuentan hoy con respaldo de variabilidad de ninguna clase.

### Uso del F1-ponderado como titular bajo desbalance severo

Existe un fuerte desbalance: Infección y Medicación concentran el 80,7 por ciento de los casos. Bajo esa distribución, el F1-ponderado (0.71) queda casi por completo determinado por dos de las ocho clases, y oculta el desempeño real en las restantes. El F1-macro honesto (0.46) es 24 puntos más bajo, y ese contraste es en sí mismo el hallazgo diagnóstico: el modelo separa bien las dos clases mayoritarias y colapsa en las demás. Reportar 0.71 de forma aislada, como hemos advertido, sobrerrepresenta el éxito del sistema.

### Colapso de un problema multi-etiqueta a una sola clase

El fenómeno es genuinamente multi-etiqueta: el 30,9 por ciento de las notas presenta dos o más naturalezas distintas. Sin embargo, el diseño colapsa cada nota a su naturaleza primaria mediante la moda de las detecciones, y ante empate el desempate depende del orden de las filas en el archivo. Verificamos que el 22,7 por ciento de las notas presenta un empate en el conteo máximo, de modo que un reordenamiento del corpus cambiaría la etiqueta de referencia de aproximadamente uno de cada ocho registros; la señal descartada se pierde, además, mayoritariamente hacia las clases dominantes, lo que refuerza el desbalance. Medir un problema multi-etiqueta con métricas mono-clase penaliza como error una naturaleza presente pero no primaria, y compromete la reproducibilidad del propio objetivo.

### Clases minoritarias sin poder estadístico

El umbral de inclusión (30 notas) se aplicó sobre el total y no sobre el conjunto de prueba, de modo que categorías como Sangre/Hemoderivados y Sistema/Organización llegan a prueba con apenas 6 y 9 casos respectivamente. Con esos tamaños, un F1 de 0.00 o de 0.40 no distingue la incapacidad del modelo de la simple ausencia de datos para estimarlo, y su intervalo de confianza cubre casi todo el rango posible. Estas colas contaminan el F1-macro, que promedia sin peso una clase estimada con 1.499 casos junto a otra con 6. Por ello, el desempeño por clase en estas categorías no es interpretable como capacidad del sistema.

### Validez externa: idioma y dominio

Finalmente, todo el OE2 se entrenó y evaluó sobre notas de alta de MIMIC-IV, íntegramente en inglés, de un único centro académico de cuidados críticos de los Estados Unidos, con un vectorizador que además elimina *stopwords* inglesas. El objetivo declarado, en cambio, es la clasificación de eventos adversos según el Anexo 02 de EsSalud, sobre texto clínico en español. No disponemos de evidencia de transferibilidad lingüística ni de dominio: el vocabulario aprendido no existe en notas en español, y median diferencias de idioma, epidemiología, patrones de prescripción, codificación y estilo documental. Las prevalencias por naturaleza observadas son un artefacto del corpus y del pipeline de supervisión débil, no una estimación de la incidencia real en EsSalud. En consecuencia, las cifras del OE2 deben leerse como una demostración de factibilidad metodológica sobre corpus en inglés, y no como desempeño esperado en el piloto peruano.

Como nota menor de calidad, advertimos también que las etiquetas se leyeron con una codificación (latin-1) distinta a la del archivo fuente (UTF-8), lo que produce nombres de clase con caracteres corruptos en las tablas de resultados. El efecto sobre las métricas es nulo, porque las etiquetas son tokens opacos para el clasificador, pero conviene corregirlo por presentación y porque anticipa un manejo de tildes y eñes que será crítico al trabajar con texto en español.

### Correcciones propuestas para el piloto

A partir de las limitaciones anteriores, y de mayor a menor prioridad, planteamos las siguientes correcciones para el piloto:

Primero, anotar manualmente las 350 notas ya previstas por al menos dos revisores clínicos, usando las definiciones del Anexo 02, y medir el acuerdo inter-anotador para constituir un verdadero patrón de oro. Sobre esa muestra reportaremos dos números separados y no intercambiables: la precisión de la heurística de la Fase 3 frente al juicio humano, y el desempeño del modelo frente a ese mismo juicio. Solo el segundo responde al OE2.

Segundo, romper la circularidad de la etiqueta. Como análisis de sensibilidad, entrenaremos y evaluaremos enmascarando en el texto los fragmentos exactos que dispararon cada patrón, para estimar cuánta señal existe más allá de reproducir el disparador; si el desempeño colapsa, quedará confirmado que el modelo solo memoriza los gatillos.

Tercero, corregir la partición para que sea por paciente. Propagaremos subject_id hasta el conjunto de datos y sustituiremos la partición aleatoria por GroupShuffleSplit para el hold-out y StratifiedGroupKFold para la validación cruzada, agrupando por paciente. Reportaremos las métricas antes y después de la corrección como cuantificación directa de la magnitud de la fuga.

Cuarto, completar una validación cruzada honesta y con incertidumbre cuantificada. Ejecutaremos la validación agrupada por paciente hasta el final, la elevaremos a fuente primaria de métricas en lugar del split único, reportaremos intervalos de confianza (bootstrap sobre las predicciones o intervalos t sobre los pliegues, empleando la desviación muestral) y aplicaremos una prueba pareada de McNemar antes de declarar cualquier superioridad entre modelos.

Quinto, replantear el OE2 como una tarea multi-etiqueta real (por ejemplo, un clasificador binario por naturaleza) y reportar F1 por etiqueta, micro y macro, además de la pérdida de Hamming, de modo que ninguna naturaleza concurrente se penalice como error. Si por defensa se conserva una versión mono-clase como línea de base, fijaremos un orden canónico de filas y un criterio de desempate clínico y documentado (por severidad o por prioridad normativa), en lugar de la moda dependiente del orden.

Sexto, adoptar métricas honestas de forma sistemática. Presentaremos siempre el F1-macro y el kappa junto al F1-ponderado y la exactitud, acompañados de la tabla por clase con su soporte, y añadiremos la matriz de confusión (que hoy se importa pero nunca se calcula) para diagnosticar hacia dónde van los errores, en particular entre Infección e Infección nosocomial. Elevaremos además el umbral de inclusión para garantizar un soporte mínimo en prueba, o agruparemos las colas irremediablemente pequeñas en una categoría "Otros", declarando explícitamente cuáles clases no son evaluables.

Finalmente, y como condición de validez externa, reencuadraremos las conclusiones actuales como factibilidad metodológica sobre corpus en inglés y constituiremos un corpus piloto de notas de EsSalud en español, aunque sea de unos cientos de notas, sobre el cual reentrenar el vectorizador y volver a medir. Mientras ese corpus no exista, evitaremos toda redacción que atribuya al modelo capacidad de clasificar eventos adversos en el contexto de EsSalud.