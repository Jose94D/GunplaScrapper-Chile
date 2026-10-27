import json
from datetime import datetime
from flask import Blueprint, render_template, request, make_response

# Importamos las herramientas de la base de datos y métricas
from core.database import get_estadisticas_globales
from core import carrusel, catalogo

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
        per_page = catalogo.por_pagina_valida(request.args.get('per_page', 24, type=int))

        # --- B. Estadísticas y Componentes Globales ---
        # 4.2: Solo contamos una visita por navegador por día (evita inflar el
        # contador con recargas, F5, o vueltas atrás del mismo visitante).
        fecha_hoy_str = datetime.now().strftime("%Y-%m-%d")
        ya_contada_hoy = request.cookies.get(COOKIE_VISITA) == fecha_hoy_str
        get_estadisticas_globales(incrementar_visita=not ya_contada_hoy)

        carrusel_imgs = [(nombre, enlace) for _, nombre, enlace in carrusel.listar_imagenes()]

        # --- C. Catálogo filtrado, ordenado y paginado ---
        datos, total_pages = catalogo.listar_catalogo_publico(search_query, grado_filtro, sort_order, page, per_page)

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

        # --- B. Datos de la ficha y del gráfico ---
        detalle = catalogo.detalle_producto(id)
        if not detalle:
            return "Producto no encontrado", 404

        return render_template('public/producto.html',
                               nombre_estandar=detalle["nombre"],
                               imagen=detalle["imagen"],
                               tiendas=detalle["tiendas"],
                               fechas_json=json.dumps(detalle["fechas"]),
                               datasets_json=json.dumps(detalle["datasets"]),
                               q=q,
                               grado=grado,
                               sort=sort,
                               per_page=per_page,
                               page=page)

    return producto_bp