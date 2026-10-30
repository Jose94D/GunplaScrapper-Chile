"""Mínimo histórico y % de baja de las tarjetas del inicio y de la ficha."""
import unittest
from datetime import datetime, timedelta

from core.catalogo import indicadores_precio
from core.database import execute_query
from tests.test_regresiones import BaseTemporal


def hace(dias):
    return (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")


class TestIndicadores(BaseTemporal):
    def setUp(self):
        super().setUp()
        execute_query("INSERT INTO tiendas (id, nombre) VALUES (1, 'A'), (2, 'B')", commit=True)
        self.pub = 0

    def producto(self, id, *tiendas):
        """tiendas: (activa, [(precio, días atrás), ...]) por cada publicación del producto."""
        execute_query("INSERT INTO productos (id, nombre_estandar, grado) VALUES (?, ?, 'HG')", (id, f"KIT {id}"), commit=True)
        for tienda, (activa, precios) in enumerate(tiendas, start=1):
            self.pub += 1
            execute_query("INSERT INTO publicacion_producto (id, producto_id, tienda_id, url, precio, es_url_activa) VALUES (?, ?, ?, ?, ?, ?)",
                          (self.pub, id, tienda, f"u{self.pub}", precios[-1][0], activa), commit=True)
            for precio, dias in precios:
                execute_query("INSERT INTO historial_precios (publicacion_producto_id, precio, fecha_registro) VALUES (?, ?, ?)",
                              (self.pub, precio, hace(dias)), commit=True)

    def test_casos(self):
        self.producto(1, (1, [(20000, 10), (20000, 3), (17000, 2), (17000, 1)]))  # bajó hace 2 días: 15 % y mínimo
        self.producto(2, (1, [(20000, 10), (20000, 1)]))                          # precio plano: nada
        self.producto(3, (1, [(20000, 1)]))                                       # recién llegado: nada
        self.producto(4, (1, [(17000, 10), (20000, 1)]))                          # subió: nada
        self.producto(5, (1, [(20000, 30), (17000, 20), (17000, 1)]))             # bajó hace 20 días: solo mínimo
        self.producto(6, (1, [(15000, 1)]), (1, [(20000, 5), (16000, 1)]))         # la que bajó no es la más barata: sin baja
        self.producto(7, (0, [(10000, 5)]), (1, [(18000, 5), (15000, 1)]))         # la tienda sin stock no cuenta para la baja
        r = indicadores_precio([1, 2, 3, 4, 5, 6, 7, 99])
        self.assertEqual(r[1], {"minimo_historico": True, "baja_pct": 15})
        for id in (2, 3, 4):
            self.assertEqual(r[id], {"minimo_historico": False, "baja_pct": None}, id)
        self.assertEqual(r[5], {"minimo_historico": True, "baja_pct": None})
        self.assertEqual(r[6], {"minimo_historico": True, "baja_pct": None})  # 15.000 es su precio más bajo, pero no bajó
        # El producto 7 bajó 17 % en su tienda con stock, pero hubo un precio menor (10.000) en otra: no es mínimo
        self.assertEqual(r[7], {"minimo_historico": False, "baja_pct": 17})
        self.assertNotIn(99, r)
        self.assertEqual(indicadores_precio([]), {})

    def test_se_ven_en_el_inicio_y_en_la_ficha(self):
        import importlib
        import sys
        self.producto(1, (1, [(20000, 10), (17000, 2)]))
        execute_query("UPDATE productos SET es_visible = 1, disponible = 1", commit=True)
        sys.modules.pop("app", None)
        cliente = importlib.import_module("app").app.test_client()
        inicio = cliente.get("/").get_data(as_text=True)
        self.assertIn("Mínimo histórico", inicio)
        self.assertIn("↓ 15 %", inicio)
        self.assertIn("↓ 15 % esta semana", cliente.get("/producto/1-kit-1").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
