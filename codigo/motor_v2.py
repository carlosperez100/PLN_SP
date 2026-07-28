# -*- coding: utf-8 -*-
"""
=============================================================================
  MOTOR v2 — CADENA COMPLETA DEL OBJETIVO GENERAL
  texto -> deteccion -> priorizacion GEMSES -> responsable institucional
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
QUE CAMBIA RESPECTO DE `motor_deteccion.py`

  1. CORRIGE EL BUG DE ALCANCE DEL REGEX.
     El motor v1 compila con `re.DOTALL` (linea 65), de modo que un `.*`
     atraviesa el documento entero: "blood glucose" en la pagina 1 e
     "insulin" en la pagina 5 disparaban hipoglicemia. Medido sobre 2,000
     epicrisis reales: 54.2% de deteccion con el patron laxo frente a 24.1%
     con la ventana acotada. Aqui cada `.*` se limita a 100 caracteres y se
     desactiva DOTALL.

  2. ANADE UN SEGUNDO DETECTOR, INDEPENDIENTE DEL LEXICO.
     `modelo_a1.pkl` (TF-IDF palabra+caracter + LinearSVC multietiqueta)
     entrenado con la etiqueta A1 — codigos ICD-10 de semantica causal
     asignados por un codificador clinico humano, NO derivados del texto.
     Es la unica senal del sistema que no es circular.

  3. ACEPTA CUALQUIER GENERO DOCUMENTAL.
     Queja, reporte de incidente, epicrisis o evolucion medica entran por la
     misma funcion `procesar_texto`. Los n-gramas de CARACTER del modelo dan
     robustez ante cambios de registro, abreviaturas y errores de tipeo, que
     es lo que distingue una queja de familiar de una epicrisis medica.

CONCORDANCIA COMO NIVEL DE CONFIANZA

  Los dos detectores operan a granularidad distinta y por eso se combinan
  en vez de competir:

    - el lexico identifica el EVENTO especifico y su severidad, que es lo
      que alimenta el Impacto de la formula GEMSES;
    - el modelo identifica la NATURALEZA, sin depender de que aparezca la
      frase disparadora.

  Coinciden en naturaleza  -> confianza ALTA
  Solo uno de los dos      -> confianza MEDIA
  Ninguno                  -> no se reporta

  Esa concordancia es medible y reportable: es el sustento de que el
  sistema no es un simple buscador de frases.

USO
    from motor_v2 import procesar_texto, procesar_lote
    r = procesar_texto("El paciente sufrio una caida de la camilla ...")
    r["matriz"]        # priorizacion GEMSES con banda y responsable
    r["detecciones"]   # evidencia por evento, con fragmento citable
=============================================================================
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import pandas as pd

from motor_deteccion import (
    TIER_B_PATRONES,
    IMPACTO_POR_SEVERIDAD,
    RESPONSABLE_POR_BANDA,
    NEGEX_PREFIJOS,
    priorizar_gemses,
)

AQUI = Path(__file__).resolve().parent
RUTA_MODELO = (AQUI.parent / "04_pipeline_codigo" / "datos_intermedios"
               / "fase4_v2" / "modelo_a1.pkl")

VENTANA_PATRON = 100   # caracteres maximos que puede saltar un `.*`
VENTANA_NEGEX = 60

# Las naturalezas del modelo A1 (vocabulario ICD) y las de los patrones
# (vocabulario Tier B) se escriben distinto. Se armonizan al Anexo 02.
ARMONIZAR = {
    "Dispositivo": "Dispositivo médico",
    "Dispositivo medico": "Dispositivo médico",
    "Dispositivo médico": "Dispositivo médico",
    "Medicacion": "Medicación",
    "Medicación": "Medicación",
    "Infeccion nosocomial": "Infección",
    "Infección": "Infección",
    "Cuidado del paciente": "Cuidado del paciente",
    "Procedimiento": "Procedimiento",
    "Sistema/Organizacion": "Gestión de la organización",
    "Sangre/Hemoderivados": "Sangre/Hemoderivados",
    "Diagnóstico": "Diagnóstico",
    "Historia Clínica": "Historia clínica",
}


def armonizar(n: str) -> str:
    return ARMONIZAR.get(str(n).strip(), str(n).strip())


# ---------------------------------------------------------------------------
# 1 — DETECTOR LEXICO, CON LA VENTANA CORREGIDA
# ---------------------------------------------------------------------------
def _acotar(patron: str, n: int = VENTANA_PATRON) -> str:
    return patron.replace(".*", ".{0," + str(n) + "}")


PATRONES_ACOTADOS: dict = {}
for _clave, _val in TIER_B_PATRONES.items():
    _nat, _ev, _sev, _rx = _val[0], _val[1], _val[2], _val[-1]
    try:
        PATRONES_ACOTADOS[_clave] = (
            _nat, _ev, _sev, re.compile(_acotar(_rx), re.IGNORECASE))
    except re.error:
        pass


def detectar_lexico(texto: str, nota_id: str = "") -> list[dict]:
    """Detector de patrones con la ventana acotada y NegEx."""
    if not isinstance(texto, str) or not texto.strip():
        return []
    out = []
    for clave, (nat, ev, sev, rx) in PATRONES_ACOTADOS.items():
        for m in rx.finditer(texto):
            ini_neg = max(0, m.start() - VENTANA_NEGEX)
            if NEGEX_PREFIJOS.search(texto[ini_neg:m.start()]):
                continue
            i, f = max(0, m.start() - 40), min(len(texto), m.end() + 40)
            out.append({
                "nota_id": str(nota_id),
                "naturaleza": armonizar(nat),
                "evento": ev,
                "severidad": sev,
                "impacto": IMPACTO_POR_SEVERIDAD.get(sev, 3),
                "patron": clave,
                "negado": False,
                "origen": "lexico",
                "fragmento": "…" + texto[i:f].replace("\n", " ") + "…",
            })
            break
    return out


# ---------------------------------------------------------------------------
# 2 — DETECTOR POR MODELO (ETIQUETA NO CIRCULAR)
# ---------------------------------------------------------------------------
_MODELO = None
_MODELO_INTENTADO = False


def cargar_modelo():
    """Carga perezosa. Si no existe el .pkl el sistema sigue funcionando
    solo con el detector lexico, y lo declara en la salida."""
    global _MODELO, _MODELO_INTENTADO
    if _MODELO_INTENTADO:
        return _MODELO
    _MODELO_INTENTADO = True
    if RUTA_MODELO.exists():
        try:
            with open(RUTA_MODELO, "rb") as f:
                _MODELO = pickle.load(f)
        except Exception:
            _MODELO = None
    return _MODELO


def detectar_modelo(textos: list[str]) -> list[list[str]]:
    """Devuelve, por texto, la lista de naturalezas predichas (armonizadas)."""
    modelo = cargar_modelo()
    if modelo is None:
        return [[] for _ in textos]
    X = modelo["vectorizador"].transform(textos)
    Y = modelo["clasificador"].predict(X)
    clases = list(modelo["binarizador"].classes_)
    return [[armonizar(clases[j]) for j, v in enumerate(fila) if v]
            for fila in Y]


# ---------------------------------------------------------------------------
# 3 — CADENA COMPLETA
# ---------------------------------------------------------------------------
def procesar_lote(textos, ids=None) -> dict:
    """
    Entrada: lista de textos de CUALQUIER genero (queja, reporte, epicrisis,
    evolucion). Salida: detecciones, matriz GEMSES priorizada y resumen.
    """
    textos = [t if isinstance(t, str) else "" for t in textos]
    ids = list(ids) if ids is not None else [f"texto_{i+1}"
                                             for i in range(len(textos))]

    det = []
    for t, i in zip(textos, ids):
        det.extend(detectar_lexico(t, i))
    df_lex = pd.DataFrame(det)

    nat_modelo = detectar_modelo(textos)
    nat_por_id = dict(zip(ids, nat_modelo))

    # concordancia entre las dos senales
    if not df_lex.empty:
        df_lex["confirmado_modelo"] = [
            nat in nat_por_id.get(nid, [])
            for nid, nat in zip(df_lex["nota_id"], df_lex["naturaleza"])
        ]
        df_lex["confianza"] = df_lex["confirmado_modelo"].map(
            {True: "Alta", False: "Media"})
    else:
        df_lex = pd.DataFrame(columns=[
            "nota_id", "naturaleza", "evento", "severidad", "impacto",
            "patron", "negado", "origen", "fragmento",
            "confirmado_modelo", "confianza"])

    # naturalezas que solo vio el modelo (el lexico no tiene patron para ellas)
    solo_modelo = []
    for nid, nats in nat_por_id.items():
        vistas = set(df_lex.loc[df_lex["nota_id"] == nid, "naturaleza"])
        for n in nats:
            if n not in vistas:
                solo_modelo.append({
                    "nota_id": nid, "naturaleza": n,
                    "evento": f"Evento de naturaleza «{n}» (sin patrón léxico)",
                    "severidad": "Medio",
                    "impacto": IMPACTO_POR_SEVERIDAD["Medio"],
                    "patron": "", "negado": False, "origen": "modelo",
                    "fragmento": "(detectado por el modelo, sin frase disparadora)",
                    "confirmado_modelo": False, "confianza": "Media",
                })
    if solo_modelo:
        df_lex = pd.concat([df_lex, pd.DataFrame(solo_modelo)],
                           ignore_index=True)

    matriz = priorizar_gemses(df_lex)

    n_alta = int((df_lex["confianza"] == "Alta").sum()) if not df_lex.empty else 0
    resumen = {
        "textos_procesados": len(textos),
        "detecciones": int(len(df_lex)),
        "eventos_unicos": int(len(matriz)),
        "naturalezas": int(df_lex["naturaleza"].nunique()) if not df_lex.empty else 0,
        "confianza_alta": n_alta,
        "concordancia_pct": round(100 * n_alta / len(df_lex), 1) if len(df_lex) else 0.0,
        "criticos_rojo": int((matriz["banda"] == "Rojo").sum()) if not matriz.empty else 0,
        "modelo_cargado": cargar_modelo() is not None,
    }
    return {"detecciones": df_lex, "matriz": matriz, "resumen": resumen}


def procesar_texto(texto: str, id_texto: str = "texto_1") -> dict:
    """Atajo para un solo texto."""
    return procesar_lote([texto], [id_texto])


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ejemplos = [
        # queja de un familiar (registro coloquial, texto corto)
        "Mi madre se cayo de la camilla mientras esperaba en emergencia, "
        "nadie la estaba vigilando y se golpeo la cabeza.",
        # reporte de incidente (estilo ERSP)
        "Se administra dosis incorrecta de heparina al paciente, "
        "presentando sangrado activo posterior.",
        # fragmento de evolucion medica
        "Patient developed a stage III pressure ulcer over the sacrum "
        "during this admission.",
        # texto sin evento adverso
        "Paciente acude a control ambulatorio, examen fisico normal, "
        "se indica continuar tratamiento.",
    ]
    r = procesar_lote(ejemplos, ["queja", "reporte", "evolucion", "control"])
    print("RESUMEN:", r["resumen"])
    print("\nDETECCIONES:")
    cols = ["nota_id", "naturaleza", "evento", "severidad", "origen", "confianza"]
    print(r["detecciones"][cols].to_string(index=False) if not r["detecciones"].empty
          else "(ninguna)")
    print("\nMATRIZ GEMSES:")
    print(r["matriz"].to_string(index=False) if not r["matriz"].empty else "(vacia)")
