document.addEventListener('DOMContentLoaded', () => {
    const rawFechas = document.getElementById('datos-fechas').textContent;
    const rawDatasets = document.getElementById('datos-datasets').textContent;
    
    const chartFechas = JSON.parse(rawFechas);
    const chartDatasets = JSON.parse(rawDatasets);

    // Los colores salen de las variables CSS del tema: ambos temas tienen el contenedor oscuro
    const colorTema = (variable) => getComputedStyle(document.body).getPropertyValue(variable).trim();

    // Paleta de colores para las distintas líneas
    const colores = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
    
    chartDatasets.forEach((dataset, index) => {
        dataset.borderColor = colores[index % colores.length];
        dataset.backgroundColor = dataset.borderColor + '20';
        dataset.tension = 0.3;
        dataset.fill = true;
    });

    const ctx = document.getElementById('graficoPrecios').getContext('2d');
    window.myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartFechas,
            datasets: chartDatasets
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true, labels: {} } },
            scales: { x: { ticks: {}, grid: {} }, y: { beginAtZero: false, ticks: {}, grid: {} } }
        }
    });

    // Chart.js no hereda el color del gráfico en las escalas: se asigna a cada una
    const aplicarColores = () => {
        const opciones = window.myChart.options;
        opciones.plugins.legend.labels.color = colorTema('--text-main');
        for (const eje of [opciones.scales.x, opciones.scales.y]) {
            eje.ticks.color = colorTema('--text-muted');
            eje.grid.color = colorTema('--border-color');
        }
        window.myChart.update();
    };
    aplicarColores();

    // main.js cambia el tema antes que este listener (se carga primero), así que aquí ya están los colores nuevos
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', aplicarColores);
    }
});