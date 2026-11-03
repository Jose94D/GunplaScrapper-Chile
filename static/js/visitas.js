// Gráfico de visitas del panel: período (7 días … todo) y agrupación por día, semana o mes
document.addEventListener('DOMContentLoaded', () => {
    const datos = JSON.parse(document.getElementById('datos-visitas').textContent);
    const variable = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    const numero = (v) => Number(v).toLocaleString('es-CL');
    const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

    let dias = 30;
    let agrupar = 'dia';

    // Etiqueta del grupo de cada fecha 'dd/mm/aaaa': la misma fecha, el lunes de su semana o su mes
    const grupo = (texto) => {
        const [d, m, a] = texto.split('/').map(Number);
        if (agrupar === 'mes') return `${MESES[m - 1]} ${a}`;
        if (agrupar === 'semana') {
            const f = new Date(a, m - 1, d);
            f.setDate(f.getDate() - (f.getDay() + 6) % 7);
            return 'Sem. ' + f.toLocaleDateString('es-CL', { day: '2-digit', month: '2-digit' });
        }
        return texto.slice(0, 5);
    };

    const series = () => {
        const inicio = dias ? Math.max(datos.fechas.length - dias, 0) : 0;
        const etiquetas = [], visitas = [], paginas = [];
        datos.fechas.slice(inicio).forEach((fecha, i) => {
            const g = grupo(fecha);
            if (etiquetas[etiquetas.length - 1] !== g) { etiquetas.push(g); visitas.push(0); paginas.push(0); }
            visitas[visitas.length - 1] += datos.visitas[inicio + i];
            paginas[paginas.length - 1] += datos.paginas[inicio + i];
        });
        return { etiquetas, visitas, paginas };
    };

    const linea = (label, color, extra) => ({ label, data: [], borderColor: color, backgroundColor: color, borderWidth: 2,
                                               pointRadius: 3, pointHoverRadius: 5, tension: 0.25, ...extra });
    const grafico = new Chart(document.getElementById('graficoVisitas'), {
        type: 'line',
        data: { labels: [], datasets: [linea('Visitas', variable('--acento'), { borderWidth: 3 }),
                                       linea('Páginas vistas', '#5AB0FF', { borderDash: [7, 5] })] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 8, font: { family: 'IBM Plex Sans' } } },
                tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${numero(c.raw)}` } }
            },
            scales: {
                x: { ticks: { font: { family: 'IBM Plex Mono', size: 11 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }, grid: { display: false } },
                y: { beginAtZero: true, ticks: { font: { family: 'IBM Plex Mono', size: 11 }, precision: 0, callback: numero }, grid: {} }
            }
        }
    });

    const dibujar = () => {
        const s = series();
        grafico.data.labels = s.etiquetas;
        grafico.data.datasets[0].data = s.visitas;
        grafico.data.datasets[1].data = s.paginas;
        grafico.update();
        const t = datos.totales[dias];
        document.getElementById('total-visitas').textContent = numero(t.visitas);
        document.getElementById('total-personas').textContent = numero(t.personas);
        document.getElementById('total-paginas').textContent = numero(t.paginas);
    };

    const aplicarColores = () => {
        const o = grafico.options;
        o.plugins.legend.labels.color = variable('--texto-suave');
        o.scales.x.ticks.color = o.scales.y.ticks.color = variable('--texto-tenue');
        o.scales.y.grid.color = variable('--borde');
        grafico.data.datasets[0].borderColor = grafico.data.datasets[0].backgroundColor = variable('--acento');
        grafico.update('none');
    };

    const alternar = (selector, alElegir) => {
        const botones = document.querySelectorAll(selector);
        botones.forEach((boton) => boton.addEventListener('click', () => {
            alElegir(boton);
            botones.forEach((b) => b.setAttribute('aria-pressed', String(b === boton)));
            dibujar();
        }));
    };
    alternar('#visitas [data-dias]', (b) => { dias = Number(b.dataset.dias); });
    alternar('#visitas [data-agrupar]', (b) => { agrupar = b.dataset.agrupar; });

    aplicarColores();
    dibujar();
    document.addEventListener('temacambiado', aplicarColores);
});
