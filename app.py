from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORTAMOS CONFIGURACIÓN CENTRALIZADA ---
from config import ADMIN_USER, ADMIN_PASS, SECRET_KEY, DEBUG, HOST, PORT, HTTPS, validar_configuracion

# --- IMPORTAMOS LOS BLUEPRINTS (Rutas) ---
from routes.admin.admin import crear_blueprint_admin
from routes.admin.admin_login import crear_blueprint_admin_login
# Importamos ambos blueprints desde views_inicio.py según la nueva estructura
from routes.public.views_inicio import crear_blueprint_inicio, crear_blueprint_producto
from routes.public.views_institucional import crear_blueprint_institucional

# --- IMPORTAMOS LOS MÓDULOS CORE ---
from core.database import init_db, get_estadisticas_globales
from core.scraper_manager import ScraperManager
from core.logger import registrar_log
from core.seguridad import proteger_csrf
from core.respaldos import respaldar_base

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.secret_key = SECRET_KEY
# Lax: el navegador no manda la cookie de sesión en formularios POST que vengan de otros sitios
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = HTTPS
proteger_csrf(app)

# 1. Inicializamos la Base de Datos (Crea tablas y parches si no existen)
init_db()

# 2. Instanciamos el Orquestador de Scrapers
scraper_manager = ScraperManager()

# --- INYECCIÓN GLOBAL DE DATOS PARA JINJA2 ---
@app.context_processor
def inject_global_data():
    """Datos del footer de todas las páginas: última actualización y visitas del mes."""
    try:
        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
    except Exception:
        # Fallback en caso de que la DB aún no tenga registros
        fecha, visitas = "N/A", 0
    return dict(fecha=fecha, visitas=visitas)

# --- REGISTRO DE RUTAS (BLUEPRINTS) ---
app.register_blueprint(crear_blueprint_inicio())
app.register_blueprint(crear_blueprint_producto())
app.register_blueprint(crear_blueprint_institucional())

# Blueprint del Login (Le pasamos las credenciales por defecto desde config.py)
app.register_blueprint(crear_blueprint_admin_login(ADMIN_USER, ADMIN_PASS))

# Blueprint del Panel (Le inyectamos el orquestador en lugar del scraper individual)
app.register_blueprint(crear_blueprint_admin(scraper_manager))

# --- TAREAS PROGRAMADAS ---
def iniciar_scheduler():
    """Programa el scraping automático. Se llama solo al ejecutar la app (no al importarla),
    para que importar el módulo, por ejemplo en pruebas, no arranque escaneos ni escriba en los logs."""
    scheduler = BackgroundScheduler()

    # 1.3: Ejecución automática todos los días a las 12:00 y a las 00:00 en punto.
    # Se usa un trigger 'cron' (horario fijo) en vez de 'interval' (cada X horas
    # desde que arrancó el server), que era el problema original: con 'interval'
    # la hora de disparo dependía de cuándo se había iniciado la aplicación y se
    # reiniciaba el conteo cada vez que el servidor se reiniciaba.
    scheduler.add_job(
        func=scraper_manager.ejecutar_todos,
        trigger="cron",
        hour="0,12",
        minute=0,
        id="scraping_automatico_diario",
        replace_existing=True
    )
    # Respaldo diario de la base, a una hora sin escaneos programados
    scheduler.add_job(func=respaldar_base, trigger="cron", hour=3, minute=0, id="respaldo_diario", replace_existing=True)
    scheduler.start()
    registrar_log("Scheduler iniciado: scraping automático a las 00:00 y 12:00, respaldo de la base a las 03:00.")
    return scheduler


if __name__ == '__main__':
    validar_configuracion()
    iniciar_scheduler()
    if DEBUG:
        # Solo para desarrollo (FLASK_DEBUG=1). use_reloader=False evita que el scheduler corra dos veces
        app.run(debug=True, host=HOST, port=PORT, use_reloader=False)
    else:
        from waitress import serve
        print(f"Gunpla Scraper Chile en http://{HOST}:{PORT}")
        serve(app, host=HOST, port=PORT)
