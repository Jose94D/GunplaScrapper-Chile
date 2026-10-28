"""Pruebas de regresión. Correr desde la raíz del proyecto: python -m unittest discover tests"""
import os
import threading
import time
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


class TestLimpiarPrecio(unittest.TestCase):
    def test_formatos_de_tiendas_y_panel(self):
        from core.precios import limpiar_precio
        casos = {"$19.990": 19990.0, "$ 19.990 CLP": 19990.0, "19,990": 19990.0, "\n  $34.990\n": 34990.0,
                 "19990": 19990.0, 19990: 19990.0, 19990.0: 19990.0, "": 0.0, None: 0.0, "Agotado": 0.0}
        for entrada, esperado in casos.items():
            self.assertEqual(limpiar_precio(entrada), esperado, repr(entrada))


class TestNormalizacion(unittest.TestCase):
    def test_turn_a_en_cualquier_orden(self):
        c = CatalogManager()
        for nombre in ["Gundam Turn A HG", "Turn A Gundam HG", "HG 1/144 Gundam Turn A - Bandai"]:
            self.assertEqual(c.normalizar_nombre(nombre), ("TURN A GUNDAM HG", "HG"), nombre)

    def test_astray_turn_red_no_se_toca(self):
        nombre, _ = CatalogManager().normalizar_nombre("MG Gundam Astray Turn Red")
        self.assertEqual(nombre, "GUNDAM ASTRAY TURN RED MG")


class PanelTemporal(BaseTemporal):
    """Blueprint del panel con sesión de administrador iniciada, sobre la base temporal."""

    def setUp(self):
        super().setUp()
        from routes.admin.admin import crear_blueprint_admin
        from routes.admin.admin_login import crear_blueprint_admin_login
        app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"))
        app.secret_key = "pruebas"
        app.register_blueprint(crear_blueprint_admin(getattr(self, "manager", None)))
        app.register_blueprint(crear_blueprint_admin_login("admin", "clave"))
        from routes.public.views_institucional import crear_blueprint_institucional
        from routes.public.views_inicio import crear_blueprint_inicio
        app.register_blueprint(crear_blueprint_institucional())  # el footer enlaza a estas páginas
        app.register_blueprint(crear_blueprint_inicio())  # y el menú y el panel, al catálogo
        from core.seguridad import proteger_csrf
        proteger_csrf(app)
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as s:
            s["admin_logged"] = True
            s["csrf_token"] = "token-de-prueba"

    def post(self, ruta, data=None, **kwargs):
        """POST como lo envía el panel: con el token CSRF de la sesión."""
        return self.cliente.post(ruta, data={"csrf_token": "token-de-prueba", **(data or {})}, **kwargs)


class TestFusion(PanelTemporal):
    def setUp(self):
        super().setUp()
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A'), (2, 'B')", commit=True)
        execute_query("INSERT INTO productos (id, nombre_estandar) VALUES (1, 'KYRIOS GUNDAM HG'), (2, 'GUNDAM KYRIOS HG')", commit=True)
        execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio) VALUES (1, 1, 1, 'a', 1), (2, 2, 2, 'b', 2)", commit=True)
        execute_query("INSERT INTO historial_precios (publicacion_producto_id, precio) VALUES (2, 2)", commit=True)

    def fusionar(self, principal, duplicado):
        return self.post("/admin/fusionar", {"id_principal": principal, "id_duplicado": duplicado})

    def test_mueve_publicaciones_e_historial_y_borra_el_duplicado(self):
        self.assertEqual(self.fusionar("1", "2").status_code, 302)
        self.assertEqual(execute_query("SELECT id FROM productos", fetchall=True), [(1,)])
        self.assertEqual(execute_query("SELECT producto_id FROM publicacion_producto ORDER BY id", fetchall=True), [(1,), (1,)])
        self.assertEqual(execute_query("SELECT COUNT(*) FROM historial_precios", fetchone=True)[0], 1)

    def test_ids_iguales_no_hace_nada(self):
        self.fusionar("1", "1")
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 2)

    def test_sin_sesion_no_fusiona(self):
        with self.cliente.session_transaction() as s:
            s.pop("admin_logged")  # el token CSRF sigue: se prueba solo el login
        respuesta = self.fusionar("1", "2")
        self.assertEqual((respuesta.status_code, respuesta.location), (302, "/admin"))
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 2)


