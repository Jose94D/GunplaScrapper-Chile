"""Resumen del estado del sistema para el panel de administración."""
from datetime import datetime

from core.database import execute_query

SIN_ESCANEOS = "Sin escaneos aún"
HORAS_ALERTA = 48


def estado_tiendas():
    """
    Último escaneo de cada tienda scrapeada, de la más atrasada a la más reciente.
    Si una tienda aún no tiene ultimo_exito (bases anteriores a esta columna), se toma su último precio registrado.
    """
    filas = execute_query("""
        SELECT t.nombre,
               COALESCE(t.ultimo_exito, (SELECT MAX(h.fecha_registro) FROM historial_precios h
                                         JOIN publicacion_producto pp ON h.publicacion_producto_id = pp.id
                                         WHERE pp.tienda_id = t.id)) AS ultimo_exito,
               t.ultimo_intento, t.productos_ultimo_escaneo, t.ultimo_error,
               (SELECT COUNT(*) FROM publicacion_producto pp WHERE pp.tienda_id = t.id AND pp.es_url_activa = 1) AS activas
        FROM tiendas t
        WHERE t.nombre != 'Manual'
        ORDER BY ultimo_exito ASC
    """, fetchall=True)

    estado = []
    for nombre, ultimo_exito, ultimo_intento, productos, error, activas in filas:
        try:
            atrasada = (datetime.now() - datetime.strptime(ultimo_exito, "%Y-%m-%d %H:%M:%S")).total_seconds() > HORAS_ALERTA * 3600
        except (TypeError, ValueError):
            atrasada = True  # nunca tuvo un escaneo exitoso
        # El error solo cuenta si es posterior al último éxito
        fallando = bool(error) and (not ultimo_exito or (ultimo_intento or "") > ultimo_exito)
        estado.append({
            "nombre": nombre, "ultimo_exito": ultimo_exito or "Nunca", "ultimo_intento": ultimo_intento or "Sin registro",
            "productos": productos if productos is not None else activas,
            "error": error if fallando else "", "ok": not atrasada and not fallando,
        })
    return estado


def resumen_panel():
    """
    Tarjetas del panel y la alerta de scraping detenido.
    Retorna dict con ultima_fecha, total_productos, escaneados_hoy, alerta_activa y mensaje_alerta.
    """
    fila = execute_query("SELECT MAX(fecha_registro) FROM historial_precios", fetchone=True)
    ultima_fecha = fila[0] if fila and fila[0] else SIN_ESCANEOS

    total_productos = execute_query("SELECT COUNT(id) FROM productos", fetchone=True)[0]

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    escaneados_hoy = execute_query(
        # Rango en vez de LIKE 'fecha%': así usa el índice de fecha_registro
        "SELECT COUNT(DISTINCT publicacion_producto_id) FROM historial_precios WHERE fecha_registro >= ?",
        (fecha_hoy,),
        fetchone=True
    )[0]

    alerta_activa = False
    mensaje_alerta = ""
    if ultima_fecha == SIN_ESCANEOS:
        alerta_activa = True
        mensaje_alerta = "El sistema aún no tiene registros. Ejecuta un escaneo manual."
    else:
        try:
            fecha_obj = datetime.strptime(ultima_fecha, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - fecha_obj).total_seconds() > HORAS_ALERTA * 3600:
                alerta_activa = True
                mensaje_alerta = f"⚠️ ¡Atención! El último escaneo exitoso fue hace más de {HORAS_ALERTA} horas ({ultima_fecha}). Verifica los scrapers."
        except ValueError:
            pass

    return {"ultima_fecha": ultima_fecha, "total_productos": total_productos, "escaneados_hoy": escaneados_hoy,
            "alerta_activa": alerta_activa, "mensaje_alerta": mensaje_alerta}
