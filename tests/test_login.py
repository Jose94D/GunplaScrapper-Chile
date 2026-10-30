"""Login del administrador: bloqueo tras intentos fallidos y sesión nueva con vencimiento."""
import time
import unittest
from unittest import mock

from tests.test_regresiones import PanelTemporal


class TestLogin(PanelTemporal):
    def setUp(self):
        super().setUp()
        self.salir()

    def salir(self):
        """Sesión sin login, solo con el token CSRF (como al abrir /admin)."""
        with self.cliente.session_transaction() as s:
            s.clear()
            s["csrf_token"] = "token-de-prueba"

    def entrar(self, clave):
        return self.post("/admin", {"username": "admin", "password": clave})

    def test_cinco_fallos_bloquean_incluso_la_clave_correcta(self):
        for _ in range(5):
            self.assertEqual(self.entrar("mala").status_code, 200)
        respuesta = self.entrar("clave")
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Demasiados intentos", respuesta.get_data(as_text=True))
        with self.cliente.session_transaction() as s:
            self.assertNotIn("admin_logged", s)

    def test_el_bloqueo_vence_a_los_15_minutos(self):
        for _ in range(5):
            self.entrar("mala")
        ahora = time.time()
        with mock.patch("routes.admin.admin_login.time.time", return_value=ahora + 15 * 60):
            self.assertEqual(self.entrar("clave").status_code, 302)

    def test_un_acierto_reinicia_el_contador(self):
        for _ in range(4):
            self.entrar("mala")
        self.assertEqual(self.entrar("clave").status_code, 302)
        self.salir()
        for _ in range(4):
            self.entrar("mala")
        self.assertEqual(self.entrar("clave").status_code, 302)

    def test_al_entrar_la_sesion_es_nueva_y_vence(self):
        with self.cliente.session_transaction() as s:
            s["dato_previo"] = "x"
        self.entrar("clave")
        with self.cliente.session_transaction() as s:
            self.assertTrue(s["admin_logged"])
            self.assertTrue(s.permanent)
            self.assertNotIn("dato_previo", s)

    def test_cerrar_sesion_solo_por_post_con_token(self):
        with self.cliente.session_transaction() as s:
            s["admin_logged"] = True
        self.assertEqual(self.cliente.get("/admin/logout").status_code, 405)  # un enlace de otro sitio ya no la cierra
        self.assertEqual(self.cliente.post("/admin/logout").status_code, 400)  # sin token CSRF
        with self.cliente.session_transaction() as s:
            self.assertTrue(s["admin_logged"])
        self.assertEqual(self.post("/admin/logout").status_code, 302)
        with self.cliente.session_transaction() as s:
            self.assertEqual(dict(s), {})
        # El panel muestra el botón dentro de un formulario con el token
        with self.cliente.session_transaction() as s:
            s["admin_logged"], s["csrf_token"] = True, "token-de-prueba"
        html = self.cliente.get("/admin/panel").get_data(as_text=True)
        formulario = html[html.index('action="/admin/logout"'):][:300]
        self.assertIn('name="csrf_token"', formulario)
        self.assertIn("Cerrar sesión", formulario)


if __name__ == "__main__":
    unittest.main()
