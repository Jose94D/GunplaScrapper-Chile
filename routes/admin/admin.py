from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, send_file, jsonify

from config import DB_NAME 
from core.logger import registrar_log, ultimos_eventos
from core.precios import limpiar_precio
from core import carrusel, catalogo, duplicados, imagenes, estadisticas, exportar, productos, usuarios

FILTROS_PANEL = ('page', 'q_admin', 'grado_admin', 'sort_admin', 'per_page')


def volver_al_panel(datos):
    """Redirige al listado del panel conservando la página y los filtros que traía la petición."""
    return redirect(url_for('admin_bp.admin_panel', **{k: datos.get(k) for k in FILTROS_PANEL}))

def crear_blueprint_admin(scraper_manager):
    admin_bp = Blueprint('admin_bp', __name__)

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'admin_logged' not in session:
                return redirect(url_for('admin_login_bp.admin_login'))
            return f(*args, **kwargs)
        return decorated_function

    @admin_bp.route('/admin/panel')
    @login_required
    def admin_panel():
        credenciales = usuarios.obtener_credenciales_admin()
        admin_actual = credenciales[0] if credenciales else "Administrador"
        
        resumen = estadisticas.resumen_panel()
        lista_logs = ultimos_eventos(10)
        lista_carrusel = carrusel.listar_imagenes()
        
        q_admin = request.args.get('q_admin', '').strip()
        grado_admin = request.args.get('grado_admin', '')
        if grado_admin == 'Todos': 
            grado_admin = ''
        page = request.args.get('page', 1, type=int)
        sort_admin = request.args.get('sort_admin', 'date_desc')
        per_page = catalogo.por_pagina_valida(request.args.get('per_page', 24, type=int))

        lista_productos, total_pages = catalogo.listar_productos_panel(q_admin, grado_admin, sort_admin, page, per_page)
        catalogo_completo = catalogo.listar_catalogo_completo()

        return render_template('admin/admin_panel.html', 
                               usuario=admin_actual, escaneados_hoy=resumen["escaneados_hoy"], 
                               total_productos=resumen["total_productos"], ultima_fecha=resumen["ultima_fecha"], 
                               lista_productos=lista_productos, lista_carrusel=lista_carrusel, 
                               lista_logs=lista_logs, tiendas=estadisticas.estado_tiendas(), duplicados=duplicados.sugerir_duplicados(), search_query=q_admin, grado_admin=grado_admin,
                               page=page, total_pages=total_pages, alerta_activa=resumen["alerta_activa"], 
                               mensaje_alerta=resumen["mensaje_alerta"], per_page=per_page, sort_admin=sort_admin,
                               catalogo_completo=catalogo_completo)

    @admin_bp.route('/admin/credenciales/actualizar', methods=['POST'])
    @login_required
    def actualizar_credenciales():
        nuevo_user = request.form.get('nuevo_usuario')
        nueva_pass = request.form.get('nueva_password')
        if nuevo_user and nueva_pass:
            usuarios.guardar_credenciales_admin(nuevo_user, nueva_pass)
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/backup')
    @login_required
    def descargar_backup():
        registrar_log("Se descargó un backup de la base de datos.")
        return send_file(DB_NAME, as_attachment=True)

    @admin_bp.route('/admin/exportar_excel')
    @login_required
    def exportar_excel():
        output = exportar.historial_excel()
        registrar_log("Se exportó el historial completo a Excel.")
        nombre_archivo = f"Reporte_Precios_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    @admin_bp.route('/admin/carrusel/nuevo', methods=['POST'])
    @login_required
    def subir_carrusel():
        carrusel.agregar_imagen(request.files.get('imagen'), request.form.get('link') or '')
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')
    
    @admin_bp.route('/admin/carrusel/editar_link/<int:img_id>', methods=['POST'])
    @login_required
    def editar_link_carrusel(img_id):
        carrusel.actualizar_enlace(img_id, request.form.get('nuevo_link') or '')
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')

    @admin_bp.route('/admin/carrusel/eliminar/<int:img_id>', methods=['POST'])
    @login_required
    def eliminar_carrusel(img_id):
        carrusel.eliminar_imagen(img_id)
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')

    @admin_bp.route('/admin/producto/nuevo', methods=['POST'])
    @login_required
    def agregar_producto():
        productos.crear_producto_manual(
            request.form.get('producto'),
            request.form.get('grado') or 'S/G',
            limpiar_precio(request.form.get('precio')),
            request.form.get('url') or None,
        )
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/producto/editar/<int:id>', methods=['GET', 'POST'])
    @login_required
    def editar_producto(id):
        if request.method == 'POST':
            productos.actualizar_producto(id, request.form.get('producto'), request.form.get('grado'))
            if request.files.get('imagen') and request.files['imagen'].filename:
                imagenes.guardar_subida(id, request.files['imagen'])
            return volver_al_panel(request.form)
            
        prod = productos.obtener_producto(id)
        if not prod: return redirect(url_for('admin_bp.admin_panel'))
        
        params = {
            'page': request.args.get('page', 1),
            'q_admin': request.args.get('q_admin', ''),
            'grado_admin': request.args.get('grado_admin', ''),
            'sort_admin': request.args.get('sort_admin', 'date_desc'),
            'per_page': request.args.get('per_page', 24)
        }
        return render_template('admin/admin_edit.html', prod=prod, params=params)

    @admin_bp.route('/admin/producto/toggle/<int:id>', methods=['POST'])
    @login_required
    def toggle_visibilidad(id):
        productos.alternar_visibilidad(id)
        return volver_al_panel(request.args)

    @admin_bp.route('/admin/producto/eliminar/<int:id>', methods=['POST'])
    @login_required
    def eliminar_producto(id):
        productos.eliminar_producto(id)
        return volver_al_panel(request.args)

    @admin_bp.route('/admin/fusionar', methods=['POST'])
    @login_required
    def fusionar_productos():
        id_duplicado = request.form.get('id_duplicado')
        id_principal = request.form.get('id_principal')
        
        if id_duplicado and id_principal and id_duplicado != id_principal:
            productos.fusionar_productos(id_principal, id_duplicado)

        respuesta = volver_al_panel(request.form)
        if request.form.get('desde') == 'duplicados':  # valor fijo, no una URL: evita redirecciones a otros sitios
            respuesta.location += '#seccion-duplicados'
        return respuesta

    @admin_bp.route('/admin/duplicados/descartar', methods=['POST'])
    @login_required
    def descartar_duplicado():
        id_a, id_b = request.form.get('id_a', type=int), request.form.get('id_b', type=int)
        if id_a and id_b and id_a != id_b:
            duplicados.descartar(id_a, id_b)
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-duplicados')

    @admin_bp.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged', None)
        registrar_log("Cierre de sesión.")
        return redirect(url_for('admin_login_bp.admin_login'))

    @admin_bp.route('/admin/force-update', methods=['POST'])
    @login_required
    def force_update():
        if not scraper_manager.iniciar_en_segundo_plano():
            return jsonify({"status": "busy", "message": "Ya hay un escaneo en curso. Espera a que termine."}), 409
        registrar_log("Escaneo forzado desde el Panel de Control.")
        return jsonify({"status": "started"}), 202

    @admin_bp.route('/admin/force-update/estado')
    @login_required
    def estado_escaneo():
        return jsonify({"en_curso": scraper_manager.en_curso()})

    return admin_bp