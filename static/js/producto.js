document.addEventListener('DOMContentLoaded', () => {
    const rawFechas = document.getElementById('datos-fechas').textContent;
    const rawDatasets = document.getElementById('datos-datasets').textContent;
    
    const chartFechas = JSON.parse(rawFechas);
    const chartDatasets = JSON.parse(rawDatasets);

    const isDark = localStorage.getItem('theme') === 'dark';
    Chart.defaults.color = isDark ? '#94a3b8' : '#64748b';
    Chart.defaults.borderColor = isDark ? '#334155' : '#e2e8f0';
    
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
            plugins: { 
                legend: { display: true, labels: { color: isDark ? '#f8fafc' : '#1e293b' } } 
            }, 
            scales: { y: { beginAtZero: false } } 
        }
    });
});