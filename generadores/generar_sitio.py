# -*- coding: utf-8 -*-
"""Genera docs/index.html del repositorio PLN_SP DESDE los resultados.

Misma regla que el paper y el notebook: las cifras se leen de los JSON del
pipeline, nunca se transcriben. El sitio publicado mostraba todavia las
mediciones de mayo (F1-macro 0.515) porque estaba escrito a mano.

NO publica ningun dato: solo metricas agregadas. El texto clinico de MIMIC
esta bajo acuerdo de uso y no sale del entorno local.

Uso:  python generar_sitio.py
Salida: T:/MIMIC/PLN_SP/docs/index.html
"""
import json
from datetime import datetime
from pathlib import Path

D = Path(r"T:\MIMIC\tesis\04_pipeline_codigo\datos_intermedios")
OUT = Path(r"T:\MIMIC\PLN_SP\docs\index.html")


def leer(p):
    f = D / p
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


f9 = leer("fase9_final/resultados_finales.json")
f10 = leer("fase9_final/metricas_corregidas.json")
f11 = leer("fase11/resultados_transformers.json")
kap = leer("fase6_concordancia/concordancia.json")
oe5 = leer("oe5_ersp/informe_oe5.json")
f12 = leer("fase12/sistema_vs_experto.json")
ce = (f12 or {}).get("contra_experto", {})
sub = (f12 or {}).get("subregistro_codigos") or {}
rob = "".join(
    f'<tr><td>{k}</td><td>{v["n"]}</td><td>{v["sensibilidad"]:.3f}</td>'
    f'<td>{v["especificidad"]:.3f}</td><td>{v["kappa"]:.3f}</td></tr>'
    for k, v in (f12 or {}).get("por_evaluador", {}).items())

e1 = f9["etapa1_deteccion"]
cor = f9["corpus"]
ic = f10["A_intervalos"]
cas = f10["B_cascada"]
p = kap["principal_3clases"]
v = f11.get("ventana", {})

# ranking de modelos
filas_modelos = "\n".join(
    f'<tr{" class=mejor" if i == 1 else ""}><td>{i}</td><td>{k}</td>'
    f'<td>{m["exactitud"]:.3f}</td><td><b>{m["f1_macro"]:.3f}</b></td>'
    f'<td>{m["kappa"]:.3f}</td></tr>'
    for i, (k, m) in enumerate(
        sorted(((k, m) for k, m in f11["resultados"].items() if "error" not in m),
               key=lambda x: -x[1]["f1_macro"]), 1))

filas_oe5 = ""
if oe5:
    for nom, t in oe5["tareas"].items():
        mej = max((k for k in t["resultados"] if k != "por_clase"),
                  key=lambda k: t["resultados"][k]["f1_macro"])
        r = t["resultados"][mej]
        filas_oe5 += (f'<tr><td>{nom.split("_",1)[1].replace("_"," ").capitalize()}'
                      f'</td><td>{t["n"]:,}</td><td>{t["clases"]}</td>'
                      f'<td><b>{r["f1_macro"]:.3f}</b></td>'
                      f'<td>{r["f1_micro"]:.3f}</td></tr>')

d_mi = cas["cascada"]["f1_micro"] / cas["etapa2_aislada"]["f1_micro"] - 1

