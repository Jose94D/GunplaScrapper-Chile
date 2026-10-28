import json
from datetime import datetime
from flask import Blueprint, Response, current_app, make_response, redirect, render_template, request, url_for
from markupsafe import escape

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

        # Los escaneos programados son a las 00:00 y 12:00
        proximo_escaneo = "12:00" if datetime.now().hour < 12 else "00:00"

        response = make_response(render_template('public/inicio.html', datos=datos, carrusel_imgs=carrusel_imgs,
                               search_query=search_query, grado_filtro=grado_filtro,
                               sort_order=sort_order, page=page, per_page=per_page,
                               total_pages=total_pages, resumen=catalogo.resumen_inicio(), proximo_escaneo=proximo_escaneo))

        if not ya_contada_hoy:
            # La cookie expira a medianoche (hora local del servidor): al día
            # siguiente vuelve a contar una visita nueva para ese navegador.
            ahora = datetime.now()
            medianoche = ahora.replace(hour=23, minute=59, second=59, microsecond=0)
            segundos_hasta_medianoche = int((medianoche - ahora).total_seconds()) + 1
            # Solo la lee el servidor: ni el JavaScript de la página ni otros sitios necesitan verla
            response.set_cookie(COOKIE_VISITA, fecha_hoy_str, max_age=segundos_hasta_medianoche, httponly=True,
                                samesite='Lax', secure=current_app.config['SESSION_COOKIE_SECURE'])

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

    producto_bp.add_app_template_filter(catalogo.slug, 'slug')

    @producto_bp.route('/producto/<int:id>')
    @producto_bp.route('/producto/<int:id>-<slug>')
    def ver_grafico(id, slug=None):
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

        # Una sola URL por producto (/producto/45-gfred-hg): la sin nombre o con nombre viejo redirige, sin perder los filtros
        slug_correcto = catalogo.slug(detalle["nombre"])
        if slug != slug_correcto:
            return redirect(url_for('producto_bp.ver_grafico', id=id, slug=slug_correcto, **request.args), 301)

        return render_template('public/producto.html',
                               nombre_estandar=detalle["nombre"],
                               imagen=detalle["imagen"],
                               mejor_precio=detalle["mejor_precio"],
                               slug_producto=slug_correcto,
                               tiendas=detalle["tiendas"],
                               ficha=detalle,
                               fechas_json=json.dumps(detalle["fechas"]),
                               datasets_json=json.dumps(detalle["datasets"]),
                               q=q,
                               grado=grado,
                               sort=sort,
                               per_page=per_page,
                               page=page)

    @producto_bp.route('/sitemap.xml')
    def sitemap():
        """Páginas públicas para los buscadores: inicio, institucionales y cada producto visible."""
        urls = [url_for('inicio_bp.index', _external=True)]
        urls += [url_for(f'institucional_bp.{p}', _external=True) for p in ('sobre_nosotros', 'faq', 'condiciones_servicio', 'politicas')]
        urls += [url_for('producto_bp.ver_grafico', id=id, slug=catalogo.slug(nombre), _external=True)
                 for id, nombre in catalogo.listar_para_sitemap()]
        lineas = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        lineas += [f'  <url><loc>{escape(u)}</loc></url>' for u in urls]
        lineas.append('</urlset>')
        return Response('\n'.join(lineas) + '\n', mimetype='application/xml')

    @producto_bp.route('/robots.txt')
    def robots():
        # El panel no debe aparecer en buscadores
        lineas = ['User-agent: *', 'Disallow: /admin', f"Sitemap: {url_for('producto_bp.sitemap', _external=True)}"]
        return Response('\n'.join(lineas) + '\n', mimetype='text/plain')

    return producto_bp