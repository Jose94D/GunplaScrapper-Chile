import hmac
import time

from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash

# Importamos las herramientas de la capa core
from core.usuarios import obtener_credenciales_admin
from core.logger import registrar_log

# Tras 5 claves incorrectas seguidas desde una misma IP, el login queda cerrado 15 minutos para ella
MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60


def crear_blueprint_admin_login(admin_user_fallback, admin_pass_fallback):
    admin_login_bp = Blueprint('admin_login_bp', __name__)
    # shortcut: en memoria y por request.remote_addr; se reinicia con el servidor y, detrás de un proxy, habría que usar ProxyFix
    fallos = {}  # ip -> (intentos fallidos, hora del último)

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
            ip = request.remote_addr
            intentos, ultimo = fallos.get(ip, (0, 0))
            if time.time() - ultimo >= BLOQUEO_SEGUNDOS:
                intentos = 0
            if intentos >= MAX_INTENTOS:
                # Ni siquiera se revisa la clave: así el bloqueo no deja seguir probando
                error = "Demasiados intentos fallidos. Espera 15 minutos e inténtalo de nuevo."
                return render_template('admin/admin_login.html', error=error), 429

            # Mantenemos 'username' del input del form HTML,
            # aunque en la base de datos ahora lo guardemos como 'email'.
            user_input = request.form.get('username', '')
            pass_input = request.form.get('password', '')
            
            # Consultamos las credenciales en la nueva tabla 'usuarios'
            cred = obtener_credenciales_admin()

            valido = False
            # Si hay credenciales en DB, comparamos con ellas usando el hash real
            if cred:
                # cred[0] es email, cred[1] es hash_clave (hash, no texto plano)
                if user_input == cred[0] and check_password_hash(cred[1], pass_input):
                    valido = True
            # Si la DB está vacía (fila id=1 aún no existe), usamos las de config.py (Fallback)
            else:
                # compare_digest tarda lo mismo acierte o no, así el tiempo de respuesta no delata la clave
                if admin_pass_fallback and user_input == admin_user_fallback and \
                        hmac.compare_digest(pass_input.encode(), admin_pass_fallback.encode()):
                    valido = True

            if valido:
                fallos.pop(ip, None)
                # Sesión nueva al entrar: no se reutiliza nada de antes del login
                session.clear()
                session.permanent = True  # vence según PERMANENT_SESSION_LIFETIME
                session['admin_logged'] = True
                registrar_log(f"Inicio de sesión exitoso: {user_input}")
                return redirect(url_for('admin_bp.admin_panel'))
            else:
                fallos[ip] = (intentos + 1, time.time())
                error = "Credenciales incorrectas."
                registrar_log(f"Intento de inicio de sesión fallido con usuario/email: {user_input}")

        # Si no es POST o falló el login, renderizamos la plantilla de acceso
        return render_template('admin/admin_login.html', error=error)

    return admin_login_bp