from flask import Flask, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORTAMOS CONFIGURACIÓN CENTRALIZADA ---
from config import ADMIN_USER, ADMIN_PASS, SECRET_KEY

# --- IMPORTAMOS LOS BLUEPRINTS (Rutas) ---
from routes.admin.admin import crear_blueprint_admin
from routes.admin.admin_login import crear_blueprint_admin_login
# Importamos ambos blueprints desde views_inicio.py según la nueva estructura
from routes.public.views_inicio import crear_blueprint_inicio, crear_blueprint_producto
from routes.public.views_institucional import crear_blueprint_institucional

# --- IMPORTAMOS LOS MÓDULOS CORE ---
from core.database import init_db, get_estadisticas_globales, execute_query
from core.scraper_manager import ScraperManager
from core.logger import registrar_log

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
        # Adaptado a la nueva tabla 'productos'
        catalogo_completo = execute_query("SELECT id, nombre_estandar, grado FROM productos ORDER BY nombre_estandar", fetchall=True)
    except Exception:
        # Fallback en caso de que la DB aún no tenga registros
        fecha, visitas = "N/A", 0
        catalogo_completo = []
        
    return dict(fecha=fecha, visitas=visitas, catalogo_completo=catalogo_completo)

# --- REGISTRO DE RUTAS (BLUEPRINTS) ---
app.register_blueprint(crear_blueprint_inicio())
app.register_blueprint(crear_blueprint_producto())
app.register_blueprint(crear_blueprint_institucional())

# Blueprint del Login (Le pasamos las credenciales por defecto desde config.py)
app.register_blueprint(crear_blueprint_admin_login(ADMIN_USER, ADMIN_PASS))

# Blueprint del Panel (Le inyectamos el orquestador en lugar del scraper individual)
app.register_blueprint(crear_blueprint_admin(scraper_manager))

# --- RUTA: FUSIÓN DE PRODUCTOS ---
@app.route('/admin/fusionar', methods=['POST'])
def admin_fusionar_productos():
    id_principal = request.form.get('id_principal')
    id_duplicado = request.form.get('id_duplicado')
    
    if not id_principal or not id_duplicado:
        registrar_log("Intento de fusión fallido: Faltan IDs.")
        return redirect('/admin')
        
    if id_principal == id_duplicado:
        registrar_log("Intento de fusión fallido: IDs idénticos.")
        return redirect('/admin')
        
    try:
        # Paso A: Migrar las publicaciones de las tiendas al producto principal
        execute_query(
            "UPDATE publicacion_producto SET producto_id = ? WHERE producto_id = ?",
            (id_principal, id_duplicado),
            commit=True
        )
        
        # Paso B: Eliminar el producto duplicado de la tabla 'productos'
        execute_query(
            "DELETE FROM productos WHERE id = ?",
            (id_duplicado,),
            commit=True
        )
        registrar_log(f"Fusión manual exitosa: El ID {id_duplicado} se unió al ID {id_principal}")
        
    except Exception as e:
        registrar_log(f"Error grave en fusión manual: {str(e)}")
        
    return redirect('/admin')


# --- TAREAS PROGRAMADAS ---
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
scheduler.start()
registrar_log("Scheduler iniciado: scraping automático programado para las 00:00 y 12:00 todos los días.")

if __name__ == '__main__':
    # use_reloader=False es importante para que el BackgroundScheduler no se ejecute dos veces en modo debug
    app.run(debug=True, port=5000, use_reloader=False)