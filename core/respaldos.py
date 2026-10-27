"""Respaldo diario de la base de datos, con rotación."""
import os
import sqlite3
from datetime import datetime, timedelta

from config import CARPETA_RESPALDOS, DIAS_RESPALDO
import core.database
from core.logger import registrar_log

PREFIJO = "precios_"


def respaldar_base(carpeta=None, dias=None):
    """
    Copia la base a <carpeta>/precios_AAAA-MM-DD.db y borra las copias de más de `dias` días.
    Usa la API de respaldo de SQLite: la copia queda consistente aunque un escaneo esté escribiendo.
    Retorna la ruta del respaldo.
    """
    carpeta = carpeta or CARPETA_RESPALDOS
    dias = DIAS_RESPALDO if dias is None else dias
    os.makedirs(carpeta, exist_ok=True)

    destino = os.path.join(carpeta, f"{PREFIJO}{datetime.now():%Y-%m-%d}.db")
    origen = sqlite3.connect(core.database.DB_NAME)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()

    limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    borrados = 0
    for nombre in os.listdir(carpeta):
        fecha = nombre[len(PREFIJO):-3]
        if nombre.startswith(PREFIJO) and nombre.endswith(".db") and fecha < limite:
            os.remove(os.path.join(carpeta, nombre))
            borrados += 1

    registrar_log(f"Respaldo diario creado: {os.path.basename(destino)} ({borrados} respaldos antiguos eliminados)")
    return destino
