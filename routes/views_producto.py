import json
from flask import Blueprint, render_template, request # ⬅ IMPORTANTE: Agregado 'request'

# Importamos las herramientas de la capa core
from core.database import execute_query, get_estadisticas_globales

def crear_blueprint_producto():
    producto_bp = Blueprint('producto_bp', __name__)

    # ATENCIÓN: La ruta ahora espera un ID (entero), no un texto
    @producto_bp.route('/producto/<int:id>')
    def ver_grafico(id):
        # 1. CAPTURAMOS LA MOCHILA DE PARÁMETROS DE LA URL
        q = request.args.get('q', '')
        grado = request.args.get('grado', '')
        sort = request.args.get('sort', '')
        per_page = request.args.get('per_page', '')
        page = request.args.get('page', '')

        # 2. Obtenemos estadísticas globales a través del core
        fecha, visitas = get_estadisticas_globales(incrementar_visita=False)
        
        # 3. Consultamos el nombre del producto en el catálogo global
        cat_data = execute_query("SELECT nombre_estandar FROM catalogo_global WHERE id = ?", (id,), fetchone=True)
        if not cat_data:
            return "Producto no encontrado", 404
        nombre_estandar = cat_data[0]

        # 4. Buscamos qué tiendas tienen vinculado este ID
        tiendas_db = execute_query("SELECT id, tienda, nombre_original, url FROM publicaciones_tiendas WHERE catalogo_id = ?", (id,), fetchall=True)
        
        tiendas = []
        datasets = []
        todas_las_fechas = set()
        tienda_historial = {}
        
        # 5. Procesamos el historial de cada tienda individual
        for t in tiendas_db:
            pub_id = t[0]
            t_nombre = t[1]
            t_orig = t[2]
            t_url = t[3]
            
            # Buscamos los precios históricos de esta publicación
            historial = execute_query("SELECT precio, fecha FROM historial_precios WHERE publicacion_id = ? ORDER BY fecha ASC", (pub_id,), fetchall=True)
            
            # Tomamos el precio más reciente para la tarjeta de la tienda
            ultimo_precio = historial[-1][0] if historial else "N/A"
            tiendas.append({
                "nombre": t_nombre,
                "nombre_original": t_orig,
                "precio": ultimo_precio,
                "url": t_url
            })
            
            # Extraemos fechas y precios enteros para el gráfico
            precios_dict = {}
            for h in historial:
                precio_str = h[0].replace('$', '').replace('.', '').replace(' ', '')
                precio_int = int(precio_str) if precio_str.isdigit() else 0
                fecha_str = h[1]
                
                precios_dict[fecha_str] = precio_int
                todas_las_fechas.add(fecha_str) # Acumulamos las fechas en un set global
                
            tienda_historial[t_nombre] = precios_dict

        # 6. Ordenamos todas las fechas de menor a mayor (Eje X del gráfico)
        fechas_ordenadas = sorted(list(todas_las_fechas))
        
        # 7. Preparamos las líneas (datasets) para Chart.js
        for t_nombre, precios_dict in tienda_historial.items():
            data_array = []
            ultimo_conocido = None
            
            for f in fechas_ordenadas:
                if f in precios_dict:
                    ultimo_conocido = precios_dict[f]
                    data_array.append(ultimo_conocido)
                else:
                    # Rellenamos huecos si la tienda no tuvo escaneo en esa fecha exacta
                    data_array.append(ultimo_conocido) 
                    
            datasets.append({
                "label": t_nombre,
                "data": data_array,
                "spanGaps": True
            })

        fechas_json = json.dumps(fechas_ordenadas)
        datasets_json = json.dumps(datasets)

        # 8. PASAMOS LOS PARÁMETROS A LA PLANTILLA PARA MANTENER LA PERSISTENCIA
        return render_template('producto.html',
                               nombre_estandar=nombre_estandar,
                               tiendas=tiendas,
                               fecha=fecha,
                               visitas=visitas,
                               fechas_json=fechas_json,
                               datasets_json=datasets_json,
                               q=q,
                               grado=grado,
                               sort=sort,
                               per_page=per_page,
                               page=page)

    return producto_bp