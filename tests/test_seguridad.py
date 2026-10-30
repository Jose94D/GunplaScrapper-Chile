"""Cabeceras de seguridad y plantillas compatibles con la CSP (sin scripts ni eventos en línea)."""
import glob
import importlib
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

import core.database

PLANTILLAS = os.path.join(os.path.dirname(__file__), "..", "templates")


class TestCabeceras(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.parche = mock.patch.object(core.database, "DB_NAME", self.db)
        self.parche.start()
        sys.modules.pop("app", None)
        self.app = importlib.import_module("app").app
        self.cliente = self.app.test_client()

    def tearDown(self):
        self.parche.stop()
        os.remove(self.db)

    def test_cada_respuesta_trae_las_cabeceras(self):
        for ruta in ("/", "/faq", "/admin", "/robots.txt"):
            h = self.cliente.get(ruta).headers
            self.assertIn("default-src 'self'", h["Content-Security-Policy"], ruta)
            self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"], ruta)
            self.assertNotIn("unsafe-inline", h["Content-Security-Policy"], ruta)
            self.assertEqual(h["X-Content-Type-Options"], "nosniff", ruta)
            self.assertEqual(h["Referrer-Policy"], "strict-origin-when-cross-origin", ruta)

    def test_paginas_de_error_propias(self):
        @self.app.route("/falla")  # antes de la primera petición: después Flask ya no acepta rutas nuevas
        def falla():
            raise RuntimeError("prueba")

        for ruta in ("/no-existe", "/producto/999-kit-inexistente"):
            r = self.cliente.get(ruta)
            self.assertEqual(r.status_code, 404, ruta)
            self.assertIn("Esta página no existe.", r.get_data(as_text=True), ruta)

        r = self.cliente.get("/falla")
        self.assertEqual(r.status_code, 500)
        html = r.get_data(as_text=True)
        self.assertIn("Algo falló de nuestro lado.", html)
        self.assertNotIn("RuntimeError", html)  # el detalle del error nunca llega al visitante


class TestPlantillasSinCodigoEnLinea(unittest.TestCase):
    """La CSP bloquearía estos casos: el script no correría y el botón dejaría de funcionar."""

    def test_sin_scripts_ni_eventos_en_linea(self):
        for ruta in glob.glob(os.path.join(PLANTILLAS, "**", "*.html"), recursive=True):
            with open(ruta, encoding="utf-8") as f:
                html = f.read()
            # Solo se permiten <script src=...> y los bloques de datos JSON, que el navegador no ejecuta
            for etiqueta in re.findall(r"<script\b[^>]*>", html):
                self.assertTrue("src=" in etiqueta or 'type="application/' in etiqueta, f"{ruta}: {etiqueta}")
            self.assertIsNone(re.search(r"\son[a-z]+\s*=", html), ruta)
            self.assertNotIn('style="', html, ruta)


if __name__ == "__main__":
    unittest.main()
