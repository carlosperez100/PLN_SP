# -*- coding: utf-8 -*-
"""
=============================================================================
  FASE 3 v2 — REANUDACION DE LA ABLACION TRAS EL CORTE
  Tesis MIA-303 — Carlos Perez Perez
=============================================================================
POR QUE EXISTE ESTE SCRIPT

  La corrida de `fase3_v2_corpus_completo.py` murio el 27-jul-2026 a las
  16:27 por un cierre del sistema (evento 1074 de Windows), tras 17 h 23 min
  y 260,000 de 331,793 epicrisis procesadas (78.4%).

  El script original escribia `progreso.json` en cada bloque, pero NUNCA lo
  leia: el docstring prometia reanudar y esa parte no estaba implementada.
  Relanzarlo tal cual habria empezado de cero.

  Peor aun: las filas de deteccion se acumulaban SOLO EN MEMORIA y se
  escribian al final. Al morir el proceso se perdieron las 203,152 + 73,998
  filas; sobrevivieron unicamente los CONTEOS del checkpoint.

QUE HACE ESTE SCRIPT

  1. Lee `progreso.json` y SALTA las 260,000 epicrisis ya procesadas.
  2. Procesa unicamente las 71,793 restantes (~2 h en vez de ~20 h).
  3. Escribe las filas de deteccion EN CADA BLOQUE (modo append), de modo
     que un nuevo corte ya no pierde nada.
  4. Combina los conteos guardados con los nuevos y emite el resultado de
     la ablacion sobre las 331,793.

LIMITACION QUE HAY QUE DECLARAR EN LA TESIS

  Los CONTEOS de la ablacion cubren las 331,793 epicrisis y son validos:
  provienen del mismo codigo determinista sobre el mismo corpus.

  En cambio las FILAS a nivel de nota solo existen para el ultimo tramo de
  71,793 epicrisis, porque las del primer tramo se perdieron con el proceso.
  Si en algun momento se necesita el corpus de candidatos completo a nivel
  de fila, hay que rehacer la corrida entera (~20 h) sobre una maquina
  estable. Para el resultado de ablacion que se reporta —la tasa de
  deteccion de cada variante— los conteos son suficientes.

SALIDAS (datos_intermedios/fase3_v2/):
  parcial_laxo.csv        filas del tramo reanudado, variante laxa
  parcial_acotado.csv     filas del tramo reanudado, variante acotada
  parcial_tier_a.csv      filas Tier A del tramo reanudado
  progreso.json           checkpoint (ahora si se lee al arrancar)
  ablacion_final.json     resultado combinado sobre las 331,793

USO:
  python fase3_v2_reanudar.py
=============================================================================
"""
import csv
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

import fase3_v2_corpus_completo as base

PATH_SALIDAS = base.PATH_SALIDAS
CHUNK = base.CHUNK
TOTAL_EPICRISIS = 331793

T0 = time.time()


def log(msg):
    el = timedelta(seconds=int(time.time() - T0))
    print(f"[{datetime.now():%H:%M:%S}] [+{el}] {msg}", flush=True)


COLS = ["note_id", "subject_id", "hadm_id", "naturaleza", "evento",
        "severidad", "tier", "patron"]


