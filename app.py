from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORTAMOS CONFIGURACIÓN CENTRALIZADA ---
from config import ADMIN_USER, ADMIN_PASS, SECRET_KEY

# --- IMPORTAMOS LOS BLUEPRINTS (Rutas) ---
from routes.admin import crear_blueprint_admin
from routes.admin_login import crear_blueprint_admin_login
from routes.views_inicio import crear_blueprint_inicio
from routes.views_producto import crear_blueprint_producto

# --- IMPORTAMOS LOS MÓDULOS CORE ---
from core.database import init_db, get_estadisticas_globales
from core.scraper_manager import ScraperManager

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.secret_key = SECRET_KEY

# 1. Inicializamos la Base de Datos (Crea tablas y parches si no existen)
init_db()

# 2. Instanciamos el Orquestador de Scrapers
scraper_manager = ScraperManager()

# --- INYECCIÓN GLOBAL DE DATOS PARA JINJA2 ---
@app.context_processor
def inject_global_data():
    try:
        # Delegamos la consulta a la capa core de datos
        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
    except Exception:
        # Fallback en caso de que la DB aún no tenga registros
        fecha, visitas = "N/A", 0
        
    return dict(fecha=fecha, visitas=visitas)

# --- REGISTRO DE RUTAS (BLUEPRINTS) ---
# Nota: Ya no le pasamos DB_NAME a los blueprints, ellos lo leen de config.py a través de core/database.py
app.register_blueprint(crear_blueprint_inicio())
app.register_blueprint(crear_blueprint_producto())

# Blueprint del Login (Le pasamos las credenciales por defecto desde config.py)
app.register_blueprint(crear_blueprint_admin_login(ADMIN_USER, ADMIN_PASS))

# Blueprint del Panel (Le inyectamos el orquestador en lugar del scraper individual)
app.register_blueprint(crear_blueprint_admin(scraper_manager))

# --- TAREAS PROGRAMADAS ---
scheduler = BackgroundScheduler()

# Ejecución automática cada 12 horas del Manager (recorre todas las tiendas)
scheduler.add_job(func=scraper_manager.ejecutar_todos, trigger="interval", hours=12)
scheduler.start()

if __name__ == '__main__':
    # use_reloader=False es importante para que el BackgroundScheduler no se ejecute dos veces en modo debug
    app.run(debug=True, port=5000, use_reloader=False)