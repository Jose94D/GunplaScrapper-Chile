"""Listados del catálogo: el público del inicio y el del panel de administración."""
import math
import re
import unicodedata

from core.database import execute_query

POR_PAGINA_PERMITIDOS = (24, 48, 120)


def slug(nombre):
    """'Gundam Exia RG' -> 'gundam-exia-rg': la parte legible de la URL de un producto."""
    texto = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '-', texto).strip('-') or 'producto'


def listar_para_sitemap():
    """[(id, nombre_estandar), ...] de los productos que se ven en el inicio (visibles y disponibles)."""
    return execute_query("SELECT id, nombre_estandar FROM productos WHERE es_visible = 1 AND disponible = 1 ORDER BY id", fetchall=True)


def por_pagina_valida(valor):
    """Productos por página: uno de los permitidos, o 24."""
    return valor if valor in POR_PAGINA_PERMITIDOS else 24


def formatear_precio(valor):
    """19990.0 -> '$19.990'; None -> 'N/A'."""
    return f"${int(valor):,.0f}".replace(",", ".") if valor is not None else "N/A"


def listar_catalogo_completo():
    """[(id, nombre_estandar, grado), ...] de todos los productos, por nombre (selector de fusión)."""
    return execute_query("SELECT id, nombre_estandar, grado FROM productos ORDER BY nombre_estandar ASC, id ASC", fetchall=True)


def listar_catalogo_publico(busqueda='', grado='', orden='price_asc', pagina=1, por_pagina=24):
    """
    Productos visibles y disponibles para el inicio.
    Retorna ([(id, nombre, grado, precio_texto, imagen), ...], total_paginas); imagen es la ruta dentro de static/ o None.
    """
    # Mejor precio actual: el más bajo entre las tiendas que hoy lo tienen (misma regla que el panel).
    # Antes era el MIN de todo el historial, que mostraba precios viejos o de tiendas que ya no lo venden.
    query_select = """
            SELECT
                p.id,
                p.nombre_estandar,
                p.grado,
                MIN(pp.precio) as precio_min_int,
                p.imagen_producto
            FROM productos p
            LEFT JOIN publicacion_producto pp ON p.id = pp.producto_id AND pp.es_url_activa = 1
        """

    # Filtramos por visibilidad Y por disponibilidad: los productos "No disponible"
    # (sin ninguna tienda activa) no deben aparecer en el módulo de inicio.
    where_conditions = ["p.es_visible = 1", "p.disponible = 1"]
    params = []

    if busqueda:
        where_conditions.append("p.nombre_estandar LIKE ?")
        params.append(f"%{busqueda}%")

    if grado:
        where_conditions.append("p.grado = ?")
        params.append(grado)

    where_clause = " WHERE " + " AND ".join(where_conditions)
    group_by_clause = " GROUP BY p.id, p.nombre_estandar, p.grado"

    if orden in ['price_asc', 'asc']: order_clause = " ORDER BY precio_min_int ASC"
    elif orden in ['price_desc', 'desc']: order_clause = " ORDER BY precio_min_int DESC"
    elif orden == 'alpha_asc': order_clause = " ORDER BY p.nombre_estandar ASC"
    elif orden == 'alpha_desc': order_clause = " ORDER BY p.nombre_estandar DESC"
    else: order_clause = " ORDER BY precio_min_int ASC"
    # Desempate fijo: sin él, filas con el mismo precio o nombre cambian de orden según el índice que use SQLite
    order_clause += ", p.id ASC"

    # Los filtros son solo sobre productos, así que no hace falta unir publicaciones para contar
    count_query = "SELECT COUNT(*) FROM productos p" + where_clause
    total_items_result = execute_query(count_query, tuple(params), fetchone=True)
    total_items = total_items_result[0] if total_items_result and total_items_result[0] else 0
    total_paginas = max(1, math.ceil(total_items / por_pagina))

    final_query = f"{query_select} {where_clause} {group_by_clause} {order_clause} LIMIT ? OFFSET ?"
    params.extend([por_pagina, (pagina - 1) * por_pagina])
    filas = execute_query(final_query, tuple(params), fetchall=True)

    return [(f[0], f[1], f[2], formatear_precio(f[3]), f[4]) for f in filas], total_paginas


