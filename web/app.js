/* ==========================================================================
   Forge Setup — frontend controller
   Talks to Python via window.pywebview.api.*, receives pushes on window.__push
   ========================================================================== */

const S = {
  apps: [],
  results: [],          // live winget repository search hits
  categories: [],
  presets: [],
  legend: [],
  installed: new Map(), // id_lower -> { version, available }
  selected: new Set(),
  status: {},           // id_lower -> { state, pct, detail }
  queue: [],            // [{ id, state }] mirrored from the engine
  view: 'browse',
  category: 'all',
  query: '',
  officialOnly: false,
  hideInstalled: false,
  upgradeOnly: false,
  history: [],
  running: false,
  paused: false,
  log: 'Idle',
  copied: false,
  theme: 'dark',
};

/* Sources Microsoft curates. Everything else is a user-added repository. */
const OFFICIAL = new Set(['winget', 'msstore']);

/* status -> [label, text colour, bar colour, weight toward run progress] */
const STATUS_META = {
  queued:      ['Queued',         'var(--t5)',        'var(--chip-line)', 0],
  downloading: ['Downloading',    'var(--t1)',        'var(--accent)',    0.4],
  verifying:   ['Verifying hash', 'var(--hue-amber)', 'var(--hue-amber)', 0.6],
  installing:  ['Installing',     'var(--hue-blue)',  'var(--hue-blue)',  0.8],
  installed:   ['Installed',      'var(--hue-green)', 'var(--hue-green)', 1],
  failed:      ['Failed',         'var(--err)',       'var(--err)',       1],
  skipped:     ['Skipped',        'var(--t5)',        'var(--chip-line)', 1],
};
const ACTIVE = new Set(['downloading', 'verifying', 'installing']);

const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt != null) n.textContent = txt;
  return n;
};

/* ── Python bridge ─────────────────────────────────────────────────── */
let apiReady = false;
const pending = [];

function api(method, ...args) {
  return new Promise((resolve, reject) => {
    const fire = () => {
      const fn = window.pywebview?.api?.[method];
      if (!fn) return reject(new Error(`API method "${method}" unavailable`));
      Promise.resolve(fn(...args)).then(resolve, reject);
    };
    apiReady ? fire() : pending.push(fire);
  });
}
window.addEventListener('pywebviewready', () => {
  apiReady = true;
  pending.splice(0).forEach((fn) => fn());
});

/* ══ Boot ═══════════════════════════════════════════════════════════ */
async function boot() {
  wireUI();
  applyTheme(localStorage.getItem('forge-theme') || 'dark');
  S.presets = loadBundles();

  let data;
  try {
    data = await api('bootstrap');
  } catch (err) {
    setEngine(false, 'Bridge down');
    log(`Failed to reach the Python backend: ${err.message}`, 'err');
    return;
  }

  S.apps = data.apps;
  S.categories = data.categories;
  S.legend = data.legend;
  S.presets = [...data.presets, ...loadBundles()];

  renderNav();
  renderLegend();
  renderTarget(data.system);

  setEngine(data.engine.available,
    data.engine.available ? `winget ${data.engine.version}`
                          : (data.engine.error ? 'Engine error' : 'Engine offline'));
  if (data.engine.available) {
    log(`winget ${data.engine.version} · ` +
        (data.engine.elevated ? 'elevated' : 'standard user'), 'sys');
    if (!data.engine.elevated) {
      log('Machine-wide packages will raise a UAC prompt. Relaunch as ' +
          'administrator to install them without prompting.', 'sys');
    }
  } else {
    toast(data.engine.error || 'winget is not available on this system.', 'err');
  }

  render();
  scanInstalled();
}

async function scanInstalled() {
  try {
    const map = await api('installed');
    S.installed = new Map(Object.entries(map));
    const known = S.apps.filter((a) => S.installed.has(a.id.toLowerCase())).length;
    log(`Installed scan: ${S.installed.size} packages known to winget, ` +
        `${known} of them in this catalog.`, 'sys');
    render();
  } catch (err) {
    log(`Installed scan failed: ${err.message}`, 'err');
  }
}

/* ══ Derived data ═══════════════════════════════════════════════════ */
function pool() { return [...S.apps, ...S.results]; }

