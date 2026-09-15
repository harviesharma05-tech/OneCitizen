const view = document.getElementById('view');
const title = document.getElementById('view-title');
const note = document.getElementById('view-note');

const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const FIELD_LABEL = {
  name_raw: 'name', address_raw: 'address', bank_account: 'bank account',
  phone: 'mobile number', dob: 'date of birth', pincode: 'pincode',
  income: 'annual income', occupation: 'occupation', education: 'education',
  aadhaar: 'Aadhaar', pan: 'PAN', gender: 'gender', land_hectares: 'landholding',
};
const money = n => '₹' + Number(n || 0).toLocaleString('en-IN');

async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json()).error || 'Request failed');
  return r.json();
}

const VIEWS = {
  citizens: {
    title: 'Citizen register',
    note: 'Each row is one resolved citizen, merged from every department that holds their data. Select a row to open the full profile.',
    render: renderCitizens,
  },
  review: {
    title: 'Merge review',
    note: 'Record pairs that looked similar but fell below the auto-merge threshold. A human decides these — the system never guesses on weak evidence.',
    render: renderReview,
  },
  fraud: {
    title: 'Flagged benefits',
    note: 'Duplicate payouts and identities sharing a bank account or mobile number. Every flag carries the reason that produced it.',
    render: renderFraud,
  },
  schemes: {
    title: 'Scheme catalogue',
    note: 'All schemes, plus pairs whose objectives and eligibility rules overlap enough to be worth consolidating.',
    render: renderSchemes,
  },
  audit: {
    title: 'Access log',
    note: 'Every privileged read is recorded. Officers can see citizen data, and the system records that they did.',
    render: renderAudit,
  },
};

document.getElementById('nav').addEventListener('click', e => {
  const link = e.target.closest('a[data-view]');
  if (!link) return;
  e.preventDefault();
  document.querySelectorAll('#nav a').forEach(a => a.classList.remove('on'));
  link.classList.add('on');
  show(link.dataset.view);
});

async function show(name) {
  const v = VIEWS[name];
  title.textContent = v.title;
  note.textContent = v.note;
  view.innerHTML = '<div class="panel"><div class="empty">Loading…</div></div>';
  try { await v.render(); }
  catch (err) { view.innerHTML = `<div class="panel"><div class="empty">${esc(err.message)}</div></div>`; }
}

/* ------------------------------------------------------------- citizens */
async function renderCitizens() {
  const riskFilter = PERMS.can_see_fraud ? `
    <select id="risk">
      <option value="">All risk levels</option>
      <option value="high">High risk</option>
      <option value="medium">Medium risk</option>
      <option value="low">Low risk</option>
    </select>` : '';

  view.innerHTML = `
    <div class="panel">
      <div class="tools">
        <input id="q" placeholder="Search by name, citizen ID, or Aadhaar">
        ${riskFilter}
      </div>
      <div id="rows"></div>
    </div>`;

  const load = async () => {
    const q = document.getElementById('q').value;
    const risk = document.getElementById('risk')?.value || '';
    const data = await get(`/api/citizens?q=${encodeURIComponent(q)}&risk=${risk}`);
    const rows = document.getElementById('rows');

    if (!data.length) { rows.innerHTML = '<div class="empty">No citizens match that search.</div>'; return; }

    rows.innerHTML = `
      <table>
        <thead><tr>
          <th>Citizen ID</th><th>Name</th><th>Aadhaar</th><th>Sources</th>
          <th>Departments</th><th>Benefits</th>${PERMS.can_see_fraud ? '<th>Risk</th>' : ''}
        </tr></thead>
        <tbody>${data.map(c => `
          <tr data-id="${c.citizen_id}">
            <td class="id">${esc(c.citizen_id)}</td>
            <td>${esc(c.name_raw)}</td>
            <td class="id">${esc(c.aadhaar) || '—'}</td>
            <td class="id">${c.source_record_count}</td>
            <td>${c.departments.map(d => `<span class="tag">${esc(d)}</span>`).join('')}</td>
            <td class="id">${money(c.total_benefit)}</td>
            ${PERMS.can_see_fraud ? `<td><span class="band ${c.risk.band}">${c.risk.score}</span></td>` : ''}
          </tr>`).join('')}
        </tbody>
      </table>`;

    rows.querySelectorAll('tr[data-id]').forEach(tr =>
      tr.addEventListener('click', () => openProfile(tr.dataset.id)));
  };

  document.getElementById('q').addEventListener('input', debounce(load, 250));
  document.getElementById('risk')?.addEventListener('change', load);
  await load();
}

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

