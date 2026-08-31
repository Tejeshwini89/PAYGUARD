const scenarios = [
  { key: 'orphaned_payment_recoverable', name: 'Orphaned Transaction', amount: 7499, severity: 'HIGH', policy: 'AUTONOMOUS', diagnosis: 'ORDER_CREATION_FAILURE', action: 'RECONSTRUCT_ORDER' },
  { key: 'fulfillment_failure', name: 'Fulfillment Failure', amount: 12999, severity: 'HIGH', policy: 'HUMAN APPROVAL', diagnosis: 'TRANSIENT_FULFILLMENT_ERROR', action: 'RETRY_FULFILLMENT' },
  { key: 'orphaned_payment', name: 'Orphaned Transaction', amount: 4999, severity: 'MEDIUM', policy: 'DENIED', diagnosis: 'DOWNSTREAM_STATE_INCOMPLETE', action: 'ESCALATE_HUMAN' },
];

const state = { records: [], selected: null, ledger: [], benchmark: null, warroomTimer: null };

const $ = (id) => document.getElementById(id);
const money = (v) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v);

async function getScenario(s) {
  const res = await fetch(`/ai-investigate/${s.key}`);
  if (!res.ok) throw new Error(`Failed to load ${s.key}`);
  return await res.json();
}

async function getLedger() {
  const res = await fetch('/ledger');
  const data = await res.json();
  return data.entries || [];
}

function policyFor(item) {
  if (!item?.policy_decisions?.length) return 'INVESTIGATING';
  const decisions = item.policy_decisions;
  if (decisions.some(d => d.status === 'ALLOW')) return 'AUTONOMOUS';
  if (decisions.some(d => d.status === 'REQUIRE_HUMAN')) return 'HUMAN APPROVAL';
  if (decisions.some(d => d.status === 'DENY')) return 'DENIED';
  return 'INVESTIGATING';
}

function flattenInvestigation(s, payload) {
  const inv = payload.investigations?.[0];
  if (!inv) return null;
  const incident = inv.incident || {};
  const diagnosis = inv.diagnosis || {};
  const decision = inv.policy_decisions?.find(x => x.action_type === diagnosis.recommended_action) || inv.policy_decisions?.[0];
  return {
    scenario: s,
    key: s.key,
    tx: payload.transaction_id,
    amount: incident.revenue_at_risk || s.amount,
    type: diagnosis.incident_type || incident.incident_type,
    title: s.name,
    severity: incident.severity || s.severity,
    policy: policyFor(inv),
    diagnosis: diagnosis.root_cause || s.diagnosis,
    confidence: Math.round((diagnosis.confidence || 0) * 100),
    evidence: diagnosis.evidence || [],
    actions: diagnosis.candidate_actions || [],
    policyDecisions: inv.policy_decisions || [],
    state: payload.state || {},
  };
}

async function runBenchmark() {
  const res = await fetch('/portfolio/benchmark?execute_autonomous=true');
  if (!res.ok) throw new Error('Benchmark failed');
  const data = await res.json();
  state.benchmark = data;
  renderBenchmark();
  replayWarRoom(data);
}

function renderBenchmark() {
  const b = state.benchmark;
  if (!b) return;
  $('benchmarkSummary').innerHTML = `
    <div class="benchmark-grid">
      <div><span>Detection precision</span><strong>${Math.round(b.detection_precision * 100)}%</strong></div>
      <div><span>Detection recall</span><strong>${Math.round(b.detection_recall * 100)}%</strong></div>
      <div><span>Verified recoveries</span><strong>${b.verified_recoveries}</strong></div>
      <div><span>Simulated revenue recovered</span><strong>${money(b.revenue_recovered)}</strong></div>
      <div><span>Unsafe autonomous actions</span><strong>${b.unsafe_autonomous_actions}</strong></div>
      <div><span>Out-of-order cases</span><strong>${b.out_of_order_cases}</strong></div>
    </div>
    <div class="benchmark-note">Controlled test data only — these amounts are simulated and are not real merchant revenue.</div>`;
}

