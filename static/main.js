let report;
const $ = id => document.getElementById(id);
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (amount, currency) => `${currency} ${(amount / (currency === 'JPY' ? 1 : 100)).toLocaleString('en-US', {minimumFractionDigits:currency === 'JPY' ? 0 : 2, maximumFractionDigits:currency === 'JPY' ? 0 : 2})}`;
async function post(path, body) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json','X-SettlementProof-Token':document.querySelector('meta[name="csrf"]').content}, body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function detail(index) {
  const c = report.cases[index];
  if (!c) { $('detail').textContent = 'No orders available.'; return; }
  document.querySelectorAll('#queue tr').forEach((row, n) => row.classList.toggle('selected', n === index));
  $('detail').innerHTML = `<div class="detail-top"><div><h3>${escape(c.invoice)} · Evidence trail</h3><small>${escape(c.order_id)}</small></div><span class="badge ${c.status}">${escape(c.status)}</span></div>` +
    (c.issues.length ? c.issues.map(i => `<div class="issue"><strong>${escape(i.code.replaceAll('_',' '))}</strong><p>${escape(i.message)}</p><small>Proposed next step: ${escape(i.action)}</small></div>`).join('') : '<p>Supplied merchant expectations match the observed completed resources.</p>') +
    `<div class="evidence">${c.evidence.map(r => `<article><strong>${escape(r.kind.toUpperCase())} / ${escape(r.id)}</strong><br>${escape(r.currency)} ${escape(r.amount)} · ${escape(r.status)}<br><code>SHA-256 prefix ${escape(r.fingerprint)}</code></article>`).join('')}</div><details><summary>Inspect evidence JSON and unique event deliveries</summary><pre>${escape(JSON.stringify({resources:c.evidence,events:c.events},null,2))}</pre></details>`;
}
async function load() {
  const response = await fetch('/api/report');
  if (!response.ok) throw new Error('Could not load reconciliation');
  report = await response.json();
  $('source').textContent = report.source === 'paypal_sandbox_api' ? 'PayPal sandbox API' : 'Synthetic demo';
  for (const k of ['orders','review','replays']) $(k).textContent = report.summary[k];
  $('totals').innerHTML = Object.entries(report.totals).map(([currency, t]) => `<div class="total"><strong>${escape(currency)} reconciliation</strong><br>Expected ${money(t.expected_minor,currency)} · Observed ${money(t.actual_minor,currency)}<br>Difference <b>${money(t.difference_minor,currency)}</b></div>`).join('');
  $('queue').innerHTML = report.cases.map((c, i) => `<tr tabindex="0" data-index="${i}" aria-label="Open evidence for ${escape(c.invoice)}"><td><strong>${escape(c.invoice)}</strong><small>${escape(c.label)}</small></td><td>${money(c.expected_minor,c.currency)}</td><td>${money(c.actual_minor,c.currency)}</td><td class="${c.difference_minor ? 'negative' : ''}">${money(c.difference_minor,c.currency)}</td><td><span class="badge ${c.status}">${c.status === 'review' ? 'Needs review' : c.status === 'watch' ? 'Watch' : 'Matched'}</span></td></tr>`).join('');
  document.querySelectorAll('[data-index]').forEach(row => { row.onclick = () => detail(Number(row.dataset.index)); row.onkeydown = e => { if (e.key === 'Enter') detail(Number(row.dataset.index)); }; });
  const authenticated = report.source === 'paypal_sandbox_api' && (report.api_evidence || []).some(call => call.status === 200);
  $('configured').textContent = authenticated ? 'Authenticated sandbox reads' : report.sandbox_configured ? 'Sandbox ready to connect' : 'Sandbox credentials needed';
  $('coverage').textContent = report.coverage_note;
  $('api-evidence').innerHTML = report.api_evidence.length ? `<details open><summary>Successful sandbox API reads</summary><pre>${escape(JSON.stringify(report.api_evidence,null,2))}</pre></details>` : '';
  detail(Math.max(0, report.cases.findIndex(c => c.status === 'review')));
}
$('ask').onsubmit = async e => {
  e.preventDefault();
  $('answer').textContent = 'Selecting investigation…';
  try {
    const a = await post('/api/investigate', {query:$('question').value});
    const p = a.prediction;
    $('answer').innerHTML = `<p>${escape(a.answer)}</p><span class="model-pill">${escape(p.model)} · ${p.abstained ? 'ABSTAINED' : escape(p.intent)} · model support ${Math.round(p.support*100)}% (not calibrated confidence)<br>Matched terms: ${escape(p.matched_terms.join(', ') || 'none')}</span>` + a.cases.map(c => `<article><strong>${escape(c.invoice)} · ${money(c.difference_minor,c.currency)} difference</strong><p>${c.issues.map(i => escape(i.message)).join('<br>')}</p><small>Evidence: ${escape(c.resource_ids.join(', '))}</small></article>`).join('');
  } catch (err) { $('answer').textContent = err.message; }
};
document.querySelectorAll('[data-query]').forEach(button => button.onclick = () => { $('question').value = button.dataset.query; $('ask').requestSubmit(); });
$('reset').onclick = async () => { await post('/api/reset',{}); $('answer').textContent = 'Demo reset. Select a new investigation.'; await load(); };
$('export').onclick = () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = 'settlementproof-audit.json'; a.click(); URL.revokeObjectURL(url);
};
$('connect').onsubmit = async e => {
  e.preventDefault(); $('sync').disabled = true; $('connect-status').textContent = 'Reading sandbox resources…';
  try {
    const body = Object.fromEntries(new FormData(e.target));
    body.refund_ids = body.refund_ids.split(',').map(s => s.trim()).filter(Boolean);
    await post('/api/sandbox',body); await load();
    $('connect-status').textContent = 'Authenticated sandbox evidence loaded.';
    $('answer').textContent = 'Data source changed. Run a fresh investigation.';
    $('overview').scrollIntoView();
  } catch (err) { $('connect-status').textContent = err.message; }
  finally { $('sync').disabled = false; }
};
load().catch(err => { $('detail').textContent = err.message; });
