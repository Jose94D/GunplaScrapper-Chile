import sqlite3
from flask import Blueprint, render_template, request

def crear_blueprint_inicio(DB_NAME):
    inicio_bp = Blueprint('inicio_bp', __name__)

    # ==========================================
    # Funciones Auxiliares Locales
    # ==========================================
    def get_db_data(incrementar_visita=False):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Lógica del contador de visitas
        if incrementar_visita:
            c.execute("UPDATE estadisticas SET contador = contador + 1 WHERE id = 1")
            
        c.execute("SELECT contador FROM estadisticas WHERE id = 1")
        visitas = c.fetchone()[0]
        
        # Extracción de la última fecha de actualización
        c.execute("SELECT MAX(fecha) FROM historial_precios")
        fecha = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return fecha[:10] if fecha else "N/A", visitas

    # ==========================================
    # Ruta Principal (Inicio)
    # ==========================================
    @inicio_bp.route('/')
    def inicio():
        sort = request.args.get('sort', 'asc')
        q = request.args.get('q', '')
        
        # Incrementamos la visita cada vez que alguien carga la página principal
        fecha, visitas = get_db_data(incrementar_visita=True)
        
        conn = sqlite3.connect(DB_NAME)
        
        # Cargamos las imágenes del carrusel
        carrusel_imgs = conn.cursor().execute("SELECT filename FROM carrusel ORDER BY id ASC").fetchall()
        
        # Consulta SQL blindada: Aísla el estado, precio y precio_base más recientes
        query = """
            SELECT hp.producto, hp.precio, hp.fecha, hp.precio_base
            FROM historial_precios hp
            INNER JOIN (
                SELECT producto, MAX(fecha) as max_fecha
                FROM historial_precios
                GROUP BY producto
            ) m ON hp.producto = m.producto AND hp.fecha = m.max_fecha
            WHERE COALESCE(hp.activo, 1) = 1
        """
        params = []
        
        # Filtro de búsqueda
        if q: 
            query += " AND hp.producto LIKE ?"
            params.append(f"%{q}%")
            
        # Ordenamiento dinámico limpiando los símbolos de moneda y separadores de miles
        query += f" ORDER BY CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER) {sort}"
        
        datos = conn.cursor().execute(query, params).fetchall()
        conn.close()
        
        return render_template('inicio.html', 
                               datos=datos, 
                               search_query=q, 
                               sort_order=sort, 
                               fecha=fecha, 
                               visitas=visitas, 
                               carrusel_imgs=carrusel_imgs)

    return inicio_bp