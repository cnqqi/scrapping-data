(function () {
  'use strict';

  var logBox = document.getElementById('logBox');
  var startBtn = document.getElementById('startBtn');
  var pauseBtn = document.getElementById('pauseBtn');
  var pauseLabel = document.getElementById('pauseLabel');
  var stopBtn = document.getElementById('stopBtn');
  var progressBar = document.getElementById('progressBar');
  var statusEl = document.getElementById('stStatus');

  if (!logBox || !startBtn || !pauseBtn || !stopBtn) return;

  var lastId = 0;
  var polling = false;
  var timer = null;
  var startedAt = 0;
  var justStarted = false;

  // Setelah menekan Mulai, status "berjalan" bisa terlambat naik karena
  // penyiapan referensi menunggu jawaban Supabase. Selama masa ini polling
  // tetap jalan supaya catatan dari thread tidak terlewat.
  var START_GRACE_MS = 30000;

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setStatus(text, modifier) {
    if (!statusEl) return;
    statusEl.classList.remove('running', 'paused', 'stopping');
    if (modifier) statusEl.classList.add(modifier);
    statusEl.textContent = text;
  }

  function setPauseButton(paused, running) {
    pauseLabel.textContent = paused ? 'Lanjut' : 'Jeda';
    pauseBtn.classList.toggle('btn-warn', !paused);
    pauseBtn.classList.toggle('btn-ok', paused);
    pauseBtn.setAttribute('aria-pressed', paused ? 'true' : 'false');
    pauseBtn.title = running
      ? (paused ? 'Lanjutkan pencarian yang dijeda' : 'Jeda setelah lowongan yang sedang diproses selesai')
      : 'Pencarian tidak sedang berjalan';
  }

  function renderState(s) {
    setText('stStart', s.started_at ? s.started_at.slice(11) || s.started_at : '-');
    setText('stEnd', s.finished_at || '-');
    setText('stFound', s.jobs_found);
    setText('stInserted', s.jobs_inserted);
    setText('stProgress', s.total_combos ? s.done_combos + ' / ' + s.total_combos : '-');

    if (s.paused) setStatus('Dijeda', 'paused');
    else if (s.stop_requested) setStatus('Sedang berhenti', 'stopping');
    else if (s.running) setStatus('Berjalan', 'running');
    else if (s.finished_at) setStatus('Selesai', null);
    else setStatus('Belum mulai', null);

    var pct = s.total_combos ? Math.round((s.done_combos / s.total_combos) * 100) : 0;
    pct = Math.max(0, Math.min(100, pct));
    progressBar.style.width = pct + '%';
    setText('progressText', pct + '%');

    startBtn.disabled = !!s.running;
    startBtn.title = s.running ? 'Pencarian sedang berjalan' : 'Mulai mencari lowongan';

    pauseBtn.disabled = !s.running;
    stopBtn.disabled = !s.running || !!s.stop_requested;
    setPauseButton(!!s.paused, !!s.running);
  }

  function clearPlaceholder() {
    var ph = logBox.querySelector('.log-placeholder');
    if (ph) ph.remove();
  }

  function appendEvent(e) {
    clearPlaceholder();

    var line = document.createElement('div');
    if (e.level === 'hr') {
      line.className = 'log-line hr';
      line.textContent = '─'.repeat(40);
      logBox.appendChild(line);
      return;
    }

    line.className = 'log-line';

    var ts = document.createElement('span');
    ts.className = 'log-ts';
    ts.textContent = e.ts;

    var tx = document.createElement('span');
    tx.className = 'log-text ' + e.level;
    tx.textContent = e.text;

    line.appendChild(ts);
    line.appendChild(tx);
    logBox.appendChild(line);
  }

  function addLog(level, text) {
    appendEvent({
      level: level,
      ts: new Date().toLocaleTimeString('id-ID', { hour12: false }),
      text: text
    });
    scrollToBottom(true);
  }

  function atBottom() {
    return logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 90;
  }

  function scrollToBottom(force) {
    if (force || atBottom()) logBox.scrollTop = logBox.scrollHeight;
  }

  function schedule(ms) {
    window.clearTimeout(timer);
    timer = window.setTimeout(tick, ms);
  }

  async function tick() {
    if (!polling) return;

    var res;
    try {
      res = await fetch('/api/state?since=' + lastId, { cache: 'no-store' });
    } catch (err) {
      addLog('warn', 'Koneksi ke server terputus, mencoba lagi…');
      schedule(2500);
      return;
    }

    var data;
    try {
      data = await res.json();
    } catch (err) {
      schedule(2500);
      return;
    }

    lastId = data.last_id;
    renderState(data.state);

    if (data.events.length) {
      var events = data.events;
      if (events.length > 800) {
        var skipped = events.length - 800;
        events = events.slice(-800);
        appendEvent({
          level: 'warn',
          ts: '',
          text: '… ' + skipped + ' catatan awal dipotong agar halaman tetap ringan.'
        });
      }
      events.forEach(appendEvent);
      scrollToBottom(false);
    }

    if (data.state.running || data.state.paused || data.state.stop_requested) {
      schedule(1200);
    } else if (justStarted && Date.now() - startedAt < START_GRACE_MS) {
      // Thread baru saja diminta mulai; status mungkin belum menyatakan berjalan.
      schedule(600);
    } else {
      polling = false;
    }
  }

  async function post(url) {
    try {
      var res = await fetch(url, { method: 'POST' });
      return await res.json();
    } catch (err) {
      return { ok: false, error: 'Tidak bisa menghubungi server' };
    }
  }

  function beginPolling(isFreshStart) {
    if (isFreshStart) {
      lastId = 0;
      startedAt = Date.now();
      justStarted = true;
    }
    if (polling) return;
    polling = true;
    tick();
  }

  startBtn.addEventListener('click', async function () {
    startBtn.disabled = true;
    var data = await post('/api/scrape/start');
    if (data.ok) {
      beginPolling(true);
    } else {
      addLog('fail', data.error || 'Gagal memulai pencarian');
      startBtn.disabled = false;
      pauseBtn.disabled = true;
      stopBtn.disabled = true;
    }
  });

  pauseBtn.addEventListener('click', async function () {
    pauseBtn.disabled = true;
    var data = await post('/api/scrape/pause');
    if (!data.ok) {
      if (data.error) addLog('fail', data.error);
      pauseBtn.disabled = false;
      return;
    }
    tick();
  });

  stopBtn.addEventListener('click', async function () {
    var ok = window.confirm(
      'Yakin ingin BERHENTI?\n\n' +
      'Pencarian akan berhenti dan tidak dilanjutkan lagi.\n' +
      'Lowongan yang sedang dibaca tetap tersimpan.'
    );
    if (!ok) return;

    stopBtn.disabled = true;
    pauseBtn.disabled = true;
    var data = await post('/api/scrape/stop');
    if (!data.ok) {
      if (data.error) addLog('fail', data.error);
      stopBtn.disabled = false;
    }
    tick();
  });

  var copyBtn = document.getElementById('copyLog');
  if (copyBtn) {
    copyBtn.addEventListener('click', async function () {
      var text = Array.prototype.map.call(
        logBox.querySelectorAll('.log-line'),
        function (line) { return line.textContent; }
      ).join('\n');
      if (!text) {
        copyBtn.textContent = 'Belum ada';
        window.setTimeout(function () { copyBtn.textContent = 'Salin'; }, 1800);
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.textContent = 'Tersalin';
      } catch (err) {
        copyBtn.textContent = 'Gagal';
      }
      window.setTimeout(function () { copyBtn.textContent = 'Salin'; }, 1800);
    });
  }

  var clearBtn = document.getElementById('clearLog');
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      logBox.innerHTML = '';
      var ph = document.createElement('div');
      ph.className = 'log-placeholder';
      ph.textContent = 'Tampilan dibersihkan. Catatan baru akan tetap masuk dari sini.';
      logBox.appendChild(ph);
    });
  }

  // Ikuti status yang sedang berjalan, supaya tombol tidak stale setelah reload.
  fetch('/api/state?since=0', { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      renderState(data.state);
      if (data.state.running || data.state.paused || data.state.stop_requested) beginPolling(false);
    })
    .catch(function () { /* server belum siap, tombol tetap di status awal */ });
})();
