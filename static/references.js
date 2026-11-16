(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  /* ── Panel "Tambah Situs Baru" ─────────────────────────────────────── */
  function initAddSource() {
    var toggle = document.getElementById('addSourceToggle');
    var label = document.getElementById('addSourceLabel');
    var panel = document.getElementById('addSourcePanel');
    var close = document.getElementById('addSourceClose');
    if (!toggle || !panel) return;

    function setOpen(open) {
      panel.classList.toggle('hidden', !open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (label) label.textContent = open ? 'Batal Tambah' : 'Tambah Situs Baru';
      if (open) {
        var first = panel.querySelector('input[name="name"]');
        if (first) first.focus();
      }
    }

    toggle.addEventListener('click', function () {
      setOpen(panel.classList.contains('hidden'));
    });
    if (close) close.addEventListener('click', function () { setOpen(false); });
  }

  /* ── Buka / tutup formulir ubah per situs ──────────────────────────── */
  function initEditToggles() {
    document.querySelectorAll('.ref-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var panel = document.getElementById(btn.dataset.target);
        if (!panel) return;

        var opening = panel.classList.contains('hidden');

        // Hanya satu formulir ubah yang boleh terbuka sekaligus.
        document.querySelectorAll('.src-edit').forEach(function (other) {
          if (other === panel) return;
          other.classList.add('hidden');
          var owner = other.closest('.src');
          var ownerBtn = owner && owner.querySelector('.ref-toggle');
          if (ownerBtn) {
            ownerBtn.setAttribute('aria-expanded', 'false');
            ownerBtn.textContent = 'Ubah';
          }
        });

        panel.classList.toggle('hidden', !opening);
        btn.setAttribute('aria-expanded', opening ? 'true' : 'false');
        btn.textContent = opening ? 'Tutup' : 'Ubah';
        btn.classList.toggle('btn-primary', opening);

        if (opening) {
          panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          var first = panel.querySelector('input:not([type="hidden"]), select');
          if (first) first.focus({ preventScroll: true });
        }
      });
    });
  }

  /* ── Penyimpanan half jadi pada formulir ubah ───────────────────────── */
  function initDirtyTracking() {
    document.querySelectorAll('.src-edit').forEach(function (panel) {
      var form = panel.querySelector('.ref-edit-form, .ref-form');
      if (!form) return;

      var dirty = form.querySelector('.ref-dirty');
      var cancel = form.querySelector('.ref-cancel');
      var toggle = panel.closest('.src')
        ? panel.closest('.src').querySelector('.ref-toggle')
        : null;
      var touched = false;

      form.querySelectorAll('input, select, textarea').forEach(function (input) {
        input.addEventListener('input', function () {
          touched = true;
          if (dirty) dirty.classList.remove('hidden');
        });
        input.addEventListener('change', function () {
          touched = true;
          if (dirty) dirty.classList.remove('hidden');
        });
      });

      form.addEventListener('submit', function () {
        touched = false;
        if (dirty) dirty.classList.add('hidden');
      });

      function closePanel(skipConfirm) {
        if (touched && !skipConfirm &&
            !window.confirm('Perubahan belum disimpan. Tutup tanpa menyimpan?')) return;
        touched = false;
        if (dirty) dirty.classList.add('hidden');
        panel.classList.add('hidden');
        if (toggle) {
          toggle.setAttribute('aria-expanded', 'false');
          toggle.textContent = 'Ubah';
          toggle.classList.remove('btn-primary');
        }
      }

      if (cancel) cancel.addEventListener('click', function () { closePanel(false); });
    });
  }

  /* ── Field selector hanya untuk sumber Custom ───────────────────────── */
  function applyScraperMode(form) {
    var select = form.querySelector('[data-scraper-select]');
    var isCustom = !select || select.value === 'custom';

    form.querySelectorAll('[data-selector-only]').forEach(function (block) {
      block.classList.toggle('hidden', !isCustom);
      block.querySelectorAll('input, select, textarea').forEach(function (input) {
        input.required = isCustom;
      });
    });
  }

  function initScraperMode() {
    document.querySelectorAll('form').forEach(function (form) {
      if (!form.querySelector('[data-scraper-select]')) return;
      applyScraperMode(form);
      form.querySelector('[data-scraper-select]')
        .addEventListener('change', function () { applyScraperMode(form); });
    });
  }

  /* ── Pencarian / penyaringan daftar ─────────────────────────────────── */
  function initFilter(inputId, containerId, emptyId) {
    var input = document.getElementById(inputId);
    var container = document.getElementById(containerId);
    var empty = document.getElementById(emptyId);
    if (!input || !container || !empty) return;

    input.addEventListener('input', function () {
      var term = input.value.trim().toLowerCase();
      var items = container.querySelectorAll('[data-search]');
      var shown = 0;

      items.forEach(function (item) {
        var hit = (item.dataset.search || '').indexOf(term) !== -1;
        item.hidden = !hit;
        if (hit) shown++;
      });

      empty.classList.toggle('hidden', shown > 0);
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        input.value = '';
        input.dispatchEvent(new Event('input'));
      }
    });
  }

  function initFilters() {
    initFilter('sourceSearch', 'sourceBody', 'sourceEmpty');
    initFilter('keywordSearch', 'keywordList', 'keywordEmpty');
  }

  /* ── Uji satu sumber dengan satu kata kunci ─────────────────────────── */
  function initTester() {
    document.querySelectorAll('.src-test').forEach(function (form) {
      var out = form.nextElementSibling;
      var btn = form.querySelector('button[type="submit"]');
      if (!out || !btn) return;

      form.addEventListener('submit', async function (e) {
        e.preventDefault();

        var original = btn.textContent;
        out.className = 'ref-test-out';
        out.hidden = false;
        out.textContent = 'Menguji… biasanya 15–60 detik';
        btn.disabled = true;
        btn.textContent = '…';

        try {
          var res = await fetch(form.action, {
            method: 'POST',
            body: new URLSearchParams(new FormData(form))
          });
          var data = await res.json();
          renderTestResult(out, data, res.status);
        } catch (err) {
          out.className = 'ref-test-out fail';
          out.textContent = 'Gagal menghubungi server.';
        } finally {
          btn.disabled = false;
          btn.textContent = original;
        }
      });
    });
  }

  function renderTestResult(out, data, status) {
    if (!data || !data.ok) {
      out.className = 'ref-test-out fail';
      out.textContent = 'Gagal: ' + ((data && data.error) || ('HTTP ' + status));
      return;
    }

    out.className = 'ref-test-out ok';
    out.textContent = '';

    var head = document.createElement('div');
    head.className = 'result-head';
    var total = document.createElement('b');
    total.textContent = data.found + ' lowongan';
    head.appendChild(total);
    head.appendChild(document.createTextNode('untuk "' + (data.keyword || '') + '"'));
    out.appendChild(head);

    if (!data.preview || !data.preview.length) {
      var none = document.createElement('div');
      none.className = 'result-line';
      none.textContent = 'Tidak ada lowongan yang cocok. Coba kata kunci lain atau periksa selector.';
      out.appendChild(none);
      return;
    }

    data.preview.forEach(function (job) {
      var line = document.createElement('div');

      var link = document.createElement('a');
      link.href = job.url || '#';
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = job.title || '(tanpa judul)';
      line.appendChild(link);

      var meta = document.createElement('div');
      meta.className = 'result-line';
      meta.textContent = (job.company || '?') + ' · ' + (job.location || '?');
      line.appendChild(meta);

      out.appendChild(line);
    });
  }

  ready(function () {
    initAddSource();
    initScraperMode();
    initEditToggles();
    initDirtyTracking();
    initFilters();
    initTester();
  });
})();
