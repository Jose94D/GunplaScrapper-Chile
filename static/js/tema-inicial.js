// Se carga en el <head>, sin defer, para aplicar las preferencias antes de dibujar la página (sin parpadeo).
// Va en un archivo y no dentro del HTML porque la CSP del sitio no permite scripts en línea.
(function () {
    var guardado = function (clave) {
        try { return localStorage.getItem(clave); } catch (e) { return null; }
    };
    // Tema: oscuro salvo que el visitante haya elegido claro.
    // data-theme lo usan nuestros estilos y data-bs-theme los componentes de Bootstrap.
    if (guardado('theme') === 'light') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
    // Vista del catálogo del inicio, para que no salte de cuadrícula a lista
    document.documentElement.dataset.vista = guardado('vista') === 'lista' ? 'lista' : 'grilla';
})();
