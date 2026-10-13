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


# ---------------------------------------------------------------- OpenAlex
# Cubre gran parte de SciELO, Redalyc, DOAJ y revistas en español.
def openalex(termino, idioma, desde, maximo, correo):
    params = {
        "search": f'"{termino}"',
        "filter": f"from_publication_date:{desde},language:{idioma}",
        "sort": "publication_date:desc",
        "per-page": maximo,
    }
    if correo:
        params["mailto"] = correo
    r = _sesion(correo).get("https://api.openalex.org/works", params=params, timeout=TIEMPO)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        loc = w.get("primary_location") or {}
        oa = w.get("open_access") or {}
        best = w.get("best_oa_location") or {}
        out.append(_item(
            titulo=w.get("title"),
            autores=", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6]),
            fuente="OpenAlex",
            revista=(loc.get("source") or {}).get("display_name"),
            fecha_pub=w.get("publication_date"),
            url=loc.get("landing_page_url") or w.get("doi") or w.get("id"),
            url_pdf=best.get("pdf_url"),
            doi=(w.get("doi") or "").replace("https://doi.org/", ""),
            idioma=w.get("language"),
            acceso_abierto=1 if oa.get("is_oa") else 0,
        ))
    return out


# ---------------------------------------------------------------- Crossref
def crossref(termino, idioma, desde, maximo, correo):
    params = {
        "query.bibliographic": termino,
        "filter": f"from-pub-date:{desde}",
        "sort": "published", "order": "desc", "rows": maximo,
        "select": "DOI,title,author,container-title,issued,URL,link,language",
    }
    if correo:
        params["mailto"] = correo
    r = _sesion(correo).get("https://api.crossref.org/works", params=params, timeout=TIEMPO)
    r.raise_for_status()
    out = []
    t_low = termino.lower()
    for w in r.json().get("message", {}).get("items", []):
        titulo = (w.get("title") or [""])[0]
        # Crossref es laxo: exigimos que el término aparezca en el título
        raices = [p[:5] for p in t_low.split() if len(p) > 3]
        if not all(r in titulo.lower() for r in raices):
            continue
        lang = w.get("language", "")
        if lang and idioma and lang != idioma:
            continue
        partes = (w.get("issued", {}).get("date-parts") or [[None]])[0]
        fecha = "-".join(str(p).zfill(2) for p in partes if p)
        pdf = next((l["URL"] for l in w.get("link", []) if "pdf" in l.get("content-type", "")), "")
        out.append(_item(
            titulo=titulo,
            autores=", ".join(f'{a.get("given","")} {a.get("family","")}'.strip() for a in w.get("author", [])[:6]),
            fuente="Crossref",
            revista=(w.get("container-title") or [""])[0],
            fecha_pub=fecha, url=w.get("URL"), url_pdf=pdf, doi=w.get("DOI"), idioma=lang,
        ))
    return out


# ---------------------------------------------------------------- arXiv
def arxiv(termino, idioma, desde, maximo, correo):
    if idioma != "en":
        return []  # arXiv es casi todo en inglés
    q = f'all:"{termino}"'
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
        "query": f'"{termino}"', "publicationDateOrYear": f"{desde}:",
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
    consulta = f'bibjson.title:"{termino}" OR bibjson.keywords:"{termino}"'
    r = _sesion(correo).get(f"https://doaj.org/api/search/articles/{requests.utils.quote(consulta)}",
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
    patrones = [t.lower() for t in terminos]
    for f in feeds:
        try:
            d = feedparser.parse(f["url"], agent="InvestigadorLocal/1.0")
        except Exception:
            continue
        for e in d.entries:
            titulo = e.get("title", "")
            texto = (titulo + " " + e.get("summary", "") + " " +
                     " ".join(t.get("term", "") for t in e.get("tags", []))).lower()
            coincide = next((p for p in patrones if p in texto), None)
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


CONECTORES = {
    "openalex": openalex,
    "crossref": crossref,
    "arxiv": arxiv,
    "semantic_scholar": semantic_scholar,
    "doaj": doaj,
}


def fecha_desde(dias):
    return (dt.date.today() - dt.timedelta(days=dias)).isoformat()