function find(id) {
  const k = id.toLowerCase();
  return pool().find((a) => a.id.toLowerCase() === k)
      || { id, name: id, publisher: '', desc: '', size: 0, hue: 'var(--accent)',
           mark: '?', source: 'winget' };
}

function isInstalled(id) { return S.installed.has(id.toLowerCase()); }
function isUpgradeable(id) {
  const rec = S.installed.get(id.toLowerCase());
  return !!(rec && rec.available && rec.available !== '-');
}
function isOfficial(app) { return OFFICIAL.has((app.source || '').toLowerCase()); }

function versionOf(app) {
  const rec = S.installed.get(app.id.toLowerCase());
  return (rec && rec.version) || app.version || '';
}

function appTile(cls, app) {
  const tile = el('div', cls);
  if (!app.icon) {
    tile.textContent = app.mark || '?';
    return tile;
  }
  const icon = document.createElement('img');
  icon.className = 'app-icon';
  icon.src = app.icon;
  icon.alt = `${app.name} icon`;
  icon.onerror = () => {
    icon.remove();
    tile.textContent = app.mark || '?';
    tile.classList.add('icon-fallback');
  };
  tile.append(icon);
  return tile;
}

function visible() {
  const q = S.query.trim().toLowerCase();
  const match = (a) => {
    if (S.officialOnly && !isOfficial(a)) return false;
    if (S.hideInstalled && isInstalled(a.id)) return false;
    if (S.upgradeOnly && !isUpgradeable(a.id)) return false;
    if (q) {
      return (`${a.name} ${a.id} ${a.publisher} ${a.desc}`).toLowerCase().includes(q);
    }
    return S.category === 'all' || a.category === S.category;
  };
  return S.apps.filter(match);
}

function extraResults() {
  if (!S.query.trim()) return [];
  const known = new Set(S.apps.map((a) => a.id.toLowerCase()));
  return S.results.filter((r) => {
    if (known.has(r.id.toLowerCase())) return false;
    if (S.officialOnly && !isOfficial(r)) return false;
    if (S.hideInstalled && isInstalled(r.id)) return false;
    return true;
  });
}

/* ══ Rendering ══════════════════════════════════════════════════════ */
function renderNav() {
  const nav = $('catNav');
  nav.replaceChildren();
  S.categories.forEach((cat) => {
    const n = el('button', 'cat' + (cat.id === S.category ? ' on' : ''));
    n.style.borderLeftColor = cat.id === S.category ? cat.hue : 'transparent';

    const dot = el('span', 'cat-dot');
    dot.style.background = cat.hue;
    const count = cat.id === 'all'
      ? S.apps.length
      : S.apps.filter((a) => a.category === cat.id).length;

    n.append(dot, el('span', 'cat-name', cat.label), el('span', 'cat-count', String(count)));
    n.onclick = () => {
      S.category = cat.id;
      $('search').value = '';
      S.query = '';
      S.results = [];
      $('clearQuery').hidden = true;
      renderNav();
      render();
      $('gridScroll').scrollTop = 0;
    };
    nav.append(n);
  });
}

function renderLegend() {
  const box = $('legend');
  box.replaceChildren();
  S.legend.forEach((l) => {
    const item = el('div', 'legend-item');
    const chip = el('span', 'legend-chip');
    chip.style.background = l.hue;
    item.append(chip, el('span', 'legend-name', l.name));
    box.append(item);
  });
}

function renderTarget(sys) {
  if (!sys) return;
  $('target').innerHTML = '';
  const lines = [
    sys.target,
    `${sys.os}${sys.build ? ' · ' + sys.build : ''}`,
    `Silent install · on`,
    sys.elevated ? 'Elevated · yes' : 'Elevated · no',
  ];
  lines.forEach((t, i) => {
    if (i) $('target').append(document.createElement('br'));
    $('target').append(document.createTextNode(t));
  });
}