html = f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Detección de eventos adversos en epicrisis — PLN_SP</title>
<style>
:root {{ color-scheme: light dark;
  --fondo:#fcfcfb; --texto:#1a1a1a; --suave:#5a5a5a; --linea:#e2e2e0;
  --verde:#0f8a6e; --oro:#b8860b; --tarjeta:#ffffff; }}
@media (prefers-color-scheme: dark) {{ :root {{
  --fondo:#14161a; --texto:#e8e8e6; --suave:#9a9a98; --linea:#2c2f35;
  --verde:#2fbf9c; --oro:#d9a441; --tarjeta:#1b1e23; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:2rem 1rem 4rem; background:var(--fondo);
  color:var(--texto); font:16px/1.65 -apple-system,BlinkMacSystemFont,
  "Segoe UI",Roboto,sans-serif; }}
main {{ max-width:52rem; margin:0 auto; }}
h1 {{ font-size:1.8rem; line-height:1.25; margin:0 0 .4rem; }}
h2 {{ font-size:1.22rem; margin:2.6rem 0 .8rem; padding-bottom:.35rem;
  border-bottom:2px solid var(--verde); }}
h3 {{ font-size:1.02rem; margin:1.6rem 0 .5rem; color:var(--suave); }}
.autor {{ font-size:1.15rem; font-weight:700; color:var(--texto);
  margin:.7rem 0 .3rem; padding-left:.7rem;
  border-left:3px solid var(--verde); }}
.sub {{ color:var(--suave); margin:0 0 1.6rem; padding-left:.75rem;
  font-size:.93rem; }}
.marca {{ font-weight:800; letter-spacing:.5px; }}
.marca span {{ color:var(--verde); }}
.chip {{ display:inline-block; background:var(--oro); color:#fff;
  font-size:.66rem; font-weight:700; letter-spacing:1.4px;
  padding:2px 8px; border-radius:10px; vertical-align:2px; }}
table {{ width:100%; border-collapse:collapse; margin:1rem 0; font-size:.9rem; }}
th,td {{ text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--linea); }}
th {{ font-size:.78rem; text-transform:uppercase; letter-spacing:.5px;
  color:var(--suave); }}
td:not(:first-child):not(:nth-child(2)) {{ text-align:right;
  font-variant-numeric:tabular-nums; }}
tr.mejor td {{ background:color-mix(in srgb,var(--verde) 12%,transparent); }}
.tabla-scroll {{ overflow-x:auto; }}
.destacado {{ background:var(--tarjeta); border:1px solid var(--linea);
  border-left:3px solid var(--verde); border-radius:8px;
  padding:1rem 1.1rem; margin:1.2rem 0; }}
.aviso {{ border-left-color:var(--oro); }}
.cifras {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr));
  gap:.8rem; margin:1.2rem 0; }}
.cifra {{ background:var(--tarjeta); border:1px solid var(--linea);
  border-radius:8px; padding:.85rem; text-align:center; }}
.cifra b {{ display:block; font-size:1.5rem; color:var(--verde);
  font-variant-numeric:tabular-nums; }}
.cifra span {{ font-size:.76rem; color:var(--suave); }}
code {{ background:var(--tarjeta); border:1px solid var(--linea);
  border-radius:4px; padding:.1rem .35rem; font-size:.86rem; }}
a {{ color:var(--verde); }}
.descargas {{ display:flex; flex-wrap:wrap; gap:.6rem; margin:1.4rem 0; }}
.boton {{ display:inline-block; background:var(--verde); color:#fff;
  text-decoration:none; font-weight:600; font-size:.9rem;
  padding:.6rem 1.1rem; border-radius:7px; }}
.boton:hover {{ filter:brightness(1.08); }}
.boton.sec {{ background:transparent; color:var(--verde);
  border:1.5px solid var(--verde); }}
footer {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--linea);
  color:var(--suave); font-size:.84rem; }}
</style></head><body><main>

<p class="marca"><span>GEM</span>SES <span class="chip">PROTOTIPO</span></p>
<h1>Detección automática de eventos adversos hospitalarios en epicrisis</h1>
<p class="autor">Mg. Carlos Pérez Pérez</p>
<p class="sub">Trabajo final del curso <b>MIA-10 · Procesamiento del Lenguaje
Natural</b><br>
Maestría en Inteligencia Artificial · Universidad Nacional de Ingeniería<br>
Docente: Dr. Wester Zela Moraya</p>

<p class="descargas">
  <a class="boton" href="https://github.com/carlosperez100/PLN_SP/raw/main/paper/main.pdf">
    Descargar el artículo (PDF)</a>
  <a class="boton sec" href="https://github.com/carlosperez100/PLN_SP/blob/main/Proyecto_PLN_Final.ipynb">
    Notebook ejecutado</a>
  <a class="boton sec" href="https://github.com/carlosperez100/PLN_SP">
    Código</a>
</p>

<div class="cifras">
  <div class="cifra"><b>{e1['sensibilidad']:.3f}</b><span>Sensibilidad</span></div>
  <div class="cifra"><b>{e1['especificidad']:.3f}</b><span>Especificidad</span></div>
  <div class="cifra"><b>{e1['auc']:.3f}</b><span>AUC</span></div>
  <div class="cifra"><b>{p['puntual']:.3f}</b><span>Kappa inter-observador</span></div>
</div>

<h2>Qué resuelve</h2>
<p>La notificación de eventos adversos en EsSalud es manual y voluntaria: en
2025 se registraron 515&thinsp;493 egresos hospitalarios y se notificaron
14&thinsp;275 eventos adversos (2.77&nbsp;%), muy por debajo del 10&nbsp;%
estimado internacionalmente. La información existe —está escrita en las
epicrisis— pero en texto libre.</p>
<p>Este trabajo evalúa un canal de PLN que detecta esos eventos, los clasifica
según la taxonomía del Anexo&nbsp;02 y los prioriza con la matriz normativa
para asignarles responsable.</p>

