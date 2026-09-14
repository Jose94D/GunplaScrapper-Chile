import json
import math
from datetime import datetime
from flask import Blueprint, render_template, request, make_response

# Importamos las herramientas de la base de datos y métricas
from core.database import execute_query, get_estadisticas_globales

COOKIE_VISITA = 'visita_contada'

# =====================================================================
# 1. BLUEPRINT DE INICIO (Página principal y Catálogo)
# =====================================================================
def crear_blueprint_inicio():
    """
    Controla la ruta principal ('/'). 
    Se encarga de mostrar el catálogo de productos, manejar el motor de búsqueda, 
    los filtros, la paginación y cargar los banners.
    """
    inicio_bp = Blueprint('inicio_bp', __name__)

    @inicio_bp.route('/')
    def index():
        # --- A. Captura de parámetros GET ---
        search_query = request.args.get('q', '').strip()
        grado_filtro = request.args.get('grado', '')
        if grado_filtro == 'Todos':
            grado_filtro = ''
            
        sort_order = request.args.get('sort', 'price_asc')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 24, type=int)
        
        # Validamos que los ítems por página sean los permitidos
        if per_page not in [24, 48, 120]:
            per_page = 24
            
        offset = (page - 1) * per_page

        # --- B. Estadísticas y Componentes Globales ---
        # 4.2: Solo contamos una visita por navegador por día (evita inflar el
        # contador con recargas, F5, o vueltas atrás del mismo visitante).
        fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")
        ya_contada_hoy = request.cookies.get(COOKIE_VISITA) == fecha_hoy_str
        get_estadisticas_globales(incrementar_visita=not ya_contada_hoy)

        # Obtenemos las imágenes adaptado a la nueva tabla 'banners'
        carrusel_imgs = execute_query("SELECT nombre_archivo, enlace FROM banners ORDER BY id ASC", fetchall=True)

        # --- C. Construcción dinámica de la consulta SQL del Catálogo ---
        # Como el precio ahora es un número (REAL) en historial_precios, la consulta es directa
        query_select = """
            SELECT 
                p.id, 
                p.nombre_estandar, 
                p.grado,
                MIN(hl.precio) as precio_min_int
            FROM productos p
            LEFT JOIN publicacion_producto pp ON p.id = pp.producto_id
            LEFT JOIN historial_precios hl ON pp.id = hl.publicacion_producto_id
        """
        
        # Filtramos por visibilidad Y por disponibilidad: los productos "No disponible"
        # (sin ninguna tienda activa) no deben aparecer en el módulo de inicio.
        where_conditions = ["p.es_visible = 1", "p.disponible = 1"]
        params = []
        
        if search_query:
            where_conditions.append("p.nombre_estandar LIKE ?")
            params.append(f"%{search_query}%")
            
        if grado_filtro:
            where_conditions.append("p.grado = ?")
            params.append(grado_filtro)
            
        where_clause = " WHERE " + " AND ".join(where_conditions)
        group_by_clause = " GROUP BY p.id, p.nombre_estandar, p.grado"
        
        # --- D. Ordenamiento de Resultados ---
        if sort_order in ['price_asc', 'asc']: order_clause = " ORDER BY precio_min_int ASC"
        elif sort_order in ['price_desc', 'desc']: order_clause = " ORDER BY precio_min_int DESC"
        elif sort_order == 'alpha_asc': order_clause = " ORDER BY p.nombre_estandar ASC"
        elif sort_order == 'alpha_desc': order_clause = " ORDER BY p.nombre_estandar DESC"
        else: order_clause = " ORDER BY precio_min_int ASC"

        # --- E. Paginación: Cálculo del total de páginas ---
        count_query = """
            SELECT COUNT(DISTINCT p.id) 
            FROM productos p
            LEFT JOIN publicacion_producto pp ON p.id = pp.producto_id
            LEFT JOIN historial_precios hl ON pp.id = hl.publicacion_producto_id
            """ + where_clause
            
        total_items_result = execute_query(count_query, tuple(params), fetchone=True)
        total_items = total_items_result[0] if total_items_result and total_items_result[0] else 0
        total_pages = max(1, math.ceil(total_items / per_page))

        # --- F. Ejecución de la consulta final ---
        final_query = f"{query_select} {where_clause} {group_by_clause} {order_clause} LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        resultados_db = execute_query(final_query, tuple(params), fetchall=True)
        
        # Formateamos el número para la vista HTML
        datos = []
        for row in resultados_db:
            precio_texto = f"${int(row[3]):,.0f}".replace(",", ".") if row[3] is not None else "N/A"
            datos.append((row[0], row[1], row[2], precio_texto))

        response = make_response(render_template('public/inicio.html', datos=datos, carrusel_imgs=carrusel_imgs, 
                               search_query=search_query, grado_filtro=grado_filtro, 
                               sort_order=sort_order, page=page, per_page=per_page, 
                               total_pages=total_pages))

        if not ya_contada_hoy:
            # La cookie expira a medianoche (hora local del servidor): al día
            # siguiente vuelve a contar una visita nueva para ese navegador.
            ahora = datetime.now()
            medianoche = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
            segundos_hasta_medianoche = int((medianoche - ahora).total_seconds()) + 1
            response.set_cookie(COOKIE_VISITA, fecha_hoy_str, max_age=segundos_hasta_medianoche)

        return response

    return inicio_bp


