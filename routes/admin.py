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
        
        total_productos_unicos = execute_query("SELECT COUNT(DISTINCT producto) FROM historial_precios", fetchone=True)[0]
        
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        escaneados_hoy = execute_query("SELECT COUNT(DISTINCT producto) FROM historial_precios WHERE fecha LIKE ?", (f"{fecha_hoy}%",), fetchone=True)[0]
        
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
        lista_carrusel = execute_query("SELECT id, filename FROM carrusel ORDER BY id ASC", fetchall=True)

        q_admin = request.args.get('q_admin', '')
        page = request.args.get('page', 1, type=int)
        sort_admin = request.args.get('sort_admin', 'date_desc')
        
        order_clause = {
            'price_asc': "CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER) ASC",
            'price_desc': "CAST(REPLACE(REPLACE(hp.precio, '$', ''), '.', '') AS INTEGER) DESC"
        }.get(sort_admin, "hp.fecha DESC")
        
        per_page = request.args.get('per_page', 24, type=int)
        if per_page not in [24, 48, 120]: per_page = 24
            
        offset = (page - 1) * per_page

        base_query = """
            SELECT hp.producto, hp.precio, hp.url, hp.fecha, COALESCE(hp.activo, 1), hp.precio_base
            FROM historial_precios hp
            INNER JOIN (
                SELECT producto, MAX(fecha) as max_fecha
                FROM historial_precios
                GROUP BY producto
            ) m ON hp.producto = m.producto AND hp.fecha = m.max_fecha
        """

        if q_admin:
            total_items = execute_query("SELECT COUNT(DISTINCT producto) FROM historial_precios WHERE producto LIKE ?", (f"%{q_admin}%",), fetchone=True)[0]
            lista_productos = execute_query(f"{base_query} WHERE hp.producto LIKE ? ORDER BY {order_clause} LIMIT ? OFFSET ?", 
                                       (f"%{q_admin}%", per_page, offset), fetchall=True)
        else:
            total_items = total_productos_unicos
            lista_productos = execute_query(f"{base_query} ORDER BY {order_clause} LIMIT ? OFFSET ?", 
                                       (per_page, offset), fetchall=True)
            
        total_pages = max(1, (total_items + per_page - 1) // per_page)

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
        # DB_NAME se importa de config.py
        return send_file(DB_NAME, as_attachment=True)

    @admin_bp.route('/admin/carrusel/nuevo', methods=['POST'])
    @login_required
    def subir_carrusel():
        file = request.files.get('imagen')
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(CARRUSEL_FOLDER, filename))
            execute_query("INSERT INTO carrusel (filename) VALUES (?)", (filename,), commit=True)
            registrar_log(f"Imagen subida al carrusel: {filename}")
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
    # CRUD de Productos (Soporte Caracteres Especiales)
    # ==========================================
    @admin_bp.route('/admin/producto/nuevo', methods=['POST'])
    @login_required
    def agregar_producto():
        producto = request.form.get('producto')
        precio = request.form.get('precio')
        url = request.form.get('url') or '#'
        if producto and precio:
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            execute_query("INSERT INTO historial_precios (producto, precio, precio_base, url, fecha, activo) VALUES (?, ?, ?, ?, ?, 1)", 
                     (producto, precio, precio, url, fecha_actual), commit=True)
            registrar_log(f"Producto creado manualmente: {producto}")
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/producto/editar/<path:nombre_producto>', methods=['GET', 'POST'])
    @login_required
    def editar_producto(nombre_producto):
        if request.method == 'POST':
            nuevo_nombre = request.form.get('producto')
            nuevo_precio = request.form.get('precio')
            nueva_url = request.form.get('url') or '#'
            execute_query("UPDATE historial_precios SET producto = ?, precio = ?, url = ? WHERE producto = ?", 
                     (nuevo_nombre, nuevo_precio, nueva_url, nombre_producto), commit=True)
            registrar_log(f"Producto modificado: {nombre_producto} -> {nuevo_nombre}")
            return redirect(url_for('admin_bp.admin_panel'))
            
        prod = execute_query("SELECT precio, url FROM historial_precios WHERE producto = ? ORDER BY fecha DESC LIMIT 1", 
                        (nombre_producto,), fetchone=True)
        if not prod: return redirect(url_for('admin_bp.admin_panel'))
        
        return render_template('admin_edit.html', nombre_producto=nombre_producto, prod=prod)

    @admin_bp.route('/admin/producto/toggle/<path:nombre_producto>')
    @login_required
    def toggle_visibilidad(nombre_producto):
        estado = execute_query("SELECT MIN(COALESCE(activo, 1)) FROM historial_precios WHERE producto = ?", (nombre_producto,), fetchone=True)[0]
        nuevo_estado = 0 if estado == 1 else 1
        execute_query("UPDATE historial_precios SET activo = ? WHERE producto = ?", (nuevo_estado, nombre_producto), commit=True)
        texto_estado = "Oculto" if nuevo_estado == 0 else "Visible"
        registrar_log(f"Visibilidad modificada: '{nombre_producto}' ahora está {texto_estado}")
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/producto/eliminar/<path:nombre_producto>')
    @login_required
    def eliminar_producto(nombre_producto):
        execute_query("DELETE FROM historial_precios WHERE producto = ?", (nombre_producto,), commit=True)
        registrar_log(f"Producto eliminado del catálogo: {nombre_producto}")
        return redirect(url_for('admin_bp.admin_panel'))

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
            # Reemplazamos la ejecución unitaria por la ejecución de todo el Manager
            total_productos, duracion = scraper_manager.ejecutar_todos()
            
            # Nota: El logger ya fue llamado desde el interior de ejecutar_todos().
            return jsonify({
                "status": "success",
                "mensaje": f"✅ ¡Escaneo General Completado con Éxito!\n\nTiempo: {duracion:.1f} segundos.\nProductos totales registrados: {total_productos}",
                "message": f"✅ ¡Escaneo General Completado con Éxito!\n\nTiempo: {duracion:.1f} segundos.\nProductos totales registrados: {total_productos}"
            }), 200
            
        except Exception as e:
            registrar_log(f"Error desde Panel de Control en ejecución forzada: {str(e)}")
            return jsonify({
                "status": "error", 
                "mensaje": f"❌ Ocurrió un problema técnico durante la ejecución global:\n{str(e)}",
                "message": f"❌ Ocurrió un problema técnico durante la ejecución global:\n{str(e)}"
            }), 500

    return admin_bp