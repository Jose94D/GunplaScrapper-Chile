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
SCRAPERS = {"hangar": "HangarScraper", "blaster": "BlasterScraper", "chilerobots": "ChileRobotsScraper", "irion": "IrionScraper",
            "geekz": "GeekzScraper", "weplay": "WeplayScraper", "luffytoys": "LuffyToysScraper", "hobbytoys": "HobbyToysScraper"}


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


if __name__ == "__main__":
    unittest.main()
