import sqlite3
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORTAMOS LOS BLUEPRINTS ---
from admin import crear_blueprint_admin
from admin_login import crear_blueprint_admin_login
from views_inicio import crear_blueprint_inicio
from views_producto import crear_blueprint_producto

# --- IMPORTAMOS LOS SCRAPERS MODULARES ---
from scrappers.hangar import HangarScraper

# --- CONFIGURACIÓN ---
DB_NAME = "precios_comunidad.db"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.secret_key = 'gunpla_secreto_super_seguro_2026'

# Instanciamos nuestros scrapers pasándoles el nombre de la DB
mi_scraper_hangar = HangarScraper(DB_NAME)

# --- INYECCIÓN GLOBAL DE DATOS PARA JINJA2 ---
@app.context_processor
def inject_global_data():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("SELECT contador FROM estadisticas WHERE id = 1")
        res_visitas = c.fetchone()
        visitas = res_visitas[0] if res_visitas else 0
        
        c.execute("SELECT MAX(fecha) FROM historial_precios")
        res_fecha = c.fetchone()
        fecha = res_fecha[0][:10] if res_fecha and res_fecha[0] else "N/A"
        
        conn.close()
    except Exception:
        fecha, visitas = "N/A", 0

    return dict(fecha=fecha, visitas=visitas)

# --- REGISTRO DE RUTAS (BLUEPRINTS) ---
app.register_blueprint(crear_blueprint_inicio(DB_NAME))
app.register_blueprint(crear_blueprint_producto(DB_NAME))

# Blueprint del Login
app.register_blueprint(crear_blueprint_admin_login(DB_NAME, ADMIN_USER, ADMIN_PASS))

# Blueprint del Panel (Ya no requiere ADMIN_USER ni ADMIN_PASS)
app.register_blueprint(crear_blueprint_admin(mi_scraper_hangar, DB_NAME))

# --- TAREAS PROGRAMADAS ---
scheduler = BackgroundScheduler()
# Ejecución automática cada 12 horas del scraper modular
scheduler.add_job(func=mi_scraper_hangar.ejecutar_escaneo, trigger="interval", hours=12)
scheduler.start()

if __name__ == '__main__':
    # use_reloader=False es importante para que el BackgroundScheduler no se ejecute dos veces en modo debug
    app.run(debug=True, port=5000, use_reloader=False)