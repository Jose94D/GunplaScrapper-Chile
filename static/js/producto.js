document.addEventListener('DOMContentLoaded', () => {
    const fechas = JSON.parse(document.getElementById('datos-fechas').textContent);   // ['12/09/2026', ...]
    const series = JSON.parse(document.getElementById('datos-datasets').textContent);
    const mejorTienda = document.querySelector('script[data-mejor-tienda]').dataset.mejorTienda;

    const variable = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

    // La tienda con el mejor precio va en dorado; las demás, en colores que se distinguen también por luminosidad
    // y con trazos distintos, para que dos tiendas con el mismo precio no queden una encima de la otra
    const otros = ['#5AB0FF', '#E879C6', '#7DD3A8', '#A78BFA', '#F27A5E'];
    const trazos = [[], [7, 5], [2, 4]];
    let siguiente = 0;
    series.forEach((s) => {
        const mejor = s.label === mejorTienda;
        if (!mejor) s.borderDash = trazos[siguiente % trazos.length];
        s.borderColor = mejor ? variable('--acento') : otros[siguiente++ % otros.length];
        s.backgroundColor = s.borderColor;
        s.borderWidth = mejor ? 3 : 2;
        s.pointRadius = 3;
        s.pointHoverRadius = 5;
        s.tension = 0.25;
        s.completo = s.data;
    });

    const pesos = (v) => '$' + Math.round(v).toLocaleString('es-CL');
    const grafico = new Chart(document.getElementById('graficoPrecios'), {
        type: 'line',
        data: { labels: fechas, datasets: series },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 8, font: { family: 'IBM Plex Sans' } } },
                tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.raw == null ? 'sin dato' : pesos(c.raw)}` } }
            },
            scales: {
                x: { ticks: { font: { family: 'IBM Plex Mono', size: 11 }, maxRotation: 0, autoSkip: true }, grid: { display: false } },
                y: { beginAtZero: false, ticks: { font: { family: 'IBM Plex Mono', size: 11 }, callback: pesos }, grid: {} }
            }
        }
    });

    // Colores de texto y líneas guía según el tema; se repite al alternarlo
    const aplicarColores = () => {
        const o = grafico.options;
        o.plugins.legend.labels.color = variable('--texto-suave');
        o.scales.x.ticks.color = o.scales.y.ticks.color = variable('--texto-tenue');
        o.scales.y.grid.color = variable('--borde');
        grafico.update('none');
    };
    aplicarColores();
    document.addEventListener('temacambiado', aplicarColores);

    // --- Rango: últimos 30 o 90 días, o todo el historial ---
    const aFecha = (texto) => { const [d, m, a] = texto.split('/'); return new Date(+a, m - 1, +d); };
    const botones = document.querySelectorAll('.rango button');
    botones.forEach((boton) => boton.addEventListener('click', () => {
        const dias = Number(boton.dataset.dias);
        const desde = dias ? Date.now() - dias * 86400000 : -Infinity;
        let inicio = fechas.findIndex((f) => aFecha(f).getTime() >= desde);
        if (inicio === -1) inicio = Math.max(fechas.length - 1, 0);  // sin escaneos en el rango: el último día conocido
        grafico.data.labels = fechas.slice(inicio);
        series.forEach((s) => { s.data = s.completo.slice(inicio); });
        grafico.update();
        botones.forEach((b) => b.setAttribute('aria-pressed', String(b === boton)));
    }));

    // --- Copiar el enlace de la ficha ---
    const copiar = document.getElementById('copiar-enlace');
    if (copiar && navigator.clipboard) {
        copiar.addEventListener('click', async () => {
            const texto = copiar.querySelector('span');
            try {
                await navigator.clipboard.writeText(document.querySelector('link[rel="canonical"]').href);
                texto.textContent = 'Enlace copiado';
            } catch (e) {
                texto.textContent = 'No se pudo copiar';
            }
            setTimeout(() => { texto.textContent = 'Copiar enlace'; }, 2000);
        });
    } else if (copiar) {
        copiar.hidden = true;
    }
});