class TestSeguridadPanel(PanelTemporal):
    def setUp(self):
        super().setUp()
        execute_query("INSERT INTO productos (id, nombre_estandar, es_visible) VALUES (1, 'KIT HG', 1)", commit=True)

    def visible(self):
        return execute_query("SELECT es_visible FROM productos WHERE id = 1", fetchone=True)[0]

    def test_post_sin_token_o_con_token_ajeno_se_rechaza(self):
        for data in ({}, {"csrf_token": "otro"}):
            self.assertEqual(self.cliente.post("/admin/producto/toggle/1", data=data).status_code, 400)
        self.assertEqual(self.visible(), 1)

    def test_acciones_que_modifican_no_aceptan_get(self):
        for ruta in ["/admin/producto/toggle/1", "/admin/producto/eliminar/1", "/admin/carrusel/eliminar/1", "/admin/force-update"]:
            self.assertEqual(self.cliente.get(ruta).status_code, 405, ruta)
        self.assertEqual(self.visible(), 1)

    def test_toggle_por_post_con_token(self):
        self.assertEqual(self.post("/admin/producto/toggle/1").status_code, 302)
        self.assertEqual(self.visible(), 0)

    def test_carrusel_solo_acepta_imagenes(self):
        import io
        carpeta = tempfile.mkdtemp()
        with mock.patch("core.carrusel.CARRUSEL_FOLDER", carpeta):
            for nombre in ["ataque.html", "logo.svg", "banner.png"]:
                self.post("/admin/carrusel/nuevo", {"imagen": (io.BytesIO(b"x"), nombre)}, content_type="multipart/form-data")
        self.assertEqual(os.listdir(carpeta), ["banner.png"])
        self.assertEqual(execute_query("SELECT nombre_archivo FROM banners", fetchall=True), [("banner.png",)])


