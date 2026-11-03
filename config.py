import os
import secrets
from dotenv import load_dotenv

# Cargamos las variables ocultas desde el archivo .env
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ==========================================
# Configuración de la Base de Datos
# ==========================================
# Ruta absoluta: la app usa la misma base aunque se inicie desde otra carpeta
DB_NAME = os.path.join(BASE_DIR, "precios_comunidad.db")

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
# Con el sitio publicado en https, las cookies solo viajan cifradas. En local (http) debe quedar apagado o no se podría iniciar sesión.
HTTPS = os.getenv("HTTPS") == "1"
# Dirección oficial del sitio (p. ej. https://www.gunplascraper-chile.cl). Si está definida, las visitas por otra dirección
# (sin www o por http) se redirigen a esta, y los enlaces para buscadores y redes la usan. Vacía en local y en las pruebas.
URL_SITIO = os.getenv("URL_SITIO", "").rstrip("/")
# Tiendas que este servidor no escanea, separadas por coma (p. ej. "Weplay": bloquea las IP de servidores de hosting)
TIENDAS_DESACTIVADAS = {t.strip() for t in os.getenv("TIENDAS_DESACTIVADAS", "").split(",") if t.strip()}


def validar_configuracion():
    """Detiene el arranque si faltan variables obligatorias del .env."""
    faltan = [n for n in ("SECRET_KEY", "ADMIN_USER", "ADMIN_PASS") if not os.getenv(n)]
    if faltan:
        raise SystemExit(f"Faltan variables en el .env: {', '.join(faltan)}. Revisa la sección Ejecutar del README.")