function replayWarRoom(b) {
  const stream = $('warroomStream');
  if (!stream) return;
  if (state.warroomTimer) clearInterval(state.warroomTimer);
  stream.innerHTML = '';
  const cases = (b.cases || []).filter(c => c.detected);
  let idx = 0;
  let recovered = 0, auto = 0, human = 0, blocked = 0;
  $('wrEvents').textContent = '0 / 100';
  $('wrIncidents').textContent = '0';
  $('wrAuto').textContent = '0';
  $('wrHuman').textContent = '0';
  $('wrBlocked').textContent = '0';
  $('wrRecovered').textContent = money(0);
  $('wrProgress').style.width = '0%';
  $('warroomStatus').textContent = 'REPLAYING';
  $('warroomStatus').style.color = 'var(--blue)';

  state.warroomTimer = setInterval(() => {
    if (idx >= cases.length) {
      clearInterval(state.warroomTimer);
      $('wrEvents').textContent = '100 / 100';
      $('wrProgress').style.width = '100%';
      $('warroomStatus').textContent = 'RECOVERY REPLAY COMPLETE';
      $('warroomStatus').style.color = 'var(--green)';
      return;
    }
    const c = cases[idx++];
    const action = (c.actions || [])[0] || {};
    const policy = action.policy || 'REVIEW';
    const verification = action.verification || '';
    if (policy === 'ALLOW_AUTONOMOUS') auto++;
    else if (policy === 'REQUIRE_HUMAN') human++;
    else blocked++;
    recovered += Number(action.revenue_recovered || 0);

    const row = document.createElement('div');
    const tagClass = policy === 'ALLOW_AUTONOMOUS' ? 'stream-green' : policy === 'REQUIRE_HUMAN' ? 'stream-amber' : 'stream-red';
    const label = policy === 'ALLOW_AUTONOMOUS' ? (verification === 'VERIFIED' ? 'RECOVERED' : 'AUTONOMOUS') : policy === 'REQUIRE_HUMAN' ? 'HUMAN REVIEW' : 'BLOCKED';
    row.className = 'stream-row';
    row.innerHTML = `
      <div class="stream-id">${c.transaction_id}</div>
      <div class="stream-main"><strong>${(c.predicted_incidents || []).join(' · ')}</strong><div class="stream-sub">${c.scenario.replaceAll('_',' ')} · confidence policy gate</div></div>
      <div class="stream-amount">${money(c.amount)}</div>
      <div class="stream-tag ${tagClass}">${label}</div>`;
    stream.prepend(row);
    while (stream.children.length > 16) stream.removeChild(stream.lastChild);

    const processed = Math.min(100, Math.round((idx / cases.length) * 100));
    $('wrEvents').textContent = `${processed} / 100`;
    $('wrIncidents').textContent = String(idx);
    $('wrAuto').textContent = String(auto);
    $('wrHuman').textContent = String(human);
    $('wrBlocked').textContent = String(blocked);
    $('wrRecovered').textContent = money(recovered);
    $('wrProgress').style.width = `${processed}%`;
  }, 120);
}

async function refreshGateway() {
  try {
    const res = await fetch('/gateway');
    const data = await res.json();
    const rp = data.razorpay || {};
    const configured = rp.configured === true;
    $('gatewayMode').textContent = configured ? 'RAZORPAY TEST API READY' : 'SIMULATOR ACTIVE';
    $('gatewayMode').style.color = configured ? 'var(--green)' : 'var(--blue)';
    $('gatewaySummary').innerHTML = `
      <div class="gateway-grid">
        <div><span>Active adapter</span><strong>${data.active_adapter || 'simulator'}</strong></div>
        <div><span>Razorpay adapter</span><strong>${configured ? 'Configured' : 'Not configured'}</strong></div>
        <div><span>Verification mode</span><strong>Read / verify only</strong></div>
      </div>
      <div class="benchmark-note">PAYGUARD keeps gateway verification separate from recovery authorization. Live money movement is not performed by the Razorpay adapter.</div>`;
    $('gatewayBadge').textContent = configured ? 'RAZORPAY TEST MODE' : 'DEMO / SIMULATOR';
  } catch (e) {
    $('gatewaySummary').textContent = 'Gateway status unavailable';
  }
}

