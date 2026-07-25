from core.database import execute_query
from core.catalog_manager import CatalogManager

def limpiar_y_revincular():
    print("⚠️ Iniciando reseteo del catálogo global...")

    # 1. Desvinculamos todas las publicaciones de las tiendas dejándolas en NULL
    execute_query("UPDATE publicaciones_tiendas SET catalogo_id = NULL", commit=True)
    print("✅ Todas las publicaciones han sido desvinculadas.")

    # 2. Eliminamos todos los registros del catálogo global antiguo
    execute_query("DELETE FROM catalogo_global", commit=True)
    print("✅ Catálogo global vaciado.")

    # 3. Reiniciamos el contador de IDs de SQLite para empezar desde el 1
    # Nota: Si este comando da error por no existir la tabla sqlite_sequence, no pasa nada.
    try:
        execute_query("DELETE FROM sqlite_sequence WHERE name='catalogo_global'", commit=True)
        print("✅ Contador de IDs reiniciado.")
    except Exception:
        pass

    # 4. Invocamos al nuevo CatalogManager para procesar todo de nuevo
    print("⚙️ Re-procesando el historial con las nuevas reglas de lectura natural...")
    manager = CatalogManager()
    manager.procesar_pendientes()

    print("🎉 ¡Reseteo y re-vinculación completados con éxito!")

if __name__ == "__main__":
    limpiar_y_revincular()