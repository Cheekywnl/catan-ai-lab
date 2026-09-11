import { projects, components, stages } from './catalog.js';
import { theftOutcomes } from './lab-math.js';

const $ = (selector, parent = document) => parent.querySelector(selector);
const main = $('#main');
const escape = value => String(value).replace(/[&<>"']/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[ch]));
let data;
const routes = { overview:'Overview', research:'Full research', projects:'Project landscape', architecture:'Architecture', belief:'Belief lab', roadmap:'Build roadmap', sources:'Sources', search:'Search results' };
const ref = (id, label = `[${id}]`) => `<a class="citation" href="${data.references[id]}" target="_blank" rel="noopener noreferrer" aria-label="${escape(label === `[${id}]` ? `Source ${id}: ${data.sources.find(s => s.id === id)?.title || ''}` : label)}">${escape(label)}</a>`;
const refs = ids => ids.map(id => ref(id)).join(' ');
const chapterLink = (id, text = 'Read the research') => `<a class="arrow-link" href="#research/${id}">${escape(text)} <span aria-hidden="true">↗</span></a>`;
const heading = (eyebrow, title, description, badge = '') => `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="lede">${description}</p></div>${badge ? `<span class="pill green">${badge}</span>` : ''}</div>`;

function overview() {
  return `${heading('THE RESEARCH WORKSPACE', 'A smarter way to play.', 'The blueprint for a Catan engine that remembers, reasons, and learns.', 'Research complete · Build proposed')}
  <section class="hero-panel hero-grid" aria-labelledby="recommendation"><div><div class="eyebrow">THE RECOMMENDATION</div><h2 id="recommendation">One engine.<br>Three ways to use it.</h2><p>Combine probabilistic card tracking, learned policy and value models, and search over plausible futures.</p><a class="button light" href="#research/1">Explore the blueprint <span aria-hidden="true">↗</span></a></div><div class="engine-preview"><div class="diagram-label">PROPOSED DECISION ENGINE</div><div class="mini-flow"><a href="#architecture/believe"><span class="flow-symbol" aria-hidden="true">◉</span><strong>Beliefs</strong><small>What could be true?</small></a><span class="flow-arrow" aria-hidden="true">→</span><a href="#architecture/learn"><span class="flow-symbol" aria-hidden="true">⌘</span><strong>Policy</strong><small>What looks promising?</small></a><span class="flow-arrow" aria-hidden="true">→</span><a href="#architecture/search"><span class="flow-symbol" aria-hidden="true">⑂</span><strong>Search</strong><small>What happens next?</small></a></div><div class="diagram-connector" aria-hidden="true"></div><div class="product-row"><span>Full-game bot</span><span>Game companion</span><span>Research workbench</span></div><a href="#architecture" class="diagram-link">Inspect the architecture <span aria-hidden="true">↗</span></a></div></section>
  <div class="stats"><div><strong>${data.sources.length}</strong><span>Sources examined</span></div><div><strong>${data.chapters.length}</strong><span>Research chapters</span></div><div><strong>4</strong><span>Players · base game</span></div><div><strong>3</strong><span>Connected products</span></div></div>
  <div class="section-heading"><h2>The decisions that shape the build</h2><a class="text-link" href="#projects">Compare all projects ↗</a></div>
  <div class="overview-columns"><section class="card decisions"><a class="decision" href="#research/3"><span class="decision-number">01</span><div><h3>Build on Catanatron</h3><p>The strongest prototype fit, after closing the observation and training-action gaps.</p><span class="small-label">SOURCE INSPECTION · [12–15]</span></div><span aria-hidden="true">↗</span></a><a class="decision" href="#research/6"><span class="decision-number">02</span><div><h3>Search before scaling training</h3><p>Start with root Monte Carlo evaluation. Use belief-aware search as the next comparison.</p><span class="small-label">PROPOSED ENGINEERING CHOICE</span></div><span aria-hidden="true">↗</span></a><a class="decision" href="#research/7"><span class="decision-number">03</span><div><h3>Generate data we can trust</h3><p>Use simulator trajectories first. External game archives need access, permission, and replay checks.</p><span class="small-label">DATA AUDIT + PROPOSAL</span></div><span aria-hidden="true">↗</span></a></section>
  <section class="card precedent"><div class="card-topline"><span class="eyebrow">CLOSEST PUBLISHED PRECEDENT</span><span class="pill neutral">2018 paper</span></div><h3>Beliefs + human preferences + search</h3><p>Dobre & Lascarides combine hidden-information planning with preferences learned from 60 human games.</p><div class="benchmark-row"><div><strong>40.70<span>%</span></strong><span>10,000 iterations</span></div><div><strong>53.65<span>%</span></strong><span>40,000 iterations</span></div></div><p class="benchmark-note">Reported wins against three Stac bots, 2,000 games per condition. Historical results; not our bot or a modern human benchmark.</p>${ref(5, 'Open the paper ↗')}</section></div>
  <div class="section-heading"><h2>Go deeper</h2><a class="text-link" href="#research/1">All 12 chapters ↗</a></div><div class="topic-grid"><a class="topic-card" href="#belief"><span class="topic-icon" aria-hidden="true">◉</span><span class="eyebrow">INTERACTIVE EXPLAINER</span><h3>Track possibilities,<br>not guesses.</h3><p>See how a hidden theft changes two players’ hands at once.</p><span class="arrow-link">Open the belief lab ↗</span></a><a class="topic-card" href="#research/5"><span class="topic-icon" aria-hidden="true">⬡</span><span class="eyebrow">SETTLEMENT PLACEMENT</span><h3>The best intersection<br>depends on the draft.</h3><p>Production, resource balance, expansion, and the choices still to come.</p><span class="arrow-link">Read chapter 05 ↗</span></a><a class="topic-card" href="#roadmap"><span class="topic-icon" aria-hidden="true">↗</span><span class="eyebrow">FROM RESEARCH TO BUILD</span><h3>A useful advisor.<br>Then a stronger agent.</h3><p>Five stages with concrete deliverables and measurable exit criteria.</p><span class="arrow-link">Review the roadmap ↗</span></a></div>
  <div class="notice"><span class="notice-icon" aria-hidden="true">i</span><div><strong>“GTO” is a research question, not a product claim.</strong><p>The target is reproducible strength against varied opponents. Four-player Catan has no established solved strategy in the evidence examined. ${chapterLink(2, 'Understand the distinction')}</p></div></div>`;
}

function research(id) {
  const chapter = data.chapters.find(c => c.id === Number(id));
  if (!chapter) return notFound();
  return `<div class="reader-layout"><aside class="chapter-nav" aria-label="Research chapters"><div class="eyebrow">THE COMPLETE BLUEPRINT</div><h2>Research index</h2><p>12 chapters · 37 sources</p><nav aria-label="Chapters">${data.chapters.map(c => `<a href="#research/${c.id}" ${c.id === chapter.id ? 'aria-current="page" class="selected"' : ''}><span>${String(c.id).padStart(2, '0')}</span>${escape(c.title)}</a>`).join('')}</nav><a class="button" href="catan-ai-research.md" download>Download Markdown ↓</a></aside><article class="research-article"><div class="reader-meta"><span class="eyebrow">CHAPTER ${String(chapter.id).padStart(2,'0')} / 12</span><span>${chapter.minutes} min read · 11 Sep 2026</span></div><h1>${escape(chapter.title)}</h1><div class="prose">${chapter.html}</div><nav class="chapter-pager" aria-label="Chapter pagination">${chapter.id > 1 ? `<a href="#research/${chapter.id - 1}"><small>← PREVIOUS</small>${escape(data.chapters[chapter.id-2].title)}</a>` : '<span></span>'}${chapter.id < 12 ? `<a href="#research/${chapter.id + 1}"><small>NEXT →</small>${escape(data.chapters[chapter.id].title)}</a>` : '<a href="#sources"><small>EVIDENCE →</small>Sources and evidence register</a>'}</nav></article></div>`;
}

function projectCard(p) {
  return `<article class="project-card"><div class="card-topline"><span class="category-label">${p.kind}</span>${p.tag ? `<span class="pill green">${p.tag}</span>` : ''}</div><h2>${p.name}</h2><div class="project-owner">${p.owner} <span>·</span> ${p.license}</div><p class="project-role">${p.role}</p><p>${p.strength}</p><div class="qualification"><strong>What to account for</strong><p>${p.limit}</p></div><div class="project-bottom"><span>${p.inspection}</span><div>${refs(p.refs)}</div></div>${chapterLink(p.chapters[0], 'Read the assessment')}</article>`;
}

function projectPage() {
  return `${heading('THE IMPLEMENTATION LANDSCAPE','Build on what exists.', 'Twelve relevant projects, their useful capabilities, and the limitations that change our implementation choices.')}<div class="notice compact"><span class="notice-icon" aria-hidden="true">i</span><p>This is a relevance comparison. Playing strength has not been independently reproduced; repository claims are labeled separately from inspected code.</p></div><div class="filter-bar"><div class="field search-field"><label for="project-query">Find a project</label><input type="search" id="project-query" placeholder="Name, capability, or limitation…" maxlength="200"></div><div class="field"><label for="project-kind">Focus</label><select id="project-kind"><option value="all">All projects</option>${['Engine','Search','Learning','Companion','Data'].map(x => `<option>${x}</option>`).join('')}</select></div><span class="result-count" id="project-count" role="status">12 projects</span></div><div class="project-grid" id="project-results">${projects.map(projectCard).join('')}</div>`;
}

function componentDetail(component) {
  return `<div class="detail-number" aria-hidden="true">${component.glyph}</div><div><span class="eyebrow">${component.label.toUpperCase()} · PROPOSED DESIGN</span><h2>${component.heading}</h2><p>${component.body}</p><ul class="check-list">${component.points.map(p => `<li>${p}</li>`).join('')}</ul><div class="detail-links">${chapterLink(component.chapter, 'Read the design rationale')}<span>${refs(component.refs)}</span></div></div>`;
}

function architecture(id = 'observe') {
  const component = components.find(c => c.id === id) || components[0];
  return `${heading('SHARED ARCHITECTURE','From observations to decisions.', 'One information boundary. One decision engine. Three product interfaces.', 'Proposed · Not implemented')}<section class="architecture-panel"><div class="diagram-label dark">SELECT A COMPONENT TO INSPECT ITS RESPONSIBILITIES</div><div class="architecture-flow">${components.map(c => `<a class="architecture-node ${c.id===component.id ? 'selected' : ''}" href="#architecture/${c.id}" ${c.id===component.id ? 'aria-current="true"' : ''}><span>${c.glyph}</span><strong>${c.label}</strong><small>${c.subtitle}</small></a>`).join('')}</div><div class="architecture-detail" id="component-detail">${componentDetail(component)}</div></section><div class="section-heading"><h2>Three views of the same engine</h2></div><div class="topic-grid product-cards"><section class="card"><span class="eyebrow">01 / FULL-GAME BOT</span><h3>Play, train, compete.</h3><p>Every legal decision in a four-player simulator. Versioned policies, self-play, and a repeatable opponent suite.</p>${chapterLink(7,'Training strategy')}</section><section class="card"><span class="eyebrow">02 / GAME COMPANION</span><h3>Track, compare, explain.</h3><p>Manual board and event entry, resource beliefs, ranked alternatives, and correction with deterministic replay.</p>${chapterLink(12,'First integrated version')}</section><section class="card"><span class="eyebrow">03 / RESEARCH WORKBENCH</span><h3>Measure, review, improve.</h3><p>Game generation, model comparison, uncertainty, and ablations. A result always names its rules and opponents.</p>${chapterLink(10,'Evaluation design')}</section></div><div class="notice"><span class="notice-icon" aria-hidden="true">!</span><div><strong>The actual hidden hand stays inside the simulator.</strong><p>Search gets a sampled world consistent with the player’s observations. Opponent simulation must also respect what each opponent can know. ${chapterLink(6,'Information failure modes')}</p></div></div>`;
}

function cards(ore, wheat) {
  return `<div class="resource-cards" aria-label="${ore} ore and ${wheat} wheat">${ore ? `<span class="resource ore"><span aria-hidden="true">◆</span> ${ore} ore</span>` : ''}${wheat ? `<span class="resource wheat"><span aria-hidden="true">❋</span> ${wheat} wheat</span>` : ''}${!ore && !wheat ? '<span class="empty-hand">Empty hand</span>' : ''}</div>`;
}

function belief() {
  return `${heading('THE BELIEF LAB','A hidden card. Two linked hands.', 'Change the known hand, then inspect the exact possibilities after one unseen random theft.', 'Interactive math explainer')}<div class="belief-layout"><section class="card belief-input"><span class="step-label">01 · BEFORE THE THEFT</span><h2>A hand we know.</h2><p>The victim holds only ore and wheat. A thief takes one card uniformly at random; we do not see which.</p><div class="belief-controls"><div class="field"><label for="ore-count">Ore cards</label><input type="number" id="ore-count" min="0" max="10" step="1" value="2"></div><div class="field"><label for="wheat-count">Wheat cards</label><input type="number" id="wheat-count" min="0" max="10" step="1" value="1"></div></div><div id="known-hand">${cards(2,1)}</div><button class="button" id="reset-belief" type="button">Reset example ↺</button><p class="micro">An isolated worked example. No opponent policy, neural network, or hidden-discard assumption.</p></section><section class="card belief-results"><span class="step-label">02 · AFTER THE UNSEEN THEFT</span><h2>Keep every feasible world.</h2><div id="belief-outcomes" aria-live="polite"></div></section></div><section class="notice"><span class="notice-icon" aria-hidden="true">↔</span><div><strong>The two hands are correlated.</strong><p>Whenever the victim lost ore, the thief gained ore. Sampling their hands independently could invent an impossible world. A joint belief preserves this connection. The thief’s display above shows only the stolen card, not their entire hand.</p></div></section><div class="two-columns"><section class="card"><span class="eyebrow">THE UPDATE RULE</span><h3>Weight outcomes by the event that produced them.</h3><div class="math-formula">P(stolen ore) = ore / total cards</div><p>For a known hand and a uniformly random theft, the probabilities are exact. Public gains and costs constrain future possibilities. Chosen actions, such as hidden discards, need a model of the player’s choice.</p>${chapterLink(4,'Read the full tracking design')}</section><section class="card"><span class="eyebrow">IN THE FUTURE COMPANION</span><h3>Display uncertainty honestly.</h3><p>Show exact holdings when deducible, possible counts with probabilities otherwise, and whether the belief is exact, sampled, or awaiting reconciliation after a missing event.</p><p>Development cards require their own model, including purchase timing, deck constraints, and played cards.</p>${refs([5,6,23,29])}</section></div>`;
}

function roadmap() {
  return `${heading('THE BUILD ROADMAP','Make each stage earn the next.', 'A useful advisor can arrive before a strong learned agent. Each stage has a concrete result and an evidence-based exit criterion.', 'All stages proposed')}<div class="notice compact"><span class="notice-icon" aria-hidden="true">i</span><p>Effort ranges assume one experienced engineer with relevant ML skills. Stages overlap; these are planning estimates, not deadlines or completed work.</p></div><div class="roadmap-list">${stages.map((s,i) => `<article class="roadmap-stage"><div class="stage-marker">${String(i+1).padStart(2,'0')}</div><div class="stage-content"><div class="stage-header"><div><span class="eyebrow">${s.focus}</span><h2>${s.title}</h2></div><span class="pill neutral">${s.effort}</span></div><div class="stage-body"><ul>${s.deliverables.map(d => `<li>${d}</li>`).join('')}</ul><div class="exit-criterion"><span class="eyebrow">EXIT CRITERION</span><p>${s.exit}</p>${chapterLink(s.chapter,'Supporting research')}</div></div></div></article>`).join('')}</div><section class="card compute-note"><div><span class="eyebrow">COMPUTE STRATEGY</span><h2>Measure before scaling.</h2><p>Profile transitions, full games, inference, and belief-aware rollouts separately. Add GPU training once the rules, data, and learning loop are validated.</p></div>${chapterLink(11,'Effort and compute rationale')}</section>`;
}

const groupLabels = { rules:'Rules & platform terms', papers:'Research papers', code:'Inspected source code', data:'Data & documentation', projects:'Project repositories & write-ups' };
function sourceCard(s) {
  return `<article class="source-entry" id="source-${s.id}"><a class="source-number" href="${s.url}" target="_blank" rel="noopener noreferrer" aria-label="Open source ${s.id}">${String(s.id).padStart(2,'0')}</a><div><span class="category-label">${groupLabels[s.group]}</span><div class="source-copy">${s.html}</div></div><a class="source-open" href="${s.url}" target="_blank" rel="noopener noreferrer" aria-label="Open source ${s.id}: ${escape(s.title)}">↗</a></article>`;
}
function sources() {
  return `${heading('THE EVIDENCE REGISTER','Every claim has a trail.', 'Papers, repositories, pinned code revisions, and data checks behind the report. Inspected 11 September 2026.', '37 numbered sources')}<div class="filter-bar"><div class="field search-field"><label for="source-query">Search the evidence</label><input type="search" id="source-query" placeholder="Author, topic, project, or source number…" maxlength="200"></div><div class="field"><label for="source-kind">Source type</label><select id="source-kind"><option value="all">All source types</option>${Object.entries(groupLabels).map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></div><span class="result-count" id="source-count" role="status">37 sources</span></div><div class="source-list" id="source-results">${data.sources.map(sourceCard).join('')}</div>`;
}

function search(query) {
  const q = query.trim().slice(0,200);
  const matching = q ? data.chapters.filter(c => (c.title+' '+c.text).toLowerCase().includes(q.toLowerCase())) : [];
  const sourceMatches = q ? data.sources.filter(s => s.text.toLowerCase().includes(q.toLowerCase())) : [];
  return `${heading('SEARCH THE WORKSPACE',q ? `Results for “${escape(q)}”` : 'Find a thread of evidence.',q ? `${matching.length} matching chapters and ${sourceMatches.length} sources.` : 'Use the search field above to explore the full report and source register.')}<div class="search-results">${matching.map(c => {const at = c.text.toLowerCase().indexOf(q.toLowerCase()); const start=Math.max(0,at-90);return `<a class="search-result" href="#research/${c.id}"><span class="eyebrow">CHAPTER ${String(c.id).padStart(2,'0')}</span><h2>${escape(c.title)}</h2><p>${start?'…':''}${escape(c.text.slice(start,start+270))}…</p><span class="arrow-link">Open chapter ↗</span></a>`}).join('')}${q&&!matching.length&&!sourceMatches.length?'<div class="empty-state"><h2>No matches found.</h2><p>Try a broader term such as “trading”, “belief”, or “PPO”.</p><a class="button" href="#research/1">Browse the research</a></div>':''}</div>${sourceMatches.length?`<div class="section-heading"><h2>Matching sources</h2></div><div class="source-list">${sourceMatches.map(sourceCard).join('')}</div>`:''}`;
}
function notFound() { return `${heading('WORKSPACE','That page could not be found.','Choose a section in the navigation, or return to the overview.')}<a class="button" href="#overview">Back to overview</a>`; }

function filterProjects() {
  const q = $('#project-query').value.trim().toLowerCase();
  const kind = $('#project-kind').value;
  const matching = projects.filter(p => (kind==='all'||p.kind===kind) && Object.values(p).flat().join(' ').toLowerCase().includes(q));
  $('#project-results').innerHTML = matching.map(projectCard).join('') || '<div class="empty-state"><h2>No projects match.</h2><p>Clear the search or choose another focus.</p></div>';
  $('#project-count').textContent = `${matching.length} project${matching.length===1?'':'s'}`;
}
function filterSources() {
  const q = $('#source-query').value.trim().toLowerCase();
  const kind = $('#source-kind').value;
  const matching = data.sources.filter(s => (kind==='all'||s.group===kind) && (s.text.toLowerCase().includes(q) || String(s.id) === q));
  $('#source-results').innerHTML = matching.map(sourceCard).join('') || '<div class="empty-state"><h2>No sources match.</h2><p>Clear the search or choose another source type.</p></div>';
  $('#source-count').textContent = `${matching.length} source${matching.length===1?'':'s'}`;
  externalLinks();
}
function updateBelief() {
  const oreInput = $('#ore-count'), wheatInput = $('#wheat-count');
  const ore = oreInput.valueAsNumber, wheat = wheatInput.valueAsNumber;
  const valid = [oreInput,wheatInput].every(el => el.value !== '' && el.validity.valid) && ore+wheat>0;
  [oreInput,wheatInput].forEach(el=>el.setAttribute('aria-invalid',String(!valid)));
  if (!valid) { $('#belief-outcomes').innerHTML='<p class="input-error" role="alert">Enter whole numbers from 0 to 10, with at least one card in total.</p>'; $('#known-hand').innerHTML=''; return; }
  $('#known-hand').innerHTML=cards(ore,wheat);
  const outcomes = theftOutcomes(ore,wheat);
  $('#belief-outcomes').innerHTML = outcomes.map(o => `<div class="outcome"><div class="outcome-header"><span>If the stolen card is <strong>${o.stolen}</strong></span><strong>${(o.probability*100).toFixed(1)}<small>%</small></strong></div><div class="probability-track"><span style="width:${o.probability*100}%"></span></div><div class="joint-hands"><div><span class="small-label">VICTIM’S REMAINING HAND</span>${cards(o.victim.ore,o.victim.wheat)}</div><span class="joint-arrow" aria-hidden="true">↔</span><div><span class="small-label">THIEF’S GAIN</span>${cards(o.thief.ore,o.thief.wheat)}</div></div></div>`).join('')+`<div class="belief-total"><span>${outcomes.length} feasible world${outcomes.length===1?'':'s'}</span><span>Total probability <strong>100%</strong></span></div>`;
}
function externalLinks() {
  main.querySelectorAll('a[href^="https://"]').forEach(a=>{a.target='_blank';a.rel='noopener noreferrer';});
  main.querySelectorAll('.prose table').forEach(table=>{if(table.parentElement.classList.contains('table-scroll'))return;const wrap=document.createElement('div');wrap.className='table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Research comparison table, scroll horizontally if needed');table.replaceWith(wrap);wrap.append(table);});
}
function render(focus = false) {
  const hash = location.hash.slice(1) || 'overview';
  const [path, params = ''] = hash.split('?');
  const [route, id] = path.split('/');
  const query = new URLSearchParams(params).get('q') || '';
  let content;
  if(route==='overview') content=overview();
  else if(route==='research') content=research(id||1);
  else if(route==='projects') content=projectPage();
  else if(route==='architecture') content=architecture(id);
  else if(route==='belief') content=belief();
  else if(route==='roadmap') content=roadmap();
  else if(route==='sources') content=sources();
  else if(route==='search') content=search(query);
  else content=notFound();
  main.innerHTML=content;
  main.classList.toggle('reader-main',route==='research');
  $('#breadcrumb').textContent=routes[route]||'Page not found';
  document.title=`${routes[route]||'Page not found'} · Catan Research Lab`;
  $('#global-query').value=route==='search'?query:'';
  $('#navigation').querySelectorAll('a').forEach(a=>{const active=a.hash.slice(1).split('/')[0]===route;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  if(route==='projects'){ $('#project-query').addEventListener('input',filterProjects);$('#project-kind').addEventListener('change',filterProjects); }
  if(route==='sources'){ $('#source-query').addEventListener('input',filterSources);$('#source-kind').addEventListener('change',filterSources); }
  if(route==='belief'){['#ore-count','#wheat-count'].forEach(s=>$(s).addEventListener('input',updateBelief));$('#reset-belief').addEventListener('click',()=>{$('#ore-count').value=2;$('#wheat-count').value=1;updateBelief();});updateBelief();}
  externalLinks();
  if(focus){window.scrollTo({top:0,behavior:'instant'});main.focus({preventScroll:true});}
}
$('#global-search').addEventListener('submit',event=>{event.preventDefault();const next='#search?q='+encodeURIComponent($('#global-query').value.trim());if(location.hash===next)render(true);else location.hash=next;});
$('.skip-link').addEventListener('click',event=>{event.preventDefault();main.focus();});
try {
  const response = await fetch('content.json');
  if (!response.ok) throw new Error('Research content could not be loaded.');
  data=await response.json();
  render();
  window.addEventListener('hashchange',()=>render(true));
} catch(error) {
  main.innerHTML=`<div class="empty-state"><h1>The research could not load.</h1><p>Refresh the page, or download the full report below.</p><a class="button" href="catan-ai-research.md" download>Download the research</a></div>`;
  console.error(error);
}
