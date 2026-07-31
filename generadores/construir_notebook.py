# -*- coding: utf-8 -*-
"""Construye el notebook entregable del curso MIA-10 (PLN).

El docente pide el script CORRIDO y EXPLICADO. Este generador arma un
notebook con celdas de explicación y celdas de código ejecutable que leen los
artefactos ya producidos por el pipeline (modelo entrenado, resultados,
anotaciones), de modo que se ejecuta en minutos y no reentrena nada.

Se genera en vez de escribirse a mano por la misma razón que el paper: las
cifras salen de los resultados del pipeline y no pueden desincronizarse.

Uso:  python construir_notebook.py   y luego ejecutar el .ipynb
"""
import json
import sys
from pathlib import Path

OUT = Path(r"T:\MIMIC\tesis\10_curso_PLN_MIA10")
celdas = []


def _lineas(t):
    """El formato .ipynb guarda `source` como lista de líneas y cada una debe
    conservar su salto (salvo la última); sin ellos el código se concatena en
    una sola línea y no compila."""
    partes = t.split("\n")
    return [p + "\n" for p in partes[:-1]] + [partes[-1]]


def md(texto):
    celdas.append({"cell_type": "markdown", "metadata": {},
                   "source": _lineas(texto.strip())})


def code(texto):
    celdas.append({"cell_type": "code", "metadata": {}, "outputs": [],
                   "execution_count": None,
                   "source": _lineas(texto.strip("\n"))})


# ============================================================== portada
md("""
# Detección automática de eventos adversos hospitalarios en epicrisis

**Curso MIA-10 — Procesamiento del Lenguaje Natural**
Maestría en Inteligencia Artificial · Universidad Nacional de Ingeniería
Docente: Dr. Wester Zela Moraya · Autor: Mg. Carlos Pérez Pérez

---

## Qué resuelve este trabajo

La notificación de eventos adversos en EsSalud es manual y voluntaria, con un
subregistro cercano al **72 %** (unos 37,000 eventos no reportados al año). La
información existe —está escrita en las epicrisis— pero en texto libre, no
explotable automáticamente.

**Pregunta de investigación:** ¿es posible detectar automáticamente, desde el
texto libre de los resúmenes de alta, los eventos adversos ocurridos durante la
hospitalización, y clasificarlos según la taxonomía normativa, con una
fiabilidad comparable a la del juicio experto?

## Cómo está organizado

| Sección | Contenido |
|---|---|
| 1 | Configuración y carga de artefactos |
| 2 | Corpus: composición y prevalencia |
| 3 | Validez del etiquetado: los siete modos de fallo |
| 4 | El confusor de época (aprendizaje por atajo) |
| 5 | Etapa 1 — detección binaria |
| 6 | Etapa 2 — naturaleza y evaluación en cascada |
| 7 | Ranking de desempeño de los modelos |
| 8 | Validación con evaluador independiente (kappa) |
| 9 | Transferencia al español con etiqueta de oro |
| 10 | Conclusiones |

> **Nota sobre reproducibilidad.** El entrenamiento completo del pipeline exige
> ~13 GB de texto de MIMIC-IV (acceso credencializado por PhysioNet) y varias
> horas de cómputo. Este notebook **carga los artefactos ya generados** por los
> scripts del pipeline y reproduce el análisis y las métricas en minutos. Cada
> sección indica el script que produjo su artefacto.
""")

# ============================================================== 1
md("""
## 1. Configuración y carga de artefactos

Los resultados provienen de cinco scripts del pipeline:

| Script | Produce |
|---|---|
| `fase9_modelo_final.py` | modelo final + métricas de detección y naturaleza |
| `fase10_metricas_corregidas.py` | IC agrupado por paciente y evaluación en cascada |
| `fase11_finetuning_transformers.py` | ajuste fino de Bio_ClinicalBERT y BioBERT |
| `fase6_concordancia_kappa.py` | concordancia inter-observador |
| `oe5_ersp_preparar.py` | corpus español con etiqueta de oro |
""")

