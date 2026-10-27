import os
import secrets
from dotenv import load_dotenv

# Cargamos las variables ocultas desde el archivo .env
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ==========================================
# Configuración de la Base de Datos
# ==========================================
# El nombre de la DB no suele ser secreto, así que puede quedar aquí
DB_NAME = "precios_comunidad.db"

# Respaldos diarios automáticos (carpeta fuera de git) y cuántos días se conservan
CARPETA_RESPALDOS = os.path.join(BASE_DIR, "respaldos")
DIAS_RESPALDO = 30

# ==========================================
# Credenciales de Administrador
# ==========================================
# Se usan mientras no se cambien desde el panel. Sin valores por defecto:
# un "admin / admin123" conocido por cualquiera abriría el panel.
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# ==========================================
# Configuración de Flask
# ==========================================
# Sin .env (por ejemplo en las pruebas) se usa una clave aleatoria en vez de una conocida:
# las sesiones solo duran hasta reiniciar, pero nadie puede falsificarlas.
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

# Modo depuración solo si se pide explícitamente: con debug activo, cualquier error
# muestra una consola que permite ejecutar código en el servidor.
DEBUG = os.getenv("FLASK_DEBUG") == "1"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))


def validar_configuracion():
    """Detiene el arranque si faltan variables obligatorias del .env."""
    faltan = [n for n in ("SECRET_KEY", "ADMIN_USER", "ADMIN_PASS") if not os.getenv(n)]
    if faltan:
        raise SystemExit(f"Faltan variables en el .env: {', '.join(faltan)}. Revisa la sección Ejecutar del README.")