def listar_productos_panel(busqueda='', grado='', orden='date_desc', pagina=1, por_pagina=24):
    """
    Todos los productos para el panel, siempre agrupados por estado: Visibles, No disponibles, Ocultos.
    Retorna ([(id, nombre, grado, precio_texto, ultima_fecha, es_visible, disponible, tier_estado), ...], total_paginas).
    """
    order_clause = {
        'price_asc': "precio_min_int ASC",
        'price_desc': "precio_min_int DESC",
        'alpha_asc': "c.nombre_estandar ASC",
        'alpha_desc': "c.nombre_estandar DESC",
        'date_desc': "ultima_fecha DESC"
    }.get(orden, "ultima_fecha DESC")

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

    # El precio es el de las publicaciones activas (precio actual)
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

    if busqueda:
        where_conditions.append("c.nombre_estandar LIKE ?")
        params.append(f"%{busqueda}%")

    if grado:
        where_conditions.append("c.grado = ?")
        params.append(grado)

    where_clause = ""
    if where_conditions:
        where_clause = " WHERE " + " AND ".join(where_conditions)

    count_query = f"SELECT COUNT(id) FROM productos c {where_clause}"
    total_items = execute_query(count_query, tuple(params), fetchone=True)[0]
    total_paginas = max(1, (total_items + por_pagina - 1) // por_pagina)

    query = f"{base_query} {where_clause} GROUP BY c.id, c.nombre_estandar, c.grado ORDER BY {order_clause}, c.id ASC LIMIT ? OFFSET ?"
    params.extend([por_pagina, (pagina - 1) * por_pagina])
    filas = execute_query(query, tuple(params), fetchall=True)

    lista = []
    for p in filas:
        precio_val = p[3]
        precio_texto = f"${precio_val:,.0f}".replace(",", ".") if precio_val is not None and precio_val > 0 else "N/A"
        # Tier de estado, mismo criterio que el ORDER BY: 0=Visible, 1=No disponible, 2=Oculto
        es_visible_val, disponible_val = p[5], p[6]
        if disponible_val == 0:
            tier_estado = 1
        elif es_visible_val == 1:
            tier_estado = 0
        else:
            tier_estado = 2
        lista.append((p[0], p[1], p[2], precio_texto, p[4] or 'Sin datos', es_visible_val, disponible_val, tier_estado))
    return lista, total_paginas


def detalle_producto(id):
    """
    Datos de la ficha de un producto: precio actual en cada tienda e historial para el gráfico.
    Retorna None si no existe, o dict con nombre, tiendas, fechas (eje X) y datasets (una línea por tienda).
    """
    fila = execute_query("SELECT nombre_estandar, imagen_producto FROM productos WHERE id = ?", (id,), fetchone=True)
    if not fila:
        return None

    publicaciones = execute_query("""
            SELECT pp.id, t.nombre, pp.nombre_original, pp.url, pp.es_url_activa 
            FROM publicacion_producto pp
            JOIN tiendas t ON pp.tienda_id = t.id
            WHERE pp.producto_id = ?
        """, (id,), fetchall=True)

    tiendas = []
    precios_activos = []  # último precio de cada tienda que hoy lo tiene: el "desde $X" al compartir
    todas_las_fechas = set()
    tienda_historial = {}
    # Todo el historial del producto en una consulta (antes era una por tienda), agrupado por publicación
    historial_por_pub = {}
    for pub_id, precio, fecha in execute_query("""
            SELECT h.publicacion_producto_id, h.precio, h.fecha_registro FROM historial_precios h
            JOIN publicacion_producto pp ON h.publicacion_producto_id = pp.id
            WHERE pp.producto_id = ? ORDER BY h.fecha_registro ASC, h.id ASC
        """, (id,), fetchall=True):
        historial_por_pub.setdefault(pub_id, []).append((precio, fecha))

    for pub_id, t_nombre, t_orig, t_url, t_activa in publicaciones:
        historial = historial_por_pub.get(pub_id, [])

        # La tarjeta muestra el último precio registrado en esa tienda
        tiendas.append({
            "nombre": t_nombre,
            "nombre_original": t_orig,
            "precio": formatear_precio(historial[-1][0]) if historial else "N/A",
            "url": t_url,
            "disponible": bool(t_activa)
        })
        if t_activa and historial and historial[-1][0]:
            precios_activos.append(historial[-1][0])

        # Un precio por día (el último registrado ese día)
        precios_por_dia = {}
        for precio, fecha in historial:
            dia = fecha[:10] if fecha else ""
            precios_por_dia[dia] = int(precio) if precio is not None else 0
            todas_las_fechas.add(dia)
        tienda_historial[t_nombre] = precios_por_dia

    # Cada tienda repite su último precio conocido en los días en que no se registró
    fechas = sorted(todas_las_fechas)
    datasets = []
    for t_nombre, precios_por_dia in tienda_historial.items():
        data, ultimo_conocido = [], None
        for dia in fechas:
            ultimo_conocido = precios_por_dia.get(dia, ultimo_conocido)
            data.append(ultimo_conocido)
        datasets.append({"label": t_nombre, "data": data, "spanGaps": True})

    return {"nombre": fila[0], "imagen": fila[1], "tiendas": tiendas, "fechas": fechas, "datasets": datasets,
            "mejor_precio": formatear_precio(min(precios_activos)) if precios_activos else None}
