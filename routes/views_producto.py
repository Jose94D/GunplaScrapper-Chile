import json
from flask import Blueprint, render_template

# Importamos las herramientas de la capa core
from core.database import execute_query, get_estadisticas_globales

def crear_blueprint_producto():
    producto_bp = Blueprint('producto_bp', __name__)

    @producto_bp.route('/producto/<path:nombre>')
    def ver_grafico(nombre):
        # 1. Obtenemos los datos a través del core
        datos = execute_query("SELECT precio, fecha, url FROM historial_precios WHERE producto = ? ORDER BY fecha ASC", (nombre,), fetchall=True)
        
        # 2. Obtenemos estadísticas globales a través del core
        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
        
        precios_limpios = []
        for f in datos:
            precio_str = f[0].replace('$', '').replace('.', '').replace(' ', '')
            precios_limpios.append(int(precio_str) if precio_str.isdigit() else 0)
                
        fechas_json = json.dumps([f[1] for f in datos])
        precios_json = json.dumps(precios_limpios)
        url_producto = datos[0][2] if datos else "#"

        return render_template('producto.html',
                               nombre=nombre,
                               fecha=fecha,
                               visitas=visitas,
                               url_producto=url_producto,
                               fechas_json=fechas_json,
                               precios_json=precios_json)

    return producto_bp