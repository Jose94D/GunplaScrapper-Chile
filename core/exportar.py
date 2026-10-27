"""Reporte en Excel con todo el historial de precios."""
import io

import pandas as pd

from core.database import execute_query

COLUMNAS = ['Modelo', 'Grado', 'Tienda', 'Precio Registrado', 'Fecha de Captura', 'Enlace']


def historial_excel():
    """Archivo .xlsx en memoria (hoja 'Historial Global'), del registro más reciente al más antiguo."""
    query = """
            SELECT
                p.nombre_estandar AS 'Modelo',
                p.grado AS 'Grado',
                t.nombre AS 'Tienda',
                hl.precio AS 'Precio Registrado',
                hl.fecha_registro AS 'Fecha de Captura',
                pp.url AS 'Enlace'
            FROM historial_precios hl
            JOIN publicacion_producto pp ON hl.publicacion_producto_id = pp.id
            JOIN productos p ON pp.producto_id = p.id
            JOIN tiendas t ON pp.tienda_id = t.id
            ORDER BY hl.fecha_registro DESC, hl.id DESC;
        """
    df = pd.DataFrame(execute_query(query, fetchall=True), columns=COLUMNAS)

    archivo = io.BytesIO()
    with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historial Global')
    archivo.seek(0)
    return archivo
