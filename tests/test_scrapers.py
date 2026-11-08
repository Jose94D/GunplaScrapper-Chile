"""Cada scraper sobre una página real de su tienda (tests/paginas/, recortada a los primeros productos), sin conexión.

esperados.json tiene lo que cada scraper obtuvo de la página completa el día que se guardó (30/10/2026).
Si un scraper deja de leer bien su tienda (en el panel, "Revisar"), se arregla el scraper y se reemplazan su página y
su entrada en esperados.json por las de la tienda actual.
"""
import importlib
import json
import os
import unittest
from unittest import mock

PAGINAS = os.path.join(os.path.dirname(__file__), "paginas")
# Irion y LuffyToys leen el catálogo por UCP, no HTML: sus pruebas están en TestUcp
SCRAPERS = {"hangar": "HangarScraper", "blaster": "BlasterScraper", "chilerobots": "ChileRobotsScraper",
            "geekz": "GeekzScraper", "weplay": "WeplayScraper", "hobbytoys": "HobbyToysScraper"}


class Respuesta:
    def __init__(self, texto):
        self.status_code, self.text, self.headers = 200, texto, {}

    def raise_for_status(self):
        pass


class TestScrapers(unittest.TestCase):
    def extraer(self, tienda):
        """Corre el scraper con la página guardada como página 1 y una vacía como página 2. Retorna (productos, URLs pedidas)."""
        modulo = importlib.import_module(f"scrapers.{tienda}")
        with open(os.path.join(PAGINAS, f"{tienda}.html"), encoding="utf-8") as f:
            paginas = [f.read(), "<html><body></body></html>"]
        pedidas = []

        def pedir(url, *args, **kwargs):
            pedidas.append(url)
            return Respuesta(paginas.pop(0))

        with mock.patch.object(modulo, "pedir", pedir), mock.patch.object(modulo.time, "sleep"), \
                mock.patch("core.logger.execute_query"):
            scraper = getattr(modulo, SCRAPERS[tienda])()
            if hasattr(scraper, "session"):
                scraper.session = mock.Mock()  # Blaster visita la portada antes: sin red en las pruebas
            return scraper.extraer_datos(), pedidas

    def test_cada_tienda(self):
        with open(os.path.join(PAGINAS, "esperados.json"), encoding="utf-8") as f:
            esperados = json.load(f)
        for tienda in SCRAPERS:
            with self.subTest(tienda=tienda):
                productos, pedidas = self.extraer(tienda)
                self.assertEqual(productos, esperados[tienda])
                # Una página sin productos es el fin del catálogo: pide la 2 y se detiene
                self.assertEqual(len(pedidas), 2)
                for p in productos:
                    self.assertTrue(p["nombre_original"].strip())
                    self.assertGreater(p["precio"], 0)
                    self.assertTrue(p["url"].startswith("https://"))
                    self.assertTrue(p["imagen"] and p["imagen"].startswith("https://"))

    def test_pagina_repetida_solo_con_descartados_termina(self):
        """Odoo y Magento repiten la última página al pasarse del final: sin esto, el escaneo no termina nunca."""
        import scrapers.geekz as geekz, scrapers.weplay as weplay
        agotado_geekz = """<form class="oe_product_cart"><h6 itemprop="name" content="AGOTADO"></h6>
            <a itemprop="url" href="/shop/agotado"></a><span itemprop="price">1000</span></form>"""
        solo_tienda = """<div class="product-item-info"><div class="product-label unavailable"></div>
            <a class="product-item-link" href="https://weplay.cl/kit">Kit</a></div>"""
        for modulo, clase, tarjeta in ((geekz, "GeekzScraper", agotado_geekz), (weplay, "WeplayScraper", solo_tienda)):
            with self.subTest(clase):
                pedidas = []

                def pedir(url, *a, **k):
                    pedidas.append(url)
                    self.assertLess(len(pedidas), 5, "no detectó la página repetida")
                    return Respuesta(f"<html><body><ol>{tarjeta}</ol></body></html>")

                with mock.patch.object(modulo, "pedir", pedir), mock.patch.object(modulo.time, "sleep"), mock.patch("core.logger.execute_query"):
                    self.assertEqual(getattr(modulo, clase)().extraer_datos(), [])
                self.assertEqual(len(pedidas), 2)

    def test_hobbytoys_descarta_agotados(self):
        import scrapers.hobbytoys as modulo

        def tarjeta(clase, nombre):
            return f"""<article class="wpr-grid-item product {clase}"><div class="wpr-grid-item-inner">
                <h2 class="wpr-grid-item-title"><a href="https://www.hobbytoys.cl/producto/{nombre}/">{nombre}</a></h2>
                <div class="wpr-grid-item-price"><span class="amount">$10.000</span></div></div></article>"""

        agotada = tarjeta("outofstock", "agotado")
        # La tienda repite su última página, que solo tiene agotados: también debe cortar ahí
        paginas = [tarjeta("instock", "con-stock") + agotada, agotada, agotada]
        with mock.patch.object(modulo, "pedir", lambda *a, **k: Respuesta(paginas.pop(0))), mock.patch.object(modulo.time, "sleep"):
            productos = modulo.HobbyToysScraper().extraer_datos()
        self.assertEqual([p["nombre_original"] for p in productos], ["con-stock"])
        self.assertEqual(len(paginas), 1)


