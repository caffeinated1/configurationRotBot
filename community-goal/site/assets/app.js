/* Community Goal — interactive guide.
 *
 * The page renders itself from the same public API it documents: one fetch of
 * api/v1/guide.json, then everything else is local. Assessment state lives in
 * localStorage only, because a half-finished evaluation of a live proposal is
 * not something a town should have to upload anywhere.
 */
(() => {
  'use strict';

  const API_BASE = 'api/v1';
  const STORE_KEY = 'community-goal:assessment:v1';
  const THEME_KEY = 'community-goal:theme';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const WEIGHT_LABEL = { 3: 'critical', 2: 'important', 1: 'supporting' };

  let guide = null;          // the full API document
  let reqIndex = new Map();  // requirement id -> requirement
  let state = load();        // id -> { pillars: {}, done: bool, notes: string }
  let filters = { instrument: null, criticalOnly: false, gapsOnly: false };

  /* ── storage ──────────────────────────────────────────────────── */

  function load() {
    try {
      return JSON.parse(localStorage.getItem(STORE_KEY) || '{}') || {};
    } catch (_) {
      return {};
    }
  }

  function save() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch (_) {
      /* private mode, blocked storage: the page still works for this session */
    }
  }

  function entry(id) {
    if (!state[id]) state[id] = { pillars: {}, done: false, notes: '' };
    return state[id];
  }

  /* ── scoring ──────────────────────────────────────────────────── */

  const pillarIds = () => guide.scoring.pillars;

  function reqPoints(req) {
    const e = state[req.id];
    if (req.type === 'action') return e && e.done ? req.weight : 0;
    if (!e) return 0;
    const hit = pillarIds().filter((p) => e.pillars[p]).length;
    return req.weight * hit;
  }

  const reqMax = (req) => req.weight * (req.type === 'commitment' ? pillarIds().length : 1);

  function reqState(req) {
    const points = reqPoints(req);
    if (points === 0) return 'empty';
    return points === reqMax(req) ? 'complete' : 'partial';
  }

  function missingPillars(req) {
    if (req.type === 'action') return state[req.id] && state[req.id].done ? [] : ['not started'];
    const e = state[req.id];
    return guide.basic_rule.pillars
      .filter((p) => !(e && e.pillars[p.id]))
      .map((p) => p.name.toLowerCase());
  }

  function score(reqs) {
    const list = reqs || guide.requirements;
    const earned = list.reduce((sum, r) => sum + reqPoints(r), 0);
    const max = list.reduce((sum, r) => sum + reqMax(r), 0);
    return { earned, max, pct: max ? Math.round((earned / max) * 100) : 0 };
  }

  const sectionReqs = (id) => guide.requirements.filter((r) => r.section_id === id);

  function band(pct) {
    return guide.scoring.bands.find((b) => pct >= b.min && pct <= b.max)
      || guide.scoring.bands[0];
  }

  /* ── boot ─────────────────────────────────────────────────────── */

  async function boot() {
    initTheme();
    try {
      const res = await fetch(`${API_BASE}/guide.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      guide = await res.json();
    } catch (err) {
      $('#loading').innerHTML =
        `<p>Could not load the guide from <code>${API_BASE}/guide.json</code>.</p>
         <p class="muted">${esc(err.message)} — if you opened this file directly, serve the
         folder over HTTP instead (<code>python3 -m http.server</code>).</p>`;
      return;
    }

    guide.requirements.forEach((r) => reqIndex.set(r.id, r));
    $('#loading').hidden = true;

    renderGuide();
    renderEvidence();
    renderApi();
    wireChrome();
    refreshScores();

    const view = new URLSearchParams(location.search).get('view');
    setView(['guide', 'readiness', 'evidence', 'api'].includes(view) ? view : 'guide');
    if (location.hash) {
      const target = document.getElementById(location.hash.slice(1));
      if (target) target.scrollIntoView();
    }
  }

  /* ── guide view ───────────────────────────────────────────────── */

  function renderGuide() {
    const m = guide.meta;
    document.title = m.title;
    $('#doc-title').textContent = m.title;
    $('#doc-subtitle').textContent = m.subtitle;
    $('#goal-statement').textContent = guide.goal.statement;
    $('#goal-rule').textContent = guide.goal.rule;
    $('#disclaimer').textContent = m.disclaimer;
    $('#source-note').textContent = m.source_note;
    $('#closing-rule').textContent = guide.goal.rule;

    const commitments = guide.requirements.filter((r) => r.type === 'commitment').length;
    $('#hero-stats').innerHTML = [
      [guide.sections.length, 'sections'],
      [guide.requirements.length, 'requirements'],
      [commitments, 'enforceable commitments'],
      [guide.evidence.length, 'checkable claims'],
    ].map(([n, label]) =>
      `<div class="stat"><strong>${n}</strong><span>${label}</span></div>`).join('');

    $('#framing').innerHTML = `
      <h2>${esc(guide.framing.heading)}</h2>
      <div class="framing-facts">
        ${guide.framing.facts.map((f) => `
          <div class="fact">
            <strong>${esc(f.claim)}</strong>
            <p>${esc(f.detail)}</p>
          </div>`).join('')}
      </div>
      <p class="framing-conclusion">${esc(guide.framing.conclusion)}</p>`;

    $('#rule').innerHTML = `
      <h2>The basic rule</h2>
      <p class="rule-statement">${esc(guide.basic_rule.statement)}</p>
      <div class="pillars">
        ${guide.basic_rule.pillars.map((p, i) => `
          <div class="pillar" id="pillar-${p.id}">
            <div class="pillar-index">Pillar ${i + 1}</div>
            <h3>${esc(p.name)}</h3>
            <p>${esc(p.question)}</p>
            <p class="failure">${esc(p.failure_mode)}</p>
          </div>`).join('')}
      </div>`;
    $('#rule').id = 'basic-rule';

    $('#instruments').innerHTML = `
      <h2>Six documents, six jobs</h2>
      <p class="muted">A protection written into the wrong instrument is not a protection.
      Each requirement below is tagged with the documents that can carry it.</p>
      <div class="table-wrap">
        <table class="instrument-table">
          <thead><tr><th>Document</th><th>Purpose</th></tr></thead>
          <tbody>
            ${guide.instruments.map((i) => `
              <tr><td>${esc(i.name)}</td><td>${esc(i.purpose)}</td></tr>`).join('')}
          </tbody>
        </table>
      </div>`;

    $('#questions').innerHTML = guide.final_questions
      .map((q) => `<li>${esc(q.question)}</li>`).join('');

    $('#filters').innerHTML = [
      `<button class="chip" data-filter="critical" aria-pressed="false">Critical only</button>`,
      `<button class="chip" data-filter="gaps" aria-pressed="false">Gaps only</button>`,
      ...guide.instruments.map((i) =>
        `<button class="chip" data-instrument="${i.id}" aria-pressed="false"
          title="${esc(i.purpose)}">${esc(i.name.split(' ')[0])}</button>`),
    ].join('');

    $('#toc').innerHTML = guide.sections.map((s) => `
      <a href="#${s.slug}" data-section="${s.id}">
        <span class="toc-num">${s.number}</span>
        <span class="toc-label">${esc(s.title)}</span>
        <span class="toc-done" data-done="${s.id}"></span>
      </a>`).join('');

    $('#sections').innerHTML = guide.sections.map(renderSection).join('');
    wireGuideEvents();
    observeSections();
  }

  function renderSection(section) {
    return `
      <section class="section" id="${section.slug}" data-section="${section.id}">
        <div class="section-num">${section.number}</div>
        <h2>${esc(section.title)}</h2>
        <p class="section-summary">${esc(section.summary)}</p>
        <p class="section-goal"><strong>Goal:</strong> ${esc(section.goal)}</p>
        <div class="section-meter">
          <span class="meter"><span data-meter="${section.id}"></span></span>
          <span data-meter-label="${section.id}">not started</span>
        </div>
        ${section.requirements.map((r) => renderRequirement(reqIndex.get(r.id))).join('')}
      </section>`;
  }

  function renderRequirement(req) {
    const instruments = req.instruments
      .map((id) => guide.instruments.find((i) => i.id === id))
      .filter(Boolean);

    return `
      <article class="req" id="${req.id}" data-req="${req.id}"
               data-weight="${req.weight}"
               data-instruments="${req.instruments.join(' ')}"
               data-state="${reqState(req)}">
        <div class="req-head">
          <div class="req-title">
            <h3><span class="req-id">${req.id}</span>${esc(req.title)}</h3>
            <p class="req-detail">${esc(req.detail)}</p>
            <div class="req-tags">
              <span class="tag tag-weight-${req.weight}">${WEIGHT_LABEL[req.weight]}</span>
              <span class="tag">${req.type}</span>
              ${req.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join('')}
            </div>
          </div>
        </div>
        ${req.pitfall ? `<div class="pitfall"><strong>What went wrong elsewhere</strong>${esc(req.pitfall)}</div>` : ''}
        ${req.note ? `<div class="note">${esc(req.note)}</div>` : ''}
        <div class="req-assess">
          <div class="assess-label">${req.type === 'commitment'
            ? 'Assess against the basic rule' : 'Mark when done'}</div>
          <div class="pillar-row">${renderControls(req)}</div>
          <textarea class="req-notes" data-notes="${req.id}" rows="1"
            placeholder="Where does this live — ordinance section, agreement clause, who owns it?"></textarea>
          ${instruments.length ? `<p class="instrument-hint">Carried by:
            ${instruments.map((i) => esc(i.name)).join(' · ')}</p>` : ''}
        </div>
      </article>`;
  }

  function renderControls(req) {
    if (req.type === 'action') {
      return `<button class="pillar-toggle" data-done="${req.id}"
        aria-pressed="false">Done</button>`;
    }
    return guide.basic_rule.pillars.map((p) => `
      <button class="pillar-toggle" data-pillar="${p.id}" data-req="${req.id}"
        aria-pressed="false" title="${esc(p.question)}">${esc(p.name)}</button>`).join('');
  }

  function wireGuideEvents() {
    $('#sections').addEventListener('click', (ev) => {
      const toggle = ev.target.closest('.pillar-toggle');
      if (!toggle) return;
      if (toggle.dataset.done) {
        const e = entry(toggle.dataset.done);
        e.done = !e.done;
      } else {
        const e = entry(toggle.dataset.req);
        e.pillars[toggle.dataset.pillar] = !e.pillars[toggle.dataset.pillar];
      }
      save();
      refreshScores();
    });

    $('#sections').addEventListener('input', (ev) => {
      const box = ev.target.closest('[data-notes]');
      if (!box) return;
      entry(box.dataset.notes).notes = box.value;
      save();
    });

    $('#filters').addEventListener('click', (ev) => {
      const chip = ev.target.closest('.chip');
      if (!chip) return;
      if (chip.dataset.filter === 'critical') filters.criticalOnly = !filters.criticalOnly;
      else if (chip.dataset.filter === 'gaps') filters.gapsOnly = !filters.gapsOnly;
      else {
        filters.instrument = filters.instrument === chip.dataset.instrument
          ? null : chip.dataset.instrument;
      }
      $$('#filters .chip').forEach((c) => {
        const on = c.dataset.filter === 'critical' ? filters.criticalOnly
          : c.dataset.filter === 'gaps' ? filters.gapsOnly
            : filters.instrument === c.dataset.instrument;
        c.setAttribute('aria-pressed', String(on));
      });
      applyFilters();
    });

    $('#expand-all').addEventListener('click', () => {
      filters = { instrument: null, criticalOnly: false, gapsOnly: false };
      $$('#filters .chip').forEach((c) => c.setAttribute('aria-pressed', 'false'));
      $('#search-input').value = '';
      $('#search-results').hidden = true;
      applyFilters();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    $('#search-input').addEventListener('input', (ev) => runSearch(ev.target.value.trim()));
  }

  function applyFilters() {
    guide.sections.forEach((section) => {
      let visible = 0;
      sectionReqs(section.id).forEach((req) => {
        const el = document.getElementById(req.id);
        const hide =
          (filters.criticalOnly && req.weight !== 3) ||
          (filters.gapsOnly && reqState(req) === 'complete') ||
          (filters.instrument && !req.instruments.includes(filters.instrument));
        el.hidden = hide;
        if (!hide) visible += 1;
      });
      const el = document.querySelector(`.section[data-section="${section.id}"]`);
      el.hidden = visible === 0;
      const link = document.querySelector(`#toc a[data-section="${section.id}"]`);
      if (link) link.hidden = visible === 0;
    });
  }

  /* ── search ───────────────────────────────────────────────────── */

  function runSearch(query) {
    const box = $('#search-results');
    if (query.length < 2) {
      box.hidden = true;
      applyFilters();
      return;
    }
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const hits = [];

    const consider = (kind, id, title, body, href) => {
      const haystack = `${title} ${body}`.toLowerCase();
      if (!terms.every((t) => haystack.includes(t))) return;
      const rank = terms.filter((t) => title.toLowerCase().includes(t)).length;
      hits.push({ kind, id, title, body, href, rank });
    };

    guide.requirements.forEach((r) => consider('requirement', r.id, r.title,
      `${r.detail} ${r.tags.join(' ')} ${r.pitfall || ''}`, `#${r.id}`));
    guide.sections.forEach((s) => consider('section', s.id, `${s.number}. ${s.title}`,
      `${s.summary} ${s.goal}`, `#${s.slug}`));
    guide.evidence.forEach((e) => consider('evidence', e.id, e.headline,
      `${e.statement} ${e.use}`, `#${e.id}`));

    hits.sort((a, b) => b.rank - a.rank);
    box.hidden = false;
    box.innerHTML = hits.length
      ? `<h2>${hits.length} result${hits.length === 1 ? '' : 's'} for “${esc(query)}”</h2>` +
        hits.slice(0, 25).map((h) => `
          <a class="result" href="${h.href}" data-kind="${h.kind}">
            <span class="result-kind">${h.kind}${h.kind === 'requirement' ? ' · ' + h.id : ''}</span>
            <strong>${highlight(h.title, terms)}</strong>
            <p>${highlight(h.body.slice(0, 180) + (h.body.length > 180 ? '…' : ''), terms)}</p>
          </a>`).join('')
      : `<h2>No matches for “${esc(query)}”</h2>
         <p class="muted">Try a shorter phrase — “drought”, “letter of credit”, “setback”.</p>`;

    box.querySelectorAll('.result').forEach((link) => {
      link.addEventListener('click', () => {
        if (link.dataset.kind === 'evidence') setView('evidence');
      });
    });
  }

  function highlight(text, terms) {
    let out = esc(text);
    terms.forEach((t) => {
      out = out.replace(new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig'),
        '<mark>$1</mark>');
    });
    return out;
  }

  /* ── score refresh ────────────────────────────────────────────── */

  function refreshScores() {
    guide.requirements.forEach((req) => {
      const el = document.getElementById(req.id);
      if (!el) return;
      el.dataset.state = reqState(req);
      const e = state[req.id];
      $$('.pillar-toggle', el).forEach((btn) => {
        const on = btn.dataset.done
          ? Boolean(e && e.done)
          : Boolean(e && e.pillars[btn.dataset.pillar]);
        btn.setAttribute('aria-pressed', String(on));
      });
      const notes = $('[data-notes]', el);
      if (notes && document.activeElement !== notes) notes.value = (e && e.notes) || '';
    });

    guide.sections.forEach((section) => {
      const s = score(sectionReqs(section.id));
      const meter = document.querySelector(`[data-meter="${section.id}"]`);
      if (meter) meter.style.width = `${s.pct}%`;
      const label = document.querySelector(`[data-meter-label="${section.id}"]`);
      if (label) label.textContent = s.pct === 0 ? 'not started' : `${s.pct}% secured`;
      const done = document.querySelector(`[data-done="${section.id}"]`);
      if (done) done.textContent = s.pct === 0 ? '' : `${s.pct}%`;
    });

    const total = score();
    const b = band(total.pct);
    $('#topbar-progress-bar').style.width = `${total.pct}%`;
    const chip = $('#score-chip');
    chip.hidden = false;
    $('#score-chip-value').textContent = `${total.pct}%`;
    $('#score-chip-label').textContent = total.pct === 0 ? 'not started' : b.label;

    renderReadiness(total, b);
    if (filters.gapsOnly) applyFilters();
  }

  /* ── readiness view ───────────────────────────────────────────── */

  function renderReadiness(total, b) {
    $('#gauge-value').innerHTML = `${total.pct}<span>%</span>`;
    $('#gauge-band').textContent = total.pct === 0 ? 'Not started' : b.label;
    $('#gauge-meaning').textContent = total.pct === 0
      ? 'Work through the guide and record what is actually written down.'
      : b.meaning;
    $('#gauge-points').textContent =
      `${total.earned} of ${total.max} weighted points · ${guide.scoring.method}`;

    const commitments = guide.requirements.filter((r) => r.type === 'commitment');
    $('#pillar-summary').innerHTML = guide.basic_rule.pillars.map((p) => {
      const hit = commitments.filter((r) => state[r.id] && state[r.id].pillars[p.id]).length;
      return `<div class="pillar-stat">
        <strong>${hit}<span style="font-size:.9rem;color:var(--ink-faint)">/${commitments.length}</span></strong>
        <span>${esc(p.name)}</span>
      </div>`;
    }).join('');

    $('#answers').innerHTML = guide.final_questions.map((q) => {
      const reqs = guide.requirements.filter((r) => q.sections.includes(r.section_id));
      const s = score(reqs);
      const ok = s.pct >= 80;
      return `<div class="answer">
        <span class="answer-state" data-ok="${ok}">${ok ? '●' : '○'}</span>
        <span>${esc(q.question)}</span>
        <span class="answer-pct">${s.pct}%</span>
      </div>`;
    }).join('');

    $('#progress-grid').innerHTML = guide.sections.map((section) => {
      const s = score(sectionReqs(section.id));
      return `<a class="progress-card" href="#${section.slug}" data-goto="guide">
        <h3>${section.number}. ${esc(section.title)}</h3>
        <span class="meter"><span style="width:${s.pct}%"></span></span>
        <span class="pct">${s.pct}% · ${s.earned}/${s.max} points</span>
      </a>`;
    }).join('');

    const gaps = guide.requirements
      .filter((r) => reqState(r) !== 'complete')
      .sort((a, b2) => b2.weight - a.weight || a.id.localeCompare(b2.id));
    $('#gap-count').textContent = gaps.length;
    $('#gap-list').innerHTML = gaps.length
      ? gaps.map((r) => `
        <a class="gap" href="#${r.id}" data-goto="guide">
          <span class="gap-weight">${WEIGHT_LABEL[r.weight]}</span>
          <span class="gap-body">
            <strong>${esc(r.title)}</strong>
            <span>${r.id} · section ${r.section_number}</span>
          </span>
          <span class="gap-missing">missing: ${esc(missingPillars(r).join(', '))}</span>
        </a>`).join('')
      : `<p class="muted">No gaps recorded. Re-read the six questions above and confirm
         each answer points at a document, not an intention.</p>`;

    $$('[data-goto="guide"]').forEach((link) => {
      link.addEventListener('click', () => setView('guide'), { once: true });
    });
  }

  /* ── evidence view ────────────────────────────────────────────── */

  function renderEvidence() {
    $('#evidence-warning').textContent = guide.meta.source_note;
    $('#evidence-grid').innerHTML = guide.evidence.map((e) => `
      <article class="evidence-card" id="${e.id}">
        <div class="evidence-topic">${esc(e.topic)}</div>
        <h3>${esc(e.headline)}</h3>
        <p>${esc(e.statement)}</p>
        <p><strong>Use:</strong> ${esc(e.use)}</p>
        <div class="evidence-verify"><strong>Verify locally:</strong> ${esc(e.verify)}</div>
        <div class="evidence-links">
          ${e.sections.map((sid) => {
            const s = guide.sections.find((x) => x.id === sid);
            return s ? `<a class="tag" href="#${s.slug}" data-goto="guide">§${s.number}</a>` : '';
          }).join('')}
        </div>
      </article>`).join('');

    $$('#evidence-grid [data-goto="guide"]').forEach((link) =>
      link.addEventListener('click', () => setView('guide')));
  }

  /* ── API view ─────────────────────────────────────────────────── */

  const ENDPOINTS = [
    ['index.json', 'Goal, counts, and every endpoint'],
    ['goal.json', 'The community goal and the six questions'],
    ['rule.json', 'The basic rule and its four pillars'],
    ['framing.json', 'The two facts that frame the decision'],
    ['sections.json', 'All ten sections with requirements'],
    ['sections/s5.json', 'One section (id or slug)'],
    ['requirements.json', 'Every requirement, flattened'],
    ['requirements/s9-r2.json', 'One requirement with its evidence'],
    ['evidence.json', 'Claims, uses, and how to verify each'],
    ['instruments.json', 'The six documents and what they carry'],
    ['questions.json', 'The six pre-vote questions'],
    ['checklist.json', 'Blank assessment template'],
    ['scoring.json', 'How the readiness score is computed'],
    ['tags.json', 'Tag facets with counts'],
    ['search.json', 'Client-side search index'],
    ['guide.json', 'The entire guide in one document'],
    ['openapi.json', 'OpenAPI 3.1 description'],
  ];

  function renderApi() {
    const origin = location.href.replace(/[^/]*$/, '');
    $('#curl-sample').textContent =
      `# what is the town trying to achieve?\n` +
      `curl -s ${origin}${API_BASE}/goal.json | jq .goal.statement\n\n` +
      `# every critical requirement that still needs a funded guarantor\n` +
      `curl -s ${origin}${API_BASE}/requirements.json \\\n` +
      `  | jq '.requirements[] | select(.weight == 3) | {id, title, instruments}'\n\n` +
      `# a blank assessment your council can fill in and publish\n` +
      `curl -s ${origin}${API_BASE}/checklist.json -o assessment.json`;

    $('#api-list').innerHTML = ENDPOINTS.map(([path, desc]) => `
      <button class="api-endpoint" data-path="${path}" aria-pressed="false">
        <span class="api-method">GET</span>
        <code>${API_BASE}/${path}</code>
        <span>${esc(desc)}</span>
      </button>`).join('');

    $('#api-list').addEventListener('click', async (ev) => {
      const btn = ev.target.closest('.api-endpoint');
      if (!btn) return;
      $$('.api-endpoint').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
      const path = `${API_BASE}/${btn.dataset.path}`;
      $('#api-url').textContent = path;
      $('#api-status').textContent = 'loading…';
      $('#api-body').textContent = '';
      try {
        const res = await fetch(path, { cache: 'no-cache' });
        const text = await res.text();
        $('#api-status').textContent = `${res.status} ${res.statusText} · ${
          (new Blob([text]).size / 1024).toFixed(1)} KB`;
        let body = text;
        try { body = JSON.stringify(JSON.parse(text), null, 2); } catch (_) { /* markdown */ }
        $('#api-body').textContent = body.length > 60000
          ? `${body.slice(0, 60000)}\n\n… truncated for display; the full response is at ${path}`
          : body;
      } catch (err) {
        $('#api-status').textContent = 'error';
        $('#api-body').textContent = err.message;
      }
    });
  }

  /* ── export / import ──────────────────────────────────────────── */

  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function exportJson() {
    const total = score();
    download('community-goal-assessment.json', JSON.stringify({
      guide: { id: guide.meta.id, version: guide.meta.version, title: guide.meta.title },
      generated_at: new Date().toISOString(),
      score: { ...total, band: band(total.pct).id },
      items: guide.requirements.map((r) => ({
        id: r.id,
        section: r.section_id,
        title: r.title,
        type: r.type,
        weight: r.weight,
        state: reqState(r),
        points: reqPoints(r),
        max_points: reqMax(r),
        pillars: r.type === 'commitment'
          ? Object.fromEntries(pillarIds().map((p) =>
            [p, Boolean(state[r.id] && state[r.id].pillars[p])]))
          : null,
        done: r.type === 'action' ? Boolean(state[r.id] && state[r.id].done) : null,
        notes: (state[r.id] && state[r.id].notes) || '',
      })),
    }, null, 2), 'application/json');
  }

  function exportMarkdown() {
    const total = score();
    const b = band(total.pct);
    const date = new Date().toISOString().slice(0, 10);
    const lines = [
      `# Data center proposal — readiness assessment`,
      ``,
      `**Assessed against:** ${guide.meta.title} (v${guide.meta.version})  `,
      `**Date:** ${date}  `,
      `**Overall readiness:** ${total.pct}% — ${b.label}`,
      ``,
      `> ${b.meaning}`,
      ``,
      `## Can we answer the six questions?`,
      ``,
      `| Question | Readiness |`,
      `| --- | --- |`,
      ...guide.final_questions.map((q) => {
        const s = score(guide.requirements.filter((r) => q.sections.includes(r.section_id)));
        return `| ${q.question} | ${s.pct}% ${s.pct >= 80 ? '' : '— not yet'} |`;
      }),
      ``,
      `## Section progress`,
      ``,
      `| # | Section | Secured |`,
      `| --- | --- | --- |`,
      ...guide.sections.map((s) => {
        const sc = score(sectionReqs(s.id));
        return `| ${s.number} | ${s.title} | ${sc.pct}% (${sc.earned}/${sc.max}) |`;
      }),
      ``,
    ];

    const gaps = guide.requirements
      .filter((r) => reqState(r) !== 'complete')
      .sort((a, c) => c.weight - a.weight || a.id.localeCompare(c.id));

    lines.push(`## Open gaps (${gaps.length})`, ``);
    if (!gaps.length) {
      lines.push(`None recorded.`, ``);
    } else {
      gaps.forEach((r) => {
        lines.push(`### ${r.id} — ${r.title}  \`${WEIGHT_LABEL[r.weight]}\``);
        lines.push(``, r.detail, ``);
        lines.push(`- **Missing:** ${missingPillars(r).join(', ')}`);
        lines.push(`- **Section:** ${r.section_number}. ${r.section_title}`);
        if (r.instruments.length) {
          lines.push(`- **Belongs in:** ${r.instruments
            .map((i) => (guide.instruments.find((x) => x.id === i) || {}).name)
            .filter(Boolean).join('; ')}`);
        }
        const note = (state[r.id] && state[r.id].notes || '').trim();
        if (note) lines.push(`- **Notes:** ${note}`);
        lines.push(``);
      });
    }

    const secured = guide.requirements.filter((r) => reqState(r) === 'complete');
    lines.push(`## Secured (${secured.length})`, ``);
    secured.forEach((r) => {
      const note = (state[r.id] && state[r.id].notes || '').trim();
      lines.push(`- **${r.id}** ${r.title}${note ? ` — ${note}` : ''}`);
    });
    lines.push(``, `---`, ``, guide.meta.disclaimer, ``);

    download(`readiness-${date}.md`, lines.join('\n'), 'text/markdown');
  }

  function importJson(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(String(reader.result));
        if (!Array.isArray(data.items)) throw new Error('no items array');
        const next = {};
        data.items.forEach((item) => {
          if (!reqIndex.has(item.id)) return;
          next[item.id] = {
            pillars: item.pillars || {},
            done: Boolean(item.done),
            notes: typeof item.notes === 'string' ? item.notes : '',
          };
        });
        state = next;
        save();
        refreshScores();
      } catch (err) {
        window.alert(`Could not read that file: ${err.message}`);
      }
    };
    reader.readAsText(file);
  }

  /* ── chrome: views, theme, scroll spy ─────────────────────────── */

  function setView(view) {
    $$('.view').forEach((el) => { el.hidden = el.id !== `view-${view}`; });
    $$('.view-tab').forEach((tab) => {
      if (tab.dataset.view === view) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    });
    const url = new URL(location.href);
    url.searchParams.set('view', view);
    history.replaceState(null, '', url.toString().replace(/%23/g, '#'));
  }

  function initTheme() {
    let stored = null;
    try { stored = localStorage.getItem(THEME_KEY); } catch (_) { /* blocked */ }
    if (stored) document.documentElement.dataset.theme = stored;
  }

  function wireChrome() {
    $$('.view-tab').forEach((tab) => tab.addEventListener('click', () => {
      setView(tab.dataset.view);
      // Views share one scroll container, so a tab switch has to reset it —
      // otherwise Readiness opens halfway down its own gap list.
      window.scrollTo(0, 0);
    }));

    $('#theme-btn').addEventListener('click', () => {
      const root = document.documentElement;
      const dark = root.dataset.theme === 'dark'
        || (root.dataset.theme !== 'light'
            && window.matchMedia('(prefers-color-scheme: dark)').matches);
      root.dataset.theme = dark ? 'light' : 'dark';
      try { localStorage.setItem(THEME_KEY, root.dataset.theme); } catch (_) { /* blocked */ }
    });

    $('#export-json').addEventListener('click', exportJson);
    $('#export-md').addEventListener('click', exportMarkdown);
    $('#import-json').addEventListener('click', () => $('#import-file').click());
    $('#import-file').addEventListener('change', (ev) => {
      if (ev.target.files[0]) importJson(ev.target.files[0]);
      ev.target.value = '';
    });
    $('#reset-all').addEventListener('click', () => {
      if (!window.confirm('Clear every answer in this assessment?')) return;
      state = {};
      save();
      refreshScores();
    });

    window.addEventListener('hashchange', () => {
      const el = document.getElementById(location.hash.slice(1));
      if (el && el.closest('#view-guide')) setView('guide');
    });
  }

  function observeSections() {
    const links = new Map($$('#toc a').map((a) => [a.dataset.section, a]));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        const link = links.get(e.target.dataset.section);
        if (link) link.classList.toggle('active', e.isIntersecting);
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    $$('.section').forEach((s) => io.observe(s));
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
