<img width="1774" height="448" alt="Banner_dark" src="https://github.com/user-attachments/assets/9c20d4d2-63f7-4aa2-bb6d-98a3a7d234e2" />

# Radar de Precios: Gunpla Scrapper Chile

> Proyecto de monitoreo automatizado y plataforma web diseñada para el seguimiento exhaustivo de precios en el mercado de modelos Gunpla en Chile.

Esta herramienta no solo permite realizar un **seguimiento histórico** de productos mediante scraping automatizado, sino que ofrece un robusto **catálogo global estandarizado**. Los usuarios pueden visualizar fluctuaciones de precios mediante gráficos interactivos, filtrar modelos por grado, y los administradores pueden gestionar la base de datos a través de un panel de control dedicado.

---

## Características Principales

### Para el Usuario (Frontend)
* **Exploración Optimizada:** Paginación dinámica (24, 48 o 120 productos por página) para una carga ultrarrápida.
* **Filtros Especializados:** Filtrado de productos por Grado (PG, MG, RG, HG, EG, SD, FM, Sin Grado).
* **Ordenamiento Flexible:** Clasificación de productos por precio (ascendente/descendente) y alfabéticamente (A-Z / Z-A).
* **Visualización de Datos:** Gráficos de tendencias generados dinámicamente con *Chart.js* para analizar la fluctuación de costos.
* **Modo Oscuro Integrado:** Interfaz web diseñada con variables CSS nativas que respetan la preferencia visual del usuario.
* **Promociones Dinámicas:** Carrusel de imágenes administrable para destacar ofertas o tiendas.

### Para el Administrador (Backend & Motor)
* **Panel de Administración:** Acceso seguro mediante credenciales para gestionar la plataforma.
* **Catálogo Global (Estandarización):** Sistema inteligente que agrupa publicaciones de distintas tiendas bajo un único modelo estandarizado.
* **Fusión de Duplicados:** Herramienta en el panel de control para unificar productos duplicados (asignando el historial de una ID duplicada a la ID principal) manteniendo la base de datos limpia.
* **Scraping Automatizado:** Recolección programada de datos desde diversas tiendas especializadas utilizando web scraping.
* **Métricas y Logs:** Registro de visitas globales y sistema de *logging* detallado para auditoría de acciones administrativas.

---

## Tecnologías Utilizadas

| Tecnología | Descripción |
| :--- | :--- |
| **Python** | Lenguaje de desarrollo principal. |
| **Flask & Jinja2** | Framework web ligero para el servidor y motor de plantillas HTML. |
| **BeautifulSoup4** | Extracción y parseo de datos HTML para los scrapers. |
| **SQLite3** | Base de datos relacional local sin dependencias externas. |
| **APScheduler** | Planificador para la ejecución periódica de recolección de precios. |
| **Chart.js** | Biblioteca JS para la renderización de gráficos históricos interactivos. |
| **HTML5 & CSS3** | Estructuración modular con Flexbox y variables CSS. |

---

## Arquitectura del Proyecto

El proyecto está estructurado de manera modular para garantizar escalabilidad y orden:

```text
GundamScrapperChile/
├── app.py                  # Punto de entrada principal y orquestador
├── config.py               # Variables de entorno y configuración general
├── core/                   # Herramientas centrales
│   ├── database.py         # Conexión DB, init y consultas SQL genéricas
│   └── logger.py           # Sistema de registro de eventos
├── routes/                 # Controladores (Blueprints de Flask)
│   ├── views_inicio.py     # Lógica de la página principal, filtros y paginación
│   ├── producto_bp.py      # Lógica de vista individual y gráficos
│   └── admin.py            # Rutas protegidas del panel de administración
├── scrapers/               # Scripts independientes de recolección por tienda
├── static/                 # Archivos estáticos (CSS, JS, imágenes del carrusel)
└── templates/              # Plantillas Jinja2 (base.html, inicio.html, admin.html...)
```

---

## Nota de Uso
Este proyecto ha sido desarrollado con fines educativos y de análisis personal. Se recomienda a los usuarios respetar las políticas de uso de los sitios web objetivo y no saturar sus servidores con peticiones excesivas. Los módulos de recolección deben incluir pausas (time.sleep) entre páginas para asegurar un comportamiento respetuoso con el tráfico de red.