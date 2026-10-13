"""Autores seguidos: validación de ORCID y alta en config.json."""
import re

from . import fuentes as F

_ORCID = re.compile(r"^(\d{4})-?(\d{4})-?(\d{4})-?(\d{3}[\dX])$")


def digito_control(base15):
    """Dígito de control ORCID (ISO 7064 mod 11-2) para los primeros 15 dígitos."""
    total = 0
    for c in base15:
        total = (total + int(c)) * 2
    resto = (12 - total % 11) % 11
    return "X" if resto == 10 else str(resto)


def normalizar_orcid(texto):
    """Acepta 0000-0002-1825-0097 o https://orcid.org/0000-0002-1825-0097.
    Devuelve la forma canónica o None si el formato o el dígito de control fallan."""
    t = (texto or "").strip().upper()
    t = re.sub(r"^(HTTPS?://)?(WWW\.)?ORCID\.ORG/", "", t).strip("/")
    m = _ORCID.match(t)
    if not m:
        return None
    digitos = "".join(m.groups())
    if digito_control(digitos[:15]) != digitos[15]:
        return None
    return "-".join(m.groups())


def por_orcid(orcid, correo):
    """Ficha de un autor a partir de su ORCID: OpenAlex si lo conoce; si no, el nombre público de ORCID."""
    ficha = None
    try:
        ficha = F.openalex_autor_por_orcid(orcid, correo)
    except Exception:
        pass
    if not ficha or not ficha["nombre"]:
        nombre = ""
        try:
            nombre = F.orcid_nombre(orcid, correo)
        except Exception:
            pass
        ficha = {"nombre": nombre or orcid, "openalex_id": (ficha or {}).get("openalex_id", "")}
    return {"nombre": ficha["nombre"], "orcid": orcid, "openalex_id": ficha["openalex_id"]}


def agregar(cfg, autor):
    """Añade el autor a cfg["autores"] si no estaba. Devuelve (autor guardado, ya_existia)."""
    lista = cfg.setdefault("autores", [])
    for a in lista:
        if (autor["openalex_id"] and a.get("openalex_id") == autor["openalex_id"]) or \
           (autor["orcid"] and a.get("orcid") == autor["orcid"]):
            return a, True
    if any(a["nombre"] == autor["nombre"] for a in lista):  # homónimos: el nombre identifica sus hallazgos
        autor["nombre"] = f'{autor["nombre"]} ({autor["orcid"] or autor["openalex_id"]})'
    lista.append(autor)
    return autor, False