function renderBundles() {
  const box = $('bundles');
  box.replaceChildren();
  const selKey = [...S.selected].map((s) => s.toLowerCase()).sort().join('+');

  S.presets.forEach((p) => {
    const same = p.apps.map((s) => s.toLowerCase()).sort().join('+') === selKey;
    const n = el('button', 'bundle' + (same ? ' on' : ''));
    n.append(el('span', 'bundle-name', p.label),
             el('span', 'bundle-n', String(p.apps.length)));
    n.title = p.blurb || `${p.apps.length} packages`;
    n.onclick = () => {
      S.selected = new Set(p.apps.filter((id) => !isInstalled(id)));
      const skipped = p.apps.length - S.selected.size;
      toast(`${p.label} — ${S.selected.size} selected` +
            (skipped ? `, ${skipped} already installed` : '') + '.');
      render();
    };
    box.append(n);
  });
}

function render() {
  $('viewBrowse').hidden = S.view !== 'browse';
  $('viewInstall').hidden = S.view !== 'install';
  $('viewHistory').hidden = S.view !== 'history';
  $('ctaDock').hidden = S.view === 'history';

  if (S.view === 'browse') renderGrid();
  else if (S.view === 'install') renderQueue();
  else renderHistory();

  renderBundles();
  syncShare();
  syncCta();
}

function renderGrid() {
  const grid = $('grid');
  grid.replaceChildren();

  const local = visible();
  const extra = extraResults();
  local.forEach((a) => grid.append(card(a)));
  extra.forEach((a) => grid.append(card(a)));

  const total = local.length + extra.length;
  const cat = S.categories.find((c) => c.id === S.category);
  $('viewTitle').textContent = S.query.trim()
    ? `Search: ${S.query.trim()}`
    : (cat ? cat.label : 'All packages');
  // While searching, "of 45" would be nonsense: most hits come from the
  // repository, not the catalog. Report the two sources separately instead.
  $('viewCount').textContent = S.query.trim()
    ? `${local.length} in catalog · ${extra.length} in repository · ` +
      `${S.selected.size} selected`
    : `${total} of ${S.apps.length} packages · ${S.selected.size} selected`;

  grid.hidden = total === 0;
  $('empty').hidden = total > 0;
  $('emptyTitle').textContent = S.query.trim()
    ? `No packages match “${S.query.trim()}”`
    : 'No packages in this category';
}

function card(app) {
  const key = app.id.toLowerCase();
  const st = S.status[key] || {};
  const installed = isInstalled(app.id) || st.state === 'installed';
  const on = S.selected.has(app.id);
  const busy = ACTIVE.has(st.state) || st.state === 'queued';
  const hue = app.hue || 'var(--accent)';

  const c = el('button', 'card' + (on ? ' on' : '') + (busy ? ' busy' : ''));
  c.dataset.id = app.id;
  if (on) c.style.outlineColor = hue;

  /* top row: tile, name/version, checkbox */
  const top = el('div', 'card-top');

  const tile = appTile('tile', app);
  tile.style.outlineColor = on ? hue : 'var(--box-line)';
  tile.style.color = on ? hue : 'var(--t2)';

  const idBox = el('div', 'card-id');
  idBox.append(el('div', 'card-name', app.name));
  const meta = el('div', 'card-meta');
  const ver = versionOf(app);
  if (ver) {
    const chip = el('span', 'ver', `v${ver}`);
    if (on) { chip.style.color = hue; chip.style.borderColor = hue; }
    meta.append(chip);
  }
  if (app.size) meta.append(el('span', 'size', fmtSize(app.size)));
  if (installed) meta.append(el('span', 'ver installed', 'Installed'));
  if (isUpgradeable(app.id)) meta.append(el('span', 'ver update', `Update v${S.installed.get(key).available}`));
  idBox.append(meta);

  const box = el('div', 'box');
  box.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 6.5"/></svg>';
  if (on) { box.style.background = hue; box.style.borderColor = hue; }
  else if (installed) c.classList.add('installed');

  top.append(tile, idBox, box);
  c.append(top);

  c.append(el('div', 'card-blurb', app.desc));

  /* footer: source provenance, publisher, repository */
  const foot = el('div', 'card-foot');
  const official = isOfficial(app);
  const shield = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  shield.setAttribute('viewBox', '0 0 24 24');
  shield.innerHTML = '<path d="M12 3l7 3v6c0 4-3 7.5-7 9-4-1.5-7-5-7-9V6z"/>';
  shield.style.color = official ? 'var(--sig-ok)' : 'var(--err)';
  foot.append(shield);
  foot.append(el('span', `sig ${official ? 'ok' : 'warn'}`,
    official ? 'Official source' : 'Third-party source'));
  foot.append(el('span', 'vrule'));
  foot.append(el('span', 'pub', app.publisher || '—'));
  foot.append(el('span', 'src', app.source || 'winget'));
  c.append(foot);

  /* bottom state ribbon */
  const rail = el('div', 'card-state');
  const fill = el('div', 'card-state-fill');
  if (st.state) {
    const meta2 = STATUS_META[st.state];
    if (meta2) fill.style.background = meta2[2];
    if (st.state === 'installing' || (busy && st.pct == null)) fill.classList.add('pulse');
    else fill.style.width = `${st.pct || 0}%`;
  }
  rail.append(fill);
  c.append(rail);

  c.title = `${app.id}${st.detail ? '\n' + st.detail : ''}`;
  c.onclick = () => toggle(app);
  return c;
}

