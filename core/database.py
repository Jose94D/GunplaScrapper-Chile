import sqlite3
from contextlib import contextmanager
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

@contextmanager
def transaccion():
    """
    Una sola conexión para varias consultas que deben aplicarse juntas:
    commit al salir del bloque, rollback si ocurre una excepción.
    """
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()

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

    # 2.1 Estado del último escaneo por tienda (migración no disruptiva, igual que 'disponible')
    c.execute("PRAGMA table_info(tiendas)")
    columnas_tiendas = [col[1] for col in c.fetchall()]
    for columna, tipo in [('ultimo_intento', 'DATETIME'), ('ultimo_exito', 'DATETIME'),
                          ('productos_ultimo_escaneo', 'INTEGER'), ('ultimo_error', 'TEXT')]:
        if columna not in columnas_tiendas:
            c.execute(f"ALTER TABLE tiendas ADD COLUMN {columna} {tipo}")

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

    # 3.1 URL de la imagen del producto en el listado de la tienda (de ahí se descarga la imagen del producto)
    c.execute("PRAGMA table_info(publicacion_producto)")
    if 'imagen_url' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE publicacion_producto ADD COLUMN imagen_url TEXT")

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

    # 9.1 Pares que el administrador marcó como productos distintos (no se vuelven a sugerir como duplicados)
    c.execute('''CREATE TABLE IF NOT EXISTS duplicados_descartados (
        id_a INTEGER,
        id_b INTEGER,
        PRIMARY KEY (id_a, id_b),
        FOREIGN KEY (id_a) REFERENCES productos(id) ON DELETE CASCADE,
        FOREIGN KEY (id_b) REFERENCES productos(id) ON DELETE CASCADE
    )''')

    # 10. Índices para las uniones y filtros que crecen con el historial (~350.000 filas por año):
    # con un año simulado, el panel pasa de ~240 a ~80 ms y la ficha de producto de ~65 a ~8 ms.
    c.execute("CREATE INDEX IF NOT EXISTS idx_publicacion_producto ON publicacion_producto(producto_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_publicacion_tienda ON publicacion_producto(tienda_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_historial_publicacion ON historial_precios(publicacion_producto_id, fecha_registro)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_historial_fecha ON historial_precios(fecha_registro)")
    
    conn.commit()
    conn.close()

def execute_query(query, args=(), fetchall=False, fetchone=False, commit=False):
    """
    Función auxiliar genérica (Helper) para ejecutar cualquier consulta SQL.
    Sin fetchall/fetchone retorna el id de la fila insertada (cursor.lastrowid),
    en vez de buscarlo después con SELECT MAX(id), que puede traer el de otra inserción.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, args)

    if fetchall:
        result = c.fetchall()
    elif fetchone:
        result = c.fetchone()
    else:
        result = c.lastrowid
        
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
    fecha_val = fecha_res[0] if fecha_res and fecha_res[0] else "N/A"  # completa: el filtro |fecha la muestra como hora día/mes/año
    
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
