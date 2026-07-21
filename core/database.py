import sqlite3
from datetime import datetime
from config import DB_NAME

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """Inicializa y parchea las tablas de la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    # Tablas base
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, accion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS carrusel (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS credenciales (id INTEGER PRIMARY KEY, usuario TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS historial_precios (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT NOT NULL, precio TEXT, url TEXT, fecha TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS estadisticas (id INTEGER PRIMARY KEY, contador INTEGER)''')
    c.execute('''INSERT OR IGNORE INTO estadisticas (id, contador) VALUES (1, 0)''')
    
    # Parches de esquema
    c.execute("PRAGMA table_info(historial_precios)")
    columnas = [col[1] for col in c.fetchall()]
    if 'activo' not in columnas:
        c.execute("ALTER TABLE historial_precios ADD COLUMN activo INTEGER DEFAULT 1")
    if 'precio_base' not in columnas:
        c.execute("ALTER TABLE historial_precios ADD COLUMN precio_base TEXT")
    
    conn.commit()
    conn.close()

def execute_query(query, args=(), fetchall=False, fetchone=False, commit=False):
    """Función maestra genérica para evitar repetir la conexión a DB."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, args)
    result = None
    if fetchall: result = c.fetchall()
    elif fetchone: result = c.fetchone()
    if commit: conn.commit()
    conn.close()
    return result

def get_estadisticas_globales(incrementar_visita=False):
    if incrementar_visita:
        execute_query("UPDATE estadisticas SET contador = contador + 1 WHERE id = 1", commit=True)
    
    visitas = execute_query("SELECT contador FROM estadisticas WHERE id = 1", fetchone=True)
    fecha_res = execute_query("SELECT MAX(fecha) FROM historial_precios", fetchone=True)
    
    visitas_val = visitas[0] if visitas else 0
    fecha_val = fecha_res[0][:10] if fecha_res and fecha_res[0] else "N/A"
    
    return fecha_val, visitas_val