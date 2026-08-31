/* Evaluator-facing metric layer: render only values returned by the benchmark API. */
(function () {
  const originalRunBenchmark = window.runBenchmark;

  window.renderMetrics = function () {
    const metrics = document.getElementById('metrics');
    if (!metrics) return;
    const b = window.state?.benchmark;
    const money = (v) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v || 0);

    if (!b) {
      metrics.innerHTML = `
        <div class="metric"><div class="label">Benchmark status</div><div class="value">READY</div><div class="delta">Run the 100-transaction evaluation</div></div>
        <div class="metric"><div class="label">Revenue at risk</div><div class="value">—</div><div class="delta">Awaiting benchmark data</div></div>
        <div class="metric"><div class="label">Verified recovered</div><div class="value">—</div><div class="delta">No benchmark executed</div></div>
        <div class="metric"><div class="label">Detection precision</div><div class="value">—</div><div class="delta">Measured after evaluation</div></div>`;
      return;
    }

    metrics.innerHTML = `
      <div class="metric"><div class="label">Revenue at risk</div><div class="value">${money(b.revenue_at_risk)}</div><div class="delta">100-transaction benchmark</div></div>
      <div class="metric"><div class="label">Verified recovered</div><div class="value">${money(b.revenue_recovered)}</div><div class="delta">${b.verified_recoveries} verified recoveries</div></div>
      <div class="metric"><div class="label">Detection precision</div><div class="value">${Math.round((b.detection_precision || 0) * 100)}%</div><div class="delta">${b.true_positives} true positives · ${b.false_positives} false positives</div></div>
      <div class="metric"><div class="label">Policy outcomes</div><div class="value">${b.autonomous_allowed} / ${b.human_required} / ${b.denied}</div><div class="delta">Autonomous · Human · Denied</div></div>`;
  };

  window.replayWarRoom = function (b) {
    const stream = document.getElementById('warroomStream');
    if (!stream) return;
    if (window.state?.warroomTimer) clearInterval(window.state.warroomTimer);
    stream.innerHTML = '';
    const cases = b.cases || [];
    let idx = 0, incidents = 0, auto = 0, human = 0, blocked = 0, recovered = 0;
    const money = (v) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v || 0);

    document.getElementById('wrEvents').textContent = '0 / 100';
    document.getElementById('wrIncidents').textContent = '0';
    document.getElementById('wrAuto').textContent = '0';
    document.getElementById('wrHuman').textContent = '0';
    document.getElementById('wrBlocked').textContent = '0';
    document.getElementById('wrRecovered').textContent = money(0);
    document.getElementById('wrProgress').style.width = '0%';
    document.getElementById('warroomStatus').textContent = 'REPLAYING';
    document.getElementById('warroomStatus').style.color = 'var(--blue)';

    window.state.warroomTimer = setInterval(() => {
      if (idx >= cases.length) {
        clearInterval(window.state.warroomTimer);
        document.getElementById('wrEvents').textContent = `${cases.length} / ${cases.length}`;
        document.getElementById('wrProgress').style.width = '100%';
        document.getElementById('warroomStatus').textContent = 'RECOVERY REPLAY COMPLETE';
        document.getElementById('warroomStatus').style.color = 'var(--green)';
        return;
      }

      const c = cases[idx++];
      const actions = c.actions || [];
      if (c.detected) incidents++;
      for (const action of actions) {
        if (action.policy === 'ALLOW_AUTONOMOUS') auto++;
        else if (action.policy === 'REQUIRE_HUMAN') human++;
        else if (action.policy === 'DENY') blocked++;
        recovered += Number(action.revenue_recovered || 0);
      }

      if (c.detected) {
        const action = actions[0] || {};
        const policy = action.policy || 'REVIEW';
        const verification = action.verification || '';
        const tagClass = policy === 'ALLOW_AUTONOMOUS' ? 'stream-green' : policy === 'REQUIRE_HUMAN' ? 'stream-amber' : 'stream-red';
        const label = policy === 'ALLOW_AUTONOMOUS' ? (verification === 'VERIFIED' ? 'RECOVERED' : 'AUTONOMOUS') : policy === 'REQUIRE_HUMAN' ? 'HUMAN REVIEW' : 'BLOCKED';
        const row = document.createElement('div');
        row.className = 'stream-row';
        row.innerHTML = `
          <div class="stream-id">${c.transaction_id}</div>
          <div class="stream-main"><strong>${(c.predicted_incidents || []).join(' · ')}</strong><div class="stream-sub">${c.scenario.replaceAll('_',' ')} · policy gate</div></div>
          <div class="stream-amount">${money(c.amount)}</div>
          <div class="stream-tag ${tagClass}">${label}</div>`;
        stream.prepend(row);
        while (stream.children.length > 16) stream.removeChild(stream.lastChild);
      }

      document.getElementById('wrEvents').textContent = `${idx} / ${cases.length}`;
      document.getElementById('wrIncidents').textContent = String(incidents);
      document.getElementById('wrAuto').textContent = String(auto);
      document.getElementById('wrHuman').textContent = String(human);
      document.getElementById('wrBlocked').textContent = String(blocked);
      document.getElementById('wrRecovered').textContent = money(recovered);
      document.getElementById('wrProgress').style.width = `${Math.round((idx / cases.length) * 100)}%`;
    }, 120);
  };

  window.runBenchmark = async function () {
    const res = await fetch('/portfolio/benchmark?execute_autonomous=true');
    if (!res.ok) throw new Error('Benchmark failed');
    const data = await res.json();
    window.state.benchmark = data;
    window.renderMetrics();
    window.renderBenchmark();
    window.replayWarRoom(data);
  };
})();