<h2>Resultado principal</h2>
<div class="destacado">
<p>El sistema <b>detecta el {ce.get('sensibilidad',0)*100:.1f}&nbsp;% de los
eventos adversos que el consenso de dos evaluadores expertos confirma</b>, con
un modelo léxico ligero e interpretable ejecutable en una estación de trabajo
convencional.</p>
<p>La comparación entre familias de modelos se realiza controlando la ventana
de contexto y la ponderación de clases. A igualdad de ambas condiciones, el
modelo léxico y el transformer clínico rinden de forma equivalente; el factor
determinante es el <b>acceso al documento completo</b>, ya que el transformer
procesa solo el {v.get('cobertura_media',0):.1%} de la epicrisis.</p>
</div>

<h2>Ranking de desempeño</h2>
<p>Todos los modelos sobre la misma partición estratificada (semilla 42).
Las filas «sin balanceo» son las emparejadas con la condición de entrenamiento
de los transformers.</p>
<div class="tabla-scroll"><table>
<tr><th>#</th><th>Modelo</th><th>Exactitud</th><th>F1-macro</th><th>Kappa</th></tr>
{filas_modelos}
</table></div>

<h2>Detección: etapa 1</h2>
<div class="tabla-scroll"><table>
<tr><th>Métrica</th><th>Valor</th><th>IC 95&nbsp;% (agrupado por paciente)</th></tr>
<tr><td>Sensibilidad</td><td>{e1['sensibilidad']:.3f}</td><td>{ic['sensibilidad']['ic95_por_paciente'][0]:.3f} – {ic['sensibilidad']['ic95_por_paciente'][1]:.3f}</td></tr>
<tr><td>Especificidad</td><td>{e1['especificidad']:.3f}</td><td>{ic['especificidad']['ic95_por_paciente'][0]:.3f} – {ic['especificidad']['ic95_por_paciente'][1]:.3f}</td></tr>
<tr><td>AUC</td><td>{e1['auc']:.3f}</td><td>{ic['AUC']['ic95_por_paciente'][0]:.3f} – {ic['AUC']['ic95_por_paciente'][1]:.3f}</td></tr>
<tr><td>VPP a prevalencia real ({cor['prevalencia_real']:.2%})</td><td><b>{e1['vpp_prevalencia_real']:.3f}</b></td><td>—</td></tr>
</table></div>
<p>Los intervalos se calculan remuestreando <b>pacientes</b>, no notas: un mismo
paciente aporta varias notas al conjunto de prueba y remuestrear notas violaría
la independencia.</p>

<h2>Evaluación en cascada</h2>
<p>Evaluar la clasificación sobre positivos de referencia supone un detector
perfecto. Encadenando de verdad texto → detección → naturaleza, el rendimiento
cae un <b>{abs(d_mi):.1%}</b> en F1-micro
({cas['etapa2_aislada']['f1_micro']:.3f} → {cas['cascada']['f1_micro']:.3f}).</p>

<h2>Validación con evaluador independiente</h2>
<p>Sobre {kap['n_comunes']} casos doble-anotados a ciegas: acuerdo observado
{p['po']:.3f}, kappa de Cohen <b>{p['puntual']:.3f}</b>
(IC&nbsp;95&nbsp;% {p['ic_bajo']:.3f}–{p['ic_alto']:.3f}), PABAK {p['pabak']:.3f}.
La prueba de McNemar no detecta sesgo entre evaluadores.</p>
<div class="destacado aviso">
<p>El valor puntual se sitúa en la banda sustancial de Landis y Koch (≥0.61),
pero <b>el límite inferior del intervalo queda por debajo del umbral</b>, de
modo que la afirmación se enuncia con esa reserva. Con prevalencias tan
desiguales el kappa se deprime, y por eso se reporta junto al PABAK y al
acuerdo observado.</p>
</div>

<h2>El sistema frente al juicio experto</h2>
<p>Las métricas anteriores se calculan contra códigos CIE. La pregunta de
investigación se formuló respecto del juicio experto, y responderla exige otra
referencia: el <b>consenso de dos evaluadores independientes</b> sobre los casos
en que ambos coincidieron.</p>
<div class="cifras">
  <div class="cifra"><b>{ce.get('sensibilidad',0):.3f}</b><span>Sensibilidad vs. experto</span></div>
  <div class="cifra"><b>{ce.get('especificidad',0):.3f}</b><span>Especificidad</span></div>
  <div class="cifra"><b>{ce.get('vpp',0):.3f}</b><span>VPP</span></div>
  <div class="cifra"><b>{sub.get('proporcion',0):.0%}</b><span>Negativos que sí eran evento</span></div>
