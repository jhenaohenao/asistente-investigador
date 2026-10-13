"""Conectores a fuentes abiertas. Cada función devuelve una lista de dicts con
las mismas claves: titulo, autores, fuente, revista, fecha_pub, url, url_pdf,
doi, idioma, acceso_abierto.

Solo se guardan metadatos y enlaces: nunca resúmenes ni abstracts.
"""
import datetime as dt
import re
import time
import xml.etree.ElementTree as ET

import feedparser
import requests

TIEMPO = 30


def _sesion(correo):
    s = requests.Session()
    agente = "InvestigadorLocal/1.0"
    if correo:
        agente += f" (mailto:{correo})"  # OpenAlex y Crossref atienden mejor así
    s.headers["User-Agent"] = agente
    return s


def _item(**kw):
    base = dict(titulo="", autores="", fuente="", revista="", fecha_pub="",
                url="", url_pdf="", doi="", idioma="", acceso_abierto=0)
    base.update({k: (v or "") for k, v in kw.items()})
    base["titulo"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", base["titulo"])).strip()
    return base


def _terminos(termino):
    """Una palabra clave con comas es una búsqueda combinada: deben aparecer
    todos los términos. Sin comas, devuelve un solo término."""
    return [t.strip() for t in termino.split(",") if t.strip()] or [termino.strip()]


# ---------------------------------------------------------------- OpenAlex
# Cubre gran parte de SciELO, Redalyc, DOAJ y revistas en español.
def openalex(termino, idioma, desde, maximo, correo):
    params = {
        "search": " AND ".join(f'"{t}"' for t in _terminos(termino)),
        "filter": f"from_publication_date:{desde},language:{idioma}",
        "sort": "publication_date:desc",
        "per-page": maximo,
    }
    return [_openalex_obra(w) for w in _openalex_get("works", params, correo).get("results", [])]


def _openalex_get(ruta, params, correo):
    if correo:
        params["mailto"] = correo
    r = _sesion(correo).get(f"https://api.openalex.org/{ruta}", params=params, timeout=TIEMPO)
    r.raise_for_status()
    return r.json()


def _openalex_obra(w):
    loc = w.get("primary_location") or {}
    oa = w.get("open_access") or {}
    best = w.get("best_oa_location") or {}
    return _item(
        titulo=w.get("title"),
        autores=", ".join((a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])[:6]),
        fuente="OpenAlex",
        revista=(loc.get("source") or {}).get("display_name"),
        fecha_pub=w.get("publication_date"),
        url=loc.get("landing_page_url") or w.get("doi") or w.get("id"),
        url_pdf=best.get("pdf_url"),
        doi=(w.get("doi") or "").replace("https://doi.org/", ""),
        idioma=w.get("language"),
        acceso_abierto=1 if oa.get("is_oa") else 0,
    )


# ---------------------------------------------------------------- Crossref
def crossref(termino, idioma, desde, maximo, correo):
    params = {
        "query.bibliographic": " ".join(_terminos(termino)),
        "filter": f"from-pub-date:{desde}",
        "sort": "published", "order": "desc", "rows": maximo,
        "select": CROSSREF_CAMPOS,
    }
    out = []
    # Crossref es laxo: exigimos que todos los términos aparezcan en el título
    raices = [p[:5] for t in _terminos(termino) for p in t.lower().split() if len(p) > 3]
    for w in _crossref_get(params, correo):
        item = _crossref_obra(w)
        if not all(r in item["titulo"].lower() for r in raices):
            continue
        if item["idioma"] and idioma and item["idioma"] != idioma:
            continue
        out.append(item)
    return out


CROSSREF_CAMPOS = "DOI,title,author,container-title,issued,URL,link,language"


def _crossref_get(params, correo):
    if correo:
        params["mailto"] = correo
    r = _sesion(correo).get("https://api.crossref.org/works", params=params, timeout=TIEMPO)
    r.raise_for_status()
    return r.json().get("message", {}).get("items", [])


def _crossref_obra(w):
    partes = (w.get("issued", {}).get("date-parts") or [[None]])[0]
    fecha = "-".join(str(p).zfill(2) for p in partes if p)
    pdf = next((l["URL"] for l in w.get("link", []) if "pdf" in l.get("content-type", "")), "")
    return _item(
        titulo=(w.get("title") or [""])[0],
        autores=", ".join(f'{a.get("given","")} {a.get("family","")}'.strip() for a in w.get("author", [])[:6]),
        fuente="Crossref",
        revista=(w.get("container-title") or [""])[0],
        fecha_pub=fecha, url=w.get("URL"), url_pdf=pdf, doi=w.get("DOI"), idioma=w.get("language", ""),
    )