class RespuestaUcp:
    def __init__(self, cuerpo, status=200):
        self.status_code, self.cuerpo = status, cuerpo

    def json(self):
        return self.cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def producto_ucp(titulo, handle, tags, disponible=True, precio=19990):
    return {"title": titulo, "handle": handle, "url": f"https://tienda.cl/products/{handle}?_pos=1", "tags": tags,
            "price_range": {"min": {"amount": precio, "currency": "CLP"}}, "media": [{"url": f"https://cdn.shopify.com/{handle}.jpg"}],
            "variants": [{"availability": {"available": disponible}}]}


def pagina_ucp(productos, cursor=None):
    return {"result": {"structuredContent": {"products": productos, "pagination": {"has_next_page": bool(cursor), "cursor": cursor}}}}


class TestUcp(unittest.TestCase):
    """Irion y LuffyToys (Shopify) leen el catálogo por UCP: core/ucp.py y sus filtros."""

    def correr(self, modulo, clase, paginas):
        import core.ucp
        pedidas = []

        def pedir(url, json=None, **k):
            pedidas.append(json["params"]["arguments"])
            return paginas.pop(0)

        with mock.patch.object(core.ucp, "pedir", pedir), mock.patch.object(core.ucp.time, "sleep"), mock.patch("core.logger.execute_query"):
            return getattr(importlib.import_module(f"scrapers.{modulo}"), clase)().extraer_datos(), pedidas

    def test_irion_kits_bandai_con_stock_en_todas_las_paginas(self):
        paginas = [RespuestaUcp(pagina_ucp([producto_ucp("BANDAI HG ZAKU II", "zaku", ["BANDAI", "GUNDAM"]),
                                            producto_ucp("BANDAI MG F91", "f91", ["BANDAI", "GUNDAM"], disponible=False),
                                            producto_ucp("PINTURA GUNDAM MARKER", "marker", ["GUNDAM"])], cursor="c2")),
                   RespuestaUcp(pagina_ucp([producto_ucp("BANDAI SD CROSS SILHOUETTE", "sd", ["GUNDAM", "Remate"], precio=7990)]))]
        productos, pedidas = self.correr("irion", "IrionScraper", paginas)
        self.assertEqual([(p["nombre_original"], p["precio"], p["url"]) for p in productos],
                         [("BANDAI HG ZAKU II", 19990.0, "https://tienda.cl/products/zaku"),
                          ("BANDAI SD CROSS SILHOUETTE", 7990.0, "https://tienda.cl/products/sd")])
        self.assertEqual(productos[0]["imagen"], "https://cdn.shopify.com/zaku.jpg")
        self.assertEqual(pedidas[1]["catalog"]["pagination"]["cursor"], "c2")
        self.assertTrue(pedidas[0]["meta"]["ucp-agent"]["profile"].endswith("/static/ucp-agente.json?v=2"))

    def test_luffytoys_solo_maquetas_y_url_de_su_coleccion(self):
        paginas = [RespuestaUcp(pagina_ucp([producto_ucp("Gundam HG Jagd Doga Model Kit", "jagd-doga", ["Gundam", "Maqueta Armable", "Bandai"]),
                                            producto_ucp("RX-78-2 Gundam Universe", "rx-78-2", ["Gundam", "Figuras Articuladas"])]))]
        productos, _ = self.correr("luffytoys", "LuffyToysScraper", paginas)
        self.assertEqual([p["url"] for p in productos], ["https://luffytoys.cl/collections/maqueta-armables/products/jagd-doga"])

    def test_un_error_de_shopify_detiene_el_scraper(self):
        error = {"error": {"code": -32001, "message": "UCP discovery failed", "data": {"content": "Missing payment handlers"}}}
        with self.assertRaisesRegex(RuntimeError, "Missing payment handlers"):
            self.correr("irion", "IrionScraper", [RespuestaUcp(error, status=422)])

    def test_una_paginacion_que_no_termina_no_deja_el_escaneo_pegado(self):
        import core.ucp
        repetida = [RespuestaUcp(pagina_ucp([], cursor=f"c{i}")) for i in range(core.ucp.MAX_PAGINAS)]
        with self.assertRaisesRegex(RuntimeError, "más de"):
            self.correr("luffytoys", "LuffyToysScraper", repetida)
        # El mismo cursor dos veces también corta (sin error: ya no hay páginas nuevas)
        productos, pedidas = self.correr("luffytoys", "LuffyToysScraper", [RespuestaUcp(pagina_ucp([], cursor="x")), RespuestaUcp(pagina_ucp([], cursor="x"))])
        self.assertEqual((productos, len(pedidas)), ([], 2))


if __name__ == "__main__":
    unittest.main()
