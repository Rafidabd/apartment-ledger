/* Public portfolio preview. All data below is fictional, bundled in this file.
 * This script uses only embedded examples and contains no persistence or network calls.
 */
(() => {
  'use strict';

  const DEMO_MONTH = '2026-11';
  const contributors = [
    { id: 'amina', name: 'Amina', target: 5000 },
    { id: 'rafi', name: 'Rafi', target: 5000 },
    { id: 'nabil', name: 'Nabil', target: 5000 }
  ];
  // Amounts are in whole BDT; entries mirror the production ledger's distinctions.
  const entries = Object.freeze([
    {id:1,date:'2026-10-31',time:'18:00',kind:'opening',amount:2000,note:'Fictional opening shared cash'},
    {id:2,date:'2026-11-01',time:'08:30',kind:'contribution',amount:5000,member:'amina'},
    {id:3,date:'2026-11-01',time:'11:10',kind:'contribution',amount:4500,member:'rafi'},
    {id:4,date:'2026-11-01',time:'12:45',kind:'contribution',amount:5000,member:'nabil'},
    {id:5,date:'2026-11-02',time:'09:12',kind:'expense',amount:650,item:'চাল',category:'Groceries'},
    {id:6,date:'2026-11-02',time:'09:15',kind:'expense',amount:180,item:'Eggs',category:'Groceries'},
    {id:7,date:'2026-11-02',time:'09:20',kind:'expense',amount:310,item:'Cooking oil',category:'Groceries'},
    {id:8,date:'2026-11-03',time:'16:20',kind:'advance_fund',amount:700,member:'rafi'},
    {id:9,date:'2026-11-04',time:'10:40',kind:'caretaker_expense',amount:350,item:'মাছ',category:'Groceries'},
    {id:10,date:'2026-11-05',time:'08:30',kind:'advance_caretaker',amount:800,member:'nabil'},
    {id:11,date:'2026-11-05',time:'17:00',kind:'expense',amount:1500,item:'Electricity bill',category:'Utilities'},
    {id:12,date:'2026-11-07',time:'13:30',kind:'repayment_fund',amount:200,member:'rafi',related:8},
    {id:13,date:'2026-11-08',time:'11:20',kind:'repayment_caretaker',amount:300,member:'nabil',related:10},
    {id:14,date:'2026-11-09',time:'10:10',kind:'caretaker_reimbursement',amount:150,related:9,note:'Partial reimbursement for fish'},
    {id:15,date:'2026-11-10',time:'18:30',kind:'expense',amount:1200,item:'Cooking gas',category:'Utilities'},
    {id:16,date:'2026-11-11',time:'09:05',kind:'expense',amount:120,item:'ডাল',category:'Groceries'},
    {id:17,date:'2026-11-11',time:'09:10',kind:'expense',amount:80,item:'আলু',category:'Groceries'},
    {id:18,date:'2026-11-11',time:'09:15',kind:'expense',amount:140,item:'সবজি',category:'Groceries'},
    {id:19,date:'2026-11-12',time:'08:15',kind:'expense',amount:900,item:'Internet bill',category:'Utilities'},
    {id:20,date:'2026-11-12',time:'09:30',kind:'caretaker_expense',amount:240,item:'Detergent',category:'Household supplies'},
    {id:21,date:'2026-11-12',time:'11:30',kind:'advance_fund',amount:500,member:'amina'},
    {id:22,date:'2026-11-12',time:'12:10',kind:'repayment_fund',amount:100,member:'rafi',related:8}
  ]);
  const labels = Object.freeze({
    opening:'Opening cash',contribution:'Roommate contribution',expense:'Shared purchase',
    caretaker_expense:'Caretaker-paid purchase',advance_fund:'Shared-fund advance',
    advance_caretaker:'Caretaker personal loan',repayment_fund:'Shared-fund repayment',
    repayment_caretaker:'Caretaker loan repayment',caretaker_reimbursement:'Caretaker reimbursement'
  });
  const inflow = new Set(['opening','contribution','income','repayment_fund']);
  const outflow = new Set(['expense','advance_fund','caretaker_reimbursement']);
  const purchases = new Set(['expense','caretaker_expense']);
  const caretakerTypes = new Set(['caretaker_expense','advance_caretaker','repayment_caretaker',
    'advance_fund','repayment_fund','caretaker_reimbursement']);
  const availableViews = new Set(['overview','calendar','transactions','roommates','caretaker','reports']);
  const money = amount => '৳' + Math.abs(amount).toLocaleString('en-BD');
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[c]);
  const sum = (list, predicate = () => true) => list.filter(predicate).reduce((acc,t) => acc+t.amount, 0);
  const monthItems = entries.filter(t => t.date.startsWith(DEMO_MONTH));
  const monthSorted = [...monthItems].sort((a,b) => b.date.localeCompare(a.date) || b.time.localeCompare(a.time) || b.id-a.id);
  const memberName = id => contributors.find(x => x.id === id)?.name || 'Household';
  const nameOf = tx => tx.item || (tx.member ? memberName(tx.member) : tx.note || labels[tx.kind]);
  const cashEffect = tx => (inflow.has(tx.kind) ? tx.amount : outflow.has(tx.kind) ? -tx.amount : 0);
  const closingCash = entries.reduce((s,t) => s + cashEffect(t), 0);
  const openingCash = entries.filter(t => t.date < DEMO_MONTH + '-01').reduce((s,t) => s + cashEffect(t), 0);
  const incoming = sum(monthItems,t => inflow.has(t.kind));
  const outgoing = sum(monthItems,t => outflow.has(t.kind));
  const spent = sum(monthItems,t => purchases.has(t.kind));
  const dueFor = base => {
    const already = sum(entries,t => t.related === base.id);
    return Math.max(0,base.amount-already);
  };
  const due = kind => entries.filter(t=>t.kind === kind).reduce((s,t)=>s+dueFor(t),0);
  const fundDue = due('advance_fund');
  const personalDue = due('advance_caretaker');
  const reimbursementDue = due('caretaker_expense');
  const categoryTotals = monthItems.filter(t=>purchases.has(t.kind)).reduce((obj,t) => {
    obj[t.category] = (obj[t.category] || 0) + t.amount;
    return obj;
  },{});
  const monthlyContributions = sum(monthItems,t=>t.kind==='contribution');
  const getBalance = who => {
    const contributed = sum(monthItems,t => t.kind==='contribution' && t.member===who.id);
    const fund = entries.filter(t=>t.kind==='advance_fund'&&t.member===who.id)
      .reduce((s,t)=>s+dueFor(t),0);
    const caretaker = entries.filter(t=>t.kind==='advance_caretaker'&&t.member===who.id)
      .reduce((s,t)=>s+dueFor(t),0);
    return {...who,contributed, gap:Math.max(0,who.target-contributed),
      fundDue:fund,caretakerDue:caretaker,followUp:Math.max(0,who.target-contributed)+fund+caretaker};
  };
  const balances = contributors.map(getBalance);
  const page = document.getElementById('main-content');
  const pageTitle = document.getElementById('current-page-label');
  let selectedDay = '2026-11-12';

  function heading(eyebrow,title,subtitle,trailing='') {
    return `<div class="page-head"><div><p class="eyebrow">${safe(eyebrow)}</p><h1>${safe(title)}</h1><p class="subtitle">${safe(subtitle)}</p></div>${trailing}</div>`;
  }
  function numberCard(label,value,note,kind='') {
    return `<div class="card metric ${kind}"><span>${safe(label)}</span><strong>${money(value)}</strong><small>${safe(note)}</small></div>`;
  }
  function blank(message) {
    return `<div class="empty-state"><strong>Nothing here yet</strong><p>${safe(message)}</p></div>`;
  }
  function activity(t, showTime=false) {
    const neg = outflow.has(t.kind) || purchases.has(t.kind);
    return `<div class="activity">
      <span class="activity-icon ${neg?'warm':''}">${neg?'↗':'↙'}</span>
      <span class="activity-main"><strong>${safe(nameOf(t))}</strong><small>${safe(labels[t.kind])} · ${safe(t.date)}${showTime ? ' · '+safe(t.time) : ''}</small></span>
      <strong class="activity-value">${money(t.amount)}</strong>
    </div>`;
  }
  function sectionTitle(title,note='',right='') {
    return `<div class="section-title"><div><h2>${safe(title)}</h2>${note?`<p>${safe(note)}</p>`:''}</div>${right}</div>`;
  }
  function categoryBars(items=categoryTotals) {
    const arr = Object.entries(items).sort((a,b)=>b[1]-a[1]);
    if(!arr.length) return blank('No purchases recorded.');
    const max = Math.max(...arr.map(x=>x[1]),1);
    return arr.map(([name,amount],i) =>
      `<div class="bar-row"><div><span>${safe(name)}</span><strong>${money(amount)}</strong></div>
         <div class="bar-track"><span class="bar-fill tone-${i%4}" style="width:${(amount/max*100).toFixed(1)}%"></span></div></div>`
    ).join('');
  }
  function overview() {
    const recent=monthSorted.slice(0,6);
    return heading('YOUR APARTMENT AT A GLANCE','Overview / November 2026',
      'A complete fictional example of shared-apartment accounting.',
      '<span class="month-chip">▣ November 2026</span>')+
      `<div class="hero-grid">
        <section class="hero-balance"><p>◉ Available shared fund</p><strong>${money(closingCash)}</strong>
          <span>Month-end cash, including an opening balance of ${money(openingCash)}</span>
          <div class="hero-totals"><div><small>Cash received</small><b>${money(incoming)}</b></div>
          <div><small>Cash paid out</small><b>${money(outgoing)}</b></div></div>
        </section>
        <div class="metric-stack">
          ${numberCard('Roommate contributions',monthlyContributions,'Received during November')}
          ${numberCard('Household spending',spent,'Includes caretaker-paid purchases','warm-metric')}
        </div>
      </div>
      ${sectionTitle('Explore the ledger','Different questions, clearly separated')}
      <div class="feature-grid">
        <a href="#calendar" class="feature-card"><span class="feature-icon">▣</span>
          <strong>Daily calendar</strong><small>See what happened on each day.</small><b>↗</b></a>
        <a href="#roommates" class="feature-card"><span class="feature-icon">◫</span>
          <strong>Roommate settlements</strong><small>Contributions, targets, and unpaid loans.</small><b>↗</b></a>
        <a href="#caretaker" class="feature-card"><span class="feature-icon">⇄</span>
          <strong>Caretaker account</strong><small>Money lent, spent, repaid and reimbursed.</small><b>↗</b></a>
      </div>
      ${sectionTitle('Money still to settle','Outstanding as of November 12')}
      <div class="three-metrics">
        ${numberCard('Owed to shared fund',fundDue,'Unpaid roommate advances')}
        ${numberCard('Personal caretaker loans',personalDue,'Borrowed from his own pocket')}
        ${numberCard('Household reimbursements',reimbursementDue,'Caretaker-paid shared purchases')}
      </div>
      <div class="two-col">
        <section class="card panel">${sectionTitle('Where money went','Household purchases by category','<a href="#reports">Full report ↗</a>')}${categoryBars()}</section>
        <section class="card panel">${sectionTitle('Recent activity','Latest fictional transactions','<a href="#transactions">View all ↗</a>')}${recent.map(x=>activity(x,true)).join('')}</section>
      </div>`;
  }
  function calendar() {
    const first = new Date(Date.UTC(2026,10,1));
    const offset = (first.getUTCDay()+6)%7;
    const days=30, cells=[];
    for(let i=0;i<offset;i++) cells.push('<span class="cal-empty" aria-hidden="true"></span>');
    for(let d=1;d<=days;d++) {
      const iso='2026-11-'+String(d).padStart(2,'0');
      const tx=monthItems.filter(t=>t.date===iso);
      const daySpent=sum(tx,t=>purchases.has(t.kind));
      cells.push(`<button type="button" class="calendar-date ${iso===selectedDay?'chosen':''} ${tx.length?'has-events':''}"
        data-day="${iso}" aria-pressed="${iso===selectedDay}" aria-label="November ${d}, ${tx.length} transactions, ${money(daySpent)} household spending">
        <span>${d}</span>${tx.length ? `<b>${money(daySpent)}</b><small>${tx.length} ${tx.length===1?'entry':'entries'}</small>` : '<i>＋</i>'}
      </button>`);
    }
    const selected=monthSorted.filter(t=>t.date===selectedDay);
    return heading('ONE DAY AT A TIME','Expense calendar',
      'Pick a date to explore individual purchases and money movements.')+
      `<div class="calendar-layout"><section class="card panel calendar-panel">
        <div class="calendar-header"><div><p class="eyebrow">MONTHLY ACTIVITY</p><h2>November 2026</h2></div>
          <span class="read-only-pill">Read-only</span></div>
        <div class="cal-weekdays">${['MON','TUE','WED','THU','FRI','SAT','SUN'].map(x=>`<span>${x}</span>`).join('')}</div>
        <div class="calendar-grid">${cells.join('')}</div>
        <p class="fine-print">Calendar figures show household purchases. Other transactions are visible when you open a day.</p>
      </section><section class="card panel calendar-detail" id="day-detail">
        ${sectionTitle(selectedDay,'Day-by-day transaction details')}
        <div class="daily-totals"><span>Household spending</span><strong>${money(sum(selected,t=>purchases.has(t.kind)))}</strong>
          <small>${selected.length} recorded movements</small></div>
        ${selected.length?selected.map(t=>activity(t,true)).join(''):blank('Choose a date with activity to see the timeline.')}
      </section></div>`;
  }
  function txMatches(t,q,category) {
    const text=[t.item,t.note,t.member?memberName(t.member):'',t.category,labels[t.kind],t.date].join(' ').toLocaleLowerCase();
    return (!q||text.includes(q))&&(category==='all'||(category==='purchase'?purchases.has(t.kind):
       category==='money'?['opening','contribution','repayment_fund','repayment_caretaker'].includes(t.kind):
       category==='advances'?t.kind.startsWith('advance_'):caretakerTypes.has(t.kind)));
  }
  function txRows(rows) {
    if(!rows.length) return '<tr><td colspan="5" class="no-results">No matching transactions.</td></tr>';
    return rows.map(t=>`<tr><td class="date-cell">${safe(t.date)}<small>${safe(t.time)}</small></td>
      <td><strong>${safe(nameOf(t))}</strong><small>${safe(labels[t.kind])}</small></td>
      <td>${safe(t.category|| (t.member?memberName(t.member):'—'))}</td>
      <td class="amount-cell">${money(t.amount)}</td>
      <td><span class="tx-badge">${purchases.has(t.kind)?'Expense':t.kind.startsWith('advance')?'Advance':
        t.kind.startsWith('repayment')||t.kind==='caretaker_reimbursement'?'Repayment':'Funding'}</span></td></tr>`).join('');
  }
  function transactions() {
    return heading('FULL RECORD','Transaction history',
      'Search and filter the fictional November entries. This preview cannot change records.')+
      `<section class="card panel transactions-panel">
        <div class="search-tools">
          <label class="search-input">⌕ <input id="tx-search" type="search" placeholder="Search চাল, Amina, utilities…" aria-label="Search transactions"></label>
          <label class="filter-input">Show <select id="tx-filter" aria-label="Filter transaction type">
            <option value="all">All transactions</option><option value="purchase">Purchases</option>
            <option value="money">Funding / repayments</option><option value="advances">Advances</option>
            <option value="caretaker">Caretaker activity</option></select></label>
        </div>
        <div class="transaction-count"><span id="tx-count">${monthSorted.length} transactions</span><span>November 2026 · fictional data</span></div>
        <div class="table-wrap"><table><thead><tr><th>Date</th><th>Description</th><th>Category / person</th><th>Amount</th><th>Type</th></tr></thead>
        <tbody id="tx-rows">${txRows(monthSorted)}</tbody></table></div>
      </section>`;
  }
  function memberCard(p) {
    return `<article class="card roommate-card">
      <div class="roommate-head"><div class="avatar">${safe(p.name[0])}</div><div><strong>${safe(p.name)}</strong><small>Fictional roommate</small></div>
        <span class="status ${p.gap?'pending':'paid'}">${p.gap?'Contribution pending':'Target met'}</span></div>
      <div class="roommate-metrics">
        <div><span>Monthly target</span><b>${money(p.target)}</b></div>
        <div><span>Contributed</span><b>${money(p.contributed)}</b></div>
        <div><span>Contribution gap</span><b>${money(p.gap)}</b></div>
        <div><span>Fund advance owed</span><b>${money(p.fundDue)}</b></div>
        <div><span>Caretaker loan owed</span><b>${money(p.caretakerDue)}</b></div>
      </div>
      <div class="follow-up"><span>Known amount to follow up <small>Contributions + outstanding advances</small></span><strong>${money(p.followUp)}</strong></div>
    </article>`;
  }
  function roommates() {
    const target=contributors.reduce((s,m)=>s+m.target,0);
    const contributionGap=balances.reduce((s,m)=>s+m.gap,0);
    return heading('MONTHLY SETTLEMENTS','Roommate accounts',
      'Individual contributions and unpaid advances, reconciled with the shared ledger.')+
      `<div class="three-metrics">
        ${numberCard('Expected contributions',target,'Fictional target for November')}
        ${numberCard('Received this month',monthlyContributions,'Recorded shared-fund contributions')}
        ${numberCard('Contributions pending',contributionGap,'Does not include loans')}
      </div>
      ${sectionTitle('Individual settlements','The same contributions and loans shown in the main application')}
      <div class="roommate-grid">${balances.map(memberCard).join('')}</div>
      <div class="note-box"><strong>Accounting distinction</strong><p>Contributions are shared-fund income. Outstanding advances are money owed by specific roommates, not household purchases. The follow-up amount is a planning figure, not new revenue or spending.</p></div>`;
  }
  function flowRow(label,value,descriptor='') {
    return `<div class="flow-row"><div><strong>${safe(label)}</strong>${descriptor?`<small>${safe(descriptor)}</small>`:''}</div><b>${money(value)}</b></div>`;
  }
  function caretaker() {
    const caretakerRecords=monthSorted.filter(t=>caretakerTypes.has(t.kind));
    const outstanding=entries.filter(t=>['advance_caretaker','advance_fund','caretaker_expense'].includes(t.kind))
      .map(t=>({...t,remaining:dueFor(t)})).filter(t=>t.remaining>0);
    return heading('SEPARATE MONEY, ONE LEDGER','Caretaker account',
      'Personal lending, communal advances, household purchases and reimbursements—never double-counted.')+
      `<div class="caretaker-hero">
        <section class="card care-primary"><span>Still owed to caretaker personally</span>
          <strong>${money(personalDue+reimbursementDue)}</strong>
          <div><small>Personal loans <b>${money(personalDue)}</b></small><small>Household reimbursements <b>${money(reimbursementDue)}</b></small></div>
        </section>
        ${numberCard('Owed to shared fund',fundDue,'Roommate borrowing from collective cash')}
        ${numberCard('Shared cash remaining',closingCash,'Matches the Overview and Reports')}
      </div>
      <div class="two-col">
        <section class="card panel">${sectionTitle('Money exchanged','Movements during November')}
          ${flowRow('Caretaker lent to roommates',sum(monthItems,t=>t.kind==='advance_caretaker'))}
          ${flowRow('Roommates repaid caretaker',sum(monthItems,t=>t.kind==='repayment_caretaker'))}
          ${flowRow('Caretaker-paid household purchases',sum(monthItems,t=>t.kind==='caretaker_expense'))}
          ${flowRow('Reimbursed from shared fund',sum(monthItems,t=>t.kind==='caretaker_reimbursement'))}
          ${flowRow('Borrowed from shared fund',sum(monthItems,t=>t.kind==='advance_fund'))}
          ${flowRow('Repaid to shared fund',sum(monthItems,t=>t.kind==='repayment_fund'))}
        </section>
        <section class="card panel">${sectionTitle('Outstanding records','Balances still unsettled')}
          ${outstanding.map(t=>flowRow(t.kind==='advance_fund'?'Shared-fund advance':t.kind==='advance_caretaker'?'Personal caretaker loan':'Household reimbursement',t.remaining,nameOf(t))).join('')}
        </section>
      </div>
      <section class="card panel">${sectionTitle('Caretaker activity','Every connected movement','<a href="#transactions">All transactions ↗</a>')}
        <div class="activity-grid">${caretakerRecords.map(t=>activity(t,true)).join('')}</div>
      </section>
      <div class="note-box"><strong>Why these balances are separate</strong><p>Borrowing from collective cash reduces available fund money. A personal loan from the caretaker does not. Caretaker-paid groceries count once as household spending; reimbursing him later changes cash and debt, not the spending figure.</p></div>`;
  }
  function reports() {
    const items = Object.entries(categoryTotals).sort((a,b)=>b[1]-a[1]);
    return heading('MONTHLY REVIEW','November 2026 report',
      'One consistent picture of fictional shared cash, spending and unsettled money.')+
      `<section class="card panel report-equation">
        <p class="eyebrow">HOW THE SHARED FUND MOVED</p>
        <div class="equation-grid"><div><small>Opening cash</small><strong>${money(openingCash)}</strong></div>
          <span>+</span><div><small>Money in</small><strong>${money(incoming)}</strong></div>
          <span>−</span><div><small>Cash out</small><strong>${money(outgoing)}</strong></div>
          <span>=</span><div class="equation-result"><small>Closing cash</small><strong>${money(closingCash)}</strong></div>
        </div>
      </section>
      <div class="three-metrics">
        ${numberCard('Household spending',spent,'Includes caretaker-paid expenses')}
        ${numberCard('Fund advances unpaid',fundDue,'Outstanding at month-end')}
        ${numberCard('Caretaker amounts unpaid',personalDue+reimbursementDue,'Personal loans + reimbursements')}
      </div>
      <div class="two-col">
        <section class="card panel">${sectionTitle('Category breakdown','Shared and caretaker-paid purchases')}
          ${categoryBars()}</section>
        <section class="card panel">${sectionTitle('Roommate contributions','Actual income, not planned targets')}
          ${balances.map(p=>flowRow(p.name,p.contributed,p.gap?`${money(p.gap)} below target`:'Target met')).join('')}
          <div class="report-footer-total"><span>Total received</span><strong>${money(monthlyContributions)}</strong></div>
        </section>
      </div>
      <div class="two-col">
        <section class="card panel">${sectionTitle('Settlement balances','Amounts owed as of November 12')}
          ${flowRow('Owed to shared fund',fundDue)}
          ${flowRow('Personal caretaker loans',personalDue)}
          ${flowRow('Caretaker reimbursements',reimbursementDue)}
        </section>
        <section class="card panel">${sectionTitle('Where spending went','Relative distribution')}
          <div class="distribution" role="img" aria-label="Spending category shares">
            ${items.map(([name,value],i)=>`<div class="distribution-row"><div><span class="dot tone-${i%4}"></span>${safe(name)}</div>
              <b>${(100*value/spent).toFixed(1)}%</b></div>`).join('')}
          </div>
        </section>
      </div>
      <div class="note-box"><strong>Reconciled by design</strong><p>Money in includes contributions and repayments to the shared fund; it excludes personal caretaker loans. Cash out includes shared-fund purchases, collective advances and reimbursements. Household spending also includes caretaker-paid purchases, but not their later reimbursement.</p></div>`;
  }

  const renderers={overview,calendar,transactions,roommates,caretaker,reports};
  function route() {
    const hash=location.hash.replace(/^#/,'').split('?')[0];
    return availableViews.has(hash)?hash:'overview';
  }
  function setSelectedNav(view) {
    document.querySelectorAll('[data-route]').forEach(link=>{
      const active=link.dataset.route===view;
      link.classList.toggle('active',active);
      if(active)link.setAttribute('aria-current','page');
      else link.removeAttribute('aria-current');
    });
    pageTitle.textContent=view.toUpperCase();
  }
  function bindInteractions(view) {
    if(view==='calendar') {
      page.querySelectorAll('[data-day]').forEach(button=>button.addEventListener('click',()=>{
        selectedDay=button.dataset.day;
        render(false);
        const chosen=page.querySelector('.calendar-date.chosen');
        if(chosen)chosen.focus({preventScroll:true});
      }));
    } else if(view==='transactions') {
      const search=page.querySelector('#tx-search');
      const filter=page.querySelector('#tx-filter');
      const update=()=>{
        const query=search.value.trim().toLocaleLowerCase();
        const matching=monthSorted.filter(t=>txMatches(t,query,filter.value));
        page.querySelector('#tx-rows').innerHTML=txRows(matching);
        page.querySelector('#tx-count').textContent=matching.length+' matching transactions';
      };
      search.addEventListener('input',update);
      filter.addEventListener('change',update);
    }
  }
  function render(scrollToTop=true) {
    const view=route();
    setSelectedNav(view);
    page.innerHTML=renderers[view]();
    bindInteractions(view);
    if(scrollToTop)window.scrollTo({top:0,behavior:'instant'});
  }
  window.addEventListener('hashchange',()=>render());
  render();

  // The public preview intentionally contains no write path.
  if (openingCash+incoming-outgoing!==closingCash ||
      balances.reduce((s,p)=>s+p.fundDue,0)!==fundDue ||
      balances.reduce((s,p)=>s+p.caretakerDue,0)!==personalDue) {
    throw new Error('Demo financial reconciliation failed.');
  }
})();