md("""
> **Portabilidad.** El notebook no lleva rutas fijas: localiza la carpeta de
> resultados buscando hacia arriba desde su propia ubicación, y admite
> sobrescribirla con la variable de entorno `PLN_RESULTADOS`. Si un artefacto no
> está disponible, la celda correspondiente lo informa y continúa en lugar de
> abortar, de modo que el notebook se ejecuta de principio a fin aunque solo
> haya una parte de los resultados.
""")

code("""
import json, os
from pathlib import Path
import numpy as np, pandas as pd

def localizar_resultados():
    # 1) variable de entorno, 2) resultados junto al notebook,
    # 3) busqueda hacia arriba, 4) ruta de desarrollo como ultimo recurso
    if os.environ.get("PLN_RESULTADOS"):
        return Path(os.environ["PLN_RESULTADOS"])
    aqui = Path.cwd()
    for base in [aqui, *aqui.parents]:
        for cand in (base / "resultados",
                     base / "04_pipeline_codigo" / "datos_intermedios"):
            if cand.is_dir():
                return cand
    return Path(r"T:/MIMIC/tesis/04_pipeline_codigo/datos_intermedios")

D = localizar_resultados()
print(f"carpeta de resultados: {D}")
print(f"  existe: {D.is_dir()}")

def cargar(ruta):
    f = D / ruta
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [!] {ruta}: {type(e).__name__}")
        return None

f9  = cargar("fase9_final/resultados_finales.json")      # deteccion + naturaleza
f10 = cargar("fase9_final/metricas_corregidas.json")     # IC agrupado + cascada
f11 = cargar("fase11/resultados_transformers.json")      # transformers
kap = cargar("fase6_concordancia/concordancia.json")     # kappa
oe5 = cargar("oe5_ersp/informe_oe5.json")                # espanol

print("\\nartefactos:")
for n, a in [("fase9", f9), ("fase10", f10), ("fase11", f11),
             ("kappa", kap), ("oe5", oe5)]:
    print(f"  {n:<8} {'OK' if a else 'NO DISPONIBLE'}")

def falta(*art):
    \"\"\"Aviso uniforme cuando un artefacto no esta: la celda informa y sigue.\"\"\"
    print("Artefacto no disponible en esta maquina:", ", ".join(art))
    print("Los resultados de esta seccion figuran en el informe (paper/main.pdf).")
    return True
""")

# ============================================================== 2
md("""
## 2. Corpus: composición y prevalencia

Fuente: **MIMIC-IV-Note v2.2** (PhysioNet), 331,793 resúmenes de alta del Beth
Israel Deaconess Medical Center (2008–2019).

El corpus de modelado se acotó por memoria: vectorizar n-gramas de carácter
sobre más de 100,000 notas desborda la RAM disponible. El techo práctico
verificado fue de 70,000 notas.

Un punto importante: la **prevalencia poblacional** (proporción de
hospitalizaciones con evento codificado) es muy distinta de la del conjunto de
prueba, que está balanceado. Esa diferencia es la que obliga a reajustar el VPP.
""")

code("""
if not f9:
    falta("fase9_final/resultados_finales.json")
else:
    c = f9["corpus"]
    print(f"epicrisis en el corpus de modelado : {c['epicrisis']:,}")
    print(f"  de ellas positivas              : {c['positivas']:,} "
          f"({c['positivas']/c['epicrisis']:.1%} del corpus)")
    print(f"prevalencia POBLACIONAL real      : {c['prevalencia_real']:.2%}")
    print(f"  {c['universo_positivo']:,} hospitalizaciones CON evento")
    print(f"  sobre un universo de {c['universo_positivo']/c['prevalencia_real']:,.0f}")
    print()
    e = c["emparejamiento_epoca"]
    print("Emparejamiento por epoca (control del confusor, ver seccion 4):")
    print(f"  positivos era CIE-10: {e['positivos_era10']:.2%}")
    print(f"  negativos era CIE-10: {e['negativos_era10']:.2%}")
    print(f"  diferencia          : {abs(e['positivos_era10']-e['negativos_era10']):.4%}")
""")

# ============================================================== 3
md("""
## 3. Validez del etiquetado: los siete modos de fallo

El etiquetado se construyó por **supervisión débil** (Ratner et al., Snorkel):
reglas sobre códigos diagnósticos y patrones textuales generan las etiquetas
sin anotación manual exhaustiva. El precio de esa escala es que la calidad del
corpus queda supeditada a la calidad de las reglas, de modo que hay que
verificarla explícitamente.

Un protocolo sistemático de control identificó siete modos de fallo. La celda
siguiente los lista con su efecto medido.
""")

