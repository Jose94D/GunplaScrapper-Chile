import json
import math
from flask import Blueprint, render_template, request

# Importamos las herramientas de la base de datos y métricas
from core.database import execute_query, get_estadisticas_globales

# =====================================================================
# 1. BLUEPRINT DE INICIO (Página principal y Catálogo)
# =====================================================================
def crear_blueprint_inicio():
    """
    Controla la ruta principal ('/'). 
    Se encarga de mostrar el catálogo de productos, manejar el motor de búsqueda, 
    los filtros, la paginación y cargar el carrusel de imágenes.
    """
    inicio_bp = Blueprint('inicio_bp', __name__)

    @inicio_bp.route('/')
    def index():
        # --- A. Captura de parámetros GET (La "mochila" de la URL) ---
        search_query = request.args.get('q', '').strip()
        grado_filtro = request.args.get('grado', '')
        if grado_filtro == 'Todos':
            grado_filtro = ''
            
        sort_order = request.args.get('sort', 'price_asc')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 24, type=int)
        
        # Validamos que los ítems por página sean los permitidos, si no, por defecto 24
        if per_page not in [24, 48, 120]:
            per_page = 24
            
        offset = (page - 1) * per_page

        # --- B. Estadísticas y Componentes Globales ---
        # Registramos que alguien visitó la página de inicio
        get_estadisticas_globales(incrementar_visita=True)

        # Obtenemos las imágenes y links del carrusel para el banner
        carrusel_imgs = execute_query("SELECT filename, link FROM carrusel ORDER BY id ASC", fetchall=True)

        # --- C. Construcción dinámica de la consulta SQL del Catálogo ---
        # Buscamos los productos y calculamos el precio mínimo activo para cada uno
        query_select = """
            SELECT 
                c.id, 
                c.nombre_estandar, 
                c.grado,
                MIN(CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER)) as precio_min_int
            FROM catalogo_global c
            LEFT JOIN publicaciones_tiendas pt ON c.id = pt.catalogo_id
            LEFT JOIN historial_precios hp ON pt.id = hp.publicacion_id
        """
        
        # Solo tomamos en cuenta precios activos
        where_conditions = ["(hp.activo = 1 OR hp.activo IS NULL)"]
        params = []
        
        # Aplicamos el filtro de texto (Buscador)
        if search_query:
            where_conditions.append("c.nombre_estandar LIKE ?")
            params.append(f"%{search_query}%")
            
        # Aplicamos el filtro de categoría/grado
        if grado_filtro:
            where_conditions.append("c.grado = ?")
            params.append(grado_filtro)
            
        where_clause = " WHERE " + " AND ".join(where_conditions)
        group_by_clause = " GROUP BY c.id, c.nombre_estandar, c.grado"
        
        # --- D. Ordenamiento de Resultados ---
        if sort_order in ['price_asc', 'asc']: order_clause = " ORDER BY precio_min_int ASC"
        elif sort_order in ['price_desc', 'desc']: order_clause = " ORDER BY precio_min_int DESC"
        elif sort_order == 'alpha_asc': order_clause = " ORDER BY c.nombre_estandar ASC"
        elif sort_order == 'alpha_desc': order_clause = " ORDER BY c.nombre_estandar DESC"
        else: order_clause = " ORDER BY precio_min_int ASC"

        # --- E. Paginación: Cálculo del total de páginas ---
        count_query = """
            SELECT COUNT(DISTINCT c.id) 
            FROM catalogo_global c
            LEFT JOIN publicaciones_tiendas pt ON c.id = pt.catalogo_id
            LEFT JOIN historial_precios hp ON pt.id = hp.publicacion_id
            """ + where_clause
            
        total_items_result = execute_query(count_query, tuple(params), fetchone=True)
        total_items = total_items_result[0] if total_items_result and total_items_result[0] else 0
        total_pages = max(1, math.ceil(total_items / per_page))

        # --- F. Ejecución de la consulta final con Límite y Offset ---
        final_query = f"{query_select} {where_clause} {group_by_clause} {order_clause} LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        resultados_db = execute_query(final_query, tuple(params), fetchall=True)
        
        # Formateamos el precio para que se vea legible en el HTML (ej: $15.000)
        datos = []
        for row in resultados_db:
            precio_texto = f"${row[3]:,.0f}".replace(",", ".") if row[3] is not None else "N/A"
            datos.append((row[0], row[1], row[2], precio_texto))

        # Renderizamos la plantilla de inicio
        return render_template('inicio.html', datos=datos, carrusel_imgs=carrusel_imgs, 
                               search_query=search_query, grado_filtro=grado_filtro, 
                               sort_order=sort_order, page=page, per_page=per_page, 
                               total_pages=total_pages)

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
        # --- A. Mantener parámetros para el botón de "Volver atrás" ---
        q = request.args.get('q', '')
        grado = request.args.get('grado', '')
        sort = request.args.get('sort', '')
        per_page = request.args.get('per_page', '')
        page = request.args.get('page', '')

        # Obtenemos estadísticas globales (sin sumar visita porque ya sumó en el inicio)
        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
        
        # --- B. Búsqueda del producto en el catálogo ---
        cat_data = execute_query("SELECT nombre_estandar FROM catalogo_global WHERE id = ?", (id,), fetchone=True)
        if not cat_data:
            return "Producto no encontrado", 404
        nombre_estandar = cat_data[0]

        # --- C. Búsqueda de publicaciones (Tiendas que venden el producto) ---
        tiendas_db = execute_query("SELECT id, tienda, nombre_original, url FROM publicaciones_tiendas WHERE catalogo_id = ?", (id,), fetchall=True)
        
        tiendas = []
        datasets = []
        todas_las_fechas = set()
        tienda_historial = {}
        
        # --- D. Recopilación de precios históricos por tienda ---
        for t in tiendas_db:
            pub_id, t_nombre, t_orig, t_url = t[0], t[1], t[2], t[3]
            
            # Buscamos el historial ordenado de más antiguo a más reciente
            historial = execute_query("SELECT precio, fecha FROM historial_precios WHERE publicacion_id = ? ORDER BY fecha ASC", (pub_id,), fetchall=True)
            
            # Último precio conocido para mostrar en la tarjeta estática
            ultimo_precio = historial[-1][0] if historial else "N/A"
            tiendas.append({
                "nombre": t_nombre,
                "nombre_original": t_orig,
                "precio": ultimo_precio,
                "url": t_url
            })
            
            # Limpiamos el texto del precio (convertir "$15.000" a entero 15000) para el gráfico
            precios_dict = {}
            for h in historial:
                precio_str = h[0].replace('$', '').replace('.', '').replace(' ', '')
                precio_int = int(precio_str) if precio_str.isdigit() else 0
                fecha_str = h[1]
                
                precios_dict[fecha_str] = precio_int
                todas_las_fechas.add(fecha_str) # Agrupamos todas las fechas detectadas
                
            tienda_historial[t_nombre] = precios_dict

        # --- E. Preparación de datos para Chart.js (Ejes X e Y) ---
        fechas_ordenadas = sorted(list(todas_las_fechas)) # Eje X: Fechas de menor a mayor
        
        for t_nombre, precios_dict in tienda_historial.items():
            data_array = []
            ultimo_conocido = None
            
            # Alineamos los precios con las fechas globales. 
            # Si una tienda no se escaneó un día específico, mantiene el precio del día anterior.
            for f in fechas_ordenadas:
                if f in precios_dict:
                    ultimo_conocido = precios_dict[f]
                    data_array.append(ultimo_conocido)
                else:
                    data_array.append(ultimo_conocido) 
                    
            datasets.append({
                "label": t_nombre,
                "data": data_array,
                "spanGaps": True # Propiedad de Chart.js para evitar cortes en la línea
            })

        # Convertimos las listas a formato JSON para que Javascript las pueda leer
        fechas_json = json.dumps(fechas_ordenadas)
        datasets_json = json.dumps(datasets)

        return render_template('producto.html',
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