class TestDuplicados(PanelTemporal):
    def setUp(self):
        super().setUp()
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A'), (2, 'B')", commit=True)
        nombres = [(1, "F91 GUNDAM HG", "HG"), (2, "GUNDAM F91 HG", "HG"),
                   (3, "NARRATIVE GUNDAM A-PACKS HG", "HG"), (4, "NARRATIVE GUNDAM C-PACKS HG", "HG"),
                   (5, "GUNDAM AGE-2 NORMAL HG", "HG"), (6, "GUNDAM AGE-3 NORMAL HG", "HG"),
                   (7, "GUNDAM X HG", "HG"), (8, "ZZ GUNDAM HG", "HG"),
                   (9, "ZAKU II HG", "HG"), (10, "ZAKU II MG", "MG"),
                   (11, "GERBERA TETRA HG", "HG"), (12, "GERBERA-TETRA HG", "HG")]
        for n in nombres:
            execute_query("INSERT INTO productos (id, nombre_estandar, grado) VALUES (?, ?, ?)", n, commit=True)
        # El 2 está en dos tiendas: es el que conviene conservar frente al 1
        for pub, prod, tienda in [(1, 1, 1), (2, 2, 1), (3, 2, 2)]:
            execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio) VALUES (?, ?, ?, ?, 1)", (pub, prod, tienda, f"u{pub}"), commit=True)

    def pares(self):
        from core.duplicados import sugerir_duplicados
        return [(d["principal"]["id"], d["duplicado"]["id"]) for d in sugerir_duplicados()]

    def test_sugiere_solo_los_mismos_kits(self):
        self.assertEqual(sorted(self.pares()), [(2, 1), (11, 12)])

    def test_descartar_no_vuelve_a_sugerir(self):
        respuesta = self.post("/admin/duplicados/descartar", {"id_a": "12", "id_b": "11"})
        self.assertTrue(respuesta.location.endswith("#seccion-duplicados"))
        self.assertEqual(self.pares(), [(2, 1)])

    def test_fusionar_desde_sugerencias(self):
        respuesta = self.post("/admin/fusionar", {"id_principal": "2", "id_duplicado": "1", "desde": "duplicados"})
        self.assertTrue(respuesta.location.endswith("#seccion-duplicados"))
        self.assertEqual(self.pares(), [(11, 12)])
        self.assertEqual(execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE producto_id = 2", fetchone=True)[0], 3)

    def test_el_panel_muestra_la_seccion(self):
        html = self.cliente.get("/admin/panel").get_data(as_text=True)
        self.assertIn("Posibles Duplicados", html)
        self.assertIn("GERBERA-TETRA HG", html)


class TestProductoManual(PanelTemporal):

    def crear(self, nombre, url=""):
        return self.post("/admin/producto/nuevo", {"producto": nombre, "grado": "HG", "precio": "19.990", "url": url})

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


def respuesta(estado, html="", headers=None):
    r = mock.Mock(status_code=estado, text=html, headers=headers or {})
    r.raise_for_status.side_effect = None if estado < 400 else Exception(f"HTTP {estado}")
    return r


class TestCatalogoTransaccion(BaseTemporal):
    def test_si_falla_a_mitad_no_queda_nada_a_medias(self):
        from core.catalog_manager import CatalogManager
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A')", commit=True)
        for pub, nombre in [(1, "HG Zaku II"), (2, "Pokemon Pikachu"), (3, "HG Gouf")]:
            execute_query("INSERT INTO publicacion_producto (id, tienda_id, nombre_original, url, precio) VALUES (?, 1, ?, ?, 1)", (pub, nombre, f"u{pub}"), commit=True)
        cm = CatalogManager()
        original = cm.normalizar_nombre
        cm.normalizar_nombre = lambda n: (_ for _ in ()).throw(RuntimeError("falla")) if "Gouf" in n else original(n)
        with self.assertRaises(RuntimeError):
            cm.procesar_pendientes()
        # Nada aplicado: ni el Zaku vinculado, ni el Pokémon borrado, ni productos creados
        self.assertEqual(execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE producto_id IS NULL", fetchone=True)[0], 3)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 0)
        # Sin la falla, se procesa todo
        CatalogManager().procesar_pendientes()
        self.assertEqual(execute_query("SELECT COUNT(*) FROM publicacion_producto", fetchone=True)[0], 2)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM productos", fetchone=True)[0], 2)


class TestReintentos(unittest.TestCase):
    """core.peticiones.pedir: reintenta lo pasajero (429, 5xx, cortes) y no lo definitivo (404)."""

    def pedir(self, respuestas, **kwargs):
        from core.peticiones import pedir
        with mock.patch("core.peticiones.requests.get", side_effect=respuestas) as get, \
                mock.patch("core.peticiones.time.sleep") as dormir:
            try:
                resultado = pedir("https://tienda.cl", **kwargs)
            except Exception as e:
                resultado = e
        return resultado, get.call_count, [c.args[0] for c in dormir.call_args_list]

    def test_429_y_luego_bien(self):
        r, llamadas, esperas = self.pedir([respuesta(429), respuesta(200)])
        self.assertEqual((r.status_code, llamadas, esperas), (200, 2, [5]))

    def test_respeta_retry_after_con_maximo(self):
        _, _, esperas = self.pedir([respuesta(429, headers={"Retry-After": "20"}), respuesta(429, headers={"Retry-After": "600"}), respuesta(200)])
        self.assertEqual(esperas, [20, 60])

    def test_corte_de_conexion_se_reintenta(self):
        import requests
        r, llamadas, esperas = self.pedir([requests.ConnectionError("corte"), respuesta(200)])
        self.assertEqual((r.status_code, llamadas, esperas), (200, 2, [5]))

    def test_si_sigue_fallando_entrega_el_error(self):
        import requests
        r, llamadas, esperas = self.pedir([respuesta(503)] * 3)
        self.assertEqual((r.status_code, llamadas, esperas), (503, 3, [5, 10]))
        r, llamadas, _ = self.pedir([requests.ConnectionError("corte")] * 3)
        self.assertEqual((type(r), llamadas), (requests.ConnectionError, 3))

    def test_404_no_se_reintenta(self):
        r, llamadas, esperas = self.pedir([respuesta(404)])
        self.assertEqual((r.status_code, llamadas, esperas), (404, 1, []))

    def test_blaster_usa_su_sesion_y_su_espera(self):
        from core.peticiones import pedir
        sesion = mock.Mock()
        sesion.get.side_effect = [respuesta(429), respuesta(200)]
        with mock.patch("core.peticiones.time.sleep") as dormir:
            self.assertEqual(pedir("https://b.cl", sesion=sesion, espera_base=15).status_code, 200)
        dormir.assert_called_once_with(15)


PAGINA_HANGAR = '<div class="product-container"><a class="product-name" href="https://www.hangar019.cl/kit-{n}">Kit {n} HG</a><span class="product-price">$19.990</span></div>'


class TestFalloAMitadDePaginacion(BaseTemporal):
    def correr(self, respuestas):
        from scrapers.hangar import HangarScraper
        from core.scraper_manager import ScraperManager
        mgr = ScraperManager()
        mgr.scrapers = {"Hangar019": (HangarScraper(), "https://www.hangar019.cl")}
        with mock.patch("core.peticiones.requests.get", side_effect=respuestas), \
                mock.patch("scrapers.hangar.time.sleep"), mock.patch("core.peticiones.time.sleep"):
            mgr.ejecutar_todos()

    def activas(self):
        return execute_query("SELECT COUNT(*) FROM publicacion_producto WHERE es_url_activa = 1", fetchone=True)[0]

    def test_error_en_pagina_2_no_marca_agotados(self):
        # Corrida completa: 2 páginas con un producto cada una
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1)), respuesta(200, PAGINA_HANGAR.format(n=2)), respuesta(200)])
        self.assertEqual(self.activas(), 2)
        # Corrida que falla en la página 2: antes dejaba el kit 2 como agotado
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1))] + [respuesta(503)] * 3)  # 503 aun tras los reintentos
        self.assertEqual(self.activas(), 2)

    def test_error_al_guardar_revierte_toda_la_tienda(self):
        from core.scraper_manager import ScraperManager
        mgr = ScraperManager()
        kit = lambda n: {"nombre_original": f"Kit {n} HG", "precio": 19990.0, "url": f"https://tienda.cl/kit-{n}"}
        mgr.guardar_datos("Tienda", "https://tienda.cl", [kit(1), kit(2)])
        historial = execute_query("SELECT COUNT(*) FROM historial_precios", fetchone=True)[0]
        # El tercer ítem viene sin precio: falla después de desactivar la tienda y reactivar el kit 1
        with self.assertRaises(KeyError):
            mgr.guardar_datos("Tienda", "https://tienda.cl", [kit(1), kit(3), {"nombre_original": "x", "url": "y"}])
        self.assertEqual(self.activas(), 2)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM publicacion_producto", fetchone=True)[0], 2)
        self.assertEqual(execute_query("SELECT COUNT(*) FROM historial_precios", fetchone=True)[0], historial)

    def test_404_despues_de_la_primera_pagina_es_fin_del_catalogo(self):
        self.correr([respuesta(200, PAGINA_HANGAR.format(n=1)), respuesta(404)])
        self.assertEqual(self.activas(), 1)


