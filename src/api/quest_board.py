from __future__ import annotations


QUEST_BOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AIGC Quest Board</title>
  <style>
    :root { color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #08111f; color: #eef6ff; }
    a { color: #7de3d8; }
    button, input, textarea, select { font: inherit; }
    button { cursor: pointer; border: 1px solid #6dd8ce; border-radius: .55rem; padding: .6rem .85rem; background: #123348; color: #fff; }
    button:hover { background: #18465f; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    :focus-visible { outline: 3px solid #ffe08a; outline-offset: 3px; }
    header { padding: 1.2rem 1.4rem; border-bottom: 1px solid #28445e; background: #0d1b2d; position: sticky; top: 0; z-index: 3; }
    header h1 { margin: 0; font-size: 1.45rem; }
    header p { margin: .35rem 0 0; color: #bad0e4; }
    main { max-width: 1440px; margin: 0 auto; padding: 1rem; }
    .boundary { border: 1px solid #a87324; background: #332610; padding: .8rem; border-radius: .65rem; margin-bottom: 1rem; }
    .status { min-height: 1.5rem; padding: .65rem; border-radius: .55rem; background: #102238; margin-bottom: 1rem; }
    .grid { display: grid; gap: 1rem; grid-template-columns: minmax(280px, .85fr) minmax(360px, 1.15fr) minmax(360px, 1.15fr); }
    .panel { border: 1px solid #28445e; border-radius: .75rem; background: #0d1b2d; padding: 1rem; min-width: 0; }
    .panel h2 { margin-top: 0; }
    .scout-box { border: 1px solid #2f756e; background: #0b2630; padding: .8rem; border-radius: .65rem; margin-bottom: 1rem; }
    .scout-box h3 { margin: 0 0 .35rem; }
    fieldset { border: 1px solid #47647f; border-radius: .55rem; margin: .75rem 0; padding: .65rem; }
    fieldset label { display: flex; gap: .45rem; align-items: center; margin: .35rem 0; font-weight: 500; }
    fieldset input[type="checkbox"] { width: auto; }
    label { display: block; margin: .65rem 0 .25rem; font-weight: 650; }
    input, textarea, select { width: 100%; border: 1px solid #47647f; border-radius: .5rem; padding: .6rem; background: #07121f; color: #fff; }
    textarea { min-height: 7rem; resize: vertical; }
    .stack { display: grid; gap: .75rem; }
    .card { border: 1px solid #365572; border-radius: .65rem; padding: .8rem; background: #101f31; }
    .card h3 { margin: 0 0 .3rem; font-size: 1rem; }
    .meta { color: #b6cce0; font-size: .88rem; overflow-wrap: anywhere; }
    .badge { display: inline-block; border: 1px solid #7691a9; border-radius: 999px; padding: .14rem .45rem; margin: .25rem .2rem .25rem 0; font-size: .76rem; }
    .actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .65rem; }
    .empty { color: #9eb5c9; font-style: italic; }
    .quest-state { font-weight: 750; }
    .small { font-size: .82rem; color: #9eb5c9; }
    @media (max-width: 1050px) { .grid { grid-template-columns: 1fr 1fr; } .intake { grid-column: 1 / -1; } }
    @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } .intake { grid-column: auto; } header { position: static; } }
  </style>
</head>
<body>
<header>
  <h1>AIGC Quest Board</h1>
  <p>Local governed opportunity discovery, intake, and Quest proposal workspace.</p>
</header>
<main>
  <section class="boundary" aria-label="Safety boundary">
    <strong>Local operator boundary:</strong> the Opportunity Scout performs bounded read-only requests to fixed, repository-approved public sources. This board records candidates and creates internal <code>PROPOSED</code> Quests. It does not apply, bid, message, accept work, deliver, pay, purchase, deploy, use credentials, or perform any consequential external action.
  </section>
  <div id="status" class="status" role="status" aria-live="polite">Loading the local Quest Board…</div>
  <div class="grid">
    <section class="panel intake" aria-labelledby="intake-heading">
      <h2 id="intake-heading">Opportunity intake</h2>
      <form id="scout-form" class="scout-box">
        <h3>Read-only Opportunity Scout</h3>
        <p class="small">Fetch public records only from fixed Phase 2 adapters. No arbitrary URL, credentials, application, message, bid, or submission.</p>
        <fieldset>
          <legend>Sources</legend>
          <label><input type="checkbox" name="scout_source" value="weworkremotely" checked> We Work Remotely RSS</label>
          <label><input type="checkbox" name="scout_source" value="remotive" checked> Remotive API</label>
          <label><input type="checkbox" name="scout_source" value="remoteok"> RemoteOK API</label>
          <label><input type="checkbox" name="scout_source" value="github"> GitHub public issues</label>
        </fieldset>
        <label for="scout_limit">Maximum candidates</label>
        <input id="scout_limit" name="scout_limit" type="number" min="1" max="25" value="6" required>
        <div class="actions"><button id="scout-button" type="submit">Discover opportunities</button></div>
      </form>

      <h3>Manual candidate</h3>
      <form id="candidate-form">
        <label for="source_id">Work source</label>
        <select id="source_id" name="source_id" required></select>
        <label for="source_url">Posting URL</label>
        <input id="source_url" name="source_url" type="url" required placeholder="https://…">
        <label for="title">Posting title</label>
        <input id="title" name="title" required maxlength="500">
        <label for="description">Description</label>
        <textarea id="description" name="description" required maxlength="50000"></textarea>
        <label for="domain">Domain</label>
        <input id="domain" name="domain" required value="software_development" pattern="[a-z0-9][a-z0-9_-]+">
        <label for="skills">Required skills <span class="small">(comma separated)</span></label>
        <input id="skills" name="skills" placeholder="python, fastapi, sqlite">
        <label for="risk_class">Risk class</label>
        <select id="risk_class" name="risk_class">
          <option value="unassessed">Unassessed</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="restricted">Restricted</option>
        </select>
        <div class="actions"><button type="submit">Record candidate</button></div>
      </form>
    </section>

    <section class="panel" aria-labelledby="candidate-heading">
      <h2 id="candidate-heading">Quest candidates</h2>
      <div id="candidates" class="stack"></div>
    </section>

    <section class="panel" aria-labelledby="quest-heading">
      <h2 id="quest-heading">Governed Quests</h2>
      <div id="quests" class="stack"></div>
    </section>
  </div>
</main>
<script>
const statusBox = document.getElementById('status');
const candidateList = document.getElementById('candidates');
const questList = document.getElementById('quests');
const sourceSelect = document.getElementById('source_id');

function esc(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {'Content-Type': 'application/json', ...(options.headers || {})},
    ...options
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || body;
    throw new Error(detail.message || detail.code || JSON.stringify(detail));
  }
  return body;
}

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.style.border = isError ? '1px solid #d65b5b' : '1px solid #2f756e';
}

function renderCandidates(items) {
  if (!items.length) {
    candidateList.innerHTML = '<p class="empty">No candidates recorded.</p>';
    return;
  }
  candidateList.innerHTML = items.map(item => {
    const qualified = item.status === 'QUALIFIED';
    const created = Boolean(item.qualification && item.qualification.quest_created);
    const actions = [];
    if (item.status === 'DISCOVERED') {
      actions.push(`<button data-action="qualify" data-id="${esc(item.candidate_id)}" data-revision="${item.revision}">Qualify candidate</button>`);
    }
    if (qualified && !created) {
      actions.push(`<button data-action="create" data-id="${esc(item.candidate_id)}" data-revision="${item.revision}">Create proposed Quest</button>`);
    }
    if (created) {
      actions.push(`<span class="badge">Quest: ${esc(item.qualification.quest_id)}</span>`);
    }
    return `<article class="card">
      <h3>${esc(item.proposed_quest_title)}</h3>
      <div><span class="badge">${esc(item.status)}</span><span class="badge">${esc(item.source_name)}</span><span class="badge">risk: ${esc(item.risk_class)}</span></div>
      <p>${esc(item.description)}</p>
      <p class="meta"><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">Open source posting</a><br>Candidate ${esc(item.candidate_id)} · revision ${item.revision}</p>
      <div class="actions">${actions.join('')}</div>
    </article>`;
  }).join('');
}

function renderQuests(items) {
  if (!items.length) {
    questList.innerHTML = '<p class="empty">No Quests created.</p>';
    return;
  }
  questList.innerHTML = items.map(item => `<article class="card">
    <h3>${esc(item.title)}</h3>
    <p class="quest-state">${esc(item.lifecycle_state)}</p>
    <p>${esc(item.purpose)}</p>
    <p class="meta">${esc(item.quest_id)} · revision ${item.revision}<br>Next governed decision: request work acceptance.</p>
    <div>${(item.acceptance_criteria || []).map(value => `<span class="badge">${esc(value)}</span>`).join('')}</div>
  </article>`).join('');
}

async function loadBoard() {
  try {
    const [sources, candidates, quests] = await Promise.all([
      api('/api/v1/quests/sources'),
      api('/api/v1/quests/candidates'),
      api('/api/v1/quests')
    ]);
    sourceSelect.innerHTML = sources.items.map(source => `<option value="${esc(source.id)}">${esc(source.name)} — ${esc(source.connector_status)}</option>`).join('');
    renderCandidates(candidates.items);
    renderQuests(quests.items);
    setStatus(`${candidates.count} candidate(s), ${quests.count} Quest(s). External action performed: false.`);
  } catch (error) {
    setStatus(`Board load failed: ${error.message}`, true);
  }
}

document.getElementById('scout-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = document.getElementById('scout-button');
  const sources = [...form.querySelectorAll('input[name="scout_source"]:checked')].map(input => input.value);
  if (!sources.length) {
    setStatus('Select at least one read-only source.', true);
    return;
  }
  const params = new URLSearchParams({limit: String(form.scout_limit.value || 6)});
  sources.forEach(source => params.append('source_id', source));
  button.disabled = true;
  setStatus('Opportunity Scout is performing bounded read-only discovery…');
  try {
    const result = await api(`/api/v1/opportunities/discover?${params.toString()}`, {method: 'POST'});
    setStatus(`Scout ${result.status}: ${result.new_candidates} new, ${result.existing_candidates} existing candidate(s); ${result.scanned_sources} source(s) read. External action performed: false.`);
    await loadBoard();
  } catch (error) {
    setStatus(`Opportunity discovery failed: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
});

document.getElementById('candidate-form').addEventListener('submit', async event => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  try {
    await api('/api/v1/quests/candidates/ingest', {
      method: 'POST',
      body: JSON.stringify({
        source_id: data.get('source_id'),
        source_url: data.get('source_url'),
        title: data.get('title'),
        description: data.get('description'),
        domain: data.get('domain'),
        required_skills: String(data.get('skills') || '').split(',').map(v => v.trim()).filter(Boolean),
        risk_class: data.get('risk_class'),
        rights_status: 'manual_operator_entry',
        ingestion_channel: 'manual',
        remote_status: 'unspecified'
      })
    });
    event.currentTarget.reset();
    setStatus('Candidate recorded.');
    await loadBoard();
  } catch (error) {
    setStatus(`Candidate ingestion failed: ${error.message}`, true);
  }
});

candidateList.addEventListener('click', async event => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  button.disabled = true;
  try {
    if (button.dataset.action === 'qualify') {
      await api(`/api/v1/quests/candidates/${encodeURIComponent(button.dataset.id)}/qualify`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: Number(button.dataset.revision),
          decision: 'QUALIFY',
          operator_role: 'ACCOUNTABLE_OPERATOR',
          reason: 'Qualified through the local operator Quest Board.'
        })
      });
      setStatus('Candidate qualified. This has not accepted the work.');
    } else if (button.dataset.action === 'create') {
      await api(`/api/v1/quests/candidates/${encodeURIComponent(button.dataset.id)}/create-quest`, {
        method: 'POST',
        body: JSON.stringify({
          expected_candidate_revision: Number(button.dataset.revision),
          operator_role: 'ACCOUNTABLE_OPERATOR'
        })
      });
      setStatus('Proposed Quest created. Work acceptance remains a separate decision.');
    }
    await loadBoard();
  } catch (error) {
    button.disabled = false;
    setStatus(`Action failed: ${error.message}`, true);
  }
});

loadBoard();
</script>
</body>
</html>
"""
