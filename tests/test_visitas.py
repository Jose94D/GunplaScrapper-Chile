"""Conteo de visitas (POST /visita) y serie del gráfico del panel."""
import importlib
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

import core.database
from core import visitas
from core.database import execute_query

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0"}


class TestVisitas(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.parche = mock.patch.object(core.database, "DB_NAME", self.db)
        self.parche.start()
        sys.modules.pop("app", None)
        self.app = importlib.import_module("app").app

    def tearDown(self):
        self.parche.stop()
        os.remove(self.db)

    def filas(self):
        return execute_query("SELECT visitante, paginas FROM visitas_diarias", fetchall=True)

    def test_una_visita_por_persona_y_dia_con_sus_paginas(self):
        cliente = self.app.test_client()
        for _ in range(3):
            self.assertEqual(cliente.post("/visita", headers=NAVEGADOR).status_code, 204)  # sin token CSRF
        self.app.test_client().post("/visita", headers=NAVEGADOR)  # otra persona
        self.assertEqual(sorted(p for _, p in self.filas()), [1, 3])

    def test_no_cuenta_bots_ni_al_administrador(self):
        for ua in ("", "Mozilla/5.0 (compatible; Googlebot/2.1)", "python-requests/2.32", "curl/8.0"):
            self.app.test_client().post("/visita", headers={"User-Agent": ua})
        admin = self.app.test_client()
        with admin.session_transaction() as s:
            s["admin_logged"] = True
        admin.post("/visita", headers=NAVEGADOR)
        self.assertEqual(self.filas(), [])

    def test_cookie_invalida_se_reemplaza(self):
        cliente = self.app.test_client()
        cliente.set_cookie("visitante", "<script>")
        cliente.post("/visita", headers=NAVEGADOR)
        self.assertRegex(self.filas()[0][0], visitas.VISITANTE_VALIDO)

    def test_serie_rellena_dias_y_cuenta_personas_distintas(self):
        hoy = date.today()
        visitas.registrar_visita("a" * 22, (hoy - timedelta(days=10)).isoformat())
        visitas.registrar_visita("a" * 22, hoy.isoformat())
        visitas.registrar_visita("b" * 22, hoy.isoformat())
        visitas.registrar_visita("b" * 22, hoy.isoformat())
        serie = visitas.serie_diaria()
        self.assertEqual(serie["visitas"], [1] + [0] * 9 + [2])
        self.assertEqual(serie["paginas"], [1] + [0] * 9 + [3])
        self.assertEqual(serie["totales"][0], {"visitas": 3, "personas": 2, "paginas": 4})
        self.assertEqual(serie["totales"][7], {"visitas": 2, "personas": 2, "paginas": 3})


class TestVistazo(unittest.TestCase):
    def test_semana_contra_la_anterior(self):
        v = visitas.vistazo({"visitas": [1] * 7 + [2] * 6 + [5]})
        self.assertEqual((v["hoy"], v["semana"], v["cambio"]), (5, 17, 143))  # 7 → 17
        self.assertEqual(len(v["puntos"].split()), 14)
        self.assertTrue(v["puntos"].endswith("100.0,2.0"))  # el máximo queda arriba

    def test_sin_historial_previo_no_compara(self):
        v = visitas.vistazo({"visitas": [0, 3]})
        self.assertEqual((v["hoy"], v["semana"], v["cambio"]), (3, 3, None))


if __name__ == "__main__":
    unittest.main()
