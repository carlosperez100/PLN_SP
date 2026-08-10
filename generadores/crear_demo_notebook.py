# -*- coding: utf-8 -*-
"""Construye DEMO_en_vivo.ipynb: demo interactiva para la exposicion.

Parte 1 (ingles, MIMIC): carga el modelo final (fase 9) y corre la CASCADA
completa sobre textos escritos al momento: deteccion con margen y abstencion,
y naturaleza si detecta.
Parte 2 (espanol, ERSP): entrena en segundos los clasificadores de oro y
clasifica descripciones en espanol: naturaleza + codigo de evento + severidad.

Todos los textos de ejemplo son SINTETICOS (escritos para la demo), ningun
texto de paciente real se muestra.
"""
import json

NB = {"cells": [], "metadata": {
    "kernelspec": {"display_name": "Python 3", "language": "python",
                   "name": "python3"},
    "language_info": {"name": "python", "version": "3.13"}},
    "nbformat": 4, "nbformat_minor": 5}


def md(texto):
    NB["cells"].append({"cell_type": "markdown", "metadata": {},
                        "source": texto})


def code(texto):
    NB["cells"].append({"cell_type": "code", "metadata": {},
                        "execution_count": None, "outputs": [],
                        "source": texto})


md("""# DEMO en vivo — Detección de eventos adversos con PLN
**MIA-10 · Carlos Pérez Pérez · UNI 2026**

Dos demostraciones:
1. **Inglés (MIMIC)** — el modelo final de la fase 9: detección con
   abstención + naturaleza (cascada completa) sobre cualquier texto que se
   escriba al momento.
2. **Español (ERSP)** — los clasificadores con etiqueta de oro, entrenados
   aquí mismo en segundos, clasificando descripciones nuevas en español.

*Los textos de ejemplo son sintéticos: ningún texto de paciente real se
muestra en pantalla.*""")

code("""import pickle, warnings
warnings.filterwarnings("ignore")
import numpy as np

RUTA = r"T:\\MIMIC\\tesis\\04_pipeline_codigo\\datos_intermedios"
with open(RUTA + r"\\fase9_final\\modelo_final.pkl", "rb") as f:
    M = pickle.load(f)

vec_d, clf_d = M["deteccion"]["vectorizador"], M["deteccion"]["clasificador"]
vec_n, clf_n = M["naturaleza"]["vectorizador"], M["naturaleza"]["clasificador"]
mlb = M["naturaleza"]["binarizador"]
print("Modelo final (fase 9) cargado: Etapa 1 (detección) + Etapa 2 (naturaleza)")""")

md("""## 1 · El detector en acción (inglés — MIMIC)

**Qué hace `detectar(texto)`** — corre la cascada completa del sistema:

1. **Etapa 1 (detección):** el TF-IDF convierte el texto en un vector y el
   LinearSVC calcula el **margen** — la distancia a la frontera de decisión.
   - margen **positivo** → detecta evento adverso (más margen = más evidencia)
   - margen **negativo** → **se abstiene**: "aquí no hay evidencia de evento".
     Esto es la clase negativa en acción (33,564 notas sin evento en el
     entrenamiento le dieron al modelo el derecho a decir "no").
2. **Etapa 2 (naturaleza):** solo si detectó, clasifica el tipo de evento
   según las clases del Anexo 02 GG-ESSALUD-2021.

Todo corre en **milisegundos, en esta laptop, sin internet** — como exige el
acuerdo de uso de datos de PhysioNet.""")