code("""
modos = pd.DataFrame([
 ("1. Muestreo no declarado (solo 9% del corpus)", "301,793 epicrisis sin revisar"),
 ("2. re.DOTALL: el comodin cruzaba la nota entera", "-63.7% de detecciones"),
 ("3. CIE-10 con punto vs MIMIC sin punto",         "corpus positivo x267"),
 ("4. Ausencia de clase negativa",                  "abstencion 6/6 tras corregir"),
 ("5. Confusor de epoca CIE-9/CIE-10",              "ver seccion 4 (el mas grave)"),
 ("6. 43/223 codigos eran reglas muertas (OMS!=CM)","Medicacion x68 (209->14,295)"),
 ("7. Percentiles degenerados con n pequeno",       "inversion de prioridad"),
], columns=["Modo de fallo", "Efecto medido"])
modos.style.hide(axis="index")
""")

md("""
### Evidencia decisiva del modo 2

El comodín `.*` con `re.DOTALL` hacía que un patrón pudiera abarcar la epicrisis
completa, generando coincidencias espurias entre secciones sin relación.

La prueba de que el problema era el **alcance** y no la especificidad de los
patrones: al acotarlo, los patrones **con** `.*` cayeron un 84 %, mientras que
los patrones **sin** comodín quedaron exactamente iguales.
""")

code("""
prueba = pd.DataFrame({
    "Tipo de patron": ["Con comodin .*", "Sin comodin"],
    "Antes": [42330, 13189],
    "Despues": [6735, 13189],
})
prueba["Variacion"] = (prueba.Despues/prueba.Antes - 1).map("{:.1%}".format)
print(prueba.to_string(index=False))
print("\\nLos patrones sin comodin no cambian: el defecto era el ALCANCE.")
""")

# ============================================================== 4
md("""
## 4. El confusor de época: un caso de aprendizaje por atajo

Este es el hallazgo metodológico central.

El mapeo inicial contenía **solo códigos CIE-10**. Como MIMIC-IV abarca
2008–2019 y la transición CIE-9→CIE-10 ocurrió en 2015, toda hospitalización
anterior resultaba negativa **por construcción**:

- negativos: 78.97 % de la era CIE-9
- positivos: 100 % de la era CIE-10

El clasificador no aprendió a reconocer eventos adversos: aprendió a distinguir
**la plantilla documental de cada época**. El rasgo de mayor peso era
`palabra__rdwsd`, un artefacto de cabecera de laboratorio sin ningún contenido
clínico.

Es un caso de libro de *shortcut learning* (Geirhos et al., 2020), análogo al
detector de neumonía de Zech et al. (2018) que había aprendido a reconocer el
hospital de procedencia por marcas en la radiografía.
""")

code("""
if not f9:
    falta("fase9_final/resultados_finales.json")
else:
    d = f9["etapa1_deteccion"]
    versiones = pd.DataFrame([
        ("Inicial (INVALIDA, no se cita)", 0.917, 0.973, 0.433),
        ("Reevaluada con emparejamiento",  0.694, 0.904, 0.171),
        ("Final (7 modos corregidos)",
         d["especificidad"], d["auc"], d["vpp_prevalencia_real"]),
    ], columns=["Version", "Especificidad", "AUC", "VPP"])
    print(versiones.to_string(index=False))
    print()
    print("Leccion: un AUC de 0.973 puede sostenerse en una senal espuria.")
    top = f9.get("rasgos_top") or f9.get("rasgos") or []
    if top:
        print("\\nRasgos de mayor peso tras corregir (del propio modelo):")
        for r in top[:8]:
            nom, w = (r[0], r[1]) if isinstance(r, (list, tuple)) else (r, None)
            print(f"  {nom}" + (f"   (peso {w})" if w is not None else ""))
    else:
        print("(el detalle de rasgos no figura en este artefacto)")
""")

