"""Localizador de pasajes.

Indexa tus PDF por página y párrafo y, ante una consulta, responde ÚNICAMENTE
dónde leer: documento, página, párrafo y qué término coincidió.
No resume, no parafrasea y no muestra fragmentos del texto.
"""
import os
import re
import unicodedata

import pymupdf as fitz

from .db import RAIZ, conectar


def _huella_archivo(ruta):
    st = os.stat(ruta)
    return f"{st.st_size}-{int(st.st_mtime)}"


def _parrafos_de_pagina(pagina):
    """Bloques de texto de la página en orden de lectura = párrafos."""
    bloques = pagina.get_text("blocks", sort=True)
    for b in bloques:
        if b[6] != 0:  # 0 = texto, 1 = imagen
            continue
        texto = re.sub(r"-\n(\w)", r"\1", b[4])  # une palabras cortadas por guion
        texto = re.sub(r"\s+", " ", texto).strip()
        if len(texto) >= 25:  # descarta encabezados, números de página, etc.
            yield texto


def indexar_carpeta(carpeta, registro=print):
    con = conectar()
    carpeta = carpeta if os.path.isabs(carpeta) else os.path.join(RAIZ, carpeta)
    os.makedirs(carpeta, exist_ok=True)
    rutas = []
    for raiz, _, archivos in os.walk(carpeta):
        rutas += [os.path.join(raiz, a) for a in archivos if a.lower().endswith(".pdf")]

    hechos = 0
    for ruta in sorted(rutas):
        h = _huella_archivo(ruta)
        fila = con.execute("SELECT id, huella FROM documentos WHERE ruta=?", (ruta,)).fetchone()
        if fila and fila["huella"] == h:
            continue
        try:
            pdf = fitz.open(ruta)
        except Exception as e:
            registro(f"  No se pudo abrir {os.path.basename(ruta)}: {e}")
            continue
        if fila:
            con.execute("DELETE FROM parrafos WHERE doc_id=?", (fila["id"],))
            con.execute("UPDATE documentos SET huella=?, paginas=?, indexado=datetime('now','localtime') WHERE id=?",
                        (h, len(pdf), fila["id"]))
            doc_id = fila["id"]
        else:
            doc_id = con.execute("INSERT INTO documentos (ruta,nombre,paginas,huella) VALUES (?,?,?,?)",
                                 (ruta, os.path.basename(ruta), len(pdf), h)).lastrowid
        total = 0
        for n, pag in enumerate(pdf, start=1):
            for k, texto in enumerate(_parrafos_de_pagina(pag), start=1):
                con.execute("INSERT INTO parrafos (texto,doc_id,pagina,parrafo) VALUES (?,?,?,?)",
                            (texto, doc_id, n, k))
                total += 1
        if total == 0:
            registro(f"  {os.path.basename(ruta)}: sin texto (¿PDF escaneado? necesita OCR)")
        hechos += 1
        pdf.close()
        con.commit()

    # Quita del índice los PDF que ya no están en la carpeta
    existentes = set(rutas)
    for fila in con.execute("SELECT id, ruta FROM documentos").fetchall():
        if fila["ruta"].startswith(carpeta) and fila["ruta"] not in existentes:
            con.execute("DELETE FROM parrafos WHERE doc_id=?", (fila["id"],))
            con.execute("DELETE FROM documentos WHERE id=?", (fila["id"],))
    con.commit()
    con.close()
    return hechos, len(rutas)


def _sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _consulta_fts(terminos, modo, raiz):
    partes = []
    for t in terminos:
        t = t.strip().replace('"', "")
        if not t:
            continue
        if " " in t:
            partes.append(f'"{t}"')                      # frase exacta
        else:
            partes.append(f'"{t}"*' if raiz else f'"{t}"')  # raíz: mejora* → mejoramiento
    union = " AND " if modo == "todas" else " OR "
    return union.join(partes)


def buscar(terminos, modo="cualquiera", raiz=True, doc_ids=None, limite=300):
    """Devuelve ubicaciones agrupadas por documento y página. Sin texto."""
    consulta = _consulta_fts(terminos, modo, raiz)
    if not consulta:
        return []
    con = conectar()
    sql = """SELECT p.doc_id, p.pagina, p.parrafo, bm25(parrafos) AS rel,
                    highlight(parrafos, 0, '\x02', '\x03') AS marcado,
                    d.nombre, d.ruta, d.paginas
             FROM parrafos p JOIN documentos d ON d.id = p.doc_id
             WHERE parrafos MATCH ?"""
    args = [consulta]
    if doc_ids:
        sql += f" AND p.doc_id IN ({','.join('?' * len(doc_ids))})"
        args += list(doc_ids)
    sql += " ORDER BY rel LIMIT ?"
    args.append(limite)
    try:
        filas = con.execute(sql, args).fetchall()
    except Exception:
        con.close()
        return []
    con.close()

    docs = {}
    for f in filas:
        # Solo se extraen las palabras que coincidieron, nunca el párrafo.
        hallados = {_sin_tildes(m) for m in re.findall("\x02(.*?)\x03", f["marcado"])}
        d = docs.setdefault(f["doc_id"], {"nombre": f["nombre"], "ruta": f["ruta"],
                                          "doc_id": f["doc_id"], "paginas_total": f["paginas"],
                                          "paginas": {}, "puntaje": 0.0, "terminos": set()})
        pg = d["paginas"].setdefault(f["pagina"], {"parrafos": [], "terminos": set()})
        pg["parrafos"].append(f["parrafo"])
        pg["terminos"] |= hallados
        d["terminos"] |= hallados
        d["puntaje"] += -f["rel"]

    salida = []
    for d in sorted(docs.values(), key=lambda x: -x["puntaje"]):
        paginas = [{"pagina": n, "parrafos": sorted(v["parrafos"]), "terminos": sorted(v["terminos"])}
                   for n, v in sorted(d["paginas"].items())]
        salida.append({"doc_id": d["doc_id"], "nombre": d["nombre"], "ruta": d["ruta"],
                       "paginas_total": d["paginas_total"], "terminos": sorted(d["terminos"]),
                       "rangos": _rangos([p["pagina"] for p in paginas]), "paginas": paginas})
    return salida


def _rangos(nums):
    """[3,4,5,9] → 'págs. 3–5, 9'"""
    if not nums:
        return ""
    grupos, ini, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        grupos.append((ini, prev))
        ini = prev = n
    grupos.append((ini, prev))
    txt = ", ".join(f"{a}–{b}" if a != b else str(a) for a, b in grupos)
    return ("págs. " if len(nums) > 1 else "pág. ") + txt


def listar_documentos():
    con = conectar()
    filas = [dict(r) for r in con.execute(
        "SELECT d.id, d.nombre, d.paginas, d.indexado, d.ruta, "
        "(SELECT count(*) FROM parrafos p WHERE p.doc_id=d.id) AS parrafos "
        "FROM documentos d ORDER BY d.nombre")]
    con.close()
    return filas
