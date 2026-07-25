import re
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
            r'\bGUNDAM HGAW\b': 'GUNDAM X HGAW',
            r'\bGRIFFIN ARBALEST CUSTOM\b': ''
        }

        # 2. Diccionario para detectar grados (Agregamos HGAW)
        self.grados_regex = {
            'PG': r'\b(PG|PERFECT GRADE)\b',
            'MG': r'\b(MG|MASTER GRADE|MGEX|MGSD)\b',
            'RG': r'\b(RG|REAL GRADE)\b',
            'HG': r'\b(HG|HIGH GRADE|HGUC|HGCE|HGAC|HGBF|HGAW|HGBD:R)\b', 
            'EG': r'\b(EG|ENTRY GRADE)\b',
            'SD': r'\b(SD|SUPER DEFORMED|SDCS|BB SENSHI|GUNDAM CROSS SILHOUETTE| CROSS SILHOUETTE)\b',
            'FM': r'\b(FM|FULL MECHANICS)\b'
        }
        
        # 3. Ruido a eliminar (Sacamos GUNPLA, agregamos ARTICULADO)
        self.ruido = [
            r'1/\d+',             
            r'\bBANDAI\b',        
            r'\bNAMCO\b',         
            r'\bMODEL KIT\b',
            r'\bFIGURA\b',
            r'\bARTICULADO\b'
        ]

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
            
            # Solo guardamos el token si después de limpiarlo aún tiene texto
            if token_limpio:
                tokens.append(token_limpio)
        
        # Unimos las palabras manteniendo su orden natural
        nombre_base = " ".join(tokens)

        # F) Formato final: [Nombre] [Grado]
        nombre_estandar = f"{nombre_base} {grado_detectado}".strip()
        
        return nombre_estandar, grado_detectado or 'Sin Grado'

    def procesar_pendientes(self):
        """Busca productos no vinculados y los empareja o crea en el catálogo."""
        registrar_log("Iniciando auto-vinculación de catálogo...")
        
        pendientes = execute_query("SELECT id, nombre_original FROM publicaciones_tiendas WHERE catalogo_id IS NULL", fetchall=True)
        
        if not pendientes:
            registrar_log("No hay productos pendientes por vincular.")
            return

        vinculados = 0
        nuevos_creados = 0

        for pub in pendientes:
            pub_id = pub[0]
            nombre_orig = pub[1]

            nombre_estandar, grado = self.normalizar_nombre(nombre_orig)

            cat_existente = execute_query("SELECT id FROM catalogo_global WHERE nombre_estandar = ?", (nombre_estandar,), fetchone=True)

            if cat_existente:
                cat_id = cat_existente[0]
                vinculados += 1
            else:
                execute_query("INSERT INTO catalogo_global (nombre_estandar, grado) VALUES (?, ?)", (nombre_estandar, grado), commit=True)
                cat_id = execute_query("SELECT id FROM catalogo_global WHERE nombre_estandar = ?", (nombre_estandar,), fetchone=True)[0]
                nuevos_creados += 1

            execute_query("UPDATE publicaciones_tiendas SET catalogo_id = ? WHERE id = ?", (cat_id, pub_id), commit=True)

        registrar_log(f"Auto-vinculación completada. Vinculados a existentes: {vinculados} | Nuevos creados: {nuevos_creados}")