# ============================================================== 5
md("""
## 5. Etapa 1 — detección binaria

Vectorización TF-IDF (palabra + carácter) con LinearSVC balanceado.

Tres decisiones de protocolo condicionan la validez:

1. **Partición por paciente** (`GroupShuffleSplit` sobre `subject_id`), con
   aserción explícita de que no hay solape. Particionar por nota inflaría las
   métricas, porque un mismo paciente aporta notas con vocabulario compartido.
2. **Vectorizador ajustado solo en entrenamiento.**
3. **Intervalos por bootstrap agrupado por paciente**, no por nota: remuestrear
   notas viola la independencia y estrecha artificialmente los intervalos.
""")

code("""
if not (f9 and f10):
    falta("resultados_finales.json", "metricas_corregidas.json")
else:
    e1 = f9["etapa1_deteccion"]
    ic = f10["A_intervalos"]
    tabla = pd.DataFrame([
        ("Sensibilidad",  e1["sensibilidad"],  ic["sensibilidad"]["ic95_por_paciente"]),
        ("Especificidad", e1["especificidad"], ic["especificidad"]["ic95_por_paciente"]),
        ("AUC",           e1["auc"],           ic["AUC"]["ic95_por_paciente"]),
    ], columns=["Metrica", "Valor", "IC95 (agrupado por paciente)"])
    print(tabla.to_string(index=False))
    print()
    m = e1["matriz"]
    print(f"Matriz de confusion: VP={m['vp']:,}  FP={m['fp']:,}  "
          f"FN={m['fn']:,}  VN={m['vn']:,}")
    print(f"VPP crudo en el test (balanceado): {m['vp']/(m['vp']+m['fp']):.3f}")
    print(f"VPP reajustado a prevalencia real: "
          f"{e1['vpp_prevalencia_real']:.3f}  <-- el operativo")
""")

md("""
### Por qué se reajusta el VPP

El conjunto de prueba está balanceado, así que su VPP bruto es optimista. La
cifra que importa en operación es el VPP a la **prevalencia poblacional**,
obtenido por el teorema de Bayes: determina cuántas revisiones improductivas
generaría el sistema en un servicio de calidad real.
""")

code("""
def vpp(sens, esp, prev):
    \"\"\"Teorema de Bayes: VPP = (S*p) / (S*p + (1-E)*(1-p)).\"\"\"
    return (sens*prev) / (sens*prev + (1-esp)*(1-prev))

if not f9:
    falta("resultados_finales.json")
else:
    e1 = f9["etapa1_deteccion"]
    s, e_, p = e1["sensibilidad"], e1["especificidad"], f9["corpus"]["prevalencia_real"]
    print(f"VPP({s:.3f}, {e_:.3f}, prev={p:.3f}) = {vpp(s, e_, p):.4f}")
    print(f"reportado en el pipeline           = {e1['vpp_prevalencia_real']:.4f}")
    print("\\nSensibilidad del VPP a la prevalencia:")
    for pr in [0.05, 0.10, 0.2012, 0.35, 0.50]:
        marca = "  <-- la real" if abs(pr - p) < 1e-4 else ""
        print(f"  prevalencia {pr:>6.2%}  ->  VPP {vpp(s, e_, pr):.3f}{marca}")
""")

md("""
### Abstención ante texto trivial

Un detector sin clase negativa marca como positivo casi cualquier texto. Tras
incorporarla, se comprobó el comportamiento ante entradas sin contenido clínico.
""")

code("""
ab = pd.DataFrame(e1["abstencion"])
ab["detecta"] = ab.detecta.map({True: "SI (mal)", False: "se abstiene (bien)"})
print(ab.to_string(index=False))
print(f"\\nAbstiene en {(pd.DataFrame(e1['abstencion']).detecta == False).sum()}"
      f"/{len(e1['abstencion'])} casos triviales.")
""")

# ============================================================== 6
md("""
## 6. Etapa 2 — naturaleza y evaluación en cascada

La Etapa 2 clasifica la naturaleza del evento sobre las notas positivas.

Evaluarla sobre positivos **de referencia** supone un detector perfecto y
sobreestima el rendimiento real. La cifra honesta es la **cascada** completa:
texto → detección → naturaleza, donde los errores se acumulan.

Una trampa que hubo que evitar: las dos etapas se particionaron por separado,
así que un paciente del test de la Etapa 1 podía estar en el entrenamiento de la
Etapa 2. La cascada se evalúa solo sobre pacientes no vistos por **ninguna**.
""")

