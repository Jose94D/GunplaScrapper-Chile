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
    # shortcut: el candado que evita escaneos simultáneos es por proceso; uno forzado desde el panel justo a la
    # misma hora que el del cron correrían a la vez. Si pasa seguido, usar un archivo de bloqueo compartido.
    "escaneo": lambda: ScraperManager().ejecutar_todos(),
    "respaldo": respaldar_base,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TAREAS:
        raise SystemExit(f"Uso: python tareas.py {'|'.join(TAREAS)}")
    init_db()  # por si el cron corre antes de que el sitio haya recibido su primera visita
    TAREAS[sys.argv[1]]()
