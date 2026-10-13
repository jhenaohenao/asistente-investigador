"""Búsqueda diaria: consulta todas las fuentes activas y guarda solo lo nuevo."""
import json
import os

from . import fuentes as F
from .db import RAIZ, conectar, huella


def cargar_config():
    with open(os.path.join(RAIZ, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def guardar_config(cfg):
    with open(os.path.join(RAIZ, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _clave(item):
    base = item["doi"].lower() if item["doi"] else (item["url"] or item["titulo"])
    return huella(base)


def ejecutar(registro=print):
    cfg = cargar_config()
    desde = F.fecha_desde(cfg.get("dias_hacia_atras", 7))
    maximo = cfg.get("max_por_fuente", 25)
    correo = cfg.get("correo_contacto", "")
    con = conectar()
    nuevos, errores = 0, []
    titulos_vistos = {r[0] for r in con.execute("SELECT lower(titulo) FROM hallazgos")}

    def guardar(item, termino):
        nonlocal nuevos
        if not item["titulo"] or item["titulo"].lower() in titulos_vistos:
            return
        cur = con.execute(
            """INSERT OR IGNORE INTO hallazgos
               (id,titulo,autores,fuente,revista,fecha_pub,url,url_pdf,doi,idioma,acceso_abierto,palabra_clave)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_clave(item), item["titulo"], item["autores"], item["fuente"], item["revista"],
             item["fecha_pub"], item["url"], item["url_pdf"], item["doi"], item["idioma"],
             item["acceso_abierto"], termino))
        if cur.rowcount:
            nuevos += 1
            titulos_vistos.add(item["titulo"].lower())

    for nombre, funcion in F.CONECTORES.items():
        if not cfg["fuentes"].get(nombre):
            continue
        for idioma, terminos in cfg["palabras_clave"].items():
            for t in terminos:
                try:
                    for it in funcion(t, idioma, desde, maximo, correo):
                        guardar(it, t)
                except Exception as e:
                    errores.append(f"{nombre} / {t}: {type(e).__name__}")
        registro(f"  {nombre}: listo")

    if cfg["fuentes"].get("rss"):
        todos = [t for ts in cfg["palabras_clave"].values() for t in ts]
        try:
            for it in F.rss(cfg.get("rss", []), todos, cfg.get("rss_filtrar_por_palabras", True), desde, correo):
                guardar(it, it.pop("_termino"))
        except Exception as e:
            errores.append(f"rss: {type(e).__name__}")
        registro("  rss: listo")

    con.execute("INSERT INTO ejecuciones (nuevos, detalle) VALUES (?,?)",
                (nuevos, "; ".join(errores[:30])))
    con.commit()
    con.close()
    return nuevos, errores
