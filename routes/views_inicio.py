from flask import Blueprint, render_template, request

# Importamos las herramientas de la capa core
from core.database import execute_query, get_estadisticas_globales

def crear_blueprint_inicio():
    inicio_bp = Blueprint('inicio_bp', __name__)

    # ==========================================
    # Ruta Principal (Inicio)
    # ==========================================
    @inicio_bp.route('/')
    def inicio():
        sort = request.args.get('sort', 'asc')
        q = request.args.get('q', '')
        
        # Delegamos la lógica de contadores y fechas a core/database.py
        fecha, visitas = get_estadisticas_globales(incrementar_visita=True)
        
        # Cargamos las imágenes del carrusel a través del conector centralizado
        carrusel_imgs = execute_query("SELECT filename FROM carrusel ORDER BY id ASC", fetchall=True)
        
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
            
        # Ordenamiento dinámico
        query += f" ORDER BY CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER) {sort}"
        
        # Ejecutamos la query pasando por execute_query() del core
        datos = execute_query(query, params, fetchall=True)
        
        return render_template('inicio.html', 
                               datos=datos, 
                               search_query=q, 
                               sort_order=sort, 
                               fecha=fecha, 
                               visitas=visitas, 
                               carrusel_imgs=carrusel_imgs)

    return inicio_bp