/* ── Install queue ─────────────────────────────────────────────────── */
function renderQueue() {
  const list = $('queueList');
  list.replaceChildren();
  S.queue.forEach((item, i) => list.append(queueRow(item, i)));

  const done = S.queue.filter((q) => q.state === 'installed').length;
  const failed = S.queue.filter((q) => q.state === 'failed').length;

  $('runTitle').textContent = S.running ? 'Installing'
    : S.paused ? 'Queue paused'
    : failed ? 'Finished with issues' : 'Install complete';
  $('runSubtitle').textContent =
    `${done} of ${S.queue.length} packages · ${failed} failed`;

  const pct = runPct();
  $('runPct').textContent = `${pct}%`;
  $('runFill').style.width = `${pct}%`;
  $('runLog').textContent = S.log || 'Idle';
  $('backToBrowse').textContent = S.running ? 'Pause queue' : 'Back to catalog';
}

function queueRow(item, i) {
  const app = find(item.id);
  const st = S.status[item.id.toLowerCase()] || {};
  const state = item.state === 'running' ? (st.state || 'downloading') : item.state;
  const meta = STATUS_META[state] || STATUS_META.queued;
  const active = ACTIVE.has(state);

  const row = el('div', 'qrow' + (state === 'queued' ? '' : ' active'));

  const tile = appTile('qtile', app);
  tile.style.outlineColor = state === 'failed' ? 'var(--err)'
    : state === 'installed' ? 'var(--hue-green)' : (app.hue || 'var(--accent)');
  row.append(tile);

  const idBox = el('div', 'qid');
  idBox.append(el('div', 'qname', app.name));
  const ver = versionOf(app);
  idBox.append(el('div', 'qver',
    `${ver ? 'v' + ver + ' · ' : ''}${app.size ? fmtSize(app.size) : app.id}`));
  row.append(idBox);

  const prog = el('div', 'qprog');
  const line = el('div', 'qstat');
  const label = el('span', 'qstat-label', meta[0]);
  label.style.color = meta[1];
  const detail = st.detail || (state === 'queued' ? `Waiting for slot ${i + 1}`
    : state === 'installed' ? 'Complete' : '');
  line.append(label, el('span', 'qstat-detail', detail));
  prog.append(line);

  const bar = el('div', 'qbar');
  const fill = el('div', 'qbar-fill');
  fill.style.background = meta[2];
  if (state === 'installing' || (active && st.pct == null)) fill.classList.add('pulse');
  else fill.style.width = `${state === 'queued' ? 0 : (st.pct ?? (meta[3] === 1 ? 100 : 0))}%`;
  bar.append(fill);
  prog.append(bar);
  row.append(prog);

  /* actions: reorder pending items, then the state-dependent button */
  const act = el('div', 'qact');
  if (state === 'queued') {
    const move = el('div', 'qmove');
    const up = el('button', 'qbtn');
    up.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 14l6-6 6 6"/></svg>';
    up.disabled = !canMove(i, -1);
    up.onclick = (e) => { e.stopPropagation(); api('queue_move', item.id, -1); };
    const down = el('button', 'qbtn');
    down.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 10l6 6 6-6"/></svg>';
    down.disabled = !canMove(i, 1);
    down.onclick = (e) => { e.stopPropagation(); api('queue_move', item.id, 1); };
    move.append(up, down);
    act.append(move);
  }

  const btn = el('button', 'qaction');
  if (state === 'failed' || state === 'skipped') {
    btn.textContent = state === 'failed' ? 'Retry' : 'Requeue';
    btn.classList.toggle('warn', state === 'failed');
    btn.onclick = () => api('queue_requeue', item.id).then(() => { S.paused = false; });
  } else if (state === 'installed') {
    btn.textContent = 'Log';
    btn.onclick = () => openConsole(true);
  } else if (active) {
    btn.textContent = 'Abort';
    btn.classList.add('warn');
    btn.onclick = () => {
      api('cancel');
      toast('Aborting the running install…', 'err');
    };
  } else {
    btn.textContent = 'Cancel';
    btn.onclick = () => api('queue_skip', item.id);
  }
  act.append(btn);
  row.append(act);
  return row;
}

