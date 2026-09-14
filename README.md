<img width="1774" height="448" alt="Banner_dark" src="https://github.com/user-attachments/assets/9c20d4d2-63f7-4aa2-bb6d-98a3a7d234e2" />

# Radar de Precios: Gunpla Scrapper Chile
 
> Herramienta de automatización y web scraping para monitoreo de mercado en tiempo real de coleccionables (Gunpla) en Chile. Desarrollo enfocado en extracción de datos, procesamiento, normalización y centralización de información.
 
Esta herramienta no solo permite realizar un **seguimiento histórico** de productos mediante scraping automatizado, sino que ofrece un robusto **catálogo global estandarizado**. Los usuarios pueden visualizar fluctuaciones de precios mediante gráficos interactivos, filtrar modelos por grado, y los administradores pueden gestionar la base de datos a través de un panel de control dedicado.
 
---
 
## Características Principales
 
### Para el Usuario (Frontend)
* **Exploración Optimizada:** Paginación dinámica (24, 48 o 120 productos por página) para una carga ultrarrápida.
* **Filtros Especializados:** Filtrado de productos por Grado (PG, MG, RG, HG, EG, SD, FM, S/G).
* **Ordenamiento Flexible:** Clasificación de productos por precio (ascendente/descendente) y alfabéticamente (A-Z / Z-A).
* **Visualización de Datos:** Gráficos de tendencias generados dinámicamente con *Chart.js* para analizar la fluctuación de costos, con el detalle de precio y disponibilidad por cada tienda.
* **Estado de Disponibilidad:** Los productos sin stock en ninguna tienda se marcan automáticamente como "No disponible" y no se muestran en el catálogo principal, sin perder el estado Visible/Oculto elegido por el administrador.
* **Modo Oscuro Integrado:** Interfaz web diseñada con variables CSS nativas que respetan la preferencia visual del usuario.
* **Promociones Dinámicas:** Carrusel de imágenes administrable para destacar ofertas o tiendas.
* **Páginas Institucionales:** Sobre Nosotros, Preguntas Frecuentes, Condiciones de Servicio y Políticas de Privacidad, accesibles desde el footer.
### Para el Administrador (Backend & Motor)
* **Panel de Administración:** Acceso seguro mediante credenciales con contraseña hasheada (no en texto plano).
* **Catálogo Global (Estandarización):** Sistema inteligente que agrupa publicaciones de distintas tiendas bajo un único modelo estandarizado, detectando grado y limpiando ruido (marcas, escalas, texto irrelevante) del nombre original.
* **Filtro de Palabras Bloqueadas:** Descarta automáticamente productos de otras franquicias o líneas ajenas a Gunpla (ej. Pokémon, Naruto, Dragon Ball) que algunas tiendas mezclan en sus catálogos, evitando tener que ocultarlos a mano.
* **Orden Priorizado por Estado:** El listado del panel siempre ordena Visibles → No disponibles → Ocultos, sin importar el criterio de orden elegido, para que lo relevante quede siempre arriba.
* **Fusión de Duplicados:** Herramienta en el panel de control para unificar productos duplicados (asignando el historial de una ID duplicada a la ID principal) manteniendo la base de datos limpia.
* **Scraping Automatizado y Respetuoso:** Recolección programada desde 8 tiendas especializadas, cada una evaluada contra su `robots.txt` antes de integrarse; los scrapers incluyen pausas (`time.sleep`) entre páginas para no sobrecargar los servidores de terceros.
* **Métricas y Logs:** Conteo de visitas mensuales únicas (deduplicadas por cookie diaria) y sistema de *logging* detallado para auditoría de acciones administrativas.
---
 
## Tiendas Monitoreadas
 
Hangar019 · Blaster Chile · ChileRobots · Irion Juguetería · Geekz · Weplay · LuffyToys · HobbyToys
 
Algunas tiendas evaluadas quedaron fuera deliberadamente por su `robots.txt` (Mirax, Top8, Bluecard, Wargaming): bloquean explícitamente el acceso automatizado a sus catálogos, y scrapearlas de todas formas no sería ético. El detalle está en la página de Preguntas Frecuentes del sitio.
 
---
 
## Tecnologías Utilizadas
 
| Tecnología | Descripción |
| :--- | :--- |
| **Python** | Lenguaje de desarrollo principal. |
| **Flask & Jinja2** | Framework web ligero para el servidor y motor de plantillas HTML. |
| **BeautifulSoup4** | Extracción y parseo de datos HTML para los scrapers. |
| **SQLite3** | Base de datos relacional local sin dependencias externas. |
| **Chart.js** | Biblioteca JS para la renderización de gráficos históricos interactivos. |
| **HTML5 & CSS3** | Estructuración modular con Flexbox y variables CSS. |
 
---
 
## Arquitectura del Proyecto
 
El proyecto está estructurado de manera modular para garantizar escalabilidad y orden:
 
```text
GundamScrapperChile/
├── app.py                          # Punto de entrada principal (rutas y arranque de Flask)
├── config.py                       # Variables de entorno y configuración general
├── ejecutar_scraping_programado.py # Script independiente disparado por cron/Task Scheduler
├── actualizar_disponibilidad.py    # Script independiente para recalcular disponibilidad
├── core/                           # Herramientas centrales
│   ├── database.py                 # Conexión DB, init, migraciones y consultas SQL genéricas
│   ├── scraper_manager.py          # Orquestador: ejecuta cada scraper y guarda los resultados
│   ├── catalog_manager.py          # Normalización de nombres, detección de grado y filtro de palabras bloqueadas
│   └── logger.py                   # Sistema de registro de eventos (tabla 'logs')
├── routes/                         # Controladores (Blueprints de Flask)
│   ├── views_inicio.py             # Página principal (filtros, paginación) y vista de detalle/gráfico
│   ├── admin.py                    # Rutas protegidas del panel de administración
│   ├── admin_login.py              # Autenticación del panel
│   └── views_institucional.py      # Sobre Nosotros, FAQ, Condiciones de Servicio, Políticas
├── scrapers/                       # Un módulo independiente por tienda
│   ├── hangar.py
│   ├── blaster.py
│   ├── chilerobots.py
│   ├── irion.py
│   ├── geekz.py
│   ├── weplay.py
│   ├── luffytoys.py
│   └── hobbytoys.py
├── static/                         # Archivos estáticos (CSS, JS, imágenes del carrusel)
├── templates/                      # Plantillas Jinja2 (base.html, inicio.html, producto.html,
│                                    #   admin_panel.html, sobre_nosotros.html, faq.html, etc.)
└── manual/                         # Documentación del proyecto (manuales, diagrama ER)
```
 
---
 
## Modelo de Base de Datos

El sistema utiliza un esquema relacional optimizado en SQLite para gestionar contenidos de forma limpia y sin redundancias:

---

## Automatización del Scraping
 
El escaneo completo de las 8 tiendas corre automáticamente dos veces al día (00:00 y 12:00). Al final de cada corrida se ejecuta automáticamente la normalización del catálogo y el recálculo de disponibilidad por producto.
 
---
 
## Nota de Uso
Este proyecto ha sido desarrollado con fines educativos y de análisis personal. Como único responsable de la extracción de datos, me comprometo a respetar las políticas de uso de los sitios web objetivo y a no saturar sus servidores con peticiones excesivas. Los módulos de recolección incluyen pausas (`time.sleep`) entre páginas para asegurar un comportamiento respetuoso con el tráfico de red. Más detalles en las páginas Sobre Nosotros y FAQ del sitio.