class TestOperacionesDelPanel(BaseTemporal):
    """Funciones de core/ que usa el panel, probadas sin Flask."""

    def setUp(self):
        super().setUp()
        from core import productos
        self.productos = productos
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A')", commit=True)
        execute_query("INSERT INTO productos (id, nombre_estandar, es_visible) VALUES (1, 'KIT HG', 1)", commit=True)
        execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio) VALUES (1, 1, 1, 'a', 1)", commit=True)
        execute_query("INSERT INTO historial_precios (publicacion_producto_id, precio) VALUES (1, 1)", commit=True)

    def contar(self, tabla):
        return execute_query(f"SELECT COUNT(*) FROM {tabla}", fetchone=True)[0]

    def test_alternar_visibilidad(self):
        self.assertEqual(self.productos.alternar_visibilidad(1), 0)
        self.assertEqual(self.productos.alternar_visibilidad(1), 1)
        self.assertIsNone(self.productos.alternar_visibilidad(999))  # antes: error 500

    def test_eliminar_borra_publicaciones_e_historial(self):
        self.productos.eliminar_producto(1)
        self.assertEqual([self.contar(t) for t in ("productos", "publicacion_producto", "historial_precios")], [0, 0, 0])

    def test_editar(self):
        self.productos.actualizar_producto(1, "KIT MG", "MG")
        self.assertEqual(self.productos.obtener_producto(1), (1, "KIT MG", "MG", None))
        self.assertIsNone(self.productos.obtener_producto(999))

    def test_crear_manual_es_todo_o_nada(self):
        # Falla el último INSERT (historial): no debe quedar un producto ni una publicación sueltos
        with mock.patch("core.productos.datetime") as reloj:
            reloj.now.side_effect = RuntimeError("falla a mitad")
            with self.assertRaises(RuntimeError):
                self.productos.crear_producto_manual("NUEVO HG", "HG", 9990.0, "https://t.cl/nuevo")
        self.assertEqual([self.contar(t) for t in ("productos", "publicacion_producto", "tiendas")], [1, 1, 1])
        self.assertTrue(self.productos.crear_producto_manual("NUEVO HG", "HG", 9990.0, "https://t.cl/nuevo"))
        self.assertFalse(self.productos.crear_producto_manual("OTRO HG", "HG", 9990.0, "https://t.cl/nuevo"))
        self.assertFalse(self.productos.crear_producto_manual("", "HG", 9990.0))

    def test_credenciales_del_admin(self):
        from core import usuarios
        from werkzeug.security import check_password_hash
        self.assertIsNone(usuarios.obtener_credenciales_admin())
        usuarios.guardar_credenciales_admin("jose", "clave-1")
        usuarios.guardar_credenciales_admin("jose", "clave-2")
        email, hash_clave = usuarios.obtener_credenciales_admin()
        self.assertEqual((email, check_password_hash(hash_clave, "clave-2")), ("jose", True))
        self.assertEqual(self.contar("usuarios"), 1)