function canMove(i, delta) {
  const j = i + delta;
  return j >= 0 && j < S.queue.length
      && S.queue[i].state === 'queued' && S.queue[j].state === 'queued';
}

function runPct() {
  if (!S.queue.length) return 0;
  const total = S.queue.reduce((t, q) => {
    const state = q.state === 'running'
      ? (S.status[q.id.toLowerCase()]?.state || 'downloading') : q.state;
    return t + (STATUS_META[state]?.[3] ?? 0);
  }, 0);
  return Math.round((total / S.queue.length) * 100);
}

/* ══ Selection ══════════════════════════════════════════════════════ */
function toggle(app) {
  if (S.view === 'install') return;
  if (isInstalled(app.id) && !(S.upgradeOnly && isUpgradeable(app.id))) {
    toast(`${app.name} is already installed.`);
    return;
  }
  S.selected.has(app.id) ? S.selected.delete(app.id) : S.selected.add(app.id);
  if (app.source && !S.apps.some((a) => a.id === app.id)
      && !S.results.some((r) => r.id === app.id)) {
    S.results.push(app);
  }
  S.copied = false;
  render();
}

function syncShare() {
  const key = [...S.selected].join('+');
  const input = $('shareInput');
  if (document.activeElement !== input) input.value = `forge://${key || 'empty'}`;

  const mb = [...S.selected].reduce((t, id) => t + (find(id).size || 0), 0);
  const unsized = [...S.selected].filter((id) => !find(id).size).length;
  $('shareMeta').textContent = S.selected.size
    ? `${fmtSize(mb)}${unsized ? ` · ${unsized} unsized` : ''} · est. ${estMinutes(mb)} min`
    : '0 MB';
  $('copyShare').textContent = S.copied ? 'Copied' : 'Copy';
}

function syncCta() {
  const n = S.selected.size;
  const btn = $('primary');

  if (S.view === 'install') {
    const done = S.queue.filter((q) => q.state === 'installed').length;
    const failed = S.queue.filter((q) => q.state === 'failed').length;
    $('ctaMeta').textContent =
      `${done} installed · ${failed} failed · ${S.queue.length} total`;
    $('ctaLabel').textContent = S.running ? 'Installing…'
      : S.paused ? 'Resume queue' : 'Finish';
    btn.disabled = S.running;
  } else {
    const names = [...S.selected].slice(0, 3).map((id) => find(id).name);
    $('ctaMeta').textContent = n
      ? names.join(' · ') + (n > 3 ? ` +${n - 3}` : '')
      : 'Nothing selected';
    $('ctaLabel').textContent = `${S.upgradeOnly ? 'Update' : 'Install'} Selected (${n})`;
    btn.disabled = n === 0;
  }
}

