import os
import io
import pandas as pd
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import Blueprint, render_template, request, session, redirect, url_for, send_file, jsonify

from config import DB_NAME 
from core.database import execute_query
from core.logger import registrar_log

CARRUSEL_FOLDER = os.path.join('static', 'carrusel')
os.makedirs(CARRUSEL_FOLDER, exist_ok=True)

def limpiar_precio_num(precio_val):
    """Auxiliar para asegurar que el precio ingresado manualmente sea un valor flotante/numérico."""
    if isinstance(precio_val, (int, float)):
        return float(precio_val)
    if not precio_val:
        return 0.0
    p_limpio = str(precio_val).replace('$', '').replace('.', '').replace(' ', '')
    try:
        return float(p_limpio)
    except ValueError:
        return 0.0

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
        admin_actual = execute_query("SELECT email FROM usuarios WHERE id = 1", fetchone=True)
        admin_actual = admin_actual[0] if admin_actual else "Administrador"
        
        ultima_fecha_res = execute_query("SELECT MAX(fecha_registro) FROM historial_precios", fetchone=True)
        ultima_fecha_completa = ultima_fecha_res[0] if ultima_fecha_res and ultima_fecha_res[0] else "Sin escaneos aún"
        
        total_productos_unicos = execute_query("SELECT COUNT(id) FROM productos", fetchone=True)[0]
        
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        escaneados_hoy = execute_query(
            "SELECT COUNT(DISTINCT publicacion_producto_id) FROM historial_precios WHERE fecha_registro LIKE ?", 
            (f"{fecha_hoy}%",), 
            fetchone=True
        )[0]
        
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

        lista_logs = execute_query("SELECT fecha_registro, accion FROM logs ORDER BY id DESC LIMIT 10", fetchall=True)
        lista_carrusel = execute_query("SELECT id, nombre_archivo, enlace FROM banners ORDER BY id ASC", fetchall=True)
        
        q_admin = request.args.get('q_admin', '').strip()
        grado_admin = request.args.get('grado_admin', '')
        if grado_admin == 'Todos': 
            grado_admin = ''
            
        page = request.args.get('page', 1, type=int)
        sort_admin = request.args.get('sort_admin', 'date_desc')
        
        order_clause = {
            'price_asc': "precio_min_int ASC",
            'price_desc': "precio_min_int DESC"
        }.get(sort_admin, "ultima_fecha DESC")

        # 2.6: Orden de estado fijo, sin importar el filtro/orden elegido por el usuario:
        # 1) Visibles  2) No disponibles  3) Ocultos.
        # "No disponible" pisa a "Oculto" para mantener coherencia con lo que se muestra
        # en la columna Estado (un producto oculto y sin stock se ve como "No disponible").
        orden_estado = """
            CASE 
                WHEN c.disponible = 0 THEN 1
                WHEN c.es_visible = 1 THEN 0
                ELSE 2
            END
        """
        order_clause = f"{orden_estado} ASC, {order_clause}"
        
        per_page = request.args.get('per_page', 24, type=int)
        if per_page not in [24, 48, 120]: per_page = 24
        offset = (page - 1) * per_page

        # CONSULTA CORREGIDA: Usa pt.precio directo de la publicación activa
        base_query = """
            SELECT 
                c.id, 
                c.nombre_estandar, 
                c.grado,
                MIN(pt.precio) as precio_min_int,
                MAX(hp.fecha_registro) as ultima_fecha,
                c.es_visible as estado_activo,
                c.disponible as estado_disponible
            FROM productos c
            LEFT JOIN publicacion_producto pt ON c.id = pt.producto_id AND pt.es_url_activa = 1
            LEFT JOIN historial_precios hp ON pt.id = hp.publicacion_producto_id
        """

        where_conditions = []
        params = []

        if q_admin:
            where_conditions.append("c.nombre_estandar LIKE ?")
            params.append(f"%{q_admin}%")

        if grado_admin:
            where_conditions.append("c.grado = ?")
            params.append(grado_admin)

        where_clause = ""
        if where_conditions:
            where_clause = " WHERE " + " AND ".join(where_conditions)

        count_query = f"SELECT COUNT(id) FROM productos c {where_clause}"
        total_items = execute_query(count_query, tuple(params), fetchone=True)[0]
        total_pages = max(1, (total_items + per_page - 1) // per_page)

        query = f"{base_query} {where_clause} GROUP BY c.id, c.nombre_estandar, c.grado ORDER BY {order_clause} LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        lista_cruda = execute_query(query, tuple(params), fetchall=True)

        lista_productos = []
        for p in lista_cruda:
            precio_val = p[3]
            precio_formateado = f"${precio_val:,.0f}".replace(",", ".") if precio_val is not None and precio_val > 0 else "N/A"
            # Tier de estado, mismo criterio que el ORDER BY: 0=Visible, 1=No disponible, 2=Oculto
            es_visible_val, disponible_val = p[5], p[6]
            if disponible_val == 0:
                tier_estado = 1
            elif es_visible_val == 1:
                tier_estado = 0
            else:
                tier_estado = 2
            lista_productos.append((p[0], p[1], p[2], precio_formateado, p[4] or 'Sin datos', es_visible_val, disponible_val, tier_estado))

        catalogo_completo = execute_query("SELECT id, nombre_estandar, grado FROM productos ORDER BY nombre_estandar ASC", fetchall=True)

        return render_template('admin_panel.html', 
                               usuario=admin_actual, escaneados_hoy=escaneados_hoy, 
                               total_productos=total_productos_unicos, ultima_fecha=ultima_fecha_completa, 
                               lista_productos=lista_productos, lista_carrusel=lista_carrusel, 
                               lista_logs=lista_logs, search_query=q_admin, grado_admin=grado_admin,
                               page=page, total_pages=total_pages, alerta_activa=alerta_activa, 
                               mensaje_alerta=mensaje_alerta, per_page=per_page, sort_admin=sort_admin,
                               catalogo_completo=catalogo_completo)

    @admin_bp.route('/admin/credenciales/actualizar', methods=['POST'])
    @login_required
    def actualizar_credenciales():
        nuevo_user = request.form.get('nuevo_usuario')
        nueva_pass = request.form.get('nueva_password')
        if nuevo_user and nueva_pass:
            hash_clave = generate_password_hash(nueva_pass)

            # La fila id=1 puede no existir todavía tras la migración: verificamos primero.
            existe = execute_query("SELECT id FROM usuarios WHERE id = 1", fetchone=True)

            if existe:
                execute_query(
                    "UPDATE usuarios SET email = ?, hash_clave = ? WHERE id = 1",
                    (nuevo_user, hash_clave),
                    commit=True
                )
            else:
                execute_query(
                    "INSERT INTO usuarios (id, email, hash_clave, rol, fecha_creacion) VALUES (1, ?, ?, 'admin', ?)",
                    (nuevo_user, hash_clave, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    commit=True
                )

            registrar_log(f"Se actualizaron las credenciales. Nuevo usuario: {nuevo_user}")
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/backup')
    @login_required
    def descargar_backup():
        registrar_log("Se descargó un backup de la base de datos.")
        return send_file(DB_NAME, as_attachment=True)

    @admin_bp.route('/admin/exportar_excel')
    @login_required
    def exportar_excel():
        query = """
            SELECT 
                p.nombre_estandar AS 'Modelo', 
                p.grado AS 'Grado', 
                t.nombre AS 'Tienda', 
                hl.precio AS 'Precio Registrado', 
                hl.fecha_registro AS 'Fecha de Captura',
                pp.url AS 'Enlace'
            FROM historial_precios hl
            JOIN publicacion_producto pp ON hl.publicacion_producto_id = pp.id
            JOIN productos p ON pp.producto_id = p.id
            JOIN tiendas t ON pp.tienda_id = t.id
            ORDER BY hl.fecha_registro DESC;
        """
        
        datos_crudos = execute_query(query, fetchall=True)
        columnas = ['Modelo', 'Grado', 'Tienda', 'Precio Registrado', 'Fecha de Captura', 'Enlace']
        df = pd.DataFrame(datos_crudos, columns=columnas)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Historial Global')
        
        output.seek(0)
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
        file = request.files.get('imagen')
        link = request.form.get('link') or ''
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(CARRUSEL_FOLDER, filename))
            
            execute_query("INSERT INTO banners (nombre_archivo, enlace) VALUES (?, ?)", (filename, link), commit=True)
            registrar_log(f"Imagen subida a banners con enlace: {filename}")
            
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')
    
    @admin_bp.route('/admin/carrusel/editar_link/<int:img_id>', methods=['POST'])
    @login_required
    def editar_link_carrusel(img_id):
        nuevo_link = request.form.get('nuevo_link') or ''
        execute_query("UPDATE banners SET enlace = ? WHERE id = ?", (nuevo_link, img_id), commit=True)
        registrar_log(f"Enlace actualizado en banner (ID imagen: {img_id})")
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')

    @admin_bp.route('/admin/carrusel/eliminar/<int:img_id>')
    @login_required
    def eliminar_carrusel(img_id):
        img = execute_query("SELECT nombre_archivo FROM banners WHERE id = ?", (img_id,), fetchone=True)
        if img:
            try: os.remove(os.path.join(CARRUSEL_FOLDER, img[0]))
            except FileNotFoundError: pass
            execute_query("DELETE FROM banners WHERE id = ?", (img_id,), commit=True)
            registrar_log(f"Imagen eliminada de banners: {img[0]}")
        return redirect(url_for('admin_bp.admin_panel') + '#seccion-carrusel')

    @admin_bp.route('/admin/producto/nuevo', methods=['POST'])
    @login_required
    def agregar_producto():
        producto = request.form.get('producto')
        grado = request.form.get('grado') or 'S/G'
        precio_raw = request.form.get('precio')
        precio = limpiar_precio_num(precio_raw)
        url = request.form.get('url') or '#'
        
        if producto and precio > 0:
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            execute_query("INSERT INTO productos (nombre_estandar, grado) VALUES (?, ?)", (producto, grado), commit=True)
            cat_id = execute_query("SELECT MAX(id) FROM productos", fetchone=True)[0]
            
            execute_query("INSERT OR IGNORE INTO tiendas (nombre, url_base) VALUES ('Manual', '#')", commit=True)
            tienda_id = execute_query("SELECT id FROM tiendas WHERE nombre = 'Manual'", fetchone=True)[0]
            
            execute_query(
                "INSERT INTO publicacion_producto (producto_id, tienda_id, nombre_original, url, precio, es_url_activa) VALUES (?, ?, ?, ?, ?, 1)", 
                (cat_id, tienda_id, producto, url, precio), 
                commit=True
            )
            pub_id = execute_query("SELECT MAX(id) FROM publicacion_producto", fetchone=True)[0]
            
            execute_query(
                "INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (?, ?, ?)", 
                (pub_id, precio, fecha_actual), 
                commit=True
            )
            registrar_log(f"Producto creado manualmente en catálogo: {producto}")
            
        return redirect(url_for('admin_bp.admin_panel'))

    @admin_bp.route('/admin/producto/editar/<int:id>', methods=['GET', 'POST'])
    @login_required
    def editar_producto(id):
        if request.method == 'POST':
            nuevo_nombre = request.form.get('producto')
            nuevo_grado = request.form.get('grado')
            execute_query("UPDATE productos SET nombre_estandar = ?, grado = ? WHERE id = ?", 
                     (nuevo_nombre, nuevo_grado, id), commit=True)
            registrar_log(f"Producto ID {id} modificado en catálogo.")
            return redirect(url_for('admin_bp.admin_panel',
                                    page=request.form.get('page'),
                                    q_admin=request.form.get('q_admin'),
                                    grado_admin=request.form.get('grado_admin'),
                                    sort_admin=request.form.get('sort_admin'),
                                    per_page=request.form.get('per_page')))
            
        prod = execute_query("SELECT id, nombre_estandar, grado FROM productos WHERE id = ?", (id,), fetchone=True)
        if not prod: return redirect(url_for('admin_bp.admin_panel'))
        
        params = {
            'page': request.args.get('page', 1),
            'q_admin': request.args.get('q_admin', ''),
            'grado_admin': request.args.get('grado_admin', ''),
            'sort_admin': request.args.get('sort_admin', 'date_desc'),
            'per_page': request.args.get('per_page', 24)
        }
        return render_template('admin_edit.html', prod=prod, params=params)

    @admin_bp.route('/admin/producto/toggle/<int:id>')
    @login_required
    def toggle_visibilidad(id):
        estado = execute_query("SELECT es_visible FROM productos WHERE id = ?", (id,), fetchone=True)[0]
        nuevo_estado = 0 if estado == 1 else 1
        
        execute_query("UPDATE productos SET es_visible = ? WHERE id = ?", (nuevo_estado, id), commit=True)
        
        texto_estado = "Oculto" if nuevo_estado == 0 else "Visible"
        registrar_log(f"Visibilidad modificada: Producto ID {id} ahora está {texto_estado}")
        return redirect(url_for('admin_bp.admin_panel',
                                page=request.args.get('page'),
                                q_admin=request.args.get('q_admin'),
                                grado_admin=request.args.get('grado_admin'),
                                sort_admin=request.args.get('sort_admin'),
                                per_page=request.args.get('per_page')))

    @admin_bp.route('/admin/producto/eliminar/<int:id>')
    @login_required
    def eliminar_producto(id):
        execute_query("DELETE FROM historial_precios WHERE publicacion_producto_id IN (SELECT id FROM publicacion_producto WHERE producto_id = ?)", (id,), commit=True)
        execute_query("DELETE FROM publicacion_producto WHERE producto_id = ?", (id,), commit=True)
        execute_query("DELETE FROM productos WHERE id = ?", (id,), commit=True)
        
        registrar_log(f"Producto eliminado completamente del catálogo ID: {id}")
        return redirect(url_for('admin_bp.admin_panel',
                                page=request.args.get('page'),
                                q_admin=request.args.get('q_admin'),
                                grado_admin=request.args.get('grado_admin'),
                                sort_admin=request.args.get('sort_admin'),
                                per_page=request.args.get('per_page')))

    @admin_bp.route('/admin/fusionar', methods=['POST'])
    @login_required
    def fusionar_productos():
        id_duplicado = request.form.get('id_duplicado')
        id_principal = request.form.get('id_principal')
        
        if id_duplicado and id_principal and id_duplicado != id_principal:
            execute_query("UPDATE publicacion_producto SET producto_id = ? WHERE producto_id = ?", (id_principal, id_duplicado), commit=True)
            execute_query("DELETE FROM productos WHERE id = ?", (id_duplicado,), commit=True)
            registrar_log(f"Fusión: Producto ID {id_duplicado} integrado en el Producto ID {id_principal}.")
            
        return redirect(url_for('admin_bp.admin_panel',
                                page=request.form.get('page'),
                                q_admin=request.form.get('q_admin'),
                                grado_admin=request.form.get('grado_admin'),
                                sort_admin=request.form.get('sort_admin'),
                                per_page=request.form.get('per_page')))

    @admin_bp.route('/admin/logout')
    def admin_logout():
        session.pop('admin_logged', None)
        registrar_log("Cierre de sesión.")
        return redirect(url_for('admin_login_bp.admin_login'))

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