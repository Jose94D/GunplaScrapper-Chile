"""Pruebas de regresión. Correr desde la raíz del proyecto: python -m unittest discover tests"""
import os
import tempfile
import unittest
from unittest import mock

from flask import Flask

import core.database
from core.database import init_db, execute_query
from core.catalog_manager import CatalogManager


class BaseTemporal(unittest.TestCase):
    """Cada prueba usa una base SQLite vacía, nunca precios_comunidad.db."""

    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.parche = mock.patch.object(core.database, "DB_NAME", self.db)
        self.parche.start()
        init_db()

    def tearDown(self):
        self.parche.stop()
        os.remove(self.db)


class TestNormalizacion(unittest.TestCase):
    def test_turn_a_en_cualquier_orden(self):
        c = CatalogManager()
        for nombre in ["Gundam Turn A HG", "Turn A Gundam HG", "HG 1/144 Gundam Turn A - Bandai"]:
            self.assertEqual(c.normalizar_nombre(nombre), ("TURN A GUNDAM HG", "HG"), nombre)

    def test_astray_turn_red_no_se_toca(self):
        nombre, _ = CatalogManager().normalizar_nombre("MG Gundam Astray Turn Red")
        self.assertEqual(nombre, "GUNDAM ASTRAY TURN RED MG")


class TestProductoManual(BaseTemporal):
    def setUp(self):
        super().setUp()
        from routes.admin.admin import crear_blueprint_admin
        app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
        app.secret_key = "pruebas"
        app.register_blueprint(crear_blueprint_admin(None))
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as s:
            s["admin_logged"] = True

    def crear(self, nombre, url=""):
        return self.cliente.post("/admin/producto/nuevo", data={"producto": nombre, "grado": "HG", "precio": "19.990", "url": url})

    def test_varios_sin_url_y_una_sola_tienda_manual(self):
        for nombre in ["KIT A HG", "KIT B HG"]:
            self.assertEqual(self.crear(nombre).status_code, 302)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 2)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE url IS NULL", fetchone=True)[0], 2)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM tiendas WHERE nombre = 'Manual'", fetchone=True)[0], 1)

    def test_url_repetida_no_crea_producto_huerfano(self):
        self.crear("KIT A HG", "https://tienda.cl/kit")
        self.assertEqual(self.crear("KIT B HG", "https://tienda.cl/kit").status_code, 302)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 1)


def respuesta(estado, html=""):
    r = mock.Mock(status_code=estado, text=html)
    r.raise_for_status.side_effect = None if estado < 400 else Exception(f"HTTP {estado}")
    return r


PAGINA_HANGAR = '<div class="product-container"><a class="product-name" href="https://www.hangar019.cl/kit-{n}">Kit {n} HG</a><span class="product-price">$19.990</span></div>'


class TestFalloAMitadDePaginacion(BaseTemporal):
    def correr(self, respuestas):
        from scrapers.hangar import HangarScraper
        from core.scraper_manager import ScraperManager
        mgr = ScraperManager()
        mgr.scrapers = {"Hangar019": (HangarScraper(), "https://www.hangar019.cl")}
        with mock.patch("scrapers.hangar.requests.get", side_effect=respuestas), mock.patch("scrapers.hangar.time.sleep"):
            mgr.ejecutar_todos()

    def activas(self):
        return execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE es_url_activa = 1", fetchone=True)[0]

    def test_error_en_pagina_2_no_marca_agotados(self):
        # Corrida completa: 2 páginas con un producto cada una
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1)), respuesta(200, PAGINA_HANGAR.format(n=2)), respuesta(200)])
        self.assertEqual(self.activas(), 2)
        # Corrida que falla en la página 2: antes dejaba el kit 2 como agotado
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1)), respuesta(503)])
        self.assertEqual(self.activas(), 2)

    def test_404_despues_de_la_primera_pagina_es_fin_del_catalogo(self):
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1)), respuesta(404)])
        self.assertEqual(self.activas(), 1)


if __name__ == "__main__":
    unittest.main()
