import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, request, session, redirect, url_for

def crear_blueprint_admin_login(DB_NAME, ADMIN_USER_FALLBACK, ADMIN_PASS_FALLBACK):
    admin_login_bp = Blueprint('admin_login_bp', __name__)

    # ==========================================
    # Funciones Auxiliares Locales
    # ==========================================
    def db_query(query, args=(), fetchone=False, commit=False):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(query, args)
        resultado = c.fetchone() if fetchone else None
        if commit:
            conn.commit()
        conn.close()
        return resultado

    def registrar_log(accion):
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query("INSERT INTO logs (fecha, accion) VALUES (?, ?)", (fecha_actual, accion), commit=True)

    # ==========================================
    # Ruta de Autenticación Principal
    # ==========================================
    @admin_login_bp.route('/admin', methods=['GET', 'POST'])
    def admin_login():
        # Si ya existe una sesión activa, redirigir inmediatamente al panel
        if 'admin_logged' in session:
            return redirect(url_for('admin_bp.admin_panel'))
        
        error = None
        if request.method == 'POST':
            user_input = request.form.get('username')
            pass_input = request.form.get('password')
            
            # Consultamos las credenciales actuales directamente en la base de datos
            cred = db_query('SELECT usuario, password FROM credenciales WHERE id = 1', fetchone=True)

            if cred and user_input == cred[0] and pass_input == cred[1]:
                session['admin_logged'] = True
                registrar_log(f"Inicio de sesión exitoso: {user_input}")
                return redirect(url_for('admin_bp.admin_panel'))
            else:
                error = "Credenciales incorrectas."
                registrar_log(f"Intento de inicio de sesión fallido con usuario: {user_input}")

        # Si no es POST o falló el login, renderizamos la plantilla de acceso
        return render_template('admin_login.html', error=error)

    return admin_login_bp