"""Interfaz local. Ejecuta `python app.py` y abre http://127.0.0.1:5077"""
import csv
import io
import os
import re
import threading
import webbrowser

import requests
from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from nucleo import autores, busqueda, pasajes
from nucleo import fuentes as F
from nucleo.db import RAIZ, conectar

app = Flask(__name__)
PUERTO = 5077
estado_tarea = {"corriendo": False, "mensaje": ""}


def _en_segundo_plano(nombre, funcion):
    if estado_tarea["corriendo"]:
        return False

    def correr():
        estado_tarea.update(corriendo=True, mensaje=f"{nombre}…")
        try:
            estado_tarea["mensaje"] = funcion()
        except Exception as e:
            estado_tarea["mensaje"] = f"Error: {e}"
        finally:
            estado_tarea["corriendo"] = False

    threading.Thread(target=correr, daemon=True).start()
    return True


@app.route("/")
def inicio():
    return render_template("index.html")


# ------------------------------------------------------------ Novedades
@app.get("/api/hallazgos")
def api_hallazgos():
    estado = request.args.get("estado", "")
    texto = request.args.get("q", "").strip()
    autor = request.args.get("autor", "")
    sql, args = "SELECT * FROM hallazgos WHERE 1=1", []
    if estado:
        sql += " AND estado=?"
        args.append(estado)
    else:
        sql += " AND estado!='descartado'"
    if autor:
        sql += " AND id IN (SELECT hallazgo_id FROM hallazgo_autor WHERE autor=?)"
        args.append(autor)
    for t in (t.strip() for t in texto.split(",")):  # con comas: deben estar todos
        if t:  # "autor: <nombre>" también encuentra lo que trajo ese autor seguido
            sql += (" AND (titulo LIKE ? OR autores LIKE ? OR revista LIKE ? OR palabra_clave LIKE ?"
                    " OR id IN (SELECT hallazgo_id FROM hallazgo_autor WHERE 'autor: ' || autor LIKE ?))")
            args += [f"%{t}%"] * 5
    sql += " ORDER BY encontrado DESC, fecha_pub DESC LIMIT " + ("5000" if autor else "500")
    con = conectar()
    filas = [dict(r) for r in con.execute(sql, args)]
    conteo = {r["estado"]: r["n"] for r in con.execute("SELECT estado, count(*) n FROM hallazgos GROUP BY estado")}
    ultima = con.execute("SELECT * FROM ejecuciones ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    return jsonify(items=filas, conteo=conteo, ultima=dict(ultima) if ultima else None)


@app.post("/api/hallazgos/<hid>/estado")
def api_estado(hid):
    nuevo = request.json.get("estado")
    if nuevo not in ("nuevo", "por_leer", "leido", "descartado"):
        abort(400)
    con = conectar()
    con.execute("UPDATE hallazgos SET estado=? WHERE id=?", (nuevo, hid))
    con.commit()
    con.close()
    return jsonify(ok=True)


@app.post("/api/hallazgos/<hid>/descargar")
def api_descargar(hid):
    """Guarda el PDF de acceso abierto en tu biblioteca para poder indexarlo."""
    con = conectar()
    h = con.execute("SELECT * FROM hallazgos WHERE id=?", (hid,)).fetchone()
    con.close()
    if not h or not h["url_pdf"]:
        return jsonify(ok=False, error="Este registro no tiene PDF abierto."), 400
    carpeta = os.path.join(RAIZ, busqueda.cargar_config().get("carpeta_pdfs", "biblioteca"))
    os.makedirs(carpeta, exist_ok=True)
    nombre = re.sub(r"[^\w\- ]", "", h["titulo"])[:90].strip() or hid
    ruta = os.path.join(carpeta, f"{nombre}.pdf")
    try:
        r = requests.get(h["url_pdf"], timeout=60, headers={"User-Agent": "InvestigadorLocal/1.0"})
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            return jsonify(ok=False, error="El enlace no entregó un PDF directo; ábrelo en el navegador."), 400
        with open(ruta, "wb") as f:
            f.write(r.content)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400
    pasajes.indexar_carpeta(carpeta, registro=lambda *_: None)
    return jsonify(ok=True, archivo=os.path.basename(ruta))


@app.post("/api/buscar_ahora")
def api_buscar_ahora():
    def tarea():
        n, err = busqueda.ejecutar(registro=lambda *_: None)
        return f"Búsqueda terminada: {n} enlaces nuevos" + (f" ({len(err)} fuentes con error)" if err else "")
    return jsonify(iniciada=_en_segundo_plano("Buscando en las fuentes", tarea))


@app.get("/api/tarea")
def api_tarea():
    return jsonify(estado_tarea)


@app.get("/exportar.csv")
def exportar():
    con = conectar()
    filas = con.execute("SELECT titulo,autores,revista,fecha_pub,doi,url,url_pdf,fuente,palabra_clave,estado,encontrado "
                        "FROM hallazgos ORDER BY encontrado DESC").fetchall()
    con.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["titulo", "autores", "revista", "fecha", "doi", "url", "pdf", "fuente", "palabra_clave", "estado", "encontrado"])
    w.writerows([tuple(f) for f in filas])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=hallazgos.csv"})


