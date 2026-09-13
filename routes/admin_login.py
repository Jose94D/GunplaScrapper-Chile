from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

# Importamos las herramientas de la capa core
from core.database import execute_query
from core.logger import registrar_log

def crear_blueprint_admin_login(admin_user_fallback, admin_pass_fallback):
    admin_login_bp = Blueprint('admin_login_bp', __name__)

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
            # Mantenemos 'username' del input del form HTML, 
            # aunque en la base de datos ahora lo guardemos como 'email'.
            user_input = request.form.get('username')
            pass_input = request.form.get('password')
            
            # Consultamos las credenciales en la nueva tabla 'usuarios'
            cred = execute_query('SELECT email, hash_clave FROM usuarios WHERE id = 1', fetchone=True)

            valido = False
            # Si hay credenciales en DB, comparamos con ellas usando el hash real
            if cred:
                # cred[0] es email, cred[1] es hash_clave (hash, no texto plano)
                if user_input == cred[0] and check_password_hash(cred[1], pass_input):
                    valido = True
            # Si la DB está vacía (fila id=1 aún no existe), usamos las de config.py (Fallback)
            else:
                if user_input == admin_user_fallback and pass_input == admin_pass_fallback:
                    valido = True

            if valido:
                session['admin_logged'] = True
                registrar_log(f"Inicio de sesión exitoso: {user_input}")
                return redirect(url_for('admin_bp.admin_panel'))
            else:
                error = "Credenciales incorrectas."
                registrar_log(f"Intento de inicio de sesión fallido con usuario/email: {user_input}")

        # Si no es POST o falló el login, renderizamos la plantilla de acceso
        return render_template('admin_login.html', error=error)

    return admin_login_bp