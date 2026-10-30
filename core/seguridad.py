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


# Todo (estilos, fuentes, scripts, imágenes) se sirve desde el propio sitio, así que la política puede ser estricta:
# sin scripts en línea ni de otros dominios, y nadie puede meter el sitio dentro de un <iframe>.
# img-src admite data: por los iconos SVG que Bootstrap trae dentro de su CSS.
CSP = ("default-src 'self'; img-src 'self' data:; object-src 'none'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


def cabeceras_seguridad(app):
    """Agrega a cada respuesta las cabeceras que piden al navegador las protecciones básicas."""
    @app.after_request
    def agregar_cabeceras(respuesta):
        respuesta.headers.setdefault('Content-Security-Policy', CSP)
        respuesta.headers.setdefault('X-Content-Type-Options', 'nosniff')  # no adivinar el tipo de un archivo
        respuesta.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')  # a otros sitios solo llega el dominio
        return respuesta
