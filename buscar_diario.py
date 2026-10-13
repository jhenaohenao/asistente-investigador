"""Lo ejecuta el Programador de tareas de Windows una vez al día.
También puedes correrlo a mano: python buscar_diario.py"""
import datetime
import os

from nucleo import busqueda, pasajes
from nucleo.db import RAIZ

if __name__ == "__main__":
    log = os.path.join(RAIZ, "registro.txt")
    with open(log, "a", encoding="utf-8") as f:
        def escribir(m):
            print(m)
            f.write(m + "\n")
        escribir(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M} ===")
        nuevos, errores = busqueda.ejecutar(registro=escribir)
        escribir(f"Enlaces nuevos: {nuevos}")
        for e in errores:
            escribir(f"  aviso: {e}")
        hechos, total = pasajes.indexar_carpeta(busqueda.cargar_config().get("carpeta_pdfs", "biblioteca"), registro=escribir)
        escribir(f"Biblioteca: {total} PDF, {hechos} indexados ahora")
