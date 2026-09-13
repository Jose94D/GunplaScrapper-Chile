import sqlite3
from datetime import datetime
from config import DB_NAME

def get_connection():
    """
    Abre y retorna una conexión activa a la base de datos SQLite
    utilizando la ruta/nombre configurado en config.py.
    """
    conn = sqlite3.connect(DB_NAME)
    # Habilitamos soporte para foreign keys en SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Inicializa la base de datos creando todas las tablas requeridas según el 
    modelo relacional final si no existen.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tabla de Productos
    c.execute('''CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_estandar TEXT,
        grado TEXT,
        marca TEXT,
        es_visible BOOLEAN DEFAULT 1,
        imagen_producto TEXT,
        disponible BOOLEAN DEFAULT 1
    )''')

    # 1.1 Migración no disruptiva: si la DB ya existía sin la columna 'disponible'
    # (bases creadas antes de este cambio), se agrega sin tocar los datos existentes.
    c.execute("PRAGMA table_info(productos)")
    columnas_productos = [col[1] for col in c.fetchall()]
    if 'disponible' not in columnas_productos:
        c.execute("ALTER TABLE productos ADD COLUMN disponible BOOLEAN DEFAULT 1")

    # 2. Tabla de Tiendas
    c.execute('''CREATE TABLE IF NOT EXISTS tiendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        url_base TEXT,
        es_activa BOOLEAN DEFAULT 1
    )''')

    # 3. Tabla de Publicaciones por Tienda
    c.execute('''CREATE TABLE IF NOT EXISTS publicacion_producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        tienda_id INTEGER,
        nombre_original TEXT,
        url TEXT UNIQUE,
        precio REAL,
        es_url_activa BOOLEAN DEFAULT 1,
        FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
        FOREIGN KEY (tienda_id) REFERENCES tiendas(id) ON DELETE CASCADE
    )''')

    # 4. Tabla de Historial de Precios Simplificado
    c.execute('''CREATE TABLE IF NOT EXISTS historial_precios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        publicacion_producto_id INTEGER,
        precio REAL,
        fecha_registro DATETIME,
        FOREIGN KEY (publicacion_producto_id) REFERENCES publicacion_producto(id) ON DELETE CASCADE
    )''')

    # 5. Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        hash_clave TEXT,
        rol TEXT DEFAULT 'user',
        fecha_creacion DATETIME
    )''')

    # 6. Tabla de Favoritos por Usuario
    c.execute('''CREATE TABLE IF NOT EXISTS favoritos_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        producto_id INTEGER,
        fecha_agregado DATETIME,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )''')

    # 7. Tabla de Banners
    c.execute('''CREATE TABLE IF NOT EXISTS banners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_archivo TEXT,
        enlace TEXT,
        orden INTEGER
    )''')

    # 8. Tabla de Visitas Mensuales
    c.execute('''CREATE TABLE IF NOT EXISTS visitas_mensuales (
        mes TEXT PRIMARY KEY, 
        contador INTEGER DEFAULT 0
    )''')

    # 9. Tabla de Logs del Sistema
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha_registro DATETIME, 
        accion TEXT,
        nivel TEXT DEFAULT 'INFO'
    )''')
    
    conn.commit()
    conn.close()

def execute_query(query, args=(), fetchall=False, fetchone=False, commit=False):
    """
    Función auxiliar genérica (Helper) para ejecutar cualquier consulta SQL.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, args)
    result = None
    
    if fetchall: 
        result = c.fetchall()
    elif fetchone: 
        result = c.fetchone()
        
    if commit: 
        conn.commit()
        
    conn.close()
    return result

def get_estadisticas_globales(incrementar_visita=False):
    """
    Obtiene la última fecha en que se actualizaron precios y el contador de visitas
    del mes en curso.
    """
    mes_actual = datetime.now().strftime("%Y-%m")
    
    if incrementar_visita:
        execute_query(
            "INSERT OR IGNORE INTO visitas_mensuales (mes, contador) VALUES (?, 0)", 
            (mes_actual,), 
            commit=True
        )
        execute_query(
            "UPDATE visitas_mensuales SET contador = contador + 1 WHERE mes = ?", 
            (mes_actual,), 
            commit=True
        )
    
    visitas = execute_query(
        "SELECT contador FROM visitas_mensuales WHERE mes = ?", 
        (mes_actual,), 
        fetchone=True
    )
    
    # Consulta apuntando a historial_precios
    fecha_res = execute_query(
        "SELECT MAX(fecha_registro) FROM historial_precios", 
        fetchone=True
    )
    
    visitas_val = visitas[0] if visitas else 0
    fecha_val = fecha_res[0][:10] if fecha_res and fecha_res[0] else "N/A"
    
    return fecha_val, visitas_val

def actualizar_disponibilidad_productos():
    """
    Recalcula el campo 'disponible' de cada producto en base al estado actual
    de sus publicaciones por tienda (publicacion_producto.es_url_activa).

    Un producto queda 'disponible = 0' (No disponible) únicamente cuando
    NINGUNA de sus publicaciones está activa (es_url_activa = 1) en ninguna tienda.
    Si al menos una tienda lo tiene activo, 'disponible = 1'.

    Este campo es independiente de 'es_visible' (control manual del admin),
    por lo que el estado Visible/Oculto elegido por el admin nunca se pierde:
    cuando el producto vuelve a estar disponible, simplemente deja de mostrarse
    como "No disponible" y vuelve a mostrar su estado normal.
    """
    from core.logger import registrar_log

    execute_query(
        """
        UPDATE productos
        SET disponible = CASE WHEN EXISTS (
            SELECT 1 FROM publicacion_producto pp
            WHERE pp.producto_id = productos.id AND pp.es_url_activa = 1
        ) THEN 1 ELSE 0 END
        """,
        commit=True
    )

    total_no_disponibles = execute_query(
        "SELECT COUNT(id) FROM productos WHERE disponible = 0", fetchone=True
    )[0]

    registrar_log(f"Disponibilidad recalculada. Productos actualmente 'No disponible': {total_no_disponibles}")
    return total_no_disponibles


def fusionar_productos_catalogo(id_principal, id_duplicado):
    """
    Mueve todas las publicaciones conectadas a un producto duplicado hacia un producto principal,
    y luego elimina el registro del producto duplicado del catálogo.
    """
    from core.logger import registrar_log
    
    try:
        # Paso A: Cambia las referencias de las publicaciones hacia el ID principal
        execute_query(
            "UPDATE publicacion_producto SET producto_id = ? WHERE producto_id = ?",
            (id_principal, id_duplicado),
            commit=True
        )
        
        # Paso B: Borra el producto duplicado de la tabla 'productos'
        execute_query(
            "DELETE FROM productos WHERE id = ?",
            (id_duplicado,),
            commit=True
        )
        
        registrar_log(f"Fusión exitosa: El producto {id_duplicado} fue fusionado hacia {id_principal}")
        return True, "Productos fusionados exitosamente."
        
    except Exception as e:
        registrar_log(f"Error al fusionar productos: {str(e)}")
        return False, f"Error en la base de datos: {str(e)}"