import sqlite3
import json
from flask import Blueprint, render_template

def crear_blueprint_producto(DB_NAME):
    producto_bp = Blueprint('producto_bp', __name__)

    def get_db_data(incrementar_visita=False):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        if incrementar_visita:
            c.execute("UPDATE estadisticas SET contador = contador + 1 WHERE id = 1")
        c.execute("SELECT contador FROM estadisticas WHERE id = 1")
        visitas = c.fetchone()[0]
        c.execute("SELECT MAX(fecha) FROM historial_precios")
        fecha = c.fetchone()[0]
        conn.commit()
        conn.close()
        return fecha[:10] if fecha else "N/A", visitas

    @producto_bp.route('/producto/<path:nombre>')
    def ver_grafico(nombre):
        conn = sqlite3.connect(DB_NAME)
        datos = conn.cursor().execute("SELECT precio, fecha, url FROM historial_precios WHERE producto = ? ORDER BY fecha ASC", (nombre,)).fetchall()
        conn.close()
        fecha, visitas = get_db_data(incrementar_visita=False)
        
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