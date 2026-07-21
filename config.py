import os
from dotenv import load_dotenv

# Cargamos las variables ocultas desde el archivo .env
load_dotenv()

# ==========================================
# Configuración de la Base de Datos
# ==========================================
# El nombre de la DB no suele ser secreto, así que puede quedar aquí
DB_NAME = "precios_comunidad.db"

# ==========================================
# Credenciales de Administrador (Fallback)
# ==========================================
# os.getenv busca la variable en el .env. Si por algún motivo no existe el archivo, 
# usará los valores después de la coma como último recurso de seguridad.
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# ==========================================
# Configuración de Flask
# ==========================================
SECRET_KEY = os.getenv("SECRET_KEY", "clave_de_respaldo_insegura")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))