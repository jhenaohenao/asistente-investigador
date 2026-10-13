# Investigador local

Herramienta de **búsqueda y localización**, no de escritura. Hace dos cosas:

1. **Novedades:** cada día busca publicaciones nuevas sobre tus palabras clave y de los autores que sigues, y te trae los enlaces.
2. **Localizar pasajes:** en tus PDF te dice *dónde* leer (documento, página, párrafo y qué término coincidió).

Por diseño, **nunca resume, parafrasea ni compara textos**. Ni siquiera guarda los abstracts de los artículos: solo título, autores, revista, fecha, DOI y enlaces.

Todo funciona en tu computador. No hay cuentas ni servicios de pago.

---

## Instalación (una sola vez)

1. Instala **Python 3.11 o superior** desde https://www.python.org/downloads/
   En la primera pantalla del instalador marca **“Add python.exe to PATH”**.
2. Descomprime esta carpeta donde quieras, por ejemplo `Documentos\Investigador`.
3. Haz doble clic en **`instalar.bat`**. Instala lo necesario y programa la búsqueda diaria a las 7:00 a. m.
   Si el PC está apagado a esa hora, la búsqueda corre apenas lo enciendas.

## Uso diario

Doble clic en **`iniciar.bat`**. Se abre en tu navegador (`http://127.0.0.1:5077`). Para salir, cierra la ventana negra.

### Novedades
- Cada tarjeta muestra la palabra clave que la trajo (o `autor: <nombre>` si llegó por un autor seguido), la fuente y si es de **acceso abierto**.
- El filtro de texto busca en título, autores, revista y etiqueta. Separa con comas para exigir todos los términos (`autor: Bostrom, enhancement`).
- El selector **Todos los autores** muestra solo lo de un autor seguido, incluidas las obras que ya habían llegado por palabra clave.
- Márcalas como *Por leer*, *Leído* o *Descartado*. Las descartadas no vuelven a aparecer.
- **Guardar en biblioteca** descarga el PDF abierto y lo indexa para buscar pasajes en él.
- **Exportar CSV** abre la lista en Excel (útil para tu bitácora de fuentes).
- **Buscar ahora** lanza la búsqueda sin esperar a la del día siguiente.

### Localizar pasajes
- Escribe términos separados por coma (`identidad personal, mind uploading`) o elige una **problemática** guardada.
- *Todos en el mismo párrafo* sirve para cruces precisos (p. ej. `cuerpo, mente`).
- *Incluir variantes* encuentra `mejoramiento` al buscar `mejora`.
- Las tildes no importan: `extension` encuentra `extensión`.
- Cada botón **pág. N · párr. X** abre el PDF directamente en esa página.

### Biblioteca
Copia tus PDF (los de tu investigación previa) a la carpeta `biblioteca` (admite subcarpetas) y pulsa **Actualizar índice**. Se actualiza solo cada día.
Si un PDF aparece como *“sin texto: requiere OCR”*, es un escaneo y no se puede buscar todavía.

### Autores seguidos
En **Ajustes → Autores seguidos** puedes añadirlos de dos maneras:
- **Por nombre:** escribe el nombre y pulsa *Buscar*. Aparecen los candidatos de OpenAlex con institución, número de obras y ORCID; pulsa *Seguir* en el correcto.
- **Por ORCID:** pega `0000-0002-1825-0097` o `https://orcid.org/0000-0002-1825-0097`. Se comprueba el formato y el dígito de control antes de guardarlo.

Cada día se buscan sus obras recientes (según *Días hacia atrás*) en OpenAlex, Crossref y DOAJ; Crossref y DOAJ solo funcionan si el autor tiene ORCID.
El botón **Obra completa** trae todas sus obras, sin límite de fecha, desde OpenAlex y su perfil público de ORCID, y te lleva a Novedades filtrado por ese autor. *Dejar de seguir* no borra sus hallazgos.

### Ajustes
Palabras clave en inglés y español (una por línea; si una línea lleva comas, como `transhumanismo, educación`, se buscan obras que tengan **todos** los términos), autores seguidos, problemáticas (grupos de términos en ambos idiomas), revistas seguidas por RSS y fuentes activas. Conviene poner tu correo: OpenAlex y Crossref atienden más rápido a quien se identifica.

---

## Fuentes incluidas

| Fuente | Qué cubre |
|---|---|
| **OpenAlex** | Índice mundial abierto. Incluye buena parte de **SciELO, Redalyc** y revistas en español. |
| **Crossref** | Todo artículo con DOI. |
| **Semantic Scholar** | Artículos con PDF abierto cuando existe. |
| **arXiv** | Preprints (sobre todo en inglés). |
| **DOAJ** | Revistas de acceso abierto, muchas latinoamericanas. |
| **ORCID** | Perfil público de los autores seguidos (solo para *Obra completa*). |
| **RSS** | Revistas que sigues: *Journal of Evolution and Technology*, *Philosophy & Technology*, *AI & Society*, *MIT Technology Review*, PhilPapers, arXiv cs.CY. Puedes añadir más en Ajustes. |

### Google Académico
No tiene API y bloquea la automatización. Lo práctico:
1. Crea alertas en https://scholar.google.com/scholar_alerts con tus términos.
2. Los enlaces te llegan por correo. (Una versión futura podría leer esas alertas de tu bandeja.)

### Bases con suscripción (JSTOR, Scopus, EBSCO, Web of Science)
Cuando tengas acceso institucional, pide a la biblioteca de tu universidad una **clave de API** (Scopus y Web of Science la ofrecen). Con esa clave se agrega un conector nuevo en `nucleo/fuentes.py`.

---

## Archivos

```
iniciar.bat            abre la aplicación
instalar.bat           instala y programa la búsqueda diaria
desinstalar_tarea.bat  quita la búsqueda diaria (no borra tus datos)
config.json            tus ajustes (palabras clave, autores seguidos, RSS...)
datos.sqlite           tus hallazgos y el índice (se crea solo)
biblioteca\            tus PDF
registro.txt           qué hizo cada búsqueda diaria
```

Para hacer copia de seguridad basta con guardar `config.json`, `datos.sqlite` y `biblioteca\`.
