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


class _Almacen:
    """Guarda hallazgos sin duplicados (por DOI/URL y por título) y anota qué autor seguido los trajo."""

    def __init__(self, con):
        self.con = con
        self.nuevos = 0
        self.ids_por_titulo = {t: i for t, i in con.execute("SELECT lower(titulo), id FROM hallazgos")}

    def guardar(self, item, termino, autor=None):
        if not item["titulo"]:
            return
        t = item["titulo"].lower()
        hid = self.ids_por_titulo.get(t)
        if hid is None:
            hid = _clave(item)
            cur = self.con.execute(
                """INSERT OR IGNORE INTO hallazgos
                   (id,titulo,autores,fuente,revista,fecha_pub,url,url_pdf,doi,idioma,acceso_abierto,palabra_clave)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (hid, item["titulo"], item["autores"], item["fuente"], item["revista"],
                 item["fecha_pub"], item["url"], item["url_pdf"], item["doi"], item["idioma"],
                 item["acceso_abierto"], termino))
            if cur.rowcount:
                self.nuevos += 1
                self.ids_por_titulo[t] = hid
        if autor:  # aunque ya existiera (p. ej. llegó por palabra clave), queda asociado al autor
            self.con.execute("INSERT OR IGNORE INTO hallazgo_autor (hallazgo_id, autor) VALUES (?,?)", (hid, autor))


def etiqueta_autor(autor):
    return f"autor: {autor['nombre']}"


def ejecutar(registro=print):
    cfg = cargar_config()
    desde = F.fecha_desde(cfg.get("dias_hacia_atras", 7))
    maximo = cfg.get("max_por_fuente", 25)
    correo = cfg.get("correo_contacto", "")
    con = conectar()
    alm = _Almacen(con)
    errores = []

    for nombre, funcion in F.CONECTORES.items():
        if not cfg["fuentes"].get(nombre):
            continue
        for idioma, terminos in cfg["palabras_clave"].items():
            for t in terminos:
                try:
                    for it in funcion(t, idioma, desde, maximo, correo):
                        alm.guardar(it, t)
                except Exception as e:
                    errores.append(f"{nombre} / {t}: {type(e).__name__}")
        registro(f"  {nombre}: listo")

    if cfg["fuentes"].get("rss"):
        todos = [t for ts in cfg["palabras_clave"].values() for t in ts]
        try:
            for it in F.rss(cfg.get("rss", []), todos, cfg.get("rss_filtrar_por_palabras", True), desde, correo):
                alm.guardar(it, it.pop("_termino"))
        except Exception as e:
            errores.append(f"rss: {type(e).__name__}")
        registro("  rss: listo")

    for autor in cfg.get("autores", []):
        for nombre, funcion in F.CONECTORES_AUTOR.items():
            if not cfg["fuentes"].get(nombre):
                continue
            try:
                for it in funcion(autor, desde, maximo, correo):
                    alm.guardar(it, etiqueta_autor(autor), autor["nombre"])
            except Exception as e:
                errores.append(f"{nombre} / {etiqueta_autor(autor)}: {type(e).__name__}")
    if cfg.get("autores"):
        registro("  autores seguidos: listo")

    con.execute("INSERT INTO ejecuciones (nuevos, detalle) VALUES (?,?)",
                (alm.nuevos, "; ".join(errores[:30])))
    con.commit()
    con.close()
    return alm.nuevos, errores


def obra_completa(nombre_autor):
    """Todas las obras de un autor seguido, sin límite de fecha (OpenAlex + perfil público de ORCID).
    Devuelve (nuevos, total asociados al autor, errores)."""
    cfg = cargar_config()
    autor = next((a for a in cfg.get("autores", []) if a["nombre"] == nombre_autor), None)
    if not autor:
        raise ValueError(f"No sigues a {nombre_autor}")
    correo = cfg.get("correo_contacto", "")
    con = conectar()
    alm = _Almacen(con)
    errores = []
    for nombre, funcion in (("openalex", F.openalex_obra_completa), ("orcid", F.orcid_obras)):
        try:
            for it in funcion(autor, correo):
                alm.guardar(it, etiqueta_autor(autor), autor["nombre"])
        except Exception as e:
            errores.append(f"{nombre}: {type(e).__name__}")
    total = con.execute("SELECT count(*) FROM hallazgo_autor WHERE autor=?", (autor["nombre"],)).fetchone()[0]
    con.commit()
    con.close()
    return alm.nuevos, total, errores
