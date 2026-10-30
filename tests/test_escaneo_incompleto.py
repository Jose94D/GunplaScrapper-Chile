"""Un escaneo que trae mucho menos que el anterior (página de la tienda cambiada) no deja el catálogo sin stock."""
import unittest
from datetime import datetime, timedelta

from core.database import execute_query
from tests.test_regresiones import BaseTemporal


class ScraperFalso:
    def __init__(self):
        self.cantidad = 0

    def extraer_datos(self):
        return [{"nombre_original": f"Kit {n} HG", "precio": 19990.0 - self.cantidad, "url": f"https://t.cl/{n}"}
                for n in range(self.cantidad)]


class TestEscaneoIncompleto(BaseTemporal):
    def setUp(self):
        super().setUp()
        from core.scraper_manager import ScraperManager
        self.scraper = ScraperFalso()
        self.manager = ScraperManager()
        self.manager.scrapers = {"T": (self.scraper, "https://t.cl")}

    def escanear(self, cantidad):
        self.scraper.cantidad = cantidad
        self.manager.ejecutar_todos()

    def activas(self):
        return execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE es_url_activa = 1", fetchone=True)[0]

    def tienda(self):
        return execute_query("SELECT productos_ultimo_escaneo, ultimo_error FROM tiendas WHERE nombre = 'T'", fetchone=True)

    def test_caida_brusca_conserva_el_stock_y_avisa(self):
        self.escanear(40)
        self.escanear(5)
        self.assertEqual(self.activas(), 40)
        productos, error = self.tienda()
        self.assertEqual(productos, 40)  # la referencia sigue siendo el último escaneo aceptado
        self.assertIn("Trajo 5 productos (antes 40)", error)
        # Lo que sí vino se actualiza igual: el kit 0 tiene el precio nuevo
        self.assertEqual(execute_query("SELECT precio FROM publicacion_producto WHERE url = 'https://t.cl/0'", fetchone=True)[0], 19985.0)
        # Al volver a la normalidad se marca lo agotado y se borra el aviso
        self.escanear(38)
        self.assertEqual((self.activas(), self.tienda()), (38, (38, None)))

    def test_baja_normal_si_marca_agotados(self):
        self.escanear(40)
        self.escanear(25)
        self.assertEqual((self.activas(), self.tienda()), (25, (25, None)))

    def test_primer_escaneo_y_tiendas_chicas_no_se_comparan(self):
        self.escanear(9)
        self.escanear(2)
        self.assertEqual((self.activas(), self.tienda()), (2, (2, None)))

    def test_tras_una_semana_de_aviso_se_acepta_la_cantidad_nueva(self):
        self.escanear(40)
        hace_8_dias = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
        execute_query("UPDATE tiendas SET ultimo_exito = ? WHERE nombre = 'T'", (hace_8_dias,), commit=True)
        self.escanear(5)
        self.assertEqual((self.activas(), self.tienda()), (5, (5, None)))


if __name__ == "__main__":
    unittest.main()
