document.addEventListener('DOMContentLoaded', function () {
    var l = document.getElementById('page-loader');
    if (l) { l.classList.add('done'); setTimeout(function () { l.remove(); }, 400); }

    var sidebar = document.getElementById('mainSidebar');
    var toggleBtn = document.getElementById('sidebarToggle');
    var toggleIcon = document.getElementById('toggleIcon');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            if (toggleIcon) {
                toggleIcon.className = sidebar.classList.contains('collapsed')
                    ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
            }
        });
    }

    var mobileBtn = document.getElementById('mobileMenuBtn');
    if (mobileBtn && sidebar) {
        mobileBtn.addEventListener('click', function () {
            sidebar.classList.toggle('show-mobile');
        });
        document.addEventListener('click', function (e) {
            if (sidebar.classList.contains('show-mobile') &&
                !sidebar.contains(e.target) &&
                !mobileBtn.contains(e.target)) {
                sidebar.classList.remove('show-mobile');
            }
        });
    }

    document.querySelectorAll('.nav-section .collapse').forEach(function (c) {
        var hasActive = c.querySelector('.nav-link.active');
        if (hasActive) {
            c.classList.add('show');
            var toggle = c.closest('.nav-section').querySelector('.nav-section-toggle');
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
        }
    });
});