class TestEstadoTiendas(BaseTemporal):
    def setUp(self):
        super().setUp()
        from core.scraper_manager import ScraperManager
        self.manager = ScraperManager()
        self.reloj = mock.patch("core.scraper_manager.datetime")
        reloj = self.reloj.start()
        self.ahora = lambda texto: setattr(reloj.now.return_value, "strftime", lambda _: texto)

    def tearDown(self):
        self.reloj.stop()
        super().tearDown()

    def estado(self):
        from core.estadisticas import estado_tiendas
        return {t["nombre"]: t for t in estado_tiendas()}

    def test_exito_y_luego_falla(self):
        from datetime import datetime
        hace_un_rato = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.ahora(hace_un_rato)
        self.manager.registrar_estado("A", "https://a.cl", productos=40)
        self.assertEqual((self.estado()["A"]["ok"], self.estado()["A"]["productos"], self.estado()["A"]["error"]), (True, 40, ""))
        self.ahora("2999-01-01 00:00:00")  # un intento posterior que falla
        self.manager.registrar_estado("A", "https://a.cl", error="HTTP 503")
        a = self.estado()["A"]
        self.assertEqual((a["ok"], a["error"], a["ultimo_exito"], a["productos"]), (False, "HTTP 503", hace_un_rato, 40))

    def test_tienda_sin_exito_reciente_queda_para_revisar(self):
        self.ahora("2026-01-01 12:00:00")
        self.manager.registrar_estado("Vieja", "https://v.cl", productos=5)
        self.manager.registrar_estado("Nueva", "https://n.cl", error="ConnectionError")
        estado = self.estado()
        self.assertFalse(estado["Vieja"]["ok"])
        self.assertEqual((estado["Nueva"]["ok"], estado["Nueva"]["ultimo_exito"]), (False, "Nunca"))
        self.assertEqual(execute_query("SELECT COUNT(*) FROM tiendas", fetchone=True)[0], 2)

    def test_tienda_manual_no_aparece(self):
        execute_query("INSERT INTO tiendas (nombre) VALUES ('Manual')", commit=True)
        self.assertNotIn("Manual", self.estado())


