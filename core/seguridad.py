import hmac
import secrets

from flask import abort, request, session
from markupsafe import Markup


def token_csrf():
    """Token aleatorio por sesión. Se crea la primera vez que una página lo pide."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def campo_csrf():
    """Campo oculto para poner dentro de cada <form method="POST">."""
    return Markup(f'<input type="hidden" name="csrf_token" value="{token_csrf()}">')


def proteger_csrf(app):
    """Rechaza todo POST que no traiga el token de la sesión, en el formulario o en la cabecera X-CSRF-Token.

    Evita que otro sitio use la sesión abierta del administrador para enviar formularios al panel.
    """
    @app.before_request
    def verificar_csrf():
        if request.method != 'POST':
            return
        esperado = session.get('csrf_token')
        enviado = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
        if not esperado or not hmac.compare_digest(enviado, esperado):
            abort(400, 'Token CSRF inválido o ausente. Recarga la página e inténtalo de nuevo.')

    app.jinja_env.globals.update(csrf_token=token_csrf, campo_csrf=campo_csrf)
