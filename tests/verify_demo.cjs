'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = p => fs.readFileSync(path.join(root, p), 'utf8');
const js = read('demo/demo.js');
const html = read('demo/index.html');
const css = read('demo/demo.css');

assert.match(html, /Fictional/i);
assert.match(html, /Read-only/i);
assert.match(html, /https:\/\/github\.com\/Rafidabd\/apartment-ledger/);
assert.match(html, /demo\.js/);
assert.match(html, /demo\.css/);
assert.match(css, /@media\(max-width:760px\)/);
assert.doesNotMatch(js, /(?:fetch\s*\(|XMLHttpRequest|localStorage|sessionStorage|document\.cookie)/);
assert.doesNotMatch(html, /<form[\s>]/i);

// Minimal DOM simulation to execute every page's rendering and the built-in
// financial reconciliation checks without downloading browser libraries.
const handlers = {};
const page = {
  innerHTML: '',
  querySelectorAll: () => [],
  querySelector: () => ({addEventListener:()=>{},value:'',innerHTML:'',textContent:''})
};
const title = {textContent: ''};
const sandbox = {
  document: {
    getElementById: id => id === 'main-content' ? page : id === 'current-page-label' ? title : null,
    querySelectorAll: () => []
  },
  location: { hash: '#overview' },
  window: {
    addEventListener: (event, callback) => { handlers[event] = callback; },
    scrollTo: () => {}
  }
};
vm.runInNewContext(js, sandbox, {filename:'demo/demo.js', timeout: 2000});
assert.match(page.innerHTML, /Overview/);
assert.match(page.innerHTML, /৳10,370/);
assert.match(page.innerHTML, /৳5,670/);
assert.match(page.innerHTML, /৳900/);
assert.match(page.innerHTML, /৳500/);
assert.match(page.innerHTML, /৳440/);

for (const [hash, expected] of [
  ['#calendar','Expense calendar'],
  ['#roommates','Roommate accounts'],
  ['#caretaker','Caretaker account'],
  ['#reports','November 2026 report'],
  ['#transactions','Transaction history']
]) {
  sandbox.location.hash = hash;
  handlers.hashchange();
  assert.match(page.innerHTML, new RegExp(expected));
}
sandbox.location.hash = '#roommates';
handlers.hashchange();
assert.match(page.innerHTML, /Contribution pending/);
assert.match(page.innerHTML, /Amina/);
assert.match(page.innerHTML, /Rafi/);
assert.match(page.innerHTML, /Nabil/);
sandbox.location.hash = '#reports';
handlers.hashchange();
assert.match(page.innerHTML, /৳2,000/);   // Prior-month opening cash
assert.match(page.innerHTML, /৳14,800/);  // Shared-fund inflows, incl. repayments
assert.match(page.innerHTML, /৳6,430/);   // Shared-fund cash outflows
assert.match(page.innerHTML, /৳10,370/);  // Closing cash
assert.match(page.innerHTML, /৳5,670/);   // Spending, including caretaker-paid

console.log('Demo verified: fictional-only, read-only, responsive assets and reconciled views.');