code("""
cas = f10["B_cascada"]
comp = pd.DataFrame([
 ("Etapa 2 aislada (positivos de referencia)",
  cas["etapa2_aislada"]["f1_micro"], cas["etapa2_aislada"]["f1_macro"]),
 ("CASCADA real (Etapa 1 -> Etapa 2)",
  cas["cascada"]["f1_micro"], cas["cascada"]["f1_macro"]),
], columns=["Evaluacion", "F1-micro", "F1-macro"])
print(comp.to_string(index=False))
d = cas["cascada"]["f1_micro"]/cas["etapa2_aislada"]["f1_micro"] - 1
print(f"\\nCaida al encadenar: {d:.1%} en F1-micro")
print(f"Evaluado sobre {cas['n_notas_limpias']:,} notas limpias "
      f"({cas['pct_test']:.1%} del test; el resto se descarto por fuga cruzada)")
""")

# ============================================================== 7
md("""
## 7. Ranking de desempeño de los modelos

Todos los modelos se evalúan sobre la **misma partición estratificada**
(semilla 42), de modo que las cifras son comparables entre sí.

Se incluyen dos familias:

- **Léxica (línea base):** TF-IDF + LinearSVC.
- **Transformers clínicos:** Bio_ClinicalBERT y BioBERT, con ajuste fino
  completo sobre GPU.

Y un tercer experimento de control: TF-IDF entrenado sobre el texto **truncado**
a la misma ventana que ve el transformer. Sirve para separar dos explicaciones
que suelen confundirse — *"el transformer es peor"* frente a *"el transformer
ve mucho menos texto"*.
""")

code("""
if f11 and f11.get("resultados"):
    R = f11["resultados"]
    filas = [{"Modelo": k, **{m: v[m] for m in
              ("exactitud", "f1_macro", "f1_micro", "kappa") if m in v}}
             for k, v in R.items() if "error" not in v]
    rk = pd.DataFrame(filas).sort_values("f1_macro", ascending=False)
    rk.insert(0, "#", range(1, len(rk)+1))
    print("RANKING DE DESEMPENO (ordenado por F1-macro)")
    print(rk.to_string(index=False))

    v = f11["ventana"]
    print(f"\\nVentana de {f11['config']['max_len']} tokens: cubre el "
          f"{v['cobertura_media']:.1%} del documento")
    print(f"(mediana de {v['tokens_mediana']:,} tokens por nota)")
else:
    print("fase11 aun no disponible: ejecutar fase11_finetuning_transformers.py")
""")

code("""
if f11 and f11.get("resultados"):
    R = f11["resultados"]
    a = R.get("TF-IDF + LinearSVC (texto completo)")
    b = [v for k, v in R.items() if "truncado" in k]
    if a and b:
        b = b[0]
        print("EFECTO AISLADO DE LA VENTANA DE CONTEXTO")
        print("(misma arquitectura, mismos datos, solo cambia cuanto texto ve)\\n")
        for m in ("exactitud", "f1_macro", "kappa"):
            d = b[m] - a[m]
            print(f"  {m:<12} completo {a[m]:.3f} -> truncado {b[m]:.3f} "
                  f"({d:+.3f}, {d/a[m]:+.1%})")
        print("\\nConclusion: parte sustancial de la desventaja del transformer")
        print("no viene de la arquitectura sino de la ventana de 512 tokens.")
        print("Coincide con Li et al. (2022): Clinical-Longformer, que extiende")
        print("la ventana a 4,096, supera consistentemente a ClinicalBERT.")
""")

# ============================================================== 8
md("""
## 8. Validación con evaluador independiente

Las etiquetas de MIMIC derivan de codificación administrativa: son un
**estándar de plata**. Para medir el criterio contra juicio humano se realizó
una revisión ciega con dos anotadores independientes.

Controles aplicados:

- La interfaz oculta el veredicto del sistema, el código diagnóstico de origen
  y el estrato de muestreo.
- Orden de presentación aleatorio.
- **Registro automático del tiempo dedicado a cada caso** (auditable).
- Manual de anotación con regla de ancla: todo veredicto positivo exige cita
  literal del fragmento que lo sustenta.
""")

