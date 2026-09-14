from flask import Blueprint, render_template

# =====================================================================
# BLUEPRINT INSTITUCIONAL (Sobre Nosotros / FAQ)
# =====================================================================
def crear_blueprint_institucional():
    """
    Controla las rutas estáticas '/sobre-nosotros' y '/faq'.
    Páginas institucionales del proyecto: qué es, stack técnico, uso ético
    y responsable del scraping, perfil del desarrollador, y preguntas frecuentes.
    """
    institucional_bp = Blueprint('institucional_bp', __name__)

    @institucional_bp.route('/sobre-nosotros')
    def sobre_nosotros():
        return render_template('public/sobre_nosotros.html')

    @institucional_bp.route('/faq')
    def faq():
        return render_template('public/faq.html')

    @institucional_bp.route('/condiciones-de-servicio')
    def condiciones_servicio():
        return render_template('public/condiciones_servicio.html')

    @institucional_bp.route('/politicas')
    def politicas():
        return render_template('public/public/politicas.html')

    return institucional_bp