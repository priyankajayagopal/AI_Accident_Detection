const $ = s => document.querySelector(s);
let selected = null, incidents = [];
const api = (p, o) => fetch('/api' + p, o).then(r => r.ok ? r.json().catch(() => ({})) : r.json().then(e => { throw new Error(e.detail || r.status); }));
const op = () => $('#operator').value;
const post = (p, body) => api(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || { operator: op() }) });
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

async function loadCams() {
  const cams = await api('/cameras');
  if (!$('#camsel').options.length) cams.forEach(c => $('#camsel').add(new Option(`${c.camera_id} - ${c.name}`, c.camera_id)));
  $('#camgrid').innerHTML = cams.map(c => `<div class="cam"><b>${c.camera_id}</b><br><span class="muted">${esc(c.road_segment)}</span><br>
    <span class="pill ${c.status === 'running' ? 'on' : ''}">${esc(c.status)}</span> ${c.stats.vehicle_count ?? ''} veh</div>`).join('');
}
async function loadIncidents() {
  incidents = await api('/incidents');
  $('#inclist').innerHTML = incidents.map(i => `<div class="item ${i.incident_id === selected ? 'sel' : ''}" onclick="sel('${i.incident_id}')">
    <b>#${i.incident_id}</b> <span class="pill st-${i.status}">${i.status}</span> <span class="pill">${i.subtype}</span>
    <span class="sev-${i.estimated_severity.level}">${i.estimated_severity.level}</span><br>
    <span class="muted">${i.location.camera_id} ${esc(i.location.road_segment)} - score ${(i.proposal_score || 0).toFixed(2)}</span></div>`).join('') || '<span class="muted">No incidents yet. Start a camera.</span>';
  if (selected) showDetail(selected);
}
window.sel = id => { selected = id; loadIncidents(); };
async function showDetail(id) {
  const d = await api('/incidents/' + id), i = d.incident, v = i.verification || {};
  const img = ['before', 'impact', 'after'].map(n => `<img src="/api/incidents/${id}/evidence/${n}.jpg" onerror="this.style.display='none'">`).join('');
  const can = s => i.status === s;
  $('#incdetail').innerHTML = `
   <div class="kpis"><div class="kpi"><b>${Math.round((v.combined_score || 0) * 100)}%</b><span>Accident confidence</span></div>
   <div class="kpi"><b class="sev-${i.estimated_severity.level}">${i.estimated_severity.level}</b><span>Severity</span></div>
   <div class="kpi"><b>${i.vehicles_involved}</b><span>Vehicles</span></div><div class="kpi"><b>${i.blocked_lanes}</b><span>Blocked lanes</span></div>
   <div class="kpi"><b>${i.traffic_density_pct ?? '-'}%</b><span>Density</span></div><div class="kpi"><b>${i.avg_speed_kmh ?? '-'}</b><span>Avg km/h</span></div>
   <div class="kpi"><b>${i.queue_length_veh ?? '-'}</b><span>Queue</span></div><div class="kpi"><b>${i.impact_speed_kmh ?? '-'}</b><span>Impact km/h</span></div></div>
   <div class="imgs">${img}</div>
   <div class="muted">Response: <b>${(i.dispatch?.services || []).join(' + ') || 'pending approval'}</b> ${i.dispatch ? '(' + i.dispatch.priority + ')' : ''}
   | Route: <b>${i.clearance ? i.clearance.diversion_route.join('>') : '-'}</b></div>
   <div class="muted">Strategy: ${esc(i.clearance?.strategy || '-')}</div>
   <ul>${(v.reasons || []).map(r => `<li>${esc(r)}</li>`).join('')}</ul>
   <div class="row"><button class="ok" ${can('verified') ? '' : 'disabled'} onclick="act('approve','${id}')">Approve response</button>
   <button class="bad" ${['verified', 'operator_approved'].includes(i.status) ? '' : 'disabled'} onclick="act('reject','${id}')">Reject</button>
   <button class="ghost" ${['simulated', 'rejected'].includes(i.status) ? '' : 'disabled'} onclick="act('close','${id}')">Mark resolved</button></div>
   <div class="muted">Flags: ${i.flags.join(', ') || 'none'}</div>`;
  $('#trace').innerHTML = d.trace.map(t => `${esc(t.agent)} > ${esc(t.step)} : <b>${esc(t.decision)}</b> <span class="muted">${t.latency_ms}ms</span>`).join('<br>');
  drawMap(i); drawSim(i.simulation);
  if (i.report_path) fetch(`/api/incidents/${id}/report`).then(r => r.text()).then(t => $('#report').textContent = t);
}
window.act = async (a, id) => { try { await post(`/incidents/${id}/${a}`); } catch (e) { alert(e.message); } setTimeout(loadIncidents, 400); };

let graph = null;
async function drawMap(i) {
  graph = graph || await api('/map');
  const P = {}; graph.nodes.forEach(n => P[n.id] = [n.x * 12, -n.y * 12]);
  const path = (arr, col, dash, w = 3) => arr && arr.length > 1 ? `<polyline points="${arr.map(n => P[n].join(',')).join(' ')}" fill="none" stroke="${col}" stroke-width="${w}" stroke-dasharray="${dash || ''}"/>` : '';
  const c = i.clearance;
  let s = graph.edges.map(e => `<line x1="${P[e.u][0]}" y1="${P[e.u][1]}" x2="${P[e.v][0]}" y2="${P[e.v][1]}" stroke="#3a4756" stroke-width="2"/>`).join('');
  if (c) { s += path(c.diversion_route, '#3fb6ff', '6 4') + path(c.emergency_route, '#3fb950', '', 4);
    const [a, b] = c.blocked_edge.split('-'); s += `<line x1="${P[a][0]}" y1="${P[a][1]}" x2="${P[b][0]}" y2="${P[b][1]}" stroke="#f85149" stroke-width="6"/>
    <text x="${(P[a][0] + P[b][0]) / 2 - 8}" y="-6" fill="#f85149" font-size="9">INCIDENT</text>`; }
  s += graph.nodes.map(n => `<circle cx="${P[n.id][0]}" cy="${P[n.id][1]}" r="4" fill="#e6edf3"/><text x="${P[n.id][0] - 8}" y="${P[n.id][1] + 13}" fill="#8b98a5" font-size="8">${n.id}</text>`).join('');
  $('#mapsvg').innerHTML = s;
  $('#maplegend').innerHTML = 'red = blocked segment | blue dashed = diversion Route B | green = emergency corridor';
}
function drawSim(sim) {
  if (!sim) { $('#simsvg').innerHTML = ''; $('#simtable').innerHTML = '<span class="muted">Available after approval.</span>'; return; }
  const q = sim.queue_series, n = q.t.length, mx = Math.max(...q.baseline, ...q.treatment, 1);
  const pl = (arr, col) => `<polyline fill="none" stroke="${col}" stroke-width="1.6" points="${arr.map((v, k) => `${20 + 370 * k / (n - 1)},${140 - 125 * v / mx}`).join(' ')}"/>`;
  $('#simsvg').innerHTML = `<line x1="20" y1="140" x2="390" y2="140" stroke="#3a4756"/>${pl(q.baseline, '#f85149')}${pl(q.treatment, '#3fb950')}
   <text x="24" y="14" fill="#f85149" font-size="9">baseline</text><text x="80" y="14" fill="#3fb950" font-size="9">with system</text><text x="330" y="154" fill="#8b98a5" font-size="8">time (s)</text>`;
  const rows = [['emergency_arrival_s', 'Emergency arrival (s)'], ['queue_dissipation_s', 'Queue dissipation (s)'], ['avg_delay_s', 'Avg delay (s)'], ['recovery_s', 'Recovery (s)'], ['max_queue_veh', 'Max queue (veh)']];
  $('#simtable').innerHTML = '<table><tr><th></th><th>Baseline</th><th>System</th><th>Gain</th></tr>' + rows.map(([k, l]) =>
    `<tr><td>${l}</td><td>${sim.baseline[k].toFixed(0)}</td><td>${sim.treatment[k].toFixed(0)}</td><td>${sim.improvement_pct[k]}%</td></tr>`).join('') + '</table>';
}
async function loadAlerts() {
  const a = await api('/alerts');
  $('#alertlist').innerHTML = a.map(x => `<div class="item alert-${x.level}">${esc(x.message)}<br><span class="muted">${x.ts.slice(11, 19)} #${x.incident_id}</span></div>`).join('') || '<span class="muted">No alerts</span>';
}
function traffic(s) {
  if (!s) return;
  $('#traffic').innerHTML = [['vehicle_count', 'Vehicles'], ['density_pct', 'Density %'], ['avg_speed_kmh', 'Avg km/h'], ['queue_length_veh', 'Queue'], ['time_s', 'Video s'], ['fps', 'FPS']]
    .map(([k, l]) => `<div class="kpi"><b>${s[k] ?? '-'}</b><span>${l}</span></div>`).join('');
}
$('#startcam').onclick = async () => { const c = $('#camsel').value; await api(`/cameras/${c}/start`, { method: 'POST' }); $('#stream').src = `/api/cameras/${c}/stream`; setTimeout(loadCams, 500); };
$('#stopcam').onclick = async () => { await api(`/cameras/${$('#camsel').value}/stop`, { method: 'POST' }); loadCams(); };
function connect() {
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onopen = () => { $('#ws').textContent = 'live'; $('#ws').className = 'pill on'; };
  ws.onclose = () => { $('#ws').textContent = 'offline'; $('#ws').className = 'pill off'; setTimeout(connect, 2000); };
  ws.onmessage = m => { const e = JSON.parse(m.data);
    if (e.type === 'traffic' && e.camera_id === $('#camsel').value) traffic(e.stats);
    else if (['incident_created', 'incident_updated'].includes(e.type)) { loadIncidents(); loadAlerts(); }
    else if (e.type === 'agent_step' && e.incident_id === selected) showDetail(selected);
    else if (e.type === 'alert') loadAlerts(); else if (e.type === 'camera') loadCams(); };
  setInterval(() => ws.readyState === 1 && ws.send('ping'), 20000);
}
loadCams(); loadIncidents(); loadAlerts(); connect(); setInterval(loadCams, 5000);