/* --------------------------------------------------------------- profile */
async function openProfile(id) {
  const c = await get(`/api/citizen/${id}`);
  document.getElementById('p-name').textContent = c.name_raw || id;
  document.getElementById('p-sub').textContent =
    `${c.citizen_id} · merged from ${c.source_record_count} department record(s)`;

  const eligible = (c.all_scheme_checks || []).filter(s => s.verdict === 'eligible');
  const needsInfo = (c.all_scheme_checks || []).filter(s => s.verdict === 'needs_info');

  document.getElementById('p-body').innerHTML = `
    <section>
      <h5>Consolidated identity</h5>
      <dl class="kv">
        <dt>Aadhaar</dt><dd class="id">${esc(c.aadhaar) || 'not on record'}</dd>
        <dt>PAN</dt><dd class="id">${esc(c.pan) || 'not on record'}</dd>
        <dt>Date of birth</dt><dd class="id">${esc(c.dob) || '—'}</dd>
        <dt>Mobile</dt><dd class="id">${esc(c.phone) || '—'}</dd>
        <dt>Bank account</dt><dd class="id">${esc(c.bank_account) || '—'}</dd>
        <dt>Address</dt><dd>${esc(c.address_raw) || '—'}</dd>
        <dt>Occupation</dt><dd>${esc(c.occupation) || 'not captured'}</dd>
        <dt>Annual income</dt><dd class="id">${c.income ? money(c.income) : 'not captured'}</dd>
        <dt>Education</dt><dd>${esc(c.education) || 'not captured'}</dd>
      </dl>
      ${c.conflicting_fields?.length ? `<p class="why">Departments disagree on:
        ${c.conflicting_fields.map(f => `<span class="tag">${esc(FIELD_LABEL[f] || f)}</span>`).join('')}
        The most recently updated source was kept.</p>` : ''}
    </section>

    <section>
      <h5>Benefit history — proof trail</h5>
      <div class="proof">
        ${c.schemes.length ? c.schemes.map(s => `
          <div>
            <span>${esc(s.scheme)}<br><em>${esc(s.department)} · ${esc(s.status)} · ${esc(s.date)} · record ${esc(s.source_record_id)}</em></span>
            <span class="id">${money(s.amount)}</span>
          </div>`).join('') : '<div><span>No benefits recorded in your scope.</span></div>'}
      </div>
    </section>

    ${PERMS.can_see_fraud && c.risk ? `
    <section>
      <h5>Risk assessment</h5>
      <p><span class="band ${c.risk.band}">${c.risk.score} / 100 — ${c.risk.band}</span></p>
      <ul class="why">${c.risk.reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>
    </section>` : ''}

    <section>
      <h5>Schemes this citizen qualifies for but has not received</h5>
      ${eligible.length ? eligible.map(s => `
        <div class="record">
          <h4>${esc(s.scheme)} <span class="tag">${esc(s.department)}</span></h4>
          <p>Qualifies on: ${s.met.map(m => esc(m)).join('; ') || 'no conditions attached'}</p>
        </div>`).join('') : '<p class="why">None — this citizen already receives everything they qualify for.</p>'}
    </section>

    ${needsInfo.length ? `
    <section>
      <h5>Blocked only by missing information</h5>
      ${needsInfo.slice(0, 5).map(s => `
        <div class="record">
          <h4>${esc(s.scheme)} <span class="tag">${esc(s.department)}</span></h4>
          <p>Needs: ${s.missing_info.map(m => esc(m)).join('; ')}</p>
        </div>`).join('')}
    </section>` : ''}`;

  document.getElementById('profile').showModal();
}

/* ---------------------------------------------------------------- review */
async function renderReview() {
  const data = await get('/api/review-queue');
  view.innerHTML = `<div class="panel">
    <h3>Pending decisions <small>${data.length} pair(s)</small></h3>
    ${data.length ? data.map(r => `
      <div class="record">
        <h4>Match confidence ${(r.score * 100).toFixed(0)}%</h4>
        <ul class="why">${r.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        <div class="pair" style="margin-top:.7rem">
          ${[r.left, r.right].map(s => `
            <div>
              <h4>${esc(s.source_dept)} · <span class="id">${esc(s.dept_record_id)}</span></h4>
              <dl class="kv">
                <dt>Name</dt><dd>${esc(s.name_raw)}</dd>
                <dt>DOB</dt><dd class="id">${esc(s.dob) || '—'}</dd>
                <dt>Aadhaar</dt><dd class="id">${esc(s.aadhaar) || 'missing'}</dd>
                <dt>Address</dt><dd>${esc(s.address_raw)}</dd>
              </dl>
            </div>`).join('')}
        </div>
        <p style="margin-top:.7rem">
          <button onclick="this.closest('.record').style.opacity=.4;this.textContent='Merged'">Merge as one citizen</button>
          <button onclick="this.closest('.record').style.opacity=.4;this.textContent='Kept separate'"
                  style="background:none;color:var(--ink);border:1px solid var(--rule)">Keep separate</button>
        </p>
      </div>`).join('') : '<div class="empty">Nothing waiting. Every pair cleared the threshold on its own.</div>'}
  </div>`;
}

/* ----------------------------------------------------------------- fraud */
async function renderFraud() {
  const d = await get('/api/fraud');
  view.innerHTML = `
    <div class="panel">
      <h3>Duplicate applications <small>same citizen, same scheme</small></h3>
      ${d.duplicate_applications.length ? `<table>
        <thead><tr><th>Citizen</th><th>Scheme</th><th>Applications</th><th>Approved</th><th>Excess paid</th><th>Severity</th></tr></thead>
        <tbody>${d.duplicate_applications.map(x => `<tr>
          <td>${esc(x.name)}<br><span class="id" style="font-size:.78rem;color:var(--ink-faint)">${esc(x.citizen_id)}</span></td>
          <td>${esc(x.scheme)}</td>
          <td class="id">${x.application_count}</td>
          <td class="id">${x.approved_count}</td>
          <td class="id">${money(x.duplicate_amount)}</td>
          <td><span class="band ${x.severity}">${esc(x.severity)}</span></td>
        </tr>`).join('')}</tbody></table>` : '<div class="empty">No duplicate applications found.</div>'}
    </div>

    <div class="panel">
      <h3>Shared identifiers <small>different citizens, same account or number</small></h3>
      ${d.rings.length ? d.rings.map(r => `
        <div class="record">
          <h4>${r.citizen_count} citizens share one ${esc(r.identifier_type)}
            <span class="band ${r.severity}">${esc(r.severity)}</span></h4>
          <p>Identifier <span class="id">${esc(r.identifier)}</span> · ${money(r.total_disbursed)} disbursed across these profiles</p>
          <p class="why">${r.citizens.map(c => esc(c.name) + ' (' + esc(c.citizen_id) + ')').join(' · ')}</p>
        </div>`).join('') : '<div class="empty">No shared-identifier patterns found.</div>'}
    </div>`;
}

/* --------------------------------------------------------------- schemes */
async function renderSchemes() {
  const d = await get('/api/schemes');
  view.innerHTML = `
    <div class="panel">
      <h3>Overlapping schemes <small>${d.overlapping.length} pair(s) worth consolidating</small></h3>
      ${d.overlapping.length ? d.overlapping.map(o => `
        <div class="record">
          <h4>${esc(o.scheme_a)} &nbsp;vs&nbsp; ${esc(o.scheme_b)}
            ${o.cross_department ? '<span class="tag">across departments</span>' : '<span class="tag">same department</span>'}</h4>
          <p>${(o.overlap * 100).toFixed(0)}% overlap — objectives ${(o.objective_similarity * 100).toFixed(0)}% similar,
             eligibility rules ${(o.eligibility_overlap * 100).toFixed(0)}% shared</p>
          <p class="why">${o.cross_department ? esc(o.dept_a) + ' and ' + esc(o.dept_b) + ' both apply' : 'Both apply'}: ${o.shared_criteria.map(c => `<span class="tag">${esc(c)}</span>`).join('') || 'no identical rules'}</p>
        </div>`).join('') : '<div class="empty">No overlapping schemes detected.</div>'}
    </div>

    <div class="panel">
      <h3>Full catalogue <small>${d.catalogue.length} schemes</small></h3>
      <table>
        <thead><tr><th>Scheme</th><th>Department</th><th>Eligibility</th><th>Benefit</th></tr></thead>
        <tbody>${d.catalogue.map(s => `<tr>
          <td>${esc(s.name)}</td><td>${esc(s.department)}</td>
          <td style="max-width:28rem">${esc(s.eligibility)}</td>
          <td>${esc(s.benefit)}</td></tr>`).join('')}</tbody>
      </table>
    </div>`;
}

/* ----------------------------------------------------------------- audit */
async function renderAudit() {
  const d = await get('/api/audit');
  view.innerHTML = `<div class="panel">
    <h3>Recent access <small>most recent first</small></h3>
    ${d.length ? `<table>
      <thead><tr><th>User</th><th>Role</th><th>Action</th><th>Target</th></tr></thead>
      <tbody>${d.map(a => `<tr>
        <td class="id">${esc(a.user)}</td><td>${esc(a.role)}</td>
        <td>${esc(a.action)}</td><td class="id">${esc(a.target)}</td></tr>`).join('')}</tbody>
    </table>` : '<div class="empty">No access recorded yet this session.</div>'}
  </div>`;
}

show('citizens');