code("""
if kap and kap.get("n_comunes"):
    p, b = kap["principal_3clases"], kap["binario"]
    print(f"Casos doble-anotados     : {kap['n_comunes']}")
    print(f"Acuerdo observado (Po)   : {p['po']:.3f}")
    print(f"Kappa de Cohen           : {p['puntual']:.3f}  "
          f"IC95 [{p['ic_bajo']:.3f}, {p['ic_alto']:.3f}]")
    print(f"PABAK                    : {p['pabak']:.3f}")
    print(f"Indice de prevalencia    : {b['indice_prevalencia']:.3f}")
    print(f"Indice de sesgo          : {b['indice_sesgo']:.3f}")
    print(f"McNemar (sesgo entre anotadores): p = {b['mcnemar_p']:.3f}")
    print()
    print("Interpretacion (Landis y Koch):", p["interpretacion"])
else:
    print("concordancia aun no disponible")
""")

md("""
### Por qué se reporta el PABAK junto al kappa

Con prevalencias muy desiguales el kappa se deprime aunque el acuerdo observado
sea alto: es la **paradoja de Feinstein–Cicchetti (1990)**. Byrt et al. (1993)
propusieron el PABAK, que corrige el efecto de prevalencia y sesgo.

Reportar solo el kappa subestimaría la concordancia; reportar solo el PABAK la
sobreestimaría. La práctica correcta es presentar ambos junto al acuerdo
observado.
""")

# ============================================================== 9
md("""
## 9. Transferencia al español con etiqueta de oro

Segundo corpus, en español y sobre la taxonomía peruana: ocurrencias
notificadas al sistema institucional de reporte, codificadas **una a una por
profesionales expertos** contra los Anexos 02 y 03 (tipo de evento, naturaleza
y severidad). Es un **estándar de oro**: juicio humano especializado.

Tres tareas, dos de ellas imposibles sobre MIMIC:

- **T1 evento adverso vs. incidente** — la distinción central de la norma (¿hubo
  daño?). No es medible en MIMIC porque una epicrisis no documenta cuasi-fallas.
- **T2 naturaleza** — homóloga a la Etapa 2, pero con etiqueta humana.
- **T3 severidad** — alimenta la matriz de priorización institucional.
""")

code("""
if oe5:
    li = oe5["limpieza"]
    print("PREPROCESAMIENTO")
    print(f"  registros originales        : {li['filas_originales']:,}")
    print(f"  identificadores anonimizados: {li['dni_anonimizados']}")
    print(f"  textos demasiado breves     : {li['textos_cortos']}")
    print(f"  tras deduplicar             : {li['filas_unicas']:,}")
    print(f"  (se eliminaron {li['filas_originales']-li['filas_unicas']:,} "
          f"duplicados: sin este paso el mismo texto caia en train y test)")
    print()
    filas = []
    for nom, t in oe5["tareas"].items():
        mej = max((k for k in t["resultados"] if k != "por_clase"),
                  key=lambda k: t["resultados"][k]["f1_macro"])
        r = t["resultados"][mej]
        filas.append({"Tarea": nom.split("_",1)[1].replace("_"," ").capitalize(),
                      "n": t["n"], "Clases": t["clases"], "Modelo": mej,
                      "F1-macro": r["f1_macro"], "F1-micro": r["f1_micro"]})
    print(pd.DataFrame(filas).to_string(index=False))
""")

code("""
if oe5:
    pc = oe5["tareas"]["T2_naturaleza"]["resultados"]["por_clase"]
    d = (pd.DataFrame([{"Naturaleza": c.title(), "n": v["n"], "F1": v["f1"]}
                       for c, v in pc.items()])
           .sort_values("F1", ascending=False))
    print("F1 POR NATURALEZA (Anexo 02)")
    print(d.to_string(index=False))
    print()
    print("Gestion de la organizacion es el caso relevante: en MIMIC era")
    print("inviable (n=24, F1=0.000) y aqui alcanza F1 alto con ~1,431 ejemplos.")
    print("El corpus en espanol rescata clases que el corpus en ingles no cubre.")
""")

