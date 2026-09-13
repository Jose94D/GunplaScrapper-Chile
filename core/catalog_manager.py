import re
import unicodedata
from core.database import execute_query
from core.logger import registrar_log

class CatalogManager:
    def __init__(self):
        # 1. Correcciones de orden y nombres rebeldes (Se aplica antes de todo)
        # Formato: { 'Lo que viene del scraper' : 'Nombre que queremos' }
        self.correcciones = {
            r'\bGUNDAM TURN\b': 'TURN A GUNDAM',
            r'\bHI-ZACK HOBBY RE-BOOT VER\b': 'HOBBY HI-ZACK A.O.Z RE-BOOT',
            r'\bAGE-?2 GUNDAM NORMAL\b': 'GUNDAM AGE-2 NORMAL',
            r'\bGRIFFIN ARBALEST CUSTOM\b': ''
        }

        # 2. Diccionario para detectar grados
        self.grados_regex = {
            'PG': r'\b(PG|PERFECT GRADE)\b',
            'MG': r'\b(MG|MASTER GRADE|MGEX|MGSD)\b',
            'RG': r'\b(RG|REAL GRADE)\b',
            'HG': r'\b(HG|HIGH GRADE|HGUC|HGCE|HGAC|HGBF|HGAW|HGBD:R|HGBD|HGFC|HGBD|HGPG)\b', 
            'EG': r'\b(EG|ENTRY GRADE)\b',
            'SD': r'\b(SD|SUPER DEFORMED|SDCS|BB SENSHI|GUNDAM CROSS SILHOUETTE|CROSS SILHOUETTE|SDMG|SD MG)\b',
            'FM': r'\b(FM|FULL MECHANICS)\b'
        }
        
        # 3. Ruido a eliminar
        self.ruido = [
            r'1/\d+',             
            r'\bBANDAI\b',        
            r'\bNAMCO\b',         
            r'\bMODEL KIT\b',
            r'\bFIGURA\b',
            r'\bARTICULADO\b',
            r'\bMOBILE SUIT\b',
            r'\bHOBBY\b',
            r'\bBEST MECHA COLLECTION\b',
            r'\bMOBLIE SUIT\b'
        ]

        # 4. Palabras clave que indican que el producto NO es de nuestro interés
        # (otras franquicias, líneas de merchandising ajenas a Gunpla, decals sueltos, etc).
        # Si el nombre original contiene alguna de estas palabras, la publicación se
        # descarta y se elimina de la base de datos en vez de intentar catalogarla.
        # La comparación ignora mayúsculas/minúsculas y acentos (ver _normalizar_para_filtro).
        self.palabras_bloqueadas = [
            'PLANNOSAURUS', 'POKEMON', '30MS', '30 MINUTES', 'NARUTO', 'SASUKE',
            'GOKU', 'NAMI', 'CHOPPER', 'GFRAME', 'EVANGELION', 'BROLY',
            'FIGURE-RISE STANDARD', 'DEMON SLAYER', 'SAND LAND', 'DECAL', 'ONE PIECE', 'GRAND SHIP COLLECTION',
            'FIGURE RISE STANDARD', 'ACTION BASE', 'GUNDAM UNIVERSE', 'WEAPON DISPLAY'
        ]

    def _normalizar_para_filtro(self, texto):
        """Mayúsculas y sin acentos, para que el filtro de palabras bloqueadas
        no falle por variaciones de tildes (ej. 'POKÉMON' vs 'POKEMON')."""
        texto = texto.upper()
        texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
        return texto

    def contiene_palabra_bloqueada(self, nombre_original):
        """Retorna la palabra bloqueada encontrada en el nombre, o None si no aplica."""
        nombre = self._normalizar_para_filtro(nombre_original)
        for palabra in self.palabras_bloqueadas:
            if self._normalizar_para_filtro(palabra) in nombre:
                return palabra
        return None

    def normalizar_nombre(self, nombre_original):
        nombre = nombre_original.upper()
        grado_detectado = ''

        # A) Aplicar correcciones manuales primero
        for mal, bien in self.correcciones.items():
            nombre = re.sub(mal, bien, nombre)

        # B) Extraer y remover el Grado del string
        for grado, patron in self.grados_regex.items():
            if re.search(patron, nombre):
                grado_detectado = grado
                nombre = re.sub(patron, '', nombre)
                break 

        # C) Eliminar ruido (Marcas, Articulado, etc.)
        for r in self.ruido:
            nombre = re.sub(r, '', nombre)

        # D) Limpiar caracteres especiales 
        nombre = re.sub(r'[^A-Z0-9\-]', ' ', nombre)

        # E) Tokenización INTELIGENTE SIN ORDENAMIENTO
        tokens = []
        for t in nombre.split():
            # strip('-') elimina guiones en los extremos, pero salva los guiones internos como MSM-07S
            token_limpio = t.strip('-')
            
            if token_limpio:
                tokens.append(token_limpio)
        
        # Unimos las palabras manteniendo su orden natural
        nombre_base = " ".join(tokens)

        # F) Formato final: [Nombre] [Grado]
        nombre_estandar = f"{nombre_base} {grado_detectado}".strip()
        
        return nombre_estandar, grado_detectado or 'S/G'

    def procesar_pendientes(self):
        """Busca publicaciones huérfanas sin producto asignado y las vincula o crea en el catálogo."""
        registrar_log("Iniciando auto-vinculación de catálogo...")
        
        # Consultamos las publicaciones huérfanas en la nueva tabla 'publicacion_producto'
        pendientes = execute_query("SELECT id, nombre_original FROM publicacion_producto WHERE producto_id IS NULL", fetchall=True)
        
        if not pendientes:
            registrar_log("No hay publicaciones pendientes por vincular.")
            return

        vinculados = 0
        nuevos_creados = 0
        descartados = 0

        for pub in pendientes:
            pub_id = pub[0]
            nombre_orig = pub[1]

            # Filtro de palabras bloqueadas: si el producto no es de nuestro interés
            # (otra franquicia, decals sueltos, etc), se elimina en vez de catalogarlo.
            palabra_bloqueada = self.contiene_palabra_bloqueada(nombre_orig)
            if palabra_bloqueada:
                # ON DELETE CASCADE en historial_precios limpia también su historial.
                execute_query("DELETE FROM publicacion_producto WHERE id = ?", (pub_id,), commit=True)
                descartados += 1
                continue

            nombre_estandar, grado = self.normalizar_nombre(nombre_orig)

            # Buscamos la coincidencia en la nueva tabla 'productos'
            prod_existente = execute_query("SELECT id FROM productos WHERE nombre_estandar = ?", (nombre_estandar,), fetchone=True)

            if prod_existente:
                prod_id = prod_existente[0]
                vinculados += 1
            else:
                execute_query("INSERT INTO productos (nombre_estandar, grado, marca) VALUES (?, ?, 'Bandai')", (nombre_estandar, grado), commit=True)
                prod_id = execute_query("SELECT id FROM productos WHERE nombre_estandar = ?", (nombre_estandar,), fetchone=True)[0]
                nuevos_creados += 1

            # Actualizamos la relación usando la columna 'producto_id'
            execute_query("UPDATE publicacion_producto SET producto_id = ? WHERE id = ?", (prod_id, pub_id), commit=True)

        registrar_log(f"Auto-vinculación completada. Vinculados a existentes: {vinculados} | Nuevos creados: {nuevos_creados} | Descartados por filtro: {descartados}")