/* ══ Install run ════════════════════════════════════════════════════ */
async function startRun() {
  const ids = [...S.selected];
  if (!ids.length) return;
  const operation = S.upgradeOnly ? 'upgrade' : 'install';
  const completion = { kind: $('completionAction').value };
  if (completion.kind === 'script') {
    completion.script = $('completionScript').value.trim();
    if (!completion.script) return toast('Enter a PowerShell command first.', 'err');
    if (!confirm('Run this PowerShell command after the queue finishes?')) return;
  }
  try {
    const check = await api('preflight', ids,
      ids.reduce((sum, id) => sum + (find(id).size || 0), 0), operation);
    if (check.warnings?.length && !confirm(`Preflight checks:\n\n${check.warnings.join('\n')}\n\nContinue?`)) return;
  } catch (err) {
    return toast(`Preflight failed: ${err.message}`, 'err');
  }

  S.view = 'install';
  S.running = true;
  S.paused = false;
  S.log = 'Resolving packages…';
  S.queue = ids.map((id) => ({ id, state: 'queued' }));
  ids.forEach((id) => { S.status[id.toLowerCase()] = { state: 'queued', pct: 0 }; });
  render();

  try {
    const res = await api(operation, ids, completion);
    if (!res.ok) { toast(res.error, 'err'); S.running = false; render(); }
  } catch (err) {
    toast(`Could not start the run: ${err.message}`, 'err');
    S.running = false;
    render();
  }
}

function renderHistory() {
  const list = $('historyList');
  list.replaceChildren();
  $('historyCount').textContent = `${S.history.length} saved run${S.history.length === 1 ? '' : 's'}`;
  if (!S.history.length) {
    list.append(el('div', 'history-empty', 'No completed runs yet. Your completed installs and upgrades will appear here.'));
    return;
  }
  S.history.forEach((entry) => {
    const row = el('div', 'history-row');
    const top = el('div', 'history-top');
    const date = entry.at ? new Date(entry.at).toLocaleString() : 'Unknown time';
    top.append(el('strong', '', entry.operation === 'upgrade' ? 'Update run' : 'Install run'),
      el('span', 'history-date', date));
    const summary = entry.summary || {};
    row.append(top, el('div', 'history-summary',
      `${summary.installed || 0} completed · ${summary.failed || 0} failed · ${summary.skipped || 0} skipped`),
      el('div', 'history-items', (entry.items || []).map((item) => `${find(item.id).name} — ${item.state}`).join(' · ')));
    list.append(row);
  });
}

async function openHistory() {
  S.view = 'history';
  render();
  try { S.history = await api('history'); renderHistory(); }
  catch (err) { toast(`Could not read history: ${err.message}`, 'err'); }
}

function backToBrowse() {
  if (S.running) {
    api('queue_pause');
    S.log = 'Pausing after the current package…';
    toast('Queue will stop after the current package.');
    renderQueue();
  } else {
    S.view = 'browse';
    S.queue = [];
    S.paused = false;
    openConsole(false);
    render();
  }
}

/* ══ Events pushed from Python ══════════════════════════════════════ */
window.__push = function (ev) {
  if (ev.type === 'log') { log(ev.line, ev.stream, ev.t); return; }

  if (ev.type === 'status') {
    const key = ev.id.toLowerCase();
    S.status[key] = { state: ev.state, pct: ev.pct, detail: ev.detail };
    if (ev.state === 'installed') {
      if (!S.installed.has(key)) S.installed.set(key, { version: '', available: '' });
      S.selected.delete(ev.id);
    }
    if (S.view === 'install') renderQueue();
    else patchCard(ev.id);
    syncCta();
    return;
  }

  if (ev.type === 'queue') {
    S.queue = ev.items;
    if (S.view === 'install') renderQueue();
    return;
  }

  if (ev.type === 'queue_done') {
    S.running = false;
    S.paused = !!ev.paused;
    const s = ev.summary;
    S.log = ev.paused
      ? `Paused — ${s.pending} still queued.`
      : `Run finished — ${s.installed} installed, ${s.failed} failed.`;
    toast(S.log, s.failed ? 'err' : 'ok');
    render();
    scanInstalled();
  }
};

/* Repaint one card in place; a full grid re-render on every progress tick
   would thrash scroll position and hover state. */
function patchCard(id) {
  const old = $('grid').querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (old) old.replaceWith(card(find(id)));
}