# =====================================================================
# 2. BLUEPRINT DEL PRODUCTO (Detalle y Gráficos Históricos)
# =====================================================================
def crear_blueprint_producto():
    """
    Controla la ruta de detalle ('/producto/<id>').
    Obtiene los detalles de un producto específico, busca qué tiendas lo venden,
    y prepara la estructura de datos (Fechas y Precios) para graficarlos con Chart.js.
    """
    producto_bp = Blueprint('producto_bp', __name__)

    @producto_bp.route('/producto/<int:id>')
    def ver_grafico(id):
        # --- A. Mantener parámetros ---
        q = request.args.get('q', '')
        grado = request.args.get('grado', '')
        sort = request.args.get('sort', '')
        per_page = request.args.get('per_page', '')
        page = request.args.get('page', '')

        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
        
        # --- B. Búsqueda del producto ---
        cat_data = execute_query("SELECT nombre_estandar FROM productos WHERE id = ?", (id,), fetchone=True)
        if not cat_data:
            return "Producto no encontrado", 404
        nombre_estandar = cat_data[0]

        # --- C. Búsqueda de publicaciones (usando JOIN con tabla de tiendas) ---
        query_tiendas = """
            SELECT pp.id, t.nombre, pp.nombre_original, pp.url, pp.es_url_activa 
            FROM publicacion_producto pp
            JOIN tiendas t ON pp.tienda_id = t.id
            WHERE pp.producto_id = ?
        """
        tiendas_db = execute_query(query_tiendas, (id,), fetchall=True)
        
        tiendas = []
        datasets = []
        todas_las_fechas = set()
        tienda_historial = {}
        
        # --- D. Recopilación de precios históricos ---
        for t in tiendas_db:
            pub_id, t_nombre, t_orig, t_url, t_activa = t[0], t[1], t[2], t[3], t[4]
            
            historial = execute_query("SELECT precio, fecha_registro FROM historial_precios WHERE publicacion_producto_id = ? ORDER BY fecha_registro ASC", (pub_id,), fetchall=True)
            
            # Formateamos el último precio extraído para la tarjeta estática
            ultimo_precio = f"${int(historial[-1][0]):,.0f}".replace(",", ".") if historial and historial[-1][0] is not None else "N/A"
            tiendas.append({
                "nombre": t_nombre,
                "nombre_original": t_orig,
                "precio": ultimo_precio,
                "url": t_url,
                "disponible": bool(t_activa)  # Registro de disponibilidad por tienda para el frontend
            })
            
            # El precio ya es numérico, lo pasamos directo a Chart.js
            precios_dict = {}
            for h in historial:
                precio_int = int(h[0]) if h[0] is not None else 0
                fecha_str = h[1][:10] if h[1] else "" # Aseguramos formato 'YYYY-MM-DD'
                
                precios_dict[fecha_str] = precio_int
                todas_las_fechas.add(fecha_str) 
                
            tienda_historial[t_nombre] = precios_dict

        # --- E. Preparación de datos para Chart.js ---
        fechas_ordenadas = sorted(list(todas_las_fechas)) 
        
        for t_nombre, precios_dict in tienda_historial.items():
            data_array = []
            ultimo_conocido = None
            
            for f in fechas_ordenadas:
                if f in precios_dict:
                    ultimo_conocido = precios_dict[f]
                    data_array.append(ultimo_conocido)
                else:
                    data_array.append(ultimo_conocido) 
                    
            datasets.append({
                "label": t_nombre,
                "data": data_array,
                "spanGaps": True 
            })

        fechas_json = json.dumps(fechas_ordenadas)
        datasets_json = json.dumps(datasets)

        return render_template('public/producto.html',
                               nombre_estandar=nombre_estandar,
                               tiendas=tiendas,
                               fecha=fecha,
                               visitas=visitas,
                               fechas_json=fechas_json,
                               datasets_json=datasets_json,
                               q=q,
                               grado=grado,
                               sort=sort,
                               per_page=per_page,
                               page=page)

    return producto_bp