def abrir_append(nombre):
    """Abre en modo append y escribe cabecera solo si el archivo es nuevo."""
    ruta = PATH_SALIDAS / nombre
    nuevo = not ruta.exists()
    f = open(ruta, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if nuevo:
        w.writerow(COLS)
    return f, w


def main():
    # ---------- checkpoint ----------
    ruta_prog = PATH_SALIDAS / "progreso.json"
    if not ruta_prog.exists():
        log("No hay progreso.json — usa el script original, no este.")
        return
    prog = json.loads(ruta_prog.read_text(encoding="utf-8"))
    ya_vistas = int(prog["notas_vistas"])
    conteo_previo = {"laxo": int(prog["laxo"]), "acotado": int(prog["acotado"])}
    seg_previos = float(prog.get("segundos", 0))

    log(f"Checkpoint: {ya_vistas:,} epicrisis ya procesadas "
        f"({ya_vistas/TOTAL_EPICRISIS:.1%})")
    log(f"Conteos previos — laxo {conteo_previo['laxo']:,} · "
        f"acotado {conteo_previo['acotado']:,}")
    log(f"Faltan {TOTAL_EPICRISIS - ya_vistas:,} epicrisis")

    # ---------- preparacion ----------
    mapping = base.cargar_mapping_tier_a()
    dx_por_hadm = base.indexar_diagnosticos(mapping)
    variantes = base.compilar_variantes()

    f_lax, w_lax = abrir_append("parcial_laxo.csv")
    f_aco, w_aco = abrir_append("parcial_acotado.csv")
    f_ta, w_ta = abrir_append("parcial_tier_a.csv")
    escritores = {"laxo": w_lax, "acotado": w_aco}

    nuevos = {"laxo": 0, "acotado": 0}
    negados = {"laxo": 0, "acotado": 0}
    por_patron = {"laxo": defaultdict(int), "acotado": defaultdict(int)}
    tier_a_nuevas = 0
    notas_vistas = 0
    saltadas = 0

    log(f"Saltando los primeros {ya_vistas:,} registros del .gz ...")

    try:
        for i, ch in enumerate(pd.read_csv(
                base.PATH_DISCHARGE,
                usecols=["note_id", "subject_id", "hadm_id", "text"],
                chunksize=CHUNK, encoding="utf-8")):

            # ---- salto rapido del tramo ya procesado ----
            if saltadas + len(ch) <= ya_vistas:
                saltadas += len(ch)
                if saltadas % (CHUNK * 4) == 0:
                    log(f"  saltadas {saltadas:,}/{ya_vistas:,}")
                continue
            if saltadas < ya_vistas:
                # bloque parcialmente procesado: nos quedamos con la cola
                corte = ya_vistas - saltadas
                ch = ch.iloc[corte:]
                saltadas = ya_vistas
                log(f"  reanudando dentro del bloque, {len(ch):,} notas utiles")

            notas_vistas += len(ch)
            ch = ch[ch["text"].notna()]
            ch = ch[ch["text"].str.len() > base.MIN_LEN_TEXTO]

            # ---------- Tier A ----------
            m_a = ch["hadm_id"].isin(dx_por_hadm)
            for nid, sid, hid in zip(ch.loc[m_a, "note_id"],
                                     ch.loc[m_a, "subject_id"],
                                     ch.loc[m_a, "hadm_id"]):
                for code in dx_por_hadm[hid]:
                    info = mapping[code]
                    w_ta.writerow((nid, sid, hid, info["naturaleza"],
                                   info["evento"], info["severidad"], "A", code))
                    tier_a_nuevas += 1

            # ---------- Tier B, ambas variantes ----------
            for nombre, patrones in variantes.items():
                w = escritores[nombre]
                for clave, (nat, ev, sev, rx) in patrones.items():
                    mask = ch["text"].str.contains(rx, regex=True, na=False)
                    if not mask.any():
                        continue
                    sub = ch[mask]
                    for nid, sid, hid, txt in zip(sub["note_id"],
                                                  sub["subject_id"],
                                                  sub["hadm_id"], sub["text"]):
                        if base.esta_negado(txt, rx):
                            negados[nombre] += 1
                            continue
                        w.writerow((nid, sid, hid, nat, ev, sev, "B", clave))
                        nuevos[nombre] += 1
                        por_patron[nombre][clave] += 1

            # ---------- checkpoint en CADA bloque ----------
            f_lax.flush(); f_aco.flush(); f_ta.flush()
            total_vistas = ya_vistas + notas_vistas
            frac = total_vistas / TOTAL_EPICRISIS
            restante = TOTAL_EPICRISIS - total_vistas
            vel = notas_vistas / max(time.time() - T0, 1e-9)
            eta = restante / max(vel, 1e-9)
            log(f"{total_vistas:>7,}/{TOTAL_EPICRISIS:,} ({frac:6.1%}) | "
                f"nuevas: laxo {nuevos['laxo']:>6,} · acotado {nuevos['acotado']:>6,} | "
                f"ETA {timedelta(seconds=int(eta))}")
            ruta_prog.write_text(json.dumps({
                "notas_vistas": total_vistas,
                "laxo": conteo_previo["laxo"] + nuevos["laxo"],
                "acotado": conteo_previo["acotado"] + nuevos["acotado"],
                "segundos": round(seg_previos + time.time() - T0, 1),
                "tramo_reanudado_desde": ya_vistas,
            }, indent=2), encoding="utf-8")

    finally:
        f_lax.close(); f_aco.close(); f_ta.close()

    # ---------- resultado combinado ----------
    tot_lax = conteo_previo["laxo"] + nuevos["laxo"]
    tot_aco = conteo_previo["acotado"] + nuevos["acotado"]
    total_vistas = ya_vistas + notas_vistas

    resultado = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "experimento": "ablacion de la ventana del patron sobre el corpus completo",
        "corpus": {
            "epicrisis_objetivo": TOTAL_EPICRISIS,
            "epicrisis_procesadas": total_vistas,
            "cobertura_pct": round(100 * total_vistas / TOTAL_EPICRISIS, 2),
        },
        "tramos": {
            "primero": {"epicrisis": ya_vistas,
                        "laxo": conteo_previo["laxo"],
                        "acotado": conteo_previo["acotado"],
                        "nota": "filas perdidas por el corte; solo sobreviven conteos"},
            "reanudado": {"epicrisis": notas_vistas,
                          "laxo": nuevos["laxo"],
                          "acotado": nuevos["acotado"],
                          "tier_a": tier_a_nuevas,
                          "nota": "filas persistidas en parcial_*.csv"},
        },
        "ablacion": {
            "detecciones_laxo": tot_lax,
            "detecciones_acotado": tot_aco,
            "reduccion_absoluta": tot_lax - tot_aco,
            "reduccion_pct": round(100 * (tot_lax - tot_aco) / max(tot_lax, 1), 1),
            "negados_laxo": negados["laxo"],
            "negados_acotado": negados["acotado"],
        },
        "top_patrones_tramo_reanudado": {
            n: dict(sorted(por_patron[n].items(), key=lambda x: -x[1])[:12])
            for n in ("laxo", "acotado")
        },
        "limitacion": (
            "Los conteos cubren las 331,793 epicrisis y son validos (mismo "
            "codigo determinista sobre el mismo corpus). Las filas a nivel de "
            "nota solo existen para el tramo reanudado: las del primer tramo "
            "se perdieron al morir el proceso original, que acumulaba en "
            "memoria. Para un corpus de candidatos completo a nivel de fila "
            "habria que rehacer la corrida entera."),
    }
    (PATH_SALIDAS / "ablacion_final.json").write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 72)
    print("ABLACION DE LA VENTANA DEL PATRON — RESULTADO SOBRE EL CORPUS COMPLETO")
    print("=" * 72)
    print(f"Epicrisis procesadas : {total_vistas:,} de {TOTAL_EPICRISIS:,} "
          f"({100*total_vistas/TOTAL_EPICRISIS:.1f}%)")
    print("-" * 72)
    print(f"  Variante LAXA (re.DOTALL, original) : {tot_lax:>8,} detecciones")
    print(f"  Variante ACOTADA (ventana 100 car.) : {tot_aco:>8,} detecciones")
    print(f"  Reduccion al acotar                 : {tot_lax-tot_aco:>8,} "
          f"({resultado['ablacion']['reduccion_pct']}%)")
    print("-" * 72)
    print(f"Total {timedelta(seconds=int(time.time()-T0))} -> {PATH_SALIDAS}")
    print("=" * 72)


if __name__ == "__main__":
    main()