/* ══ Console ════════════════════════════════════════════════════════ */
function log(line, kind = 'out', time) {
  const box = $('console');
  const n = el('div', `logline ${kind}`);
  n.append(el('span', 'ts', time || new Date().toTimeString().slice(0, 8)));
  n.append(document.createTextNode(line));
  box.append(n);
  while (box.children.length > 2000) box.firstChild.remove();
  box.scrollTop = box.scrollHeight;
}

function openConsole(force) {
  const box = $('console');
  const open = force ?? box.hidden;
  box.hidden = !open;
  $('toggleConsole').textContent = open ? 'Hide console' : 'Console';
  if (open) box.scrollTop = box.scrollHeight;
}

/* ══ Search ═════════════════════════════════════════════════════════ */
let searchTimer, searchSeq = 0;

function onSearch(value) {
  S.query = value;
  $('clearQuery').hidden = !value;
  render();

  clearTimeout(searchTimer);
  if (value.trim().length < 2) {
    S.results = S.results.filter((r) => S.selected.has(r.id));
    $('searchSpin').hidden = true;
    return;
  }

  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq;
    $('searchSpin').hidden = false;
    try {
      const hits = await api('search', value.trim());
      if (seq !== searchSeq) return;             // a newer query superseded this
      const keep = S.results.filter((r) => S.selected.has(r.id));
      const ids = new Set(hits.map((h) => h.id));
      S.results = [...hits, ...keep.filter((k) => !ids.has(k.id))];
      render();
    } catch (err) {
      log(`Search failed: ${err.message}`, 'err');
    } finally {
      if (seq === searchSeq) $('searchSpin').hidden = true;
    }
  }, 420);
}

/* ══ Bundles (user-saved, persisted locally) ════════════════════════ */
function loadBundles() {
  try { return JSON.parse(localStorage.getItem('forge-bundles') || '[]'); }
  catch { return []; }
}
function saveBundles(list) {
  localStorage.setItem('forge-bundles', JSON.stringify(list));
}

/* ══ Theme ══════════════════════════════════════════════════════════ */
function applyTheme(theme) {
  S.theme = theme;
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('forge-theme', theme);
}