# ---------------------------------------------------------------- arXiv
def arxiv(termino, idioma, desde, maximo, correo):
    if idioma != "en":
        return []  # arXiv es casi todo en inglés
    q = " AND ".join(f'all:"{t}"' for t in _terminos(termino))
    r = _sesion(correo).get("https://export.arxiv.org/api/query", params={
        "search_query": q, "sortBy": "submittedDate", "sortOrder": "descending",
        "max_results": maximo}, timeout=TIEMPO)
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in ET.fromstring(r.content).findall("a:entry", ns):
        fecha = (e.findtext("a:published", "", ns) or "")[:10]
        if fecha and fecha < desde:
            continue
        url = e.findtext("a:id", "", ns)
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), "")
        out.append(_item(
            titulo=e.findtext("a:title", "", ns),
            autores=", ".join(a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)[:6]),
            fuente="arXiv", revista="arXiv (preprint)", fecha_pub=fecha,
            url=url, url_pdf=pdf, idioma="en", acceso_abierto=1,
        ))
    time.sleep(3)  # arXiv pide pausas entre consultas
    return out


# ---------------------------------------------------------------- Semantic Scholar
def semantic_scholar(termino, idioma, desde, maximo, correo):
    r = _sesion(correo).get("https://api.semanticscholar.org/graph/v1/paper/search/bulk", params={
        "query": " + ".join(f'"{t}"' for t in _terminos(termino)), "publicationDateOrYear": f"{desde}:",
        "fields": "title,authors,venue,publicationDate,url,externalIds,openAccessPdf",
        "sort": "publicationDate:desc"}, timeout=TIEMPO)
    if r.status_code == 429:  # límite de uso sin clave; se reintenta mañana
        return []
    r.raise_for_status()
    out = []
    for p in (r.json().get("data") or [])[:maximo]:
        pdf = (p.get("openAccessPdf") or {}).get("url", "")
        out.append(_item(
            titulo=p.get("title"),
            autores=", ".join(a.get("name", "") for a in (p.get("authors") or [])[:6]),
            fuente="Semantic Scholar", revista=p.get("venue"),
            fecha_pub=p.get("publicationDate"), url=p.get("url"), url_pdf=pdf,
            doi=(p.get("externalIds") or {}).get("DOI"), acceso_abierto=1 if pdf else 0,
        ))
    time.sleep(1.5)
    return out


# ---------------------------------------------------------------- DOAJ
def doaj(termino, idioma, desde, maximo, correo):
    consulta = " AND ".join(f'(bibjson.title:"{t}" OR bibjson.keywords:"{t}")' for t in _terminos(termino))
    return _doaj_buscar(consulta, desde, maximo, correo)


def _doaj_buscar(consulta, desde, maximo, correo):
    # safe="": la consulta va en la ruta y puede llevar "/" (p. ej. la URL de un ORCID)
    r = _sesion(correo).get(f"https://doaj.org/api/search/articles/{requests.utils.quote(consulta, safe='')}",
                            params={"pageSize": maximo, "sort": "created_date:desc"}, timeout=TIEMPO)
    r.raise_for_status()
    out = []
    anio_desde = desde[:4]
    for res in r.json().get("results", []):
        b = res.get("bibjson", {})
        anio = str(b.get("year", ""))
        if anio and anio < anio_desde:
            continue
        links = b.get("link", [])
        url = next((l["url"] for l in links if l.get("type") == "fulltext"), "")
        doi = next((i["id"] for i in b.get("identifier", []) if i.get("type") == "doi"), "")
        out.append(_item(
            titulo=b.get("title"),
            autores=", ".join(a.get("name", "") for a in b.get("author", [])[:6]),
            fuente="DOAJ", revista=b.get("journal", {}).get("title"),
            fecha_pub=f'{anio}-{str(b.get("month","01")).zfill(2)}' if anio else "",
            url=url or (f"https://doi.org/{doi}" if doi else ""), doi=doi, acceso_abierto=1,
            idioma=",".join(b.get("journal", {}).get("language", [])),
        ))
    return out


# ---------------------------------------------------------------- RSS
def rss(feeds, terminos, filtrar, desde, correo):
    out = []
    patrones = [(t, [p.lower() for p in _terminos(t)]) for t in terminos]
    for f in feeds:
        try:
            d = feedparser.parse(f["url"], agent="InvestigadorLocal/1.0")
        except Exception:
            continue
        for e in d.entries:
            titulo = e.get("title", "")
            texto = (titulo + " " + e.get("summary", "") + " " +
                     " ".join(t.get("term", "") for t in e.get("tags", []))).lower()
            coincide = next((t for t, ps in patrones if all(p in texto for p in ps)), None)
            if filtrar and not coincide:
                continue
            fecha = ""
            if e.get("published_parsed"):
                fecha = time.strftime("%Y-%m-%d", e.get("published_parsed"))
                if fecha < desde:
                    continue
            item = _item(titulo=titulo, autores=e.get("author", ""), fuente="RSS",
                         revista=f["nombre"], fecha_pub=fecha, url=e.get("link", ""))
            item["_termino"] = coincide or "(revista seguida)"
            out.append(item)
    return out