code("""def detectar(texto):
    margen = float(clf_d.decision_function(vec_d.transform([texto]))[0])
    print(f"  texto : {texto[:90]}{'...' if len(texto) > 90 else ''}")
    print(f"  margen: {margen:+.3f}", end="  ")
    if margen < 0:
        print("->  SE ABSTIENE (no hay evidencia de evento adverso)")
    else:
        print("->  EVENTO ADVERSO DETECTADO")
        etiquetas = mlb.inverse_transform(
            clf_n.predict(vec_n.transform([texto])))[0]
        print(f"  naturaleza (Anexo 02): {', '.join(etiquetas) if etiquetas else '(sin clase dominante)'}")
    print()

# --- 3 casos CON evento (sintéticos) ----------------------------------------
detectar("Postoperative course complicated by wound dehiscence and surgical "
         "site infection requiring reoperation.")
detectar("Patient sustained a fall from bed during hospitalization "
         "resulting in hip fracture requiring surgical repair.")
detectar("The patient developed a stage 3 pressure ulcer on the sacrum "
         "during the ICU stay.")

# --- 2 casos SIN contenido clinico: la abstencion en accion ------------------
detectar("Routine follow up visit. Vital signs stable. No acute events "
         "during the hospital stay.")
detectar("ok")""")

md("""**Cómo leer la salida:** la úlcera por presión dispara con margen ~+4
(evidencia fuerte); la caída de cama, ~+1.9; y ante el texto de control sin
eventos o la palabra "ok", el margen es negativo y el sistema **se abstiene**
— no inventa. Un detector sin clase negativa habría marcado evento hasta en
"ok".

**Demo interactiva:** pedir al público un escenario clínico (en inglés) y
escribirlo en la celda siguiente. *Consejo: frases tipo "hospital course
complicated by..." son el registro típico de una nota de alta.*""")

code("""# ESCRIBIR AQUI el texto que proponga el público (y Ctrl+Enter):
detectar("Patient developed ventilator associated pneumonia on hospital "
         "day 5, treated with broad spectrum antibiotics.")""")

md("""## 2 · El modelo en español (ERSP — etiqueta de oro)

**Qué pasa en la celda siguiente:** se entrenan, **aquí mismo y en
segundos**, tres clasificadores sobre los 6,336 casos peruanos reales cuya
etiqueta asignó un profesional leyendo cada descripción (estándar de oro):

- **naturaleza** del evento (Anexo 02) — LinearSVC
- **código de evento específico** (41 clases modelables) — LinearSVC
- **severidad** (Anexo 03) — Regresión logística

Que entrene en segundos frente al público es parte del argumento: el mismo
enfoque que le ganó al transformer no necesita GPU ni nube.""")

code("""import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

d = pd.read_csv(RUTA + r"\\oe5_ersp\\corpus_limpio.csv")
d = d.dropna(subset=["desc"])
print(f"corpus español: {len(d):,} casos únicos (etiqueta de oro)")

def entrenar(col, Clf, min_ej=30):
    sub = d[d[col].notna() & (d[col].astype(str).str.strip() != "")]
    vc = sub[col].value_counts()
    sub = sub[sub[col].isin(vc[vc >= min_ej].index)]
    pipe = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                        strip_accents="unicode"), Clf)
    pipe.fit(sub.desc, sub[col])
    return pipe

m_nat = entrenar("naturaleza", LinearSVC(class_weight="balanced"))
m_ev  = entrenar("evento",     LinearSVC(class_weight="balanced"))
m_sev = entrenar("severidad",  LogisticRegression(max_iter=3000,
                                                  class_weight="balanced"))
print("tres clasificadores entrenados (naturaleza · evento · severidad)")""")

code("""def clasificar_es(texto):
    print(f"  texto     : {texto[:90]}{'...' if len(texto) > 90 else ''}")
    print(f"  naturaleza: {m_nat.predict([texto])[0]}")
    print(f"  evento    : {m_ev.predict([texto])[0]}")
    print(f"  severidad : {m_sev.predict([texto])[0]}")
    print()

# --- casos sintéticos en español -------------------------------------------
clasificar_es("PACIENTE ADULTO MAYOR SUFRE CAIDA AL LEVANTARSE DE LA CAMA "
              "SIN SUPERVISION, PRESENTA HEMATOMA EN REGION FRONTAL")
clasificar_es("SE ADMINISTRA DOSIS DOBLE DE ANTICOAGULANTE POR ERROR EN LA "
              "TRANSCRIPCION DE LA INDICACION MEDICA")
clasificar_es("PACIENTE POSTOPERADO PRESENTA SECRECION PURULENTA EN HERIDA "
              "QUIRURGICA CON FIEBRE PERSISTENTE")""")

