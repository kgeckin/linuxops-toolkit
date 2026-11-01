/* LinuxOps dashboard: no external JS, trackers, cookies, or remote requests. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = { current: null, history: [], live: [], health: null, alerts: [], range: 60, auto: true, mode: 'live', section: 'overview', lastSeen: 0, liveInterval: 2, connection: 'connecting' };
  const LIVE_LIMIT = 120; // at 2 seconds, ~4 minutes of browser-only fine-resolution data
  const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
  const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
  const sections = {
    overview: ['System overview', 'A measured view of local Linux health, utilization and operating context.'],
    compute: ['Compute & memory', 'Processor load, memory utilization and Linux kernel load averages.'],
    storage: ['Storage analysis', 'Filesystem capacity, allocation and utilization over time.'],
    network: ['Network telemetry', 'Traffic counters and derived transfer rates from successive samples.'],
    alerts: ['Policy observations', 'Current threshold violations with clear, reproducible rules.'],
    about: ['How LinuxOps works', 'A transparent local monitoring architecture with privacy-first boundaries.']
  };
  const text = (id, value) => { const el = $(id); if (el) el.textContent = String(value); };
  const pct = val => Number.isFinite(Number(val)) ? number.format(Number(val)) + '%' : '—';
  const fmt = val => Number.isFinite(Number(val)) ? number.format(Number(val)) : '—';
  const bytes = val => {
    const n = Number(val);
    if (!Number.isFinite(n) || n < 0) return '—';
    for (const [divisor, unit] of [[1e12, 'TB'], [1e9, 'GB'], [1e6, 'MB'], [1e3, 'KB']]) {
      if (n >= divisor) return number.format(n / divisor) + ' ' + unit;
    }
    return Math.round(n) + ' B';
  };
  const when = (ts, seconds = false) => { const date = new Date(ts); return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}) }); };
  const setBar = (id, value) => { $(id).style.width = Math.max(0, Math.min(100, Number(value) || 0)) + '%'; };
  const setDonut = (id, value) => { $(id).style.setProperty('--usage', Math.max(0, Math.min(100, Number(value) || 0)) + '%'); };

  const plotPoints = () => state.mode === 'live' ? state.live : state.history;

  function selectView(name) {
    if (!Object.hasOwn(sections, name)) return;
    state.section = name;
    for (const [key, button] of Object.entries(Object.fromEntries([...document.querySelectorAll('[data-view]')].map(el => [el.dataset.view, el])))) {
      const active = key === name;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
      $('screen-' + key).hidden = !active;
    }
    text('view-title', sections[name][0]);
    text('view-subtitle', sections[name][1]);
    text('crumb', sections[name][0]);
    window.location.hash = name;
    drawAll();
  }

  const lineSVG = (points, field, mode = 'percent', themeColor = 'var(--blue)') => {
    if (!points.length) return '<p class="chart-empty">Collecting readings. Live samples appear as they arrive.</p>';
    const width = 650, height = 250, left = 52, top = 17, plotW = 578, plotH = 191;
    const series = points.map((p, index) => ({
      value: Math.max(0, Number(field(p, index, points)) || 0),
      time: p.timestamp,
    }));
    const maxObserved = Math.max(0, ...series.map(x => x.value));
    const ceiling = mode === 'percent' ? 100 : Math.max(1, Math.ceil(maxObserved * 1.22));
    const y = v => top + plotH - Math.min(1, v / ceiling) * plotH;
    const x = i => left + (series.length === 1 ? plotW / 2 : i * plotW / (series.length - 1));
    const line = series.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
    const fill = line + ` L${x(series.length - 1).toFixed(1)},${(top + plotH).toFixed(1)} L${x(0).toFixed(1)},${(top + plotH).toFixed(1)} Z`;
    const ticks = [0, .25, .5, .75, 1].map(t => {
      const yy = top + plotH - t * plotH;
      const label = mode === 'percent' ? Math.round(100 * t) + '%' : (ceiling * t < 1000 ? fmt(ceiling * t) : compact.format(ceiling * t));
      return `<line x1="${left}" y1="${yy}" x2="${left + plotW}" y2="${yy}" class="axis-grid"/><text x="${left - 11}" y="${yy + 4}" text-anchor="end" class="axis-text">${label}</text>`;
    }).join('');
    const markers = [0, Math.floor((series.length - 1) / 2), series.length - 1].filter((v, i, arr) => arr.indexOf(v) === i).map(i => `<text x="${x(i)}" y="${height - 11}" text-anchor="middle" class="axis-text">${when(series[i].time, state.mode === 'live')}</text>`).join('');
    const dot = series.length === 1 ? `<circle cx="${x(0)}" cy="${y(series[0].value)}" r="5" fill="${themeColor}"/>` : '';
    const latest = series[series.length - 1];
    const safeTitle = `Latest: ${fmt(latest.value)}${mode === 'percent' ? '%' : ' B/s'}`;
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${safeTitle}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"><title>${safeTitle}</title><defs><linearGradient id="fill-${mode}-${themeColor.includes('teal') ? 'teal' : 'blue'}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${themeColor}" stop-opacity=".29"/><stop offset="1" stop-color="${themeColor}" stop-opacity="0"/></linearGradient></defs>${ticks}<path d="${fill}" fill="${themeColor}" opacity=".12"/><path d="${line}" stroke="${themeColor}" class="plot-line"/>${dot}${markers}</svg>`;
  };

  function drawLine(id, metric, mode, color) {
    const node = $(id);
    if (!node) return;
    node.innerHTML = lineSVG(plotPoints(), metric, mode, color);
  }

  function netRate(points, i, key) {
    const current = points[i];
    const measured = key === 'bytes_received' ? current.network.rx_bytes_per_sec : current.network.tx_bytes_per_sec;
    if (measured != null && Number.isFinite(measured)) return measured;
    if (!i) return 0;
    const previous = points[i - 1];
    const elapsed = (Date.parse(current.timestamp) - Date.parse(previous.timestamp)) / 1000;
    if (!Number.isFinite(elapsed) || elapsed <= 0) return 0;
    const delta = current.network[key] - previous.network[key];
    return Math.max(0, delta) / elapsed;
  }

  function spark() {
    const points = plotPoints().slice(-20);
    if (points.length < 2) return;
    const d = points.map((p, i) => `${i ? 'L' : 'M'}${i * 100 / (points.length - 1)},${33 - p.cpu.percent / 100 * 30}`).join(' ');
    $('spark-cpu').innerHTML = `<svg viewBox="0 0 100 36" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--teal)" stroke-width="3" stroke-linecap="round"/></svg>`;
  }

  function drawAll() {
    // Only redraw the visible charts, not all six SVG graphs every two seconds.
    const cpu = p => p.cpu.percent, memory = p => p.memory.percent, disk = p => p.disk.percent;
    switch (state.section) {
      case 'overview':
        drawLine('cpu-chart', cpu, 'percent', 'var(--blue)');
        spark();
        text('cpu-points', plotPoints().length + (state.mode === 'live' ? ' live readings' : ' archived readings'));
        break;
      case 'compute':
        drawLine('cpu-detail-chart', cpu, 'percent', 'var(--blue)');
        drawLine('memory-detail-chart', memory, 'percent', 'var(--teal)');
        break;
      case 'storage':
        drawLine('disk-chart', disk, 'percent', 'var(--gold)');
        break;
      case 'network':
        drawLine('rx-chart', (p, i, a) => netRate(a, i, 'bytes_received'), 'rate', 'var(--teal)');
        drawLine('tx-chart', (p, i, a) => netRate(a, i, 'bytes_sent'), 'rate', 'var(--blue)');
        break;
      default: break;
    }
  }

  function renderAlerts() {
    const target = $('alerts-list');
    target.replaceChildren();
    const alerts = state.alerts;
    text('alerts-active', alerts.length);
    text('nav-alert-count', alerts.length);
    if (!alerts.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-alerts';
      const glyph = document.createElement('span'); glyph.textContent = '✓';
      const title = document.createElement('strong'); title.textContent = 'No threshold violations';
      const sub = document.createElement('p'); sub.textContent = 'Current local values are below the configured health thresholds.';
      empty.append(glyph, title, sub); target.append(empty);
      return;
    }
    for (const alert of alerts) {
      const row = document.createElement('div'); row.className = 'alert-entry';
      const mark = document.createElement('span'); mark.className = 'alert-mark'; mark.textContent = '◇';
      const center = document.createElement('div');
      const title = document.createElement('strong'); title.textContent = alert.message;
      const subtitle = document.createElement('small'); subtitle.textContent = 'Latest reading · ' + when(alert.timestamp);
      center.append(title, subtitle);
      const badge = document.createElement('span'); badge.className = 'alert-badge ' + (alert.severity === 'critical' ? 'critical' : ''); badge.textContent = alert.severity.toUpperCase();
      row.append(mark, center, badge); target.append(row);
    }
  }

  function render() {
    const sample = state.current;
    if (!sample) return;
    text('cpu-now', pct(sample.cpu.percent)); text('memory-now', pct(sample.memory.percent));
    text('disk-now', pct(sample.disk.percent)); text('uptime-now', Math.floor(sample.uptime_seconds / 3600) + 'h ' + Math.floor(sample.uptime_seconds % 3600 / 60) + 'm');
    text('cores', sample.cpu.logical_cores); text('compute-cores', sample.cpu.logical_cores);
    text('memory-used', bytes(sample.memory.used_bytes)); text('memory-total', bytes(sample.memory.total_bytes));
    text('disk-used', bytes(sample.disk.used_bytes)); text('disk-total', bytes(sample.disk.total_bytes));
    text('disk-mount', sample.disk.mount); text('disk-detail-used', bytes(sample.disk.used_bytes)); text('disk-detail-free', bytes(sample.disk.free_bytes));
    text('memory-ring-value', pct(sample.memory.percent)); text('memory-ring-used', bytes(sample.memory.used_bytes));
    text('memory-free', bytes(Math.max(0, sample.memory.total_bytes - sample.memory.used_bytes)));
    text('swap-used', bytes(sample.memory.swap_used_bytes)); text('disk-ring-value', pct(sample.disk.percent));
    text('load1', sample.cpu.load_1m); text('load5', sample.cpu.load_5m); text('load15', sample.cpu.load_15m);
    text('rx-total', bytes(sample.network.bytes_received)); text('tx-total', bytes(sample.network.bytes_sent));
    text('rx-rate-now', sample.network.rx_bytes_per_sec == null ? 'Measuring…' : bytes(sample.network.rx_bytes_per_sec) + '/s');
    text('tx-rate-now', sample.network.tx_bytes_per_sec == null ? 'Measuring…' : bytes(sample.network.tx_bytes_per_sec) + '/s');
    text('packets-rx', compact.format(sample.network.packets_received)); text('packets-tx', compact.format(sample.network.packets_sent));
    text('cpu-health', pct(sample.cpu.percent)); text('memory-health', pct(sample.memory.percent)); text('disk-health', pct(sample.disk.percent));
    text('sample-age', state.health ? state.health.age_seconds + ' seconds ago' : '—');
    setDonut('memory-donut', sample.memory.percent); setDonut('disk-donut', sample.disk.percent);
    setBar('memory-bar', sample.memory.percent); setBar('disk-bar', sample.disk.percent);
    const status = state.health?.status || 'waiting';
    const label = $('health-status'); label.className = 'health-pill ' + status;
    label.textContent = status.toUpperCase();
    text('context-label', sample.context === 'container' ? 'CONTAINER DATA' : 'LINUX ENVIRONMENT');
    text('updated', 'Measured ' + when(sample.timestamp, true));
    renderAlerts();
    if (state.mode === 'live') drawAll();
  }

  async function getJSON(path) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const response = await fetch(path, { signal: controller.signal, headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  function updateConnection() {
    const label = $('live-indicator');
    const name = label.querySelector('span');
    const age = state.current ? Math.max(0, Math.round((Date.now() - Date.parse(state.current.timestamp)) / 1000)) : null;
    if (age !== null) text('sample-age', age + ' seconds ago');
    const stale = age !== null && age > Math.max(10, state.liveInterval * 4);
    let title = 'CONNECTING';
    if (!state.auto) title = 'DISPLAY PAUSED';
    else if (state.connection === 'connected' && !stale) title = 'LIVE · ' + state.liveInterval + ' SEC';
    else if (state.connection === 'reconnecting' || stale) title = 'RECONNECTING';
    else if (state.connection === 'waiting') title = 'AWAITING SAMPLE';
    name.textContent = title;
    label.classList.toggle('offline', title === 'RECONNECTING');
    label.classList.toggle('paused', !state.auto);
    text('mode-caption', state.mode === 'live' ? 'Live data · every ' + state.liveInterval + ' seconds' : 'Archived data · saved periodically');
    if (stale && state.auto && state.health) {
      $('health-status').textContent = 'STALE';
      $('health-status').className = 'health-pill stale';
    }
  }

  function acceptReading(payload) {
    const sample = payload.sample;
    if (!sample || !sample.timestamp || !sample.network) return;
    state.current = sample;
    state.health = payload.health;
    state.alerts = payload.health?.alerts || [];
    state.connection = 'connected';
    state.lastSeen = Date.now();
    const previous = state.live[state.live.length - 1];
    // Do not count replayed samples after reconnect as new chart data.
    if (!previous || previous.timestamp !== sample.timestamp) {
      state.live.push(sample);
      if (state.live.length > LIVE_LIMIT) state.live.splice(0, state.live.length - LIVE_LIMIT);
    }
    $('error').hidden = true;
    render();
    updateConnection();
  }

  async function refreshSnapshot() {
    const result = await getJSON('/api/v1/overview');
    if (result.ready && state.auto && state.connection !== 'connected') {
      acceptReading({ sample: result.sample, health: result.health });
    }
  }

  let archiveLoading = false;
  async function refreshHistory() {
    if (archiveLoading) return;
    archiveLoading = true;
    try {
      const response = await getJSON('/api/v1/history?minutes=' + state.range + '&limit=5000');
      state.history = response.points || [];
      if (state.mode === 'history') drawAll();
    } catch (error) {
      $('error').hidden = false;
      text('error-detail', 'Historical records cannot be loaded. Live measurements can still continue.');
    } finally {
      archiveLoading = false;
    }
  }

  let eventSource = null;
  let fallback = null;
  function stopLive() {
    if (eventSource) eventSource.close();
    eventSource = null;
    if (fallback) clearInterval(fallback);
    fallback = null;
  }
  function startLive() {
    stopLive();
    if (!state.auto || document.hidden) return;
    state.connection = 'connecting';
    updateConnection();
    if (typeof EventSource !== 'undefined') {
      eventSource = new EventSource('/api/v1/live');
      eventSource.addEventListener('reading', event => {
        try { acceptReading(JSON.parse(event.data)); } catch (error) { console.warn('Invalid live data received'); }
      });
      eventSource.addEventListener('status', () => { state.connection = 'waiting'; updateConnection(); });
      eventSource.onerror = () => { state.connection = 'reconnecting'; updateConnection(); };
    } else {
      // Compatibility fallback for clients without EventSource, never duplicates SSE.
      fallback = setInterval(async () => {
        try { await refreshSnapshot(); } catch { state.connection = 'reconnecting'; updateConnection(); }
      }, 2000);
      refreshSnapshot().catch(() => {});
    }
  }

  function exportCSV() {
    const points = plotPoints();
    if (!points.length) return;
    const rows = [['Timestamp','Context','CPU %','Memory %','Disk %','RX bytes','TX bytes'],...points.map(p=>[
      p.timestamp,p.context,p.cpu.percent,p.memory.percent,p.disk.percent,p.network.bytes_received,p.network.bytes_sent,
    ])];
    const quote = value => '"' + String(value ?? '').replaceAll('"','""').replace(/^[=+@-]/,"'$&") + '"';
    const csv = rows.map(row => row.map(quote).join(',')).join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'linuxops-telemetry.csv'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const nav = [...document.querySelectorAll('[data-view]')];
  nav.forEach(button => button.addEventListener('click', () => selectView(button.dataset.view)));
  $('refresh').addEventListener('click', () => {
    refreshSnapshot().catch(() => {
      $('error').hidden = false;
      text('error-detail', 'The local API is unavailable. Check linuxops serve.');
    });
    if (state.mode === 'history') refreshHistory();
  });
  $('range').addEventListener('change', event => { state.range = Number(event.target.value); refreshHistory(); });
  document.querySelectorAll('[data-chart-mode]').forEach(button => button.addEventListener('click', () => {
    state.mode = button.dataset.chartMode;
    document.querySelectorAll('[data-chart-mode]').forEach(b => {
      const selected = b === button;
      b.classList.toggle('selected', selected);
      b.setAttribute('aria-pressed', String(selected));
    });
    $('history-range').hidden = state.mode === 'live';
    if (state.mode === 'history') refreshHistory();
    drawAll(); updateConnection();
  }));
  $('export').addEventListener('click', exportCSV);
  $('auto-refresh').addEventListener('click', () => {
    state.auto = !state.auto;
    $('auto-refresh').textContent = state.auto ? 'Ⅱ' : '▶';
    $('auto-refresh').title = state.auto ? 'Pause live display' : 'Resume live display';
    $('auto-refresh').setAttribute('aria-label', $('auto-refresh').title);
    startLive(); updateConnection();
  });
  const stored = (()=>{try{return localStorage.getItem('linuxops-theme')}catch{return null}})();
  document.documentElement.dataset.theme = stored === 'light' ? 'light' : 'dark';
  $('theme').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('linuxops-theme', next) } catch {}
    drawAll();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopLive();
    else if (state.auto) startLive();
  });
  window.addEventListener('beforeunload', stopLive);
  selectView(window.location.hash.replace('#','') || 'overview');
  updateConnection();
  startLive();
  // The first reading normally arrives directly through SSE without extra requests.
  refreshSnapshot().catch(() => {});
  setInterval(updateConnection, 1000);
  setInterval(() => {
    if (state.mode === 'history' && !document.hidden) refreshHistory();
  }, 60000);
})();
