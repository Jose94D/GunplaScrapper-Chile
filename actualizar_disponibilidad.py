"""
Ubicación: raíz del proyecto (junto a app.py y config.py)

Script independiente: recalcula el estado 'No disponible' de los productos
según la disponibilidad actual por tienda (publicacion_producto.es_url_activa).

Uso manual (desde la raíz del proyecto):
    python actualizar_disponibilidad.py

Uso como tarea programada (cron, ejemplo cada 30 min):
    */30 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python actualizar_disponibilidad.py

No vuelve a scrapear nada: solo reevalúa, con los datos ya guardados en la DB,
qué productos quedaron sin ninguna publicación activa en ninguna tienda.
"""

from core.database import init_db, actualizar_disponibilidad_productos

if __name__ == "__main__":
    init_db()  # asegura que la columna 'disponible' exista si la DB es antigua
    total = actualizar_disponibilidad_productos()
    print(f"Disponibilidad recalculada. Productos 'No disponible': {total}")
