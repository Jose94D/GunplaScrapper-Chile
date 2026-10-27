"""Sugerencias de productos duplicados: el mismo kit escrito distinto por dos tiendas."""
import re
from difflib import SequenceMatcher

from core.database import execute_query
from core.logger import registrar_log

SIMILITUD_MINIMA = 0.88
# Palabras que casi todas las tiendas agregan o quitan, y no distinguen un kit de otro
RELLENO = {"GUNDAM", "VER", "UNIT", "TYPE"}


def _firma(nombre, grado):
    """
    (texto comparable, tokens que deben coincidir exactos).
    Los tokens con dígitos o de hasta 2 letras identifican el modelo: F91, AGE-3, X frente a ZZ,
    A-PACKS frente a C-PACKS. Si difieren, no son el mismo kit aunque el resto sea igual.
    """
    comparables, clave = [], set()
    for token in nombre.split():
        if token == grado or token in RELLENO:
            continue
        partes = token.split("-")
        clave.update(p for p in partes if p and (re.search(r"\d", p) or len(p) <= 2))
        comparables.append("".join(partes))  # HYAKU-SHIKI = HYAKUSHIKI
    return " ".join(sorted(comparables)), frozenset(clave)


def _parecidos(productos):
    """Pares (similitud, a, b) del mismo grado cuyos nombres solo cambian en orden, guiones, relleno o una letra."""
    por_grado = {}
    for p in productos:
        por_grado.setdefault(p["grado"], []).append((p, *_firma(p["nombre"], p["grado"])))
    pares = []
    # shortcut: compara todos contra todos dentro de cada grado (~0,1 s con 430 productos); con miles, precalcular y guardar
    for lista in por_grado.values():
        for i, (a, texto_a, clave_a) in enumerate(lista):
            for b, texto_b, clave_b in lista[i + 1:]:
                if clave_a != clave_b or not texto_a or not texto_b:
                    continue
                m = SequenceMatcher(None, texto_a, texto_b)
                if m.quick_ratio() >= SIMILITUD_MINIMA and m.ratio() >= SIMILITUD_MINIMA:
                    pares.append((m.ratio(), a, b))
    return pares


def sugerir_duplicados(limite=20):
    """
    Posibles duplicados para revisar en el panel, del más parecido al menos, sin los ya descartados.
    En cada par, 'principal' es el que conviene conservar (más tiendas; si empatan, el más antiguo).
    """
    productos = [
        {"id": f[0], "nombre": f[1], "grado": f[2], "tiendas": f[3]}
        for f in execute_query("""
            SELECT p.id, p.nombre_estandar, p.grado, COUNT(pp.id)
            FROM productos p LEFT JOIN publicacion_producto pp ON pp.producto_id = p.id
            GROUP BY p.id ORDER BY p.id
        """, fetchall=True)
    ]
    descartados = set(execute_query("SELECT id_a, id_b FROM duplicados_descartados", fetchall=True))

    sugerencias = []
    for similitud, a, b in sorted(_parecidos(productos), key=lambda par: (-par[0], par[1]["id"], par[2]["id"])):
        if (min(a["id"], b["id"]), max(a["id"], b["id"])) in descartados:
            continue
        principal, duplicado = (b, a) if b["tiendas"] > a["tiendas"] else (a, b)
        sugerencias.append({"principal": principal, "duplicado": duplicado, "similitud": round(similitud * 100)})
        if len(sugerencias) == limite:
            break
    return sugerencias


def descartar(id_a, id_b):
    """Marca el par como productos distintos: no se vuelve a sugerir."""
    execute_query("INSERT OR IGNORE INTO duplicados_descartados (id_a, id_b) VALUES (?, ?)",
                  (min(id_a, id_b), max(id_a, id_b)), commit=True)
    registrar_log(f"Sugerencia de duplicado descartada: productos {id_a} y {id_b} son distintos.")
