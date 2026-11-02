"""Tareas programadas para el cron del servidor.

Cuando la app la sirve un servidor web (LiteSpeed, Passenger, Apache) en vez de `python app.py`, el scheduler
interno no arranca: ese servidor importa la app, abre y cierra procesos según las visitas, y puede tener varios
a la vez. En ese caso el cron del hosting llama a este script:

    python tareas.py escaneo     a las 00:00 y 12:00
    python tareas.py respaldo    a las 03:00
"""
import sys

from core.database import init_db
from core.respaldos import respaldar_base
from core.scraper_manager import ScraperManager

TAREAS = {
    "escaneo": lambda: ScraperManager().ejecutar_todos(),  # se omite si ya hay uno en curso (panel o cron)
    "respaldo": respaldar_base,
    # Lo lanza el botón Forzar escaneo, que ya tomó el candado: no es para el cron
    "escaneo-forzado": lambda: ScraperManager().ejecutar_ya_bloqueado(),
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TAREAS:
        raise SystemExit("Uso: python tareas.py escaneo|respaldo")
    init_db()  # por si el cron corre antes de que el sitio haya recibido su primera visita
    TAREAS[sys.argv[1]]()
