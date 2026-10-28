'use strict';
/* Genesis ARK Gateway R0.1. Static demonstration only; no live permissions or mutations. */
const REPO = 'https://github.com/Esomoire-consultancy-Company/genesis-ark';
const roles = Object.freeze({
  developer: {
    overline: 'ENGINEERING ENTRANCE', title: 'Build on documented foundations.',
    text: 'Inspect reference implementations, tests, engineering contracts and bounded capabilities already published in the repository.',
    link: 'Explore implementations', href: '#capabilities',
    steps: ['Review the technical scope', 'Study the test and evidence record', 'Contribute through reviewable changes']
  },
  member: {
    overline: 'COMMONS ENTRANCE · CONCEPT', title: 'Discover your place in the network.',
    text: 'Explore how a future member-facing entrance could explain identity, participation and accredited nodes before any application for access.',
    link: 'Understand the network', href: '#architecture',
    steps: ['Discover the available roles', 'Understand identity and consent boundaries', 'Find governance and eligibility information']
  },
  operator: {
    overline: 'OPERATOR ENTRANCE · CONCEPT', title: 'Understand how governed work moves.',
    text: 'Follow the conceptual path from intent and permissions to bounded operations, observed outcomes and evidence.',
    link: 'Explore operating methods', href: '#journey',
    steps: ['Identify the requested capability', 'Understand checks and execution limits', 'Review evidence and reconciliation duties']
  },
  auditor: {
    overline: 'ASSURANCE ENTRANCE', title: 'Follow the claim to its evidence.',
    text: 'Inspect the repository’s published evidence records, scope limitations and explicit non-claims before relying on an engineering milestone.',
    link: 'Inspect evidence', href: '#evidence',
    steps: ['Read published verification scope', 'Check exclusions and untested conditions', 'Evaluate promotion prerequisites']
  }
});
const nodes = Object.freeze({
  genesis: {
    icon: '✧', title: 'Genesis', type: 'ARCHITECTURE CONCEPT', index: '01 / 07',
    text: 'The root architectural framework for governed identity, capabilities, runtime boundaries, operations and continuity across the network.',
    boundary: 'Defines shared contracts; does not replace an operating legal entity or a competent authority.',
    href: REPO
  },
  warden: {
    icon: '◇', title: 'Warden', type: 'POLICY & AUTHORITY', index: '02 / 07',
    text: 'Evaluates permission and stability at defined gates. The published Alpha example uses a one-shot capability token for one narrowly registered operation.',
    boundary: 'A stability check cannot invent or extend an underlying permit. The Alpha control plane is E2 in its published record.',
    href: REPO + '/blob/main/docs/evidence/WARDEN-STABILITY-GATE-R0.1.md'
  },
  synnergyze: {
    icon: '↝', title: 'Synnergyze', type: 'OPERATIONS ORCHESTRATION · CONCEPT', index: '03 / 07',
    text: 'The proposed orchestration layer for coordinating work across people, systems, capabilities and organisational responsibilities.',
    boundary: 'This public portal does not expose a Synnergyze runtime or provide execution rights.',
    href: REPO
  },
  river: {
    icon: '≈', title: 'RiverOS', type: 'EVIDENCE & CONTINUITY', index: '04 / 07',
    text: 'Provides the evidence-led architectural principle for recording intent, effects and verification. The Alpha control-plane implementation includes a hash-chain evidence journal.',
    boundary: 'A local journal example must not be presented as proof of a globally deployed RiverOS service.',
    href: REPO + '/blob/main/docs/evidence/GES-ALPHA-CONTROL-PLANE-R0.1.md'
  },
  digital: {
    icon: '◉', title: 'DigitalMe', type: 'IDENTITY PRINCIPAL · CONCEPT', index: '05 / 07',
    text: 'The intended identity and representation principal that can bind a person or organisation to permitted activities in the broader ecosystem.',
    boundary: 'No identity registration, login or consent capture is implemented in this static preview.',
    href: REPO
  },
  bnr: {
    icon: '⌘', title: 'BNR', type: 'REGISTRY & MEMBERSHIP · CONCEPT', index: '06 / 07',
    text: 'Believers Network Rail is the proposed registry-facing office for membership, affiliations and authorised relationships across Commons nodes.',
    boundary: 'Prospective registration is not offered here. Any future workflow must validate authority and preserve official registries.',
    href: REPO
  },
  vsr: {
    icon: '↗', title: 'VSR', type: 'USER EXPERIENCE · CONCEPT', index: '07 / 07',
    text: 'The Virtual Silk Road is the wider interface and network experience, intended to make complex services discoverable and understandable.',
    boundary: 'The preview is a navigation demonstration, not evidence of a fully operational VSR service.',
    href: REPO + '/blob/main/docs/knowledge-hub-proxy.md'
  }
});
const methods = Object.freeze({
  lbm: {
    labels: ['LEARN', 'BUILD', 'MAINTAIN'],
    titles: ['Understand the problem and the governing boundaries.', 'Build only within the defined and reviewable scope.', 'Preserve the result, its ownership and its evidence.'],
    descriptions: [
      'Capture the intent, constraints, actors and evidence needed before selecting a tool or proposing a change.',
      'Create or modify the smallest suitable artefact, run checks and request approvals before changing an operational environment.',
      'Document the accepted state, obligations, responsibilities, recoverability and ongoing checks.'
    ]
  },
  ocm: {
    labels: ['OBSERVE', 'CORRECT', 'MAINTAIN'],
    titles: ['Observe what happened, not only what was requested.', 'Correct verified gaps without bypassing authority.', 'Sustain the corrected and reconciled operating state.'],
    descriptions: [
      'Inspect telemetry, records and real outcomes. Distinguish normal behaviour from suspected defects and unknown effects.',
      'Understand root causes, secure bounded approval, test the repair and reconcile evidence before declaring success.',
      'Keep controls, documentation, measurements and accountability current; reopen work when fresh evidence requires it.'
    ]
  }
});
function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}
function setRole(role) {
  const item = roles[role];
  if (!item) return;
  document.querySelectorAll('[data-role]').forEach(button => {
    const chosen = button.dataset.role === role;
    button.classList.toggle('active', chosen);
    button.setAttribute('aria-pressed', String(chosen));
  });
  setText('role-overline', item.overline);
  setText('role-title', item.title);
  setText('role-text', item.text);
  const link = document.getElementById('role-link');
  if (link) {
    link.href = item.href;
    link.replaceChildren(document.createTextNode(item.link + ' '));
    const arrow = document.createElement('span');
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '↗';
    link.appendChild(arrow);
  }
  const list = document.getElementById('role-steps');
  if (list) list.replaceChildren(...item.steps.map(step => {
    const li = document.createElement('li');
    li.textContent = step;
    return li;
  }));
}
function setNode(node) {
  const item = nodes[node];
  if (!item) return;
  document.querySelectorAll('[data-node]').forEach(button => {
    const selected = button.dataset.node === node;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  setText('node-index', item.index);
  setText('node-icon', item.icon);
  setText('node-title', item.title);
  setText('node-type', item.type);
  setText('node-text', item.text);
  setText('node-boundary', item.boundary);
  const link = document.getElementById('node-link');
  if (link) {
    link.href = item.href;
    if (item.href.startsWith('https://')) {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  }
}
let activeFilter = 'all';
function updateCapabilities() {
  const input = document.getElementById('capability-search');
  const query = (input ? input.value : '').trim().toLocaleLowerCase();
  let visibleCount = 0;
  document.querySelectorAll('.cap-card').forEach(card => {
    const isKind = activeFilter === 'all' || card.dataset.kind === activeFilter;
    const isMatch = ((card.dataset.search || '') + ' ' + (card.textContent || '')).toLocaleLowerCase().includes(query);
    const visible = isKind && isMatch;
    card.hidden = !visible;
    if (visible) visibleCount++;
  });
  const empty = document.getElementById('capability-empty');
  if (empty) empty.hidden = visibleCount !== 0;
}
function setFilter(filter) {
  if (!['all', 'implementation', 'blueprint', 'evidence'].includes(filter)) return;
  activeFilter = filter;
  document.querySelectorAll('[data-filter]').forEach(button => {
    const selected = button.dataset.filter === filter;
    button.classList.toggle('chosen', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  updateCapabilities();
}
let activeMethod = 'lbm', activeStep = 0;
function renderMethod() {
  const item = methods[activeMethod];
  setText('method-label', activeMethod.toUpperCase());
  setText('method-title', item.titles[activeStep]);
  setText('method-description', item.descriptions[activeStep]);
  document.querySelectorAll('[data-method]').forEach(button => {
    const selected = button.dataset.method === activeMethod;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  document.querySelectorAll('[data-step]').forEach((button, index) => {
    const selected = index === activeStep;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
    button.replaceChildren();
    const number = document.createElement('span');
    number.textContent = String(index + 1).padStart(2, '0');
    button.append(number, ' ' + item.labels[index]);
  });
}
document.querySelectorAll('[data-role]').forEach(button =>
  button.addEventListener('click', () => setRole(button.dataset.role)));
document.querySelectorAll('[data-node]').forEach(button =>
  button.addEventListener('click', () => setNode(button.dataset.node)));
document.getElementById('capability-search')?.addEventListener('input', updateCapabilities);
document.querySelectorAll('[data-filter]').forEach(button =>
  button.addEventListener('click', () => setFilter(button.dataset.filter)));
document.querySelectorAll('[data-method]').forEach(button =>
  button.addEventListener('click', () => {
    if (!(button.dataset.method in methods)) return;
    activeMethod = button.dataset.method;
    activeStep = 0;
    renderMethod();
  }));
document.querySelectorAll('[data-step]').forEach(button =>
  button.addEventListener('click', () => {
    const index = Number(button.dataset.step);
    if (!Number.isInteger(index) || index < 0 || index > 2) return;
    activeStep = index;
    renderMethod();
  }));
if ('IntersectionObserver' in window) {
  const nav = Array.from(document.querySelectorAll('.side-nav a[href^="#"]'));
  const observer = new IntersectionObserver(entries => {
    entries.filter(entry => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
      .slice(0, 1).forEach(entry => {
        nav.forEach(a => {
          const selected = a.hash === '#' + entry.target.id;
          a.classList.toggle('active', selected);
          if (selected) a.setAttribute('aria-current', 'location');
          else a.removeAttribute('aria-current');
        });
      });
  }, {rootMargin: '-12% 0px -55% 0px', threshold: [0, .1, .3]});
  document.querySelectorAll('#home, #architecture, #capabilities, #journey, #evidence')
    .forEach(section => observer.observe(section));
}
setRole('developer');
setNode('genesis');
setFilter('all');
renderMethod();
