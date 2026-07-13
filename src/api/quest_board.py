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
    button.danger { border-color: #dc7b7b; background: #51252b; }
    button.warning { border-color: #e0b35d; background: #4b391d; }
    button.approve { border-color: #68d7a1; background: #174a36; }
    :focus-visible { outline: 3px solid #ffe08a; outline-offset: 3px; }
    header { padding: 1.2rem 1.4rem; border-bottom: 1px solid #28445e; background: #0d1b2d; position: sticky; top: 0; z-index: 3; }
    header h1 { margin: 0; font-size: 1.45rem; }
    header p { margin: .35rem 0 0; color: #bad0e4; }
    main { max-width: 1480px; margin: 0 auto; padding: 1rem; }
    .boundary { border: 1px solid #a87324; background: #332610; padding: .8rem; border-radius: .65rem; margin-bottom: 1rem; }
    .status { min-height: 1.5rem; padding: .65rem; border-radius: .55rem; background: #102238; margin-bottom: 1rem; }
    .stats { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1rem; }
    .grid { display: grid; gap: 1rem; grid-template-columns: minmax(280px, .8fr) minmax(360px, 1.1fr) minmax(390px, 1.2fr); }
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
    .assessment, .gate { border-left: 3px solid #6dd8ce; margin: .7rem 0; padding: .5rem .65rem; background: #0b2630; }
    .gate { border-left-color: #e0b35d; background: #2a2315; }
    .assessment h4, .gate h4 { margin: 0 0 .35rem; }
    .assessment dl, .gate dl { display: grid; grid-template-columns: auto 1fr; gap: .2rem .55rem; margin: .35rem 0; font-size: .85rem; }
    .assessment dt, .gate dt { font-weight: 700; }
    .assessment dd, .gate dd { margin: 0; overflow-wrap: anywhere; }
    .actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .65rem; }
    .empty { color: #9eb5c9; font-style: italic; }
    .quest-state { font-weight: 750; }
    .small { font-size: .82rem; color: #9eb5c9; }
    @media (max-width: 1080px) { .grid { grid-template-columns: 1fr 1fr; } .intake { grid-column: 1 / -1; } }
    @media (max-width: 740px) { .grid { grid-template-columns: 1fr; } .intake { grid-column: auto; } header { position: static; } .assessment dl, .gate dl { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<header>
  <h1>AIGC Quest Board</h1>
  <p>Local governed opportunity discovery, assessment, Quest proposal, and internal work-acceptance workspace.</p>
</header>
<main>
  <section class="boundary" aria-label="Safety boundary">
    <strong>Local operator boundary:</strong> the Opportunity Scout performs bounded read-only requests to fixed, repository-approved public sources. Ology + Risk Scout assessment never auto-qualifies. <strong>WORK_ACCEPTED</strong> means permission to undertake bounded internal work; it does not accept an external contract. <strong>ACCEPTED_FOR_DELIVERY</strong> is a later, separate completed-work Judgment Gate. This board does not apply, bid, message, deliver, pay, purchase, deploy, use credentials, or perform any consequential external action.
  </section>
  <div id="status" class="status" role="status" aria-live="polite">Loading the local Quest Board…</div>
  <div id="stats" class="stats" aria-label="Quest Board statistics"></div>
  <div class="grid">
    <section class="panel intake" aria-labelledby="intake-heading">
      <h2 id="intake-heading">Opportunity intake</h2>
      <form id="scout-form" class="scout-box">
        <h3>Read-only Opportunity Scout</h3>
        <p class="small">Fetch, classify, and risk-score public records through fixed Phase 2 adapters. No arbitrary URL, credentials, application, message, bid, or submission.</p>
        <fieldset>
          <legend>Sources</legend>
          <label><input type="checkbox" name="scout_source" value="weworkremotely" checked> We Work Remotely RSS</label>
          <label><input type="checkbox" name="scout_source" value="remotive" checked> Remotive API</label>
          <label><input type="checkbox" name="scout_source" value="remoteok"> RemoteOK API</label>
          <label><input type="checkbox" name="scout_source" value="github"> GitHub public issues</label>
        </fieldset>
        <label for="scout_limit">Maximum candidates</label>
        <input id="scout_limit" name="scout_limit" type="number" min="1" max="25" value="6" required>
        <div class="actions"><button id="scout-button" type="submit">Discover and assess</button></div>
      </form>

      <h3>Manual candidate</h3>
      <p class="small">Manual candidates remain explicitly unassessed until a separate governed assessment operation exists.</p>
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
        <label for="risk_class">Operator-entered risk class</label>
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
const statsBox = document.getElementById('stats');
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

function renderAssessment(item) {
  if (!item.assessment) {
    return '<section class="assessment"><h4>Assessment</h4><p class="small">No governed assessment packet. Manual or legacy candidate.</p></section>';
  }
  const ology = item.assessment.ology || {};
  const risk = item.assessment.risk || {};
  const skills = ology.required_skills || [];
  const flags = risk.risk_flags || [];
  return `<section class="assessment" aria-label="Ology and risk assessment">
    <h4>Ology + Risk Scout ${esc(item.assessment.assessment_version)}</h4>
    <dl>
      <dt>Domain</dt><dd>${esc(ology.primary_domain)}</dd>
      <dt>Radar</dt><dd>${esc(risk.radar_score)} / 100 — ${esc(risk.radar_decision)}</dd>
      <dt>Review</dt><dd>${risk.operator_review_required ? 'Operator review required' : 'No review recorded'}; qualification recommended: ${risk.qualification_recommended ? 'yes' : 'no'}</dd>
    </dl>
    <div>${skills.map(value => `<span class="badge">skill: ${esc(value)}</span>`).join('')}</div>
    <div>${flags.map(value => `<span class="badge">risk: ${esc(value)}</span>`).join('')}</div>
  </section>`;
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
      actions.push(`<button data-candidate-action="qualify" data-id="${esc(item.candidate_id)}" data-revision="${item.revision}">Qualify candidate</button>`);
    }
    if (qualified && !created) {
      actions.push(`<button data-candidate-action="create" data-id="${esc(item.candidate_id)}" data-revision="${item.revision}">Create proposed Quest</button>`);
    }
    if (created) {
      actions.push(`<span class="badge">Quest: ${esc(item.qualification.quest_id)}</span>`);
    }
    return `<article class="card">
      <h3>${esc(item.proposed_quest_title)}</h3>
      <div><span class="badge">${esc(item.status)}</span><span class="badge">${esc(item.source_name)}</span><span class="badge">risk: ${esc(item.risk_class)}</span></div>
      <p>${esc(item.description)}</p>
      ${renderAssessment(item)}
      <p class="meta"><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">Open source posting</a><br>Candidate ${esc(item.candidate_id)} · revision ${item.revision}</p>
      <div class="actions">${actions.join('')}</div>
    </article>`;
  }).join('');
}

function gateDetails(item) {
  const approval = item.approval_request || null;
  const acceptance = item.work_acceptance || null;
  if (!approval && !acceptance) return '';
  return `<section class="gate" aria-label="Work-acceptance evidence">
    <h4>Work-Acceptance Gate</h4>
    <dl>
      <dt>Approval request</dt><dd>${esc(approval && approval.approval_request_id)}</dd>
      <dt>Approval status</dt><dd>${esc(approval && approval.status)}</dd>
      <dt>Transition digest</dt><dd>${esc(approval && approval.transition_digest)}</dd>
      <dt>Receipt</dt><dd>${esc(acceptance && acceptance.authorization_receipt_id)}</dd>
    </dl>
  </section>`;
}

function questActions(item) {
  const id = esc(item.quest_id);
  const revision = Number(item.revision);
  const reasonId = `reason-${id}`;
  const controls = [`<label for="${reasonId}">Operator reason</label><input id="${reasonId}" data-quest-reason="${id}" maxlength="4000" placeholder="Record the basis for this decision">`];
  if (item.lifecycle_state === 'PROPOSED') {
    controls.push(`<button class="warning" data-quest-action="request" data-id="${id}" data-revision="${revision}">Request work approval</button>`);
    controls.push(`<button class="danger" data-quest-action="reject" data-id="${id}" data-revision="${revision}">Reject Quest</button>`);
    controls.push(`<button class="danger" data-quest-action="cancel" data-id="${id}" data-revision="${revision}">Cancel Quest</button>`);
  } else if (item.lifecycle_state === 'APPROVAL_REQUIRED') {
    controls.push(`<button class="approve" data-quest-action="accept" data-id="${id}" data-revision="${revision}">Authorize and accept work</button>`);
    controls.push(`<button class="danger" data-quest-action="reject" data-id="${id}" data-revision="${revision}">Reject Quest</button>`);
    controls.push(`<button class="danger" data-quest-action="cancel" data-id="${id}" data-revision="${revision}">Cancel Quest</button>`);
  } else if (item.lifecycle_state === 'WORK_ACCEPTED') {
    controls.push(`<button class="danger" data-quest-action="cancel" data-id="${id}" data-revision="${revision}">Cancel Quest</button>`);
  } else {
    return '';
  }
  return `<div class="actions">${controls.join('')}</div>`;
}

function renderQuests(items) {
  if (!items.length) {
    questList.innerHTML = '<p class="empty">No Quests created.</p>';
    return;
  }
  questList.innerHTML = items.map(item => {
    const next = item.lifecycle_state === 'PROPOSED'
      ? 'Request work approval.'
      : item.lifecycle_state === 'APPROVAL_REQUIRED'
        ? 'Obtain a bound authorization receipt, then accept work.'
        : item.lifecycle_state === 'WORK_ACCEPTED'
          ? 'Bounded internal work is authorized; delivery acceptance remains separate.'
          : 'Terminal or later lifecycle state.';
    return `<article class="card">
      <h3>${esc(item.title)}</h3>
      <p class="quest-state">${esc(item.lifecycle_state)}</p>
      <p>${esc(item.purpose)}</p>
      <p class="meta">${esc(item.quest_id)} · revision ${item.revision}<br>${esc(next)}</p>
      ${gateDetails(item)}
      <div>${(item.acceptance_criteria || []).map(value => `<span class="badge">${esc(value)}</span>`).join('')}</div>
      ${questActions(item)}
    </article>`;
  }).join('');
}

function renderStats(stats) {
  const values = [
    ['Candidates', stats.total_candidates],
    ['Awaiting review', stats.awaiting_review],
    ['Proposed', stats.proposed_quests],
    ['Approval required', stats.approval_required],
    ['Work accepted', stats.work_accepted]
  ];
  statsBox.innerHTML = values.map(([label, value]) => `<span class="badge">${esc(label)}: ${esc(value)}</span>`).join('');
}

async function loadBoard() {
  try {
    const [sources, board] = await Promise.all([
      api('/api/v1/quests/sources'),
      api('/api/v1/quest-board')
    ]);
    sourceSelect.innerHTML = sources.items.map(source => `<option value="${esc(source.id)}">${esc(source.name)} — ${esc(source.connector_status)}</option>`).join('');
    renderCandidates(board.candidates);
    renderQuests(board.active_quests);
    renderStats(board.stats);
    setStatus(`${board.stats.total_candidates} candidate(s), ${board.stats.total_quests} Quest(s). External action performed: false.`);
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
  setStatus('Opportunity Scout is performing bounded read-only discovery and assessment…');
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
    setStatus('Candidate recorded. It remains unassessed and unqualified.');
    await loadBoard();
  } catch (error) {
    setStatus(`Candidate ingestion failed: ${error.message}`, true);
  }
});

candidateList.addEventListener('click', async event => {
  const button = event.target.closest('button[data-candidate-action]');
  if (!button) return;
  button.disabled = true;
  try {
    if (button.dataset.candidateAction === 'qualify') {
      await api(`/api/v1/quests/candidates/${encodeURIComponent(button.dataset.id)}/qualify`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: Number(button.dataset.revision),
          decision: 'QUALIFY',
          operator_role: 'ACCOUNTABLE_OPERATOR',
          reason: 'Qualified through the local operator Quest Board.'
        })
      });
      setStatus('Candidate qualified. This has not created a Quest or accepted work.');
    } else if (button.dataset.candidateAction === 'create') {
      await api(`/api/v1/quests/candidates/${encodeURIComponent(button.dataset.id)}/create-quest`, {
        method: 'POST',
        body: JSON.stringify({
          expected_candidate_revision: Number(button.dataset.revision),
          operator_role: 'ACCOUNTABLE_OPERATOR'
        })
      });
      setStatus('Proposed Quest created. Work acceptance remains a separate receipt-bound decision.');
    }
    await loadBoard();
  } catch (error) {
    button.disabled = false;
    setStatus(`Candidate action failed: ${error.message}`, true);
  }
});

questList.addEventListener('click', async event => {
  const button = event.target.closest('button[data-quest-action]');
  if (!button) return;
  const id = button.dataset.id;
  const revision = Number(button.dataset.revision);
  const reasonInput = questList.querySelector(`input[data-quest-reason="${CSS.escape(id)}"]`);
  const reason = String(reasonInput && reasonInput.value || '').trim();
  const action = button.dataset.questAction;
  if (['reject', 'cancel'].includes(action) && !reason) {
    setStatus('A reason is required to reject or cancel a Quest.', true);
    reasonInput && reasonInput.focus();
    return;
  }
  if (action === 'accept' && !window.confirm('Authorize and record WORK_ACCEPTED for bounded internal work? This does not accept an external contract.')) {
    return;
  }
  button.disabled = true;
  try {
    if (action === 'request') {
      await api(`/api/v1/quests/${encodeURIComponent(id)}/request-work-approval`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: revision,
          operator_role: 'ACCOUNTABLE_OPERATOR',
          reason: reason || 'Work-acceptance review requested from the local Quest Board.'
        })
      });
      setStatus('Work approval requested. Quest is APPROVAL_REQUIRED; work is not accepted yet.');
    } else if (action === 'accept') {
      const prepared = await api(`/api/v1/quests/${encodeURIComponent(id)}/work-acceptance-authorization-bundle`);
      const authorization = await api('/api/v1/identity/authorize', {
        method: 'POST',
        body: JSON.stringify(prepared.bundle)
      });
      if (!authorization.passed || authorization.result !== 'PERMIT') {
        throw new Error(`Authorization did not permit work acceptance: ${authorization.reason_codes.join(', ')}`);
      }
      await api(`/api/v1/quests/${encodeURIComponent(id)}/accept-work`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: revision,
          operator_role: 'ACCOUNTABLE_OPERATOR',
          authorization_receipt_id: authorization.receipt_id,
          authorization_request: prepared.bundle.request,
          reason: reason || 'Bounded internal work accepted through the local Quest Board.'
        })
      });
      setStatus('WORK_ACCEPTED recorded with durable authorization evidence. No external contract or action was accepted.');
    } else if (action === 'reject') {
      await api(`/api/v1/quests/${encodeURIComponent(id)}/reject`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: revision,
          operator_role: 'ACCOUNTABLE_OPERATOR',
          reason
        })
      });
      setStatus('Quest rejected with an attributable reason.');
    } else if (action === 'cancel') {
      await api(`/api/v1/quests/${encodeURIComponent(id)}/cancel`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: revision,
          operator_role: 'ACCOUNTABLE_OPERATOR',
          reason
        })
      });
      setStatus('Quest cancelled with an attributable reason.');
    }
    await loadBoard();
  } catch (error) {
    button.disabled = false;
    setStatus(`Quest action failed: ${error.message}`, true);
  }
});

loadBoard();
</script>
</body>
</html>
"""
