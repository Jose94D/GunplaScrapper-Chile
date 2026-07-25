import os
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, session, redirect, url_for, send_file, jsonify

# Importamos el nombre de la DB para la función de descarga de backup
from config import DB_NAME 

# Importamos las herramientas de la capa core
from core.database import execute_query
from core.logger import registrar_log

CARRUSEL_FOLDER = os.path.join('static', 'carrusel')
os.makedirs(CARRUSEL_FOLDER, exist_ok=True)

def crear_blueprint_admin(scraper_manager):
    admin_bp = Blueprint('admin_bp', __name__)

    # ==========================================
    # Funciones Auxiliares
    # ==========================================
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'admin_logged' not in session:
                return redirect(url_for('admin_login_bp.admin_login'))
            return f(*args, **kwargs)
        return decorated_function

    # ==========================================
    # Panel de Control Principal
    # ==========================================
    @admin_bp.route('/admin/panel')
    @login_required
    def admin_panel():
        admin_actual = execute_query("SELECT usuario FROM credenciales WHERE id = 1", fetchone=True)[0]
        
        ultima_fecha_res = execute_query("SELECT MAX(fecha) FROM historial_precios", fetchone=True)
        ultima_fecha_completa = ultima_fecha_res[0] if ultima_fecha_res and ultima_fecha_res[0] else "Sin escaneos aún"
        
        # Ahora contamos los productos únicos desde el catálogo global
        total_productos_unicos = execute_query("SELECT COUNT(id) FROM catalogo_global", fetchone=True)[0]
        
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        escaneados_hoy = execute_query("SELECT COUNT(DISTINCT publicacion_id) FROM historial_precios WHERE fecha LIKE ?", (f"{fecha_hoy}%",), fetchone=True)[0]
        
        alerta_activa = False
        mensaje_alerta = ""
        if ultima_fecha_completa == "Sin escaneos aún":
            alerta_activa = True
            mensaje_alerta = "El sistema aún no tiene registros. Ejecuta un escaneo manual."
        else:
            try:
                fecha_obj = datetime.strptime(ultima_fecha_completa, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - fecha_obj).total_seconds() > 172800:
                    alerta_activa = True
                    mensaje_alerta = f"⚠️ ¡Atención! El último escaneo exitoso fue hace más de 48 horas ({ultima_fecha_completa}). Verifica los scrapers."
            except ValueError:
                pass 

        lista_logs = execute_query("SELECT fecha, accion FROM logs ORDER BY id DESC LIMIT 10", fetchall=True)
        lista_carrusel = execute_query("SELECT id, filename, link FROM carrusel ORDER BY id ASC", fetchall=True)
        
        q_admin = request.args.get('q_admin', '')
        page = request.args.get('page', 1, type=int)
        sort_admin = request.args.get('sort_admin', 'date_desc')
        
        order_clause = {
            'price_asc': "precio_min_int ASC",
            'price_desc': "precio_min_int DESC"
        }.get(sort_admin, "ultima_fecha DESC")
        
        per_page = request.args.get('per_page', 24, type=int)
        if per_page not in [24, 48, 120]: per_page = 24
        offset = (page - 1) * per_page

        # NUEVA CONSULTA: Lista el catálogo global y calcula su estado y precio
        base_query = """
            SELECT 
                c.id, 
                c.nombre_estandar, 
                c.grado,
                MIN(CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER)) as precio_min_int,
                MAX(hp.fecha) as ultima_fecha,
                MIN(COALESCE(hp.activo, 1)) as estado_activo
            FROM catalogo_global c
            LEFT JOIN publicaciones_tiendas pt ON c.id = pt.catalogo_id
            LEFT JOIN historial_precios hp ON pt.id = hp.publicacion_id
        """

        if q_admin:
            total_items = execute_query("SELECT COUNT(id) FROM catalogo_global WHERE nombre_estandar LIKE ?", (f"%{q_admin}%",), fetchone=True)[0]
            query = f"{base_query} WHERE c.nombre_estandar LIKE ? GROUP BY c.id, c.nombre_estandar, c.grado ORDER BY {order_clause} LIMIT ? OFFSET ?"
            lista_cruda = execute_query(query, (f"%{q_admin}%", per_page, offset), fetchall=True)
        else:
            total_items = total_productos_unicos
            query = f"{base_query} GROUP BY c.id, c.nombre_estandar, c.grado ORDER BY {order_clause} LIMIT ? OFFSET ?"
            lista_cruda = execute_query(query, (per_page, offset), fetchall=True)
            
        total_pages = max(1, (total_items + per_page - 1) // per_page)

        # Formateamos los datos para la plantilla
        lista_productos = []
        for p in lista_cruda:
            precio_formateado = f"${p[3]:,.0f}".replace(",", ".") if p[3] else "N/A"
            lista_productos.append((p[0], p[1], p[2], precio_formateado, p[4] or 'Sin datos', p[5] if p[5] is not None else 1))

        return render_template('admin_panel.html', 
                               usuario=admin_actual, escaneados_hoy=escaneados_hoy, 
                               total_productos=total_productos_unicos, ultima_fecha=ultima_fecha_completa, 
                               lista_productos=lista_productos, lista_carrusel=lista_carrusel, 
                               lista_logs=lista_logs, search_query=q_admin, 
                               page=page, total_pages=total_pages, alerta_activa=alerta_activa, 
                               mensaje_alerta=mensaje_alerta, per_page=per_page, sort_admin=sort_admin)

    # ==========================================
    # Gestión de Ajustes, Backups y Carrusel
    # ==========================================
    @admin_bp.route('/admin/credenciales/actualizar', methods=['POST'])
    @login_required
    def actualizar_credenciales():
        nuevo_user = request.form.get('nuevo_usuario')
        nueva_pass = request.form.get('nueva_password')
        if nuevo_user and nueva_pass:
            execute_query("UPDATE credenciales SET usuario = ?, password = ? WHERE id = 1", (nuevo_user, nueva_pass), commit=True)
            registrar_log(f"Se actualizaron las credenciales. Nuevo usuario: {nuevo_user}")
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/backup')
    @login_required
    def descargar_backup():
        registrar_log("Se descargó un backup de la base de datos.")
        return send_file(DB_NAME, as_attachment=True)

    @admin_bp.route('/admin/carrusel/nuevo', methods=['POST'])
    @login_required
    def subir_carrusel():
        file = request.files.get('imagen')
        link = request.form.get('link') or ''  # Capturamos el link desde el formulario (si no hay, queda en blanco)
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(CARRUSEL_FOLDER, filename))
            
            # Actualizamos el INSERT para guardar también el link
            execute_query("INSERT INTO carrusel (filename, link) VALUES (?, ?)", (filename, link), commit=True)
            registrar_log(f"Imagen subida al carrusel con enlace: {filename}")
            
        return redirect(url_for('admin_bp.admin_panel'))
    
    @admin_bp.route('/admin/carrusel/editar_link/<int:img_id>', methods=['POST'])
    @login_required
    def editar_link_carrusel(img_id):
        nuevo_link = request.form.get('nuevo_link') or ''
        execute_query("UPDATE carrusel SET link = ? WHERE id = ?", (nuevo_link, img_id), commit=True)
        registrar_log(f"Enlace actualizado en carrusel (ID imagen: {img_id})")
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/carrusel/eliminar/<int:img_id>')
    @login_required
    def eliminar_carrusel(img_id):
        img = execute_query("SELECT filename FROM carrusel WHERE id = ?", (img_id,), fetchone=True)
        if img:
            try: os.remove(os.path.join(CARRUSEL_FOLDER, img[0]))
            except FileNotFoundError: pass
            execute_query("DELETE FROM carrusel WHERE id = ?", (img_id,), commit=True)
            registrar_log(f"Imagen eliminada del carrusel: {img[0]}")
        return redirect(url_for('admin_bp.admin_panel'))

    # ==========================================
    # CRUD de Productos (Relacional)
    # ==========================================
    @admin_bp.route('/admin/producto/nuevo', methods=['POST'])
    @login_required
    def agregar_producto():
        producto = request.form.get('producto')
        grado = request.form.get('grado') or 'S/G'
        precio = request.form.get('precio')
        url = request.form.get('url') or '#'
        
        if producto and precio:
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 1. Crear en el Catálogo
            execute_query("INSERT INTO catalogo_global (nombre_estandar, grado) VALUES (?, ?)", (producto, grado), commit=True)
            cat_id = execute_query("SELECT MAX(id) FROM catalogo_global", fetchone=True)[0]
            
            # 2. Crear una tienda "Manual"
            execute_query("INSERT INTO publicaciones_tiendas (catalogo_id, tienda, nombre_original, url) VALUES (?, 'Manual', ?, ?)", (cat_id, producto, url), commit=True)
            pub_id = execute_query("SELECT MAX(id) FROM publicaciones_tiendas", fetchone=True)[0]
            
            # 3. Asignarle el precio
            execute_query("INSERT INTO historial_precios (publicacion_id, precio, precio_base, url, fecha, activo) VALUES (?, ?, ?, ?, ?, 1)", 
                     (pub_id, precio, precio, url, fecha_actual), commit=True)
            registrar_log(f"Producto creado manualmente en catálogo: {producto}")
            
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/producto/editar/<int:id>', methods=['GET', 'POST'])
    @login_required
    def editar_producto(id):
        if request.method == 'POST':
            nuevo_nombre = request.form.get('producto')
            nuevo_grado = request.form.get('grado')
            execute_query("UPDATE catalogo_global SET nombre_estandar = ?, grado = ? WHERE id = ?", 
                     (nuevo_nombre, nuevo_grado, id), commit=True)
            registrar_log(f"Producto ID {id} modificado en catálogo.")
            return redirect(url_for('admin_bp.admin_panel',
                                    page=request.form.get('page'),
                                    q_admin=request.form.get('q_admin'),
                                    sort_admin=request.form.get('sort_admin'),
                                    per_page=request.form.get('per_page')))
            
        prod = execute_query("SELECT id, nombre_estandar, grado FROM catalogo_global WHERE id = ?", (id,), fetchone=True)
        if not prod: return redirect(url_for('admin_bp.admin_panel'))
        
        params = {
            'page': request.args.get('page', 1),
            'q_admin': request.args.get('q_admin', ''),
            'sort_admin': request.args.get('sort_admin', 'date_desc'),
            'per_page': request.args.get('per_page', 24)
        }
        return render_template('admin_edit.html', prod=prod, params=params)

    @admin_bp.route('/admin/producto/toggle/<int:id>')
    @login_required
    def toggle_visibilidad(id):
        # Buscamos el estado actual
        estado = execute_query("""
            SELECT MIN(COALESCE(hp.activo, 1)) 
            FROM historial_precios hp 
            JOIN publicaciones_tiendas pt ON hp.publicacion_id = pt.id 
            WHERE pt.catalogo_id = ?
        """, (id,), fetchone=True)[0]
        
        nuevo_estado = 0 if estado == 1 else 1
        
        # Actualizamos el estado en todos los historiales vinculados a este catálogo
        execute_query("""
            UPDATE historial_precios SET activo = ? 
            WHERE publicacion_id IN (SELECT id FROM publicaciones_tiendas WHERE catalogo_id = ?)
        """, (nuevo_estado, id), commit=True)
        
        texto_estado = "Oculto" if nuevo_estado == 0 else "Visible"
        registrar_log(f"Visibilidad modificada: Catálogo ID {id} ahora está {texto_estado}")
        return redirect(url_for('admin_bp.admin_panel',
                                page=request.args.get('page'),
                                q_admin=request.args.get('q_admin'),
                                sort_admin=request.args.get('sort_admin'),
                                per_page=request.args.get('per_page')))

    @admin_bp.route('/admin/producto/eliminar/<int:id>')
    @login_required
    def eliminar_producto(id):
        # Eliminamos en cascada manualmente (Historial -> Tiendas -> Catálogo)
        execute_query("DELETE FROM historial_precios WHERE publicacion_id IN (SELECT id FROM publicaciones_tiendas WHERE catalogo_id = ?)", (id,), commit=True)
        execute_query("DELETE FROM publicaciones_tiendas WHERE catalogo_id = ?", (id,), commit=True)
        execute_query("DELETE FROM catalogo_global WHERE id = ?", (id,), commit=True)
        registrar_log(f"Producto eliminado completamente del catálogo ID: {id}")
        return redirect(url_for('admin_bp.admin_panel',
                                page=request.args.get('page'),
                                q_admin=request.args.get('q_admin'),
                                sort_admin=request.args.get('sort_admin'),
                                per_page=request.args.get('per_page')))

    @admin_bp.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged', None)
        registrar_log("Cierre de sesión.")
        return redirect(url_for('admin_login_bp.admin_login'))

    # ==========================================
    # Ejecución Forzada Manual
    # ==========================================
    @admin_bp.route('/admin/force-update')
    @login_required
    def force_update():
        try:
            total_productos, duracion = scraper_manager.ejecutar_todos()
            return jsonify({
                "status": "success",
                "message": f"✅ ¡Escaneo General Completado con Éxito!\n\nTiempo: {duracion:.1f} segundos.\nProductos totales registrados: {total_productos}"
            }), 200
        except Exception as e:
            registrar_log(f"Error desde Panel de Control en ejecución forzada: {str(e)}")
            return jsonify({
                "status": "error", 
                "message": f"❌ Ocurrió un problema técnico durante la ejecución global:\n{str(e)}"
            }), 500

    return admin_bp