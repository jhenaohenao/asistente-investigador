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
- `nucleo/fuentes.py`: conectores (OpenAlex, Crossref, arXiv, Semantic Scholar, DOAJ, RSS, ORCID). Todos devuelven el mismo dict vía `_item()`.
  - `CONECTORES`: por palabra clave. Una palabra clave con comas exige todos los términos (`_terminos()`), con la sintaxis de cada API.
  - `CONECTORES_AUTOR`: obras recientes de un autor seguido (OpenAlex por ID u ORCID, Crossref `orcid:`, DOAJ `bibjson.author.orcid_id`).
  - `openalex_obra_completa` y `orcid_obras`: todas las obras de un autor, sin límite de fecha.
- `nucleo/autores.py`: validación de ORCID (ISO 7064 mod 11-2) y alta de autores en `config.json`.
- `nucleo/busqueda.py`: corre las fuentes y guarda solo lo nuevo (sin duplicados por DOI/URL/título, clase `_Almacen`). Lo que llega por un autor se etiqueta `autor: <nombre>` y se anota en la tabla `hallazgo_autor` (aunque el hallazgo ya existiera), que usa el selector de autor de Novedades.
- `nucleo/pasajes.py`: índice SQLite FTS5 por página y párrafo (sin tildes).
- `config.json`: palabras clave, autores seguidos (`autores`: lista de `{nombre, orcid, openalex_id}`), problemáticas, RSS y fuentes activas.

## Pendientes
- Conectores de Scopus / Web of Science cuando haya clave institucional.
- Leer alertas de Google Scholar desde el correo (Scholar no tiene API).
- OCR para PDF escaneados.