# ---------------------------------------------------------------- Autores seguidos
# Un autor es {nombre, orcid, openalex_id}. Igual que arriba: solo metadatos y enlaces.
def openalex_candidatos(nombre, correo):
    """Autores de OpenAlex que coinciden con un nombre, para elegir el correcto."""
    d = _openalex_get("authors", {"search": nombre, "per-page": 10}, correo)
    return [_openalex_autor_ficha(a) for a in d.get("results", [])]


def openalex_autor_por_orcid(orcid, correo):
    r = _sesion(correo).get(f"https://api.openalex.org/authors/orcid:{orcid}",
                            params={"mailto": correo} if correo else None, timeout=TIEMPO)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _openalex_autor_ficha(r.json())


def _openalex_autor_ficha(a):
    inst = a.get("last_known_institutions") or [a.get("last_known_institution") or {}]
    return {
        "nombre": a.get("display_name") or "",
        "openalex_id": (a.get("id") or "").rsplit("/", 1)[-1],
        "orcid": (a.get("orcid") or "").rsplit("/", 1)[-1],
        "institucion": ", ".join(i["display_name"] for i in inst if i and i.get("display_name")),
        "obras": a.get("works_count") or 0,
    }


def orcid_nombre(orcid, correo):
    """Nombre público registrado en ORCID (por si OpenAlex no conoce al autor)."""
    r = _sesion(correo).get(f"https://pub.orcid.org/v3.0/{orcid}/person",
                            headers={"Accept": "application/json"}, timeout=TIEMPO)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    n = r.json().get("name") or {}
    return " ".join(((n.get(k) or {}).get("value") or "") for k in ("given-names", "family-name")).strip()


def _filtro_autor(autor):
    if autor.get("openalex_id"):
        return f"authorships.author.id:{autor['openalex_id']}"
    return f"authorships.author.orcid:https://orcid.org/{autor['orcid']}"


def openalex_autor(autor, desde, maximo, correo):
    if not (autor.get("openalex_id") or autor.get("orcid")):
        return []
    d = _openalex_get("works", {"filter": f"{_filtro_autor(autor)},from_publication_date:{desde}",
                                "sort": "publication_date:desc", "per-page": maximo}, correo)
    return [_openalex_obra(w) for w in d.get("results", [])]


def crossref_autor(autor, desde, maximo, correo):
    if not autor.get("orcid"):
        return []
    return [_crossref_obra(w) for w in _crossref_get({
        "filter": f"orcid:{autor['orcid']},from-pub-date:{desde}",
        "sort": "published", "order": "desc", "rows": maximo, "select": CROSSREF_CAMPOS}, correo)]


def doaj_autor(autor, desde, maximo, correo):
    if not autor.get("orcid"):
        return []
    return _doaj_buscar(f'bibjson.author.orcid_id:"https://orcid.org/{autor["orcid"]}"', desde, maximo, correo)


def openalex_obra_completa(autor, correo, tope=10000):
    """Todas las obras del autor en OpenAlex, sin límite de fecha (paginado con cursor)."""
    if not (autor.get("openalex_id") or autor.get("orcid")):
        return []
    out, cursor = [], "*"
    while cursor and len(out) < tope:
        d = _openalex_get("works", {"filter": _filtro_autor(autor), "per-page": 200, "cursor": cursor}, correo)
        resultados = d.get("results", [])
        out += [_openalex_obra(w) for w in resultados]
        cursor = (d.get("meta") or {}).get("next_cursor") if resultados else None
    return out


def orcid_obras(autor, correo):
    """Obras declaradas en el perfil público de ORCID (título, revista, fecha, DOI, enlace)."""
    if not autor.get("orcid"):
        return []
    r = _sesion(correo).get(f"https://pub.orcid.org/v3.0/{autor['orcid']}/works",
                            headers={"Accept": "application/json"}, timeout=TIEMPO)
    r.raise_for_status()
    out = []
    for g in r.json().get("group", []):
        w = (g.get("work-summary") or [{}])[0]
        ids = (w.get("external-ids") or {}).get("external-id") or []
        doi = next((i.get("external-id-value") or "" for i in ids if i.get("external-id-type") == "doi"), "")
        f = w.get("publication-date") or {}
        fecha = "-".join(v for v in (((f.get(k) or {}).get("value") or "") for k in ("year", "month", "day")) if v)
        out.append(_item(
            titulo=((w.get("title") or {}).get("title") or {}).get("value"),
            autores=autor.get("nombre"), fuente="ORCID",
            revista=(w.get("journal-title") or {}).get("value"), fecha_pub=fecha,
            url=(w.get("url") or {}).get("value") or (f"https://doi.org/{doi}" if doi else ""),
            doi=doi,
        ))
    return out


CONECTORES_AUTOR = {
    "openalex": openalex_autor,
    "crossref": crossref_autor,
    "doaj": doaj_autor,
}

CONECTORES = {
    "openalex": openalex,
    "crossref": crossref,
    "arxiv": arxiv,
    "semantic_scholar": semantic_scholar,
    "doaj": doaj,
}


def fecha_desde(dias):
    return (dt.date.today() - dt.timedelta(days=dias)).isoformat()
