from flask import Flask, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler

# --- IMPORTAMOS CONFIGURACIÓN CENTRALIZADA ---
from config import ADMIN_USER, ADMIN_PASS, SECRET_KEY

# --- IMPORTAMOS LOS BLUEPRINTS (Rutas) ---
from routes.admin import crear_blueprint_admin
from routes.admin_login import crear_blueprint_admin_login
from routes.views_inicio import crear_blueprint_inicio
from routes.views_producto import crear_blueprint_producto

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
        # NUEVO: Obtenemos el catálogo completo solo para el menú desplegable de fusión
        catalogo_completo = execute_query("SELECT id, nombre_estandar, grado FROM catalogo_global ORDER BY nombre_estandar", fetchall=True)
    except Exception:
        # Fallback en caso de que la DB aún no tenga registros
        fecha, visitas = "N/A", 0
        catalogo_completo = []
        
    return dict(fecha=fecha, visitas=visitas, catalogo_completo=catalogo_completo)

# --- REGISTRO DE RUTAS (BLUEPRINTS) ---
# Nota: Ya no le pasamos DB_NAME a los blueprints, ellos lo leen de config.py a través de core/database.py
app.register_blueprint(crear_blueprint_inicio())
app.register_blueprint(crear_blueprint_producto())

# Blueprint del Login (Le pasamos las credenciales por defecto desde config.py)
app.register_blueprint(crear_blueprint_admin_login(ADMIN_USER, ADMIN_PASS))

# Blueprint del Panel (Le inyectamos el orquestador en lugar del scraper individual)
app.register_blueprint(crear_blueprint_admin(scraper_manager))

# --- NUEVA RUTA: FUSIÓN DE PRODUCTOS ---
@app.route('/admin/fusionar', methods=['POST'])
def admin_fusionar_productos():
    id_principal = request.form.get('id_principal')
    id_duplicado = request.form.get('id_duplicado')
    
    if not id_principal or not id_duplicado:
        registrar_log("Intento de fusión fallido: Faltan IDs.")
        return redirect('/admin/panel')
        
    if id_principal == id_duplicado:
        registrar_log("Intento de fusión fallido: IDs idénticos.")
        return redirect('/admin/panel')
        
    try:
        # Paso A: Migrar las tiendas al producto principal
        execute_query(
            "UPDATE publicaciones_tiendas SET catalogo_id = ? WHERE catalogo_id = ?",
            (id_principal, id_duplicado),
            commit=True
        )
        
        # Paso B: Eliminar el producto duplicado
        execute_query(
            "DELETE FROM catalogo_global WHERE id = ?",
            (id_duplicado,),
            commit=True
        )
        registrar_log(f"Fusión manual exitosa: El ID {id_duplicado} se unió al ID {id_principal}")
        
    except Exception as e:
        registrar_log(f"Error grave en fusión manual: {str(e)}")
        
    return redirect('/admin/panel')


# --- TAREAS PROGRAMADAS ---
scheduler = BackgroundScheduler()

# Ejecución automática cada 12 horas del Manager (recorre todas las tiendas)
scheduler.add_job(func=scraper_manager.ejecutar_todos, trigger="interval", hours=12)
scheduler.start()

if __name__ == '__main__':
    # use_reloader=False es importante para que el BackgroundScheduler no se ejecute dos veces en modo debug
    app.run(debug=True, port=5000, use_reloader=False)