async function refreshDashboard() {
  const results = [];
  for (const s of scenarios) {
    try {
      const payload = await getScenario(s);
      const flat = flattenInvestigation(s, payload);
      if (flat) results.push(flat);
    } catch (e) {
      console.error(e);
    }
  }
  state.records = results;
  state.ledger = await getLedger();
  renderMetrics();
  renderIncidents();
  renderLedger();
  if (state.selected) {
    const current = state.records.find(x => x.key === state.selected.key);
    if (current) showDetail(current);
  }
}

function renderMetrics() {
  const atRisk = state.records.reduce((a, r) => a + r.amount, 0) * 8;
  const recoverable = state.records.reduce((a, r) => a + (r.policy === 'DENIED' ? 0 : r.amount), 0) * 5;
  const recovered = state.ledger.reduce((a, e) => a + Number(e.revenue_recovered || 0), 0);
  const incidents = state.records.length;
  $('metrics').innerHTML = `
    <div class="metric"><div class="label">Revenue at risk</div><div class="value">${money(atRisk)}</div><div class="delta">+ live incident exposure</div></div>
    <div class="metric"><div class="label">Potentially recoverable</div><div class="value">${money(recoverable)}</div><div class="delta">policy-aware estimate</div></div>
    <div class="metric"><div class="label">Recovered in session</div><div class="value">${money(recovered)}</div><div class="delta">verified outcomes</div></div>
    <div class="metric"><div class="label">Active incidents</div><div class="value">${incidents}</div><div class="delta">cross-system anomalies</div></div>`;
}

function renderIncidents() {
  $('incidentList').innerHTML = state.records.map((r, idx) => `
    <div class="incident-row" data-key="${r.key}">
      <div>
        <div class="incident-top"><span class="severity ${r.severity === 'HIGH' ? 'sev-high' : 'sev-medium'}"></span><span class="incident-title">${r.title}</span></div>
        <div class="incident-meta">${r.type} · confidence ${r.confidence}% · ${r.tx}</div>
      </div>
      <div class="incident-right"><div class="amount">${money(r.amount)}</div><span class="policy-pill ${r.policy === 'AUTONOMOUS' ? 'pill-green' : r.policy === 'HUMAN APPROVAL' ? 'pill-amber' : 'pill-red'}">${r.policy}</span></div>
    </div>`).join('');
  document.querySelectorAll('.incident-row').forEach(el => el.addEventListener('click', () => {
    const item = state.records.find(x => x.key === el.dataset.key);
    state.selected = item; showDetail(item);
  }));
}

function formatEvidence(e) {
  if (e == null) return 'No evidence returned.';
  if (typeof e === 'string') return e;
  const fact = e.fact || e.name || 'Evidence';
  const value = e.value == null ? '' : String(e.value);
  const source = e.source ? ` · ${e.source}` : '';
  return `<strong>${fact}</strong><span class="evidence-value">${value}</span><span class="evidence-source">${source}</span>`;
}

