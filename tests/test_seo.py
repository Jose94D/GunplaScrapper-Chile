"""URLs con nombre, metadatos para compartir, sitemap.xml y robots.txt."""
import importlib
import os
import sys
import tempfile
import unittest
from unittest import mock

import core.database
from core.catalogo import formatear_fecha, slug
from core.database import execute_query


class TestSlug(unittest.TestCase):
    def test_convierte_nombres(self):
        casos = {"GFRED HG": "gfred-hg", "HYAKU-SHIKI VER 2 0 MG": "hyaku-shiki-ver-2-0-mg",
                 "Ñu Gúndam  (Ver.Ka)": "nu-gundam-ver-ka", "": "producto", "!!!": "producto"}
        for nombre, esperado in casos.items():
            self.assertEqual(slug(nombre), esperado, nombre)


class TestFormatearFecha(unittest.TestCase):
    def test_hora_dia_mes_anio(self):
        casos = {"2026-10-28 12:05:09": "12:05 28/10/2026", "2026-10-28": "28/10/2026",
                 "Nunca": "Nunca", "N/A": "N/A", None: None}
        for valor, esperado in casos.items():
            self.assertEqual(formatear_fecha(valor), esperado, valor)


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

    def test_resumen_de_precios_de_la_ficha(self):
        from core.catalogo import detalle_producto
        # Con un solo precio registrado no hay "mínimo histórico" (los precios planos no se marcan)
        self.assertFalse(detalle_producto(45)["minimo_historico"])
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (2, 'B')", commit=True)
        execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio, es_url_activa) VALUES (2, 45, 2, 'v', 25000, 1)", commit=True)
        execute_query("""INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES
                         (2, 30000, '2026-10-20 12:00:00'), (2, 25000, '2026-10-28 12:00:00')""", commit=True)
        d = detalle_producto(45)
        self.assertEqual((d["mejor_precio"], d["mejor_tienda"], d["ahorro"], d["ahorro_pct"]), ("$25.000", "B", "$2.990", 11))
        self.assertTrue(d["minimo_historico"])
        self.assertEqual([(t["nombre"], t["es_mejor"], t["diferencia"]) for t in d["tiendas"]], [("B", True, None), ("A", False, "+$2.990")])
        self.assertEqual((d["tiendas_con_stock"], d["tiendas_total"], d["seguimiento_desde"]), (2, 2, "20/10/2026"))

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
        # ?v=<fecha> solo si la imagen existe en disco (en GitHub Actions no está)
        self.assertRegex(html, r'<meta property="og:image" content="http://localhost/static/productos/45\.webp(\?v=\d+)?">')
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

    def test_privacidad_sin_terceros_y_cookie_protegida(self):
        for ruta in ("/", "/producto/45-gfred-hg", "/politicas"):
            html = self.cliente.get(ruta).get_data(as_text=True)
            for externo in ("googleapis", "gstatic", "jsdelivr"):
                self.assertNotIn(externo, html, ruta)
        cookie = self.app.test_client().get("/").headers["Set-Cookie"]  # cliente nuevo: el anterior ya tiene la cookie
        self.assertIn("visita_contada=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


if __name__ == "__main__":
    unittest.main()