class TestRespaldos(BaseTemporal):
    def test_crea_copia_y_borra_las_antiguas(self):
        import sqlite3
        from core.respaldos import respaldar_base
        execute_query("INSERT INTO productos (nombre_estandar) VALUES ('KIT HG')", commit=True)
        carpeta = tempfile.mkdtemp()
        for nombre in ["precios_2020-01-01.db", "precios_2999-01-01.db", "otro.db"]:
            open(os.path.join(carpeta, nombre), "w").close()
        destino = respaldar_base(carpeta, dias=30)
        copia = sqlite3.connect(destino)
        self.assertEqual(copia.execute("SELECT nombre_estandar FROM productos").fetchall(), [("KIT HG",)])
        copia.close()
        self.assertEqual(sorted(os.listdir(carpeta)), sorted(["otro.db", "precios_2999-01-01.db", os.path.basename(destino)]))


class TestConfiguracion(unittest.TestCase):
    def test_no_arranca_sin_variables_obligatorias(self):
        import config
        with mock.patch.dict(os.environ, {"SECRET_KEY": "x", "ADMIN_USER": "y", "ADMIN_PASS": ""}):
            with self.assertRaises(SystemExit) as error:
                config.validar_configuracion()
            self.assertIn("ADMIN_PASS", str(error.exception))
        with mock.patch.dict(os.environ, {"SECRET_KEY": "x", "ADMIN_USER": "y", "ADMIN_PASS": "z"}):
            config.validar_configuracion()

    def test_debug_apagado_por_defecto(self):
        import importlib, config
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLASK_DEBUG", None)
            self.assertFalse(importlib.reload(config).DEBUG)


class ScraperBloqueado:
    """Scraper falso que no termina hasta que la prueba lo libera."""
    def __init__(self):
        self.liberar = threading.Event()

    def extraer_datos(self):
        self.liberar.wait(5)
        return []


class TestEscaneoUnoALaVez(PanelTemporal):
    def setUp(self):
        from core.scraper_manager import ScraperManager
        self.scraper = ScraperBloqueado()
        self.manager = ScraperManager()
        self.manager.scrapers = {"Lenta": (self.scraper, "https://lenta.cl")}
        super().setUp()

    def esperar_fin(self):
        for _ in range(100):
            if not self.manager.en_curso():
                return
            time.sleep(0.05)
        self.fail("el escaneo no terminó")

    def test_forzar_escaneo_corre_en_segundo_plano_y_no_se_duplica(self):
        respuesta = self.post("/admin/force-update")
        self.assertEqual(respuesta.status_code, 202)
        self.assertTrue(self.cliente.get("/admin/force-update/estado").json["en_curso"])
        # Mientras corre: ni otro forzado ni el programado inician un segundo escaneo
        self.assertEqual(self.post("/admin/force-update").status_code, 409)
        self.assertIsNone(self.manager.ejecutar_todos())
        self.scraper.liberar.set()
        self.esperar_fin()
        self.assertFalse(self.cliente.get("/admin/force-update/estado").json["en_curso"])
        self.assertEqual(self.post("/admin/force-update").status_code, 202)
        self.esperar_fin()


class TestImportarApp(BaseTemporal):
    def test_importar_no_arranca_el_scheduler(self):
        import importlib, sys
        sys.modules.pop("app", None)
        importlib.import_module("app")
        logs = execute_query("SELECT accion FROM logs", fetchall=True)
        self.assertFalse([l for (l,) in logs if "Scheduler" in l], logs)


if __name__ == "__main__":
    unittest.main()