function showDetail(r) {
  $('detailEmpty').classList.add('hidden');
  $('detailContent').classList.remove('hidden');
  const mainAction = r.actions[0];
  const allowed = r.policy === 'AUTONOMOUS';
  $('detailContent').innerHTML = `
    <div class="detail-wrap">
      <div class="detail-title">
        <div><div class="panel-kicker">INCIDENT ${r.tx}</div><h3>${r.title}</h3><div class="incident-meta">${r.type}</div></div>
        <div><div class="detail-amount">${money(r.amount)}</div><div class="incident-meta">Revenue at risk</div></div>
      </div>

      <div class="detail-grid">
        <div class="state-box"><div class="lbl">PAYMENT</div><div class="st">${r.state.payment || '—'}</div></div>
        <div class="state-box"><div class="lbl">ORDER</div><div class="st">${r.state.order || '—'}</div></div>
        <div class="state-box"><div class="lbl">INVENTORY</div><div class="st">${r.state.inventory || '—'}</div></div>
        <div class="state-box"><div class="lbl">FULFILLMENT</div><div class="st">${r.state.fulfillment || '—'}</div></div>
      </div>

      <div class="detail-section"><h4>AI DIAGNOSIS</h4><div class="evidence-item"><strong>${r.diagnosis}</strong><br/>Confidence ${r.confidence}%</div></div>
      <div class="detail-section"><h4>EVIDENCE</h4><div class="evidence">${r.evidence.map(e => `<div class="evidence-item">${formatEvidence(e)}</div>`).join('') || '<div class="evidence-item">No extra evidence returned.</div>'}</div></div>

      ${mainAction ? `<div class="detail-section"><h4>RECOVERY PLAN</h4><div class="action-card">
        <div class="action-head"><div class="action-type">${mainAction.action_type}</div><div class="action-val">EV ${Number(mainAction.expected_value || 0).toLocaleString('en-IN')}</div></div>
        <div class="action-meta">Expected recovery ${money(mainAction.expected_recovery || 0)} · Cost ${money(mainAction.action_cost || 0)} · Confidence ${Math.round((mainAction.confidence || 0) * 100)}%</div>
        <div class="action-buttons">${allowed ? `<button class="primary-btn" id="executeAction">Execute recovery</button>` : `<button class="secondary-btn" disabled>${r.policy === 'HUMAN APPROVAL' ? 'Requires human approval' : 'Blocked by policy'}</button>`}<button class="secondary-btn" id="ledgerJump">View decision ledger</button></div>
      </div></div>` : ''}
    </div>`;
  if (allowed) $('executeAction').addEventListener('click', () => executeRecovery(r, mainAction));
  $('ledgerJump').addEventListener('click', () => $('ledgerSection').scrollIntoView({behavior:'smooth'}));
}

async function executeRecovery(r, action) {
  const btn = $('executeAction');
  btn.disabled = true; btn.textContent = 'Executing…';
  try {
    const res = await fetch(`/recover/${r.key}/${encodeURIComponent(action.action_type)}`, { method: 'POST' });
    const data = await res.json();
    const status = data?.outcome?.verification?.status || 'UNKNOWN';
    showToast(`Recovery ${status.toLowerCase()}: ${action.action_type}`);
    await refreshGateway();
refreshDashboard();
    state.selected = r; showDetail(r);
  } catch (e) {
    showToast('Recovery request failed');
  }
}

function renderLedger() {
  if (!state.ledger.length) {
    $('ledgerTable').innerHTML = '<div class="empty-table">No recovery decisions yet. Execute a permitted action to populate the ledger.</div>';
    return;
  }
  const header = '<div class="ledger-row header"><div>INCIDENT</div><div>ACTION</div><div>POLICY</div><div>VERIFICATION</div><div>RECOVERED</div></div>';
  const rows = state.ledger.slice().reverse().map(e => `<div class="ledger-row"><div class="mono">${e.incident_id}</div><div>${e.action_type}</div><div>${e.policy_status}</div><div>${e.verification_status}</div><div>${money(e.revenue_recovered || 0)}</div></div>`).join('');
  $('ledgerTable').innerHTML = header + rows;
}

function showToast(msg) {
  const t = $('toast'); t.textContent = msg; t.classList.remove('hidden');
  clearTimeout(window.__toast); window.__toast = setTimeout(() => t.classList.add('hidden'), 2600);
}

$('runPortfolio').addEventListener('click', async () => { showToast('Running 100-transaction incident sweep…'); try { await runBenchmark(); await refreshGateway();
refreshDashboard(); showToast('Benchmark complete — results are simulated'); } catch (e) { console.error(e); showToast('Benchmark failed'); } });
$('refreshLedger').addEventListener('click', async () => { state.ledger = await getLedger(); renderLedger(); showToast('Ledger refreshed'); });
$('navIncidents').addEventListener('click', () => $('incidentsSection').scrollIntoView({behavior:'smooth'}));
$('navDecisions').addEventListener('click', () => $('ledgerSection').scrollIntoView({behavior:'smooth'}));
$('navWarroom').addEventListener('click', () => $('warroomPanel').scrollIntoView({behavior:'smooth'}));

refreshGateway();
refreshDashboard();