md("""**Cómo leer la salida:** la caída se clasifica como CUIDADO DEL
PACIENTE / CAÍDA DEL PACIENTE; el error de dosis como MEDICACIÓN /
PRESCRIPCIÓN ERRÓNEA; la herida purulenta como INFECCIÓN / SITIO QUIRÚRGICO.
El sistema responde en la taxonomía normativa peruana, en español, con las
tres dimensiones que exige el reporte institucional.

**Demo interactiva:** pedir al público un caso en español (como se relataría
en un reporte real) y escribirlo en la celda siguiente.""")

code("""# ESCRIBIR AQUI el caso que proponga el público (y Ctrl+Enter):
clasificar_es("EQUIPO DE ASPIRACION FALLA DURANTE PROCEDIMIENTO EN SALA DE "
              "OPERACIONES, SE REEMPLAZA CON EQUIPO DE RESPALDO")""")

md("""## 3 · ⭐ DEMO INTERACTIVA: escriba el texto y el modelo identifica

**Así se usa frente al público:** escriba (o pida que le dicten) un caso
clínico en la caja, y presione el botón del idioma correspondiente:

- **ESPAÑOL** → clasifica contra la taxonomía peruana: naturaleza + código
  de evento + severidad (modelos de oro del ERSP).
- **ENGLISH** → corre la cascada MIMIC: detección con margen (o abstención)
  + naturaleza.

No hay que tocar código: solo escribir y hacer clic.""")

code("""import ipywidgets as w
from IPython.display import display, clear_output

caja = w.Textarea(
    value=("PACIENTE SUFRE CAIDA DE LA CAMILLA EN EMERGENCIA MIENTRAS "
           "ESPERABA EVALUACION, PRESENTA TRAUMATISMO EN CODO DERECHO"),
    placeholder="Escriba aquí el caso clínico...",
    layout=w.Layout(width="95%", height="100px"))

b_es = w.Button(description="ANALIZAR — ESPAÑOL (ERSP)",
                button_style="success", layout=w.Layout(width="270px"))
b_en = w.Button(description="ANALYZE — ENGLISH (MIMIC)",
                button_style="primary", layout=w.Layout(width="270px"))
salida = w.Output()

def _es(_):
    with salida:
        clear_output()
        t = caja.value.strip()
        if len(t) < 15:
            print("Escriba un caso más completo (mínimo una frase).")
        else:
            print("=== CLASIFICACIÓN (taxonomía peruana, etiqueta de oro) ===\\n")
            clasificar_es(t)

def _en(_):
    with salida:
        clear_output()
        t = caja.value.strip()
        if len(t) < 15:
            print("Escriba un caso más completo (mínimo una frase).")
        else:
            print("=== CASCADA MIMIC: detección + naturaleza ===\\n")
            detectar(t)

b_es.on_click(_es)
b_en.on_click(_en)
display(w.VBox([caja, w.HBox([b_es, b_en]), salida]))""")

md("""*(La caja viene precargada con un ejemplo: un clic en ANALIZAR —
ESPAÑOL ya muestra el resultado. Luego bórrela y escriba el caso que
proponga el público.)*

---
### Qué demuestran estas celdas

- La **abstención** funciona: el margen negativo ante texto trivial es la
  clase negativa en acción.
- La **cascada** completa corre en milisegundos en una laptop — sin nube,
  sin GPU, cumpliendo el DUA.
- El pipeline en **español** se entrena en segundos y clasifica contra la
  taxonomía normativa peruana: naturaleza, código de evento y severidad.""")

with open(r"T:\MIMIC\PLN_SP\DEMO_en_vivo.ipynb", "w", encoding="utf-8") as f:
    json.dump(NB, f, ensure_ascii=False, indent=1)
print("[OK] T:\\MIMIC\\PLN_SP\\DEMO_en_vivo.ipynb creado")