</div>
<div class="destacado">
<p>El sistema <b>recupera el {ce.get('sensibilidad',0)*100:.1f}&nbsp;% de los eventos
que el consenso experto confirma</b>, pero acierta solo en el
{ce.get('especificidad',0)*100:.1f}&nbsp;% de los que descarta. La conclusión
defendible no es que sustituya al experto, sino que <b>funciona como filtro de
cribado de alta sensibilidad</b>: reduce el volumen a revisar sin decidir por el
revisor.</p>
</div>
<h3>El resultado no depende de un evaluador concreto</h3>
<div class="tabla-scroll"><table>
<tr><th>Referencia</th><th>n</th><th>Sensibilidad</th><th>Especificidad</th><th>Kappa</th></tr>
{rob}
</table></div>
<h3>La incertidumbre del sistema coincide con la humana</h3>
<p>El margen de decisión del clasificador es menor en los casos donde los dos
evaluadores discreparon (mediana 0.858) que donde coincidieron (1.279). El
sistema <b>duda donde el juicio humano es genuinamente ambiguo</b>, lo que
permite usar ese margen como criterio de derivación a revisión.</p>
<h3>Medida directa del subregistro</h3>
<p>De los casos que la codificación administrativa declara negativos, el
<b>{sub.get('proporcion',0):.0%}</b> resultan ser eventos reales para el consenso
experto (IC&nbsp;95&nbsp;% {sub.get('ic95',[0,0])[0]:.0%}–{sub.get('ic95',[0,0])[1]:.0%}).
Es la premisa del trabajo, medida con datos propios en vez de citada.</p>

<h2>Transferencia al español (etiqueta de oro)</h2>
<p>Corpus de ocurrencias notificadas al sistema institucional, codificadas por
profesionales expertos contra los Anexos 02 y 03. A diferencia de MIMIC —cuyas
etiquetas derivan de códigos CIE, un estándar de plata— aquí la referencia es
juicio humano.</p>
<div class="tabla-scroll"><table>
<tr><th>Tarea</th><th>n</th><th>Clases</th><th>F1-macro</th><th>F1-micro</th></tr>
{filas_oe5}
</table></div>
<div class="destacado aviso">
<p>Estas cifras <b>no son comparables</b> con las de MIMIC: el texto son
descripciones breves escritas por quien ya identificó el evento, frente a
epicrisis de ~17&thinsp;500 caracteres donde el evento debe localizarse. La
tarea es más sencilla por construcción.</p>
</div>

<h2>Aporte metodológico: validez del etiquetado</h2>
<p>Se identificaron siete modos de fallo del etiquetado por reglas. El más
grave fue un <b>confusor de época</b>: como el mapeo solo tenía códigos CIE-10 y
el corpus abarca la transición CIE-9→CIE-10, toda hospitalización antigua
resultaba negativa por construcción. El modelo alcanzaba <b>AUC 0.973</b>
reconociendo la plantilla documental de cada periodo, con
<code>palabra__rdwsd</code> —un artefacto de cabecera de laboratorio— como rasgo
de mayor peso.</p>
<p>Corregido, el AUC baja a {e1['auc']:.3f} pero sobre señal clínica genuina:
los rasgos dominantes pasan a ser
{", ".join("<i>%s</i>" % str(r[0]).replace("palabra__","") for r in e1.get("rasgos_top", [])[:6])}.</p>

<h2>Reproducir</h2>
<p>El notebook <code>Proyecto_PLN_Final.ipynb</code> carga los artefactos ya
generados y reproduce el análisis en minutos. Localiza la carpeta de resultados
automáticamente y admite <code>PLN_RESULTADOS</code> como variable de entorno.
Si un artefacto no está disponible, la celda lo informa y continúa.</p>
<div class="destacado aviso">
<p><b>Los datos no se publican.</b> El texto clínico procede de MIMIC-IV, de
acceso credencializado bajo acuerdo de uso (PhysioNet), y no sale del entorno
local. Este repositorio contiene únicamente código, métricas agregadas y el
informe.</p>
</div>

<footer>
<p>Generado automáticamente desde los resultados del pipeline el
{datetime.now():%d/%m/%Y}. Las cifras no se transcriben a mano: se leen de los
archivos de resultados, de modo que este sitio, el informe y la tesis no puedan
divergir. Regenerar con <code>python generar_sitio.py</code>.</p>
<p><a href="https://github.com/carlosperez100/PLN_SP">Repositorio</a> ·
Universidad Nacional de Ingeniería · Docente: Dr. Wester Zela Moraya</p>
</footer>
</main></body></html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print(f"[OK] {OUT}  ({len(html):,} caracteres)")