/* ══ Wiring ═════════════════════════════════════════════════════════ */
function wireUI() {
  $('search').addEventListener('input', (e) => onSearch(e.target.value));
  $('clearQuery').onclick = () => { $('search').value = ''; onSearch(''); $('search').focus(); };

  $('officialOnly').onclick = (e) => {
    S.officialOnly = !S.officialOnly;
    e.currentTarget.setAttribute('aria-pressed', String(S.officialOnly));
    render();
  };
  $('hideInstalled').onclick = (e) => {
    S.hideInstalled = !S.hideInstalled;
    e.currentTarget.setAttribute('aria-pressed', String(S.hideInstalled));
    render();
  };
  $('upgradeOnly').onclick = (e) => {
    S.upgradeOnly = !S.upgradeOnly;
    if (S.upgradeOnly) S.hideInstalled = false;
    e.currentTarget.setAttribute('aria-pressed', String(S.upgradeOnly));
    $('hideInstalled').setAttribute('aria-pressed', String(S.hideInstalled));
    S.selected.clear();
    render();
  };
  $('selectAll').onclick = () => {
    [...visible(), ...extraResults()].forEach((a) => {
      if (!isInstalled(a.id) || (S.upgradeOnly && isUpgradeable(a.id))) S.selected.add(a.id);
    });
    S.copied = false;
    render();
  };
  $('clearAll').onclick = () => { S.selected.clear(); S.copied = false; render(); };
  $('resetFilters').onclick = () => {
    S.query = ''; S.officialOnly = false; S.hideInstalled = false; S.category = 'all';
    S.upgradeOnly = false;
    $('search').value = '';
    $('clearQuery').hidden = true;
    $('officialOnly').setAttribute('aria-pressed', 'false');
    $('hideInstalled').setAttribute('aria-pressed', 'false');
    $('upgradeOnly').setAttribute('aria-pressed', 'false');
    renderNav();
    render();
  };

  $('saveBundle').onclick = () => {
    const ids = [...S.selected];
    if (!ids.length) return toast('Select some packages first.', 'err');
    const mine = loadBundles();
    const label = `Bundle ${mine.length + 1}`;
    mine.push({ id: `user-${Date.now()}`, label, blurb: 'Saved selection', apps: ids });
    saveBundles(mine);
    S.presets = S.presets.filter((p) => !String(p.id).startsWith('user-')).concat(mine);
    toast(`Saved “${label}” — ${ids.length} packages.`, 'ok');
    render();
  };

  $('exportProfile').onclick = async () => {
    if (!S.selected.size) return toast('Select some packages first.', 'err');
    const res = await api('export_profile', 'Forge profile', [...S.selected]);
    if (res.ok) toast(`Exported ${res.count} apps.`, 'ok');
    else if (!res.cancelled) toast(res.error || 'Profile export failed.', 'err');
  };
  $('importProfile').onclick = async () => {
    const res = await api('import_profile');
    if (!res.ok) { if (!res.cancelled) toast(res.error || 'Profile import failed.', 'err'); return; }
    S.selected = new Set(res.apps.filter((id) => !isInstalled(id)));
    S.copied = false;
    toast(`${res.name} — ${S.selected.size} selected.`, 'ok');
    render();
  };
  $('showHistory').onclick = openHistory;
  $('closeHistory').onclick = () => { S.view = 'browse'; render(); };
  $('completionAction').onchange = (e) => { $('completionScript').hidden = e.target.value !== 'script'; };

  $('shareInput').addEventListener('input', (e) => {
    const raw = e.target.value.replace(/^forge:\/\//i, '').trim();
    if (raw === 'empty' || !raw) { S.selected.clear(); render(); return; }
    const ids = raw.split(/[+,\s]+/).filter(Boolean);
    // Accept any id winget might know; the catalog lookup only fixes casing.
    // Already-installed packages are dropped, matching card clicks and bundles.
    const resolved = ids.map((id) => {
      const hit = pool().find((a) => a.id.toLowerCase() === id.toLowerCase());
      return hit ? hit.id : id;
    });
    S.selected = new Set(resolved.filter((id) => !isInstalled(id)));
    const dropped = resolved.length - S.selected.size;
    S.copied = false;
    renderBundles(); syncCta(); renderGrid();
    $('shareMeta').textContent = `${S.selected.size} parsed` +
      (dropped ? ` · ${dropped} installed` : '');
  });

  $('copyShare').onclick = () => {
    const text = `forge://${[...S.selected].join('+') || 'empty'}`;
    navigator.clipboard.writeText(text).then(
      () => { S.copied = true; syncShare(); toast('Bundle string copied.', 'ok'); },
      () => toast('Clipboard unavailable.', 'err'));
  };

  $('primary').onclick = () => {
    if (S.view === 'install') {
      if (S.running) return;
      if (S.paused) { api('queue_resume'); S.running = true; S.paused = false; renderQueue(); syncCta(); return; }
      S.view = 'browse'; S.queue = []; openConsole(false); render();
    } else startRun();
  };
  $('backToBrowse').onclick = backToBrowse;
  $('toggleConsole').onclick = () => openConsole();
  $('themeToggle').onclick = () => applyTheme(S.theme === 'dark' ? 'light' : 'dark');

  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'f') { e.preventDefault(); $('search').focus(); $('search').select(); }
    if (e.key === 'Escape' && document.activeElement === $('search')) {
      $('search').value = ''; onSearch(''); $('search').blur();
    }
    if (e.ctrlKey && e.key === '`') { e.preventDefault(); openConsole(); }
  });
}

/* ══ Helpers ════════════════════════════════════════════════════════ */
function fmtSize(mb) {
  if (!mb) return '—';
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}
function estMinutes(mb) { return Math.max(1, Math.round(mb / 28)); }

function setEngine(ok, text) {
  const pill = $('enginePill');
  pill.classList.toggle('ok', ok);
  pill.classList.toggle('bad', !ok);
  $('engineText').textContent = text;
}

function toast(msg, kind = '') {
  const n = el('div', `toast ${kind}`, msg);
  $('toasts').append(n);
  setTimeout(() => {
    n.classList.add('out');
    setTimeout(() => n.remove(), 180);
  }, 3400);
}

boot();
