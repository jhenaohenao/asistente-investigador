"""Base de datos local (SQLite). Todo queda en la carpeta del programa."""
import hashlib
import os
import sqlite3

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_DB = os.path.join(RAIZ, "datos.sqlite")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS hallazgos (
    id           TEXT PRIMARY KEY,      -- huella del DOI o de la URL (evita duplicados)
    titulo       TEXT NOT NULL,
    autores      TEXT,
    fuente       TEXT,                  -- de dónde vino (OpenAlex, arXiv, RSS...)
    revista      TEXT,
    fecha_pub    TEXT,
    url          TEXT,
    url_pdf      TEXT,
    doi          TEXT,
    idioma       TEXT,
    acceso_abierto INTEGER DEFAULT 0,
    palabra_clave TEXT,                 -- qué término lo trajo
    encontrado   TEXT DEFAULT (datetime('now','localtime')),
    estado       TEXT DEFAULT 'nuevo'   -- nuevo | por_leer | leido | descartado
);
CREATE INDEX IF NOT EXISTS ix_hall_encontrado ON hallazgos(encontrado);

CREATE TABLE IF NOT EXISTS documentos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta    TEXT UNIQUE NOT NULL,
    nombre  TEXT,
    paginas INTEGER,
    huella  TEXT,                       -- detecta si el PDF cambió
    indexado TEXT DEFAULT (datetime('now','localtime'))
);

-- Un registro por párrafo. remove_diacritics: "extension" encuentra "extensión".
CREATE VIRTUAL TABLE IF NOT EXISTS parrafos USING fts5(
    texto,
    doc_id UNINDEXED,
    pagina UNINDEXED,
    parrafo UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TABLE IF NOT EXISTS ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT DEFAULT (datetime('now','localtime')),
    nuevos INTEGER,
    detalle TEXT
);
"""


def conectar():
    con = sqlite3.connect(RUTA_DB)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def huella(texto):
    return hashlib.sha1(texto.strip().lower().encode("utf-8")).hexdigest()[:20]
