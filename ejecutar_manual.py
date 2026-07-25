from core.scraper_manager import ScraperManager # Ajusta la ruta 'core.' si tu archivo está en otro lado

print("🚀 Iniciando prueba manual de Scrapers y Catálogo...")

# Instanciamos el manager
manager = ScraperManager()

# Ejecutamos el proceso completo (Scraping + Base de datos + Normalización)
total, duracion = manager.ejecutar_todos()

print("--------------------------------------------------")
print(f"✅ Prueba finalizada con éxito.")
print(f"📦 Total de productos extraídos: {total}")
print(f"⏱️ Tiempo total: {duracion:.1f} segundos")
print("--------------------------------------------------")
print("Revisa tu base de datos (SQLite) para confirmar los cambios.")