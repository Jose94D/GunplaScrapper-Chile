"""Imágenes de productos: lectura desde los listados, reducción a WebP, descarga única y reemplazo desde el panel."""
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

from bs4 import BeautifulSoup
from PIL import Image

from core.database import execute_query
from core import imagenes
from tests.test_regresiones import BaseTemporal, PanelTemporal


def png(ancho=1200, alto=900, transparente=True):
    salida = io.BytesIO()
    Image.new("RGBA" if transparente else "RGB", (ancho, alto), (200, 30, 30, 128) if transparente else (200, 30, 30)).save(salida, "PNG")
    return salida.getvalue()


class TestUrlImagen(unittest.TestCase):
    def url(self, html):
        return imagenes.url_imagen(BeautifulSoup(f"<div>{html}</div>", "html.parser").div, "https://tienda.cl")

    def test_formatos_de_las_tiendas(self):
        casos = {
            # PrestaShop: la miniatura del listado se cambia por la foto grande
            '<img src="https://www.hangar019.cl/83-home_default/epyon.jpg">': "https://www.hangar019.cl/83-large_default/epyon.jpg",
            '<img src="/web/image/product.template/24825/image/400x400">': "https://tienda.cl/web/image/product.template/24825/image/400x400",
            '<img data-src="https://www.weplay.cl/pub/media/a.jpg" src="data:image/gif;base64,R0lGOD">': "https://www.weplay.cl/pub/media/a.jpg",
            # Shopify: srcset con varios anchos y // sin protocolo -> el más chico de al menos 400 px
            '<img src="//b.cl/x.webp?width=3840" srcset="//b.cl/x.webp?width=240 240w, //b.cl/x.webp?width=480 480w, //b.cl/x.webp?width=960 960w">': "https://b.cl/x.webp?width=480",
            # Carga diferida con srcset de relleno (data:) y el real en data-srcset
            '<img srcset="data:image/svg+xml;utf8,<svg></svg>" data-srcset="//l.cl/a_200x.webp 200w, //l.cl/a_300x.webp 300w">': "https://l.cl/a_300x.webp",
            '<span>sin imagen</span>': None,
            '<img src="data:image/gif;base64,R0lGOD">': None,
            '<img src="javascript:alert(1)">': None,
        }
        for html, esperado in casos.items():
            self.assertEqual(self.url(html), esperado, html)


class TestAWebp(unittest.TestCase):
    def test_reduce_y_convierte(self):
        webp = imagenes.a_webp(png())
        with Image.open(io.BytesIO(webp)) as img:
            self.assertEqual((img.format, img.size), ("WEBP", (400, 300)))
        self.assertLess(len(webp), 40_000)

    def test_imagen_chica_no_se_agranda(self):
        with Image.open(io.BytesIO(imagenes.a_webp(png(200, 300, False)))) as img:
            self.assertEqual(img.size, (200, 300))

    def test_lo_que_no_es_imagen_falla(self):
        with self.assertRaises(Exception):
            imagenes.a_webp(b"<html>no soy una imagen</html>")


class RespuestaFalsa:
    def __init__(self, datos, estado=200):
        self.datos, self.estado = datos, estado

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def raise_for_status(self):
        if self.estado >= 400:
            raise Exception(f"HTTP {self.estado}")

    def iter_content(self, tamano):
        for i in range(0, len(self.datos), tamano):
            yield self.datos[i:i + tamano]


class ConCarpetaTemporal:
    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.mkdtemp()
        self.parche_carpeta = mock.patch.object(imagenes, "CARPETA", self.carpeta)
        self.parche_carpeta.start()

    def tearDown(self):
        self.parche_carpeta.stop()
        shutil.rmtree(self.carpeta, ignore_errors=True)
        super().tearDown()


