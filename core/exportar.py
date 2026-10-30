"""Reporte en Excel con todo el historial de precios."""
import io

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

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
    # Modo de solo escritura: las filas van directo al archivo, sin armar la planilla completa en memoria
    libro = Workbook(write_only=True)
    hoja = libro.create_sheet('Historial Global')
    encabezado = []
    for nombre in COLUMNAS:
        celda = WriteOnlyCell(hoja, value=nombre)
        celda.font = Font(bold=True)
        encabezado.append(celda)
    hoja.append(encabezado)
    for fila in execute_query(query, fetchall=True):
        hoja.append(fila)

    archivo = io.BytesIO()
    libro.save(archivo)
    archivo.seek(0)
    return archivo
