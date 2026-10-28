'use strict';
/* Genesis synthetic workbench — never carries production authority. */
const state = { catalog: null, scenarios: [], sequence: 0 };
const $ = id => document.getElementById(id);
const statusLabel = text => text || 'NONE';
function option(value, label) {
  const item = document.createElement('option');
  item.value = value;
  item.textContent = label;
  return item;
}
function setOptions(select, records, makeLabel, emptyText) {
  const choices = [];
  if (emptyText) choices.push(option('', emptyText));
  for (const item of records) choices.push(option(item.id, makeLabel(item)));
  select.replaceChildren(...choices);
}
function actorById(actorId) {
  return state.catalog.actors.find(a => a.id === actorId);
}
function membership(actorId) {
  return state.catalog.memberships.find(m => m.actor_id === actorId);
}
function showActor() {
  if (!state.catalog) return;
  const actorId = $('actor').value;
  const actor = actorById(actorId);
  const members = membership(actorId);
  const reps = state.catalog.representations.filter(r => r.actor_id === actorId);
  const licences = state.catalog.licences.filter(l => l.actor_id === actorId);
  $('actor-state').textContent = statusLabel(actor?.state);
  $('actor-role').textContent = statusLabel(actor?.role).replaceAll('_', ' ').toUpperCase();
  $('membership-state').textContent = members?.state || 'NOT A MEMBER';
  $('representation-state').textContent = reps.length ? reps.map(r => `${r.node_id} · ${r.state}`).join(' / ') : 'NOT REPRESENTING A NODE';
  $('actor-licences').replaceChildren(...(licences.length ? licences.map(lic => {
    const div = document.createElement('div');
    div.className = 'licence';
    const title = document.createElement('strong');
    title.textContent = lic.id + ' · ' + lic.state;
    const subtitle = document.createElement('span');
    subtitle.textContent = `${lic.actions.join(', ')} | valid to ${lic.valid_until}`;
    div.append(title, subtitle);
    return div;
  }) : [(() => {const x=document.createElement('div');x.textContent='No synthetic licence';return x;})()]));
}
function preserveSyntheticOption(select, value) {
  if (value && ![...select.options].some(o => o.value === value)) {
    select.appendChild(option(value, value + ' · NEGATIVE TEST ONLY'));
  }
}
function applyScenario(index) {
  if (index === '') return;
  const selected = state.scenarios[Number(index)];
  if (!selected) return;
  const r = selected.request;
  preserveSyntheticOption($('actor'), r.actor_id);
  preserveSyntheticOption($('action'), r.action);
  $('actor').value = r.actor_id;
  $('action').value = r.action;
  $('node').value = r.node_id || '';
  $('supplier').value = r.legal_supplier_id || '';
  showActor();
  $('decision-explanation').textContent = `Scenario ${selected.name}: expected ${selected.decision}. Click Evaluate to produce a real synthetic test receipt.`;
}
async function read(path) {
  const response = await fetch(path, {cache: 'no-store', credentials: 'omit'});
  if (!response.ok) throw new Error(`Local fixture request failed (${response.status})`);
  return response.json();
}
async function initialize() {
  try {
    const [catalog, scenarios] = await Promise.all([read('/catalog'), read('/scenarios')]);
    if (!catalog.synthetic || catalog.executable !== false || !scenarios.synthetic) throw new Error('Unexpected non-synthetic fixture response');
    state.catalog = catalog;
    state.scenarios = scenarios.scenarios;
    setOptions($('actor'), catalog.actors, a => `${a.id} · ${a.role}`);
    $('action').replaceChildren(option('', 'Choose a synthetic action'), ...catalog.actions.map(a => option(a,a)));
    setOptions($('node'), catalog.organizations.filter(o=>o.kind==='bnr_node'), o=>`${o.id} · ${o.name}`, 'No node selected');
    setOptions($('supplier'), catalog.organizations.filter(o=>o.kind==='legal_supplier'), o=>`${o.id} · ${o.name}`, 'No legal supplier selected');
    $('scenario').replaceChildren(option('', 'Manual test — select fields below'), ...state.scenarios.map((s,i)=>option(String(i),`${s.name} · ${s.decision}`)));
    $('actor-count').textContent = String(catalog.actors.length).padStart(2,'0');
    $('licence-count').textContent = String(catalog.licences.length).padStart(2,'0');
    $('scenario-count').textContent = String(state.scenarios.length).padStart(2,'0');
    $('actor').addEventListener('change',()=>{$('scenario').value='';showActor();});
    for (const field of ['action','node','supplier']) $(field).addEventListener('change',()=>{$('scenario').value='';});
    $('scenario').addEventListener('change',()=>applyScenario($('scenario').value));
    $('run').disabled = false;
    $('scenario').value = '0';
    applyScenario('0');
    $('decision-explanation').textContent = 'All fixture actors are fictional. Pick a scenario and evaluate to inspect the resulting non-executable receipt.';
  } catch (err) {
    $('decision-explanation').textContent = `Fixture unavailable: ${err.message}. The test environment denies simulation until its catalogue is valid.`;
    $('decision-pill').textContent = 'UNAVAILABLE';
    $('decision-pill').className = 'decision deny';
    $('run').disabled = true;
  }
}
$('decision-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.catalog || $('run').disabled) return;
  $('run').disabled = true;
  const selected = $('scenario').value === '' ? null : state.scenarios[Number($('scenario').value)];
  const request = {
    request_id: `SYN-REQ-WORKBENCH-${++state.sequence}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    actor_id: $('actor').value,
    action: $('action').value,
    environment: 'synthetic-ci',
  };
  if ($('node').value) request.node_id = $('node').value;
  if ($('supplier').value) request.legal_supplier_id = $('supplier').value;
  // Explicitly selected negative test scenarios may carry an intentionally
  // non-synthetic environment or action. This cannot grant authority.
  if (selected) {
    if (selected.request.environment) request.environment = selected.request.environment;
    if (selected.request.action && selected.request.action !== request.action) request.action = selected.request.action;
  }
  try {
    const response = await fetch('/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(request),cache:'no-store',credentials:'omit'});
    const result = await response.json();
    if (!response.ok || result.synthetic !== true || result.executable !== false) throw new Error('Simulator rejected or returned non-synthetic data');
    const decision = result.decision;
    if (!['ALLOW','DENY','ESCALATE'].includes(decision)) throw new Error('Unknown decision outcome');
    $('decision-pill').textContent = decision;
    $('decision-pill').className = `decision ${decision.toLowerCase()}`;
    $('receipt-request').textContent = result.request_id;
    $('receipt-reason').textContent = result.reason_code;
    $('receipt-digest').textContent = result.evidence_sha256;
    $('receipt-json').textContent = JSON.stringify(result, null, 2);
    $('decision-explanation').textContent = selected ? `${selected.name}: expected ${selected.decision}; observed ${decision}. ${decision===selected.decision?'PASS — expected result.':'MISMATCH — test fixture needs correction.'} No real action executed.` : `Simulated ${decision}: ${result.reason_code}. No real action executed.`;
  } catch (err) {
    $('decision-pill').textContent = 'ERROR';
    $('decision-pill').className = 'decision deny';
    $('decision-explanation').textContent = `Fail closed: ${err.message}. No action executed.`;
  } finally {
    $('run').disabled = false;
  }
});
initialize();