class TestDescargaUnica(ConCarpetaTemporal, BaseTemporal):
    def setUp(self):
        super().setUp()
        from core.scraper_manager import ScraperManager
        ScraperManager().guardar_datos("A", "https://a.cl", [
            {"nombre_original": "Kit 1", "precio": 1.0, "url": "https://a.cl/1", "imagen": "https://a.cl/1.png"},
            {"nombre_original": "Kit 2", "precio": 1.0, "url": "https://a.cl/2", "imagen": "https://a.cl/roto.png"},
            {"nombre_original": "Kit 3", "precio": 1.0, "url": "https://a.cl/3"},
        ])
        for pub, prod in [(1, 1), (2, 2), (3, 3)]:
            execute_query("INSERT INTO productos (id, nombre_estandar) VALUES (?, ?)", (prod, f"KIT {prod}"), commit=True)
            execute_query("UPDATE publicacion_producto SET producto_id = ? WHERE id = ?", (prod, pub), commit=True)

    def descargar(self):
        def get(url, **kwargs):
            return RespuestaFalsa(png()) if url.endswith("1.png") else RespuestaFalsa(b"", 404)
        with mock.patch("core.imagenes.requests.get", side_effect=get) as llamadas, mock.patch("core.imagenes.time.sleep"):
            resultado = imagenes.descargar_pendientes()
        return resultado, llamadas.call_count

    def imagen(self, id):
        return execute_query("SELECT imagen_producto FROM productos WHERE id = ?", (id,), fetchone=True)[0]

    def test_descarga_una_vez_y_reintenta_solo_las_fallidas(self):
        self.assertEqual(self.descargar(), ((1, 1), 2))  # el producto 3 no tiene URL: ni se intenta
        self.assertEqual(self.imagen(1), "productos/1.webp")
        self.assertTrue(os.path.exists(os.path.join(self.carpeta, "1.webp")))
        self.assertIsNone(self.imagen(2))
        self.assertEqual(self.descargar(), ((0, 1), 1))  # segunda corrida: solo reintenta la que falló

    def test_reescaneo_sin_imagen_conserva_la_url(self):
        from core.scraper_manager import ScraperManager
        ScraperManager().guardar_datos("A", "https://a.cl", [{"nombre_original": "Kit 1", "precio": 2.0, "url": "https://a.cl/1"}])
        self.assertEqual(execute_query("SELECT imagen_url FROM publicacion_producto WHERE id = 1", fetchone=True)[0], "https://a.cl/1.png")

    def test_fusion_hereda_la_imagen_y_eliminar_borra_el_archivo(self):
        from core import productos
        self.descargar()
        productos.fusionar_productos(3, 1)  # el 3 no tenía imagen: hereda la del 1
        self.assertEqual(self.imagen(3), "productos/1.webp")
        productos.eliminar_producto(3)
        self.assertFalse(os.path.exists(os.path.join(self.carpeta, "1.webp")))


class TestReemplazoDesdeElPanel(ConCarpetaTemporal, PanelTemporal):
    def setUp(self):
        super().setUp()
        execute_query("INSERT INTO productos (id, nombre_estandar, grado) VALUES (1, 'KIT HG', 'HG')", commit=True)

    def editar(self, archivo, nombre):
        return self.post("/admin/producto/editar/1", {"producto": "KIT HG", "grado": "HG", "imagen": (io.BytesIO(archivo), nombre)},
                         content_type="multipart/form-data")

    def test_subir_reemplaza_y_rechaza_lo_que_no_es_imagen(self):
        self.assertEqual(self.editar(png(), "caja.png").status_code, 302)
        self.assertEqual(execute_query("SELECT imagen_producto FROM productos WHERE id = 1", fetchone=True)[0], "productos/1.webp")
        antes = os.path.getsize(os.path.join(self.carpeta, "1.webp"))
        self.editar(b"<script>alert(1)</script>", "caja.png")   # extensión de imagen, contenido falso
        self.editar(png(), "caja.html")                           # extensión no permitida
        self.assertEqual(os.path.getsize(os.path.join(self.carpeta, "1.webp")), antes)

    def test_la_pagina_de_edicion_muestra_el_campo(self):
        html = self.cliente.get("/admin/producto/editar/1").get_data(as_text=True)
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertIn('name="imagen"', html)

    def test_filtro_sin_imagen_y_vuelta_al_mismo_filtro(self):
        execute_query("INSERT INTO productos (id, nombre_estandar, grado, imagen_producto) VALUES (2, 'CON FOTO HG', 'HG', 'productos/2.webp')", commit=True)
        html = self.cliente.get("/admin/panel?sin_imagen=1").get_data(as_text=True)
        self.assertIn(">KIT HG</a>", html)
        self.assertNotIn(">CON FOTO HG</a>", html)  # el selector de la ventana de fusión sí lista todo el catálogo
        self.assertIn("Sin imagen <span>1</span>", html)
        # Al guardar la edición se vuelve al panel con el filtro puesto
        self.assertIn('name="sin_imagen" value="1"', self.cliente.get("/admin/producto/editar/1?sin_imagen=1").get_data(as_text=True))
        respuesta = self.post("/admin/producto/editar/1", {"producto": "KIT HG", "grado": "HG", "sin_imagen": "1"})
        self.assertIn("sin_imagen=1", respuesta.headers["Location"])


if __name__ == "__main__":
    unittest.main()