# ------------------------------------------------------------ Autores seguidos
@app.get("/api/autores/candidatos")
def api_autores_candidatos():
    nombre = request.args.get("nombre", "").strip()
    if not nombre:
        return jsonify(candidatos=[])
    try:
        return jsonify(candidatos=F.openalex_candidatos(nombre, busqueda.cargar_config().get("correo_contacto", "")))
    except Exception as e:
        return jsonify(error=f"OpenAlex no respondió ({type(e).__name__})."), 502


@app.post("/api/autores")
def api_autores_agregar():
    """Sigue a un autor: {orcid} (se valida y se busca su nombre) o un candidato {nombre, openalex_id, orcid}."""
    d = request.json or {}
    cfg = busqueda.cargar_config()
    orcid = autores.normalizar_orcid(d.get("orcid")) or ""
    if d.get("orcid") and not orcid and not d.get("openalex_id"):
        return jsonify(error="ORCID no válido: revisa el formato 0000-0000-0000-0000 y el dígito final (puede ser X)."), 400
    if d.get("openalex_id"):  # candidato de OpenAlex: un ORCID mal formado se descarta
        autor = {"nombre": (d.get("nombre") or "").strip() or d["openalex_id"], "orcid": orcid,
                 "openalex_id": d["openalex_id"].rsplit("/", 1)[-1]}
    elif orcid:
        autor = autores.por_orcid(orcid, cfg.get("correo_contacto", ""))
    else:
        return jsonify(error="Falta el ORCID o el autor de OpenAlex."), 400
    autor, ya = autores.agregar(cfg, autor)
    if not ya:
        busqueda.guardar_config(cfg)
    return jsonify(autor=autor, ya_existia=ya)


@app.post("/api/autores/quitar")
def api_autores_quitar():
    nombre = (request.json or {}).get("nombre")
    cfg = busqueda.cargar_config()
    cfg["autores"] = [a for a in cfg.get("autores", []) if a["nombre"] != nombre]
    busqueda.guardar_config(cfg)
    return jsonify(ok=True)


@app.post("/api/autores/obra_completa")
def api_obra_completa():
    nombre = (request.json or {}).get("nombre", "")

    def tarea():
        n, total, err = busqueda.obra_completa(nombre)
        return (f"Obra completa de {nombre}: {total} obras ({n} nuevas)"
                + (f" · no respondió: {', '.join(err)}" if err else ""))
    return jsonify(iniciada=_en_segundo_plano(f"Trayendo la obra completa de {nombre}", tarea))


# ------------------------------------------------------------ Pasajes
@app.post("/api/indexar")
def api_indexar():
    def tarea():
        carpeta = busqueda.cargar_config().get("carpeta_pdfs", "biblioteca")
        hechos, total = pasajes.indexar_carpeta(carpeta, registro=lambda *_: None)
        return f"Biblioteca al día: {total} PDF ({hechos} indexados ahora)"
    return jsonify(iniciada=_en_segundo_plano("Indexando tus PDF", tarea))


@app.get("/api/documentos")
def api_documentos():
    carpeta = busqueda.cargar_config().get("carpeta_pdfs", "biblioteca")
    ruta = carpeta if os.path.isabs(carpeta) else os.path.join(RAIZ, carpeta)
    return jsonify(documentos=pasajes.listar_documentos(), carpeta=ruta)


@app.post("/api/pasajes")
def api_pasajes():
    d = request.json or {}
    terminos = [t for t in d.get("terminos", []) if t.strip()]
    tema = d.get("tema")
    if tema:
        terminos += busqueda.cargar_config().get("temas", {}).get(tema, [])
    return jsonify(resultados=pasajes.buscar(terminos, d.get("modo", "cualquiera"),
                                             bool(d.get("raiz", True)), d.get("doc_ids") or None),
                   terminos=terminos)


@app.get("/pdf/<int:doc_id>")
def ver_pdf(doc_id):
    con = conectar()
    f = con.execute("SELECT ruta FROM documentos WHERE id=?", (doc_id,)).fetchone()
    con.close()
    if not f or not os.path.exists(f["ruta"]):
        abort(404)
    return send_file(f["ruta"], mimetype="application/pdf")


# ------------------------------------------------------------ Configuración
@app.get("/api/config")
def api_config():
    return jsonify(busqueda.cargar_config())


@app.post("/api/config")
def api_config_guardar():
    cfg = busqueda.cargar_config()
    cfg.update(request.json or {})
    busqueda.guardar_config(cfg)
    return jsonify(ok=True)


if __name__ == "__main__":
    os.makedirs(os.path.join(RAIZ, "biblioteca"), exist_ok=True)
    if not os.environ.get("NO_ABRIR"):
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PUERTO}")).start()
    print(f"Investigador local en http://127.0.0.1:{PUERTO}  (cierra esta ventana para salir)")
    app.run(host="127.0.0.1", port=PUERTO, debug=False)
