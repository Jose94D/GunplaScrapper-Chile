"""URLs con nombre, metadatos para compartir, sitemap.xml y robots.txt."""
import importlib
import os
import sys
import tempfile
import unittest
from unittest import mock

import core.database
from core.catalogo import slug
from core.database import execute_query


class TestSlug(unittest.TestCase):
    def test_convierte_nombres(self):
        casos = {"GFRED HG": "gfred-hg", "HYAKU-SHIKI VER 2 0 MG": "hyaku-shiki-ver-2-0-mg",
                 "Ñu Gúndam  (Ver.Ka)": "nu-gundam-ver-ka", "": "producto", "!!!": "producto"}
        for nombre, esperado in casos.items():
            self.assertEqual(slug(nombre), esperado, nombre)


class TestSeo(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.parche = mock.patch.object(core.database, "DB_NAME", self.db)
        self.parche.start()
        sys.modules.pop("app", None)
        self.app = importlib.import_module("app").app
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A')", commit=True)
        execute_query("""INSERT INTO productos (id, nombre_estandar, grado, imagen_producto, es_visible, disponible) VALUES
                         (45, 'GFRED HG', 'HG', 'productos/45.webp', 1, 1), (46, 'OCULTO HG', 'HG', NULL, 0, 1)""", commit=True)
        execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio, es_url_activa) VALUES (1, 45, 1, 'u', 27990, 1)", commit=True)
        execute_query("INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (1, 27990, '2026-10-28 12:00:00')", commit=True)
        self.cliente = self.app.test_client()

    def tearDown(self):
        self.parche.stop()
        os.remove(self.db)

    def test_url_sin_nombre_redirige_conservando_filtros(self):
        for ruta in ("/producto/45", "/producto/45-nombre-viejo"):
            r = self.cliente.get(ruta, query_string={"q": "gfred", "page": 2})
            self.assertEqual(r.status_code, 301, ruta)
            self.assertTrue(r.location.startswith("/producto/45-gfred-hg?"), r.location)
            self.assertIn("q=gfred", r.location)
        self.assertEqual(self.cliente.get("/producto/45-gfred-hg").status_code, 200)
        self.assertEqual(self.cliente.get("/producto/999").status_code, 404)

    def test_metadatos_para_compartir(self):
        html = self.cliente.get("/producto/45-gfred-hg").get_data(as_text=True)
        self.assertIn('<meta property="og:image" content="http://localhost/static/productos/45.webp">', html)
        self.assertIn('content="GFRED HG · desde $27.990"', html)
        self.assertIn('<link rel="canonical" href="http://localhost/producto/45-gfred-hg">', html)
        self.assertIn('summary_large_image', html)
        self.assertEqual(html.count('property="og:title"'), 1)  # el bloque reemplaza al general, no lo duplica

    def test_el_inicio_enlaza_a_la_url_con_nombre(self):
        self.assertIn('/producto/45-gfred-hg?', self.cliente.get("/").get_data(as_text=True))

    def test_sitemap_y_robots(self):
        r = self.cliente.get("/sitemap.xml")
        self.assertEqual(r.mimetype, "application/xml")
        xml = r.get_data(as_text=True)
        self.assertIn("<loc>http://localhost/producto/45-gfred-hg</loc>", xml)
        self.assertNotIn("oculto", xml)  # solo productos que se ven en el inicio
        self.assertIn("<loc>http://localhost/faq</loc>", xml)
        robots = self.cliente.get("/robots.txt").get_data(as_text=True)
        self.assertIn("Disallow: /admin", robots)
        self.assertIn("Sitemap: http://localhost/sitemap.xml", robots)


if __name__ == "__main__":
    unittest.main()