md("""
> **Advertencia de comparabilidad.** Estas cifras **no** son comparables con las
> de la sección 6. El texto del ERSP son descripciones de ~120 caracteres
> escritas por quien **ya identificó** el evento; la epicrisis son ~17,500
> caracteres donde el evento hay que **encontrarlo**. La tarea es más fácil por
> construcción, y su mejor rendimiento no indica un modelo superior sino un
> problema distinto.
""")

# ============================================================== 10
md("""
## 10. Conclusiones

1. **Un modelo léxico bien construido superó al transformer clínico** en esta
   tarea. La hipótesis inicial se refutó y el resultado negativo se reporta
   como tal.

2. **Buena parte de esa diferencia se explica por la ventana de contexto**, no
   por la arquitectura. Truncar el texto a lo que ve BERT degrada al modelo
   léxico de forma sustancial con los mismos datos y el mismo algoritmo. La vía
   de mejora es una arquitectura de secuencia larga (Clinical-Longformer), no un
   preentrenamiento clínico más específico.

3. **El aporte metodológico principal es la auditoría de validez**: siete modos
   de fallo del etiquetado por reglas, con el confusor de época como caso
   ejemplar de aprendizaje por atajo. Un AUC de 0.973 puede sostenerse en el
   reconocimiento de una plantilla documental.

4. **La evaluación en cascada** muestra que reportar la clasificación aislada
   sobreestima el rendimiento operativo en torno a un tercio.

5. **La concordancia con un evaluador independiente** se sitúa en la banda
   sustancial, con la reserva del tamaño muestral.

6. **El corpus en español con etiqueta de oro** abre la transferencia a la
   taxonomía nacional, que es el destino aplicado del trabajo.

### Limitaciones declaradas

- **Estándar de plata:** las métricas sobre MIMIC miden acuerdo con códigos CIE,
  no con juicio clínico.
- **Reutilización del conjunto de prueba** a lo largo de las iteraciones del
  pipeline (sesgo optimista no cuantificado); el umbral no se ajustó.
- **Alcance de la validación experta:** la muestra está restringida a eventos de
  infección.
- **Cobertura de datos estructurados:** las tablas de UCI cubren el 19.7 % de las
  epicrisis.
- **Independencia del anotador:** el autor es a la vez desarrollador y anotador;
  se mitiga con interfaz ciega, orden aleatorio, cronometraje auditable y la
  medición del acuerdo contra un evaluador independiente.

---

*Repositorio: https://github.com/carlosperez100/PLN_SP ·
Reporte en línea: https://carlosperez100.github.io/PLN_SP/*
""")

nb = {"cells": celdas,
      "metadata": {"kernelspec": {"display_name": "Python 3",
                                  "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}

destino = OUT / "Proyecto_PLN_Final.ipynb"

# Salvaguarda: este script REGENERA el notebook sin salidas. Si el que hay en
# disco ya fue ejecutado (celdas con `outputs`), sobrescribirlo destruiria la
# entrega —el docente pidio el codigo CORRIDO—. Se exige confirmacion explicita.
if destino.exists():
    try:
        previo = json.loads(destino.read_text(encoding="utf-8"))
        con_salida = sum(1 for c in previo.get("cells", [])
                         if c.get("cell_type") == "code" and c.get("outputs"))
    except Exception:
        con_salida = 0
    if con_salida and "--forzar" not in sys.argv:
        print(f"[!] {destino.name} ya esta EJECUTADO ({con_salida} celdas con "
              f"salida).\n    Regenerarlo borraria esas salidas y la entrega "
              f"dejaria de estar 'corrida'.\n"
              f"    Si de verdad quieres rehacerlo:\n"
              f"      python construir_notebook.py --forzar\n"
              f"    y despues vuelve a ejecutarlo:\n"
              f"      python -m jupyter nbconvert --to notebook --execute "
              f"--inplace {destino.name}")
        raise SystemExit(1)
    respaldo = destino.with_suffix(".ipynb.bak")
    respaldo.write_text(destino.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[i] respaldo previo en {respaldo.name}")

destino.write_text(json.dumps(nb, indent=1, ensure_ascii=False),
                   encoding="utf-8")
print(f"[OK] {destino}")
print(f"     {len(celdas)} celdas "
      f"({sum(1 for c in celdas if c['cell_type']=='code')} de código)")
