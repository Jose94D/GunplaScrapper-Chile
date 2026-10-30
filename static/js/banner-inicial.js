// Banner del tema antes de que se dibuje (se carga justo después del banner); main.js lo actualiza al alternar
(function () {
    var b = document.getElementById('main-banner');
    if (b && !document.documentElement.dataset.theme) b.src = b.dataset.srcLight;
})();
