<img width="1774" height="448" alt="Banner_dark" src="https://github.com/user-attachments/assets/9c20d4d2-63f7-4aa2-bb6d-98a3a7d234e2" />

# Radar de Precios: Gunpla Chile

> Proyecto de monitoreo automatizado diseñado para el seguimiento de precios en el mercado de modelos Gunpla en Chile.

Esta herramienta permite realizar un **seguimiento histórico** de productos, visualizar fluctuaciones de precios mediante gráficos interactivos y gestionar una base de datos local de manera eficiente.

---

## Características Principales

* **Scraping automatizado:** Recolección programada de datos desde diversas tiendas especializadas en modelos Gunpla.
* **Gestión de historial:** Almacenamiento persistente en SQLite de todos los precios capturados a lo largo del tiempo.
* **Visualización de datos:** Gráficos de tendencias generados dinámicamente con *Chart.js* para analizar la fluctuación de costos.
* **Interfaz web intuitiva:** Plataforma construida en *Flask* que permite buscar, filtrar y explorar el historial de cada modelo.
* **Ordenamiento flexible:** Clasificación de productos por precio (ascendente o descendente) para identificar oportunidades de compra rápidamente.
* **Acceso directo:** Navegación integrada hacia la página original del producto para una consulta inmediata.

---

## 🛠 Tecnologías Utilizadas

| Tecnología | Descripción |
| :--- | :--- |
| **Python** | Lenguaje de desarrollo principal. |
| **Flask** | Framework web ligero para el servidor. |
| **BeautifulSoup4** | Extracción y parseo de datos HTML. |
| **SQLite3** | Base de datos relacional para el historial. |
| **APScheduler** | Planificador para la ejecución periódica del proceso. |
| **Chart.js** | Biblioteca JS para la renderización de gráficos. |

---

## Estructura del Proyecto

* **`app.py`**: Archivo central que orquestra la lógica de la aplicación, las rutas de la interfaz web y la configuración del planificador de tareas.
* **`precios_comunidad.db`**: Base de datos SQLite (generada automáticamente al iniciar).

---

## Nota de Uso
Este proyecto ha sido desarrollado con fines educativos y de análisis personal. Se recomienda a los usuarios respetar las políticas de uso de los sitios web objetivo y no saturar sus servidores con peticiones excesivas. El script incluye un time.sleep entre páginas para asegurar un comportamiento respetuoso con el tráfico de red.
