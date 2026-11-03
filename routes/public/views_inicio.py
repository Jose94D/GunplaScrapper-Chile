import json
import secrets
from datetime import datetime
from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, session, url_for
from markupsafe import escape

from core import carrusel, catalogo, visitas

COOKIE_VISITANTE = 'visitante'

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

        # --- B. Componentes Globales ---
        carrusel_imgs = [(nombre, enlace) for _, nombre, enlace in carrusel.listar_imagenes()]

        # --- C. Catálogo filtrado, ordenado y paginado ---
        datos, total_pages = catalogo.listar_catalogo_publico(search_query, grado_filtro, sort_order, page, per_page)

        # Los escaneos programados son a las 00:00 y 12:00
        proximo_escaneo = "12:00" if datetime.now().hour < 12 else "00:00"

        indicadores = catalogo.indicadores_precio([fila[0] for fila in datos])

        return render_template('public/inicio.html', datos=datos, indicadores=indicadores, carrusel_imgs=carrusel_imgs,
                               search_query=search_query, grado_filtro=grado_filtro,
                               sort_order=sort_order, page=page, per_page=per_page,
                               total_pages=total_pages, resumen=catalogo.resumen_inicio(), proximo_escaneo=proximo_escaneo)

    @inicio_bp.route('/visita', methods=['POST'])
    def registrar_visita():
        """Lo llama main.js al abrir cada página pública. Los bots que no ejecutan JavaScript nunca llegan aquí,
        y tampoco se cuentan el administrador ni los rastreadores que se identifican como tales."""
        respuesta = Response(status=204)
        if 'admin_logged' in session or visitas.es_bot(request.headers.get('User-Agent')):
            return respuesta
        visitante = request.cookies.get(COOKIE_VISITANTE, '')
        if not visitas.VISITANTE_VALIDO.match(visitante):
            visitante = secrets.token_urlsafe(16)
        visitas.registrar_visita(visitante)
        # Se renueva en cada visita: dura un año desde la última. Solo la lee el servidor
        respuesta.set_cookie(COOKIE_VISITANTE, visitante, max_age=365 * 24 * 3600, httponly=True,
                             samesite='Lax', secure=current_app.config['SESSION_COOKIE_SECURE'])
        return respuesta

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
            abort(404)

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

    @producto_bp.route('/favicon.ico')
    def favicon():
        # Google y algunos navegadores lo piden siempre en la raíz, sin mirar el <link rel="icon">
        return current_app.send_static_file('favicon.ico')

    @producto_bp.route('/robots.txt')
    def robots():
        # El panel no debe aparecer en buscadores
        lineas = ['User-agent: *', 'Disallow: /admin', f"Sitemap: {url_for('producto_bp.sitemap', _external=True)}"]
        return Response('\n'.join(lineas) + '\n', mimetype='text/plain')

    return producto_bp