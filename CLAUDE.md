# Investigador local — guía para Claude Code

Herramienta local (Windows) de búsqueda académica sobre transhumanismo, en inglés y español.

## Regla principal (no negociable)
La herramienta SOLO busca y señala ubicaciones. Nunca debe:
- resumir, parafrasear ni generar texto sobre el contenido de las fuentes;
- comparar textos entre sí;
- guardar o mostrar abstracts o fragmentos de párrafos.
El localizador de pasajes devuelve únicamente documento, página, párrafo y término coincidente.

## Estructura
- `app.py`: interfaz Flask en http://127.0.0.1:5077 (`templates/index.html`).
- `buscar_diario.py`: lo ejecuta el Programador de tareas de Windows (`programar_tarea.ps1`).
- `nucleo/fuentes.py`: conectores (OpenAlex, Crossref, arXiv, Semantic Scholar, DOAJ, RSS). Todos devuelven el mismo dict vía `_item()`.
- `nucleo/busqueda.py`: corre las fuentes y guarda solo lo nuevo (sin duplicados por DOI/URL/título).
- `nucleo/pasajes.py`: índice SQLite FTS5 por página y párrafo (sin tildes).
- `config.json`: palabras clave, problemáticas, RSS y fuentes activas.

## Pendientes
- Conectores de Scopus / Web of Science cuando haya clave institucional.
- Leer alertas de Google Scholar desde el correo (Scholar no tiene API).
- OCR para PDF escaneados.
