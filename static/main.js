(function () {
  'use strict';

  function initNav() {
    var toggle = document.getElementById('navToggle');
    var nav = document.getElementById('siteNav');
    if (!toggle || !nav) return;

    function close() {
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    }

    function open() {
      nav.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
    }

    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      if (nav.classList.contains('is-open')) close(); else open();
    });

    document.addEventListener('click', function (e) {
      if (nav.classList.contains('is-open') && !nav.contains(e.target)) close();
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 860) close();
    });
  }

  function initFlash() {
    var box = document.querySelector('.flash-messages');
    if (!box) return;

    Array.prototype.forEach.call(box.querySelectorAll('.alert'), function (alert) {
      window.setTimeout(function () {
        alert.classList.remove('flash-enter');
        alert.classList.add('flash-exit');
        window.setTimeout(function () {
          if (alert.parentNode) alert.remove();
          if (box.children.length === 0) box.remove();
        }, 400);
      }, 6000);
    });
  }

  // Konfirmasi untuk aksi merusak (hapus sumber / kata kunci).
  function initConfirm() {
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.confirm(form.dataset.confirm)) e.preventDefault();
      });
    });

    document.querySelectorAll('button[data-confirm]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        if (!window.confirm(btn.dataset.confirm)) {
          e.preventDefault();
          e.stopPropagation();
        }
      });
    });
  }

  // Cegah klik ganda pada tombol submit, tanpa merusak form yang di-handle JS.
  function initSubmitGuard() {
    document.querySelectorAll('form').forEach(function (form) {
      if (form.hasAttribute('data-no-guard')) return;
      form.addEventListener('submit', function () {
        var btn = form.querySelector('button[type="submit"]');
        if (!btn) return;
        window.setTimeout(function () {
          btn.disabled = true;
          btn.setAttribute('aria-busy', 'true');
        }, 0);
      });
    });
  }

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(function () {
    initNav();
    initFlash();
    initConfirm();
    initSubmitGuard();
  });
})();
