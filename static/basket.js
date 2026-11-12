(() => {
  const form = document.getElementById('basket-form');
  const holder = document.getElementById('basket-rows');
  const template = document.getElementById('basket-template');
  if (!form || !holder || !template) return;

  const total = document.getElementById('basket-total');
  const count = document.getElementById('basket-count');
  const add = document.getElementById('basket-add');
  const money = value => '৳' + value.toLocaleString('en-BD', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });
  const rows = () => [...holder.querySelectorAll('[data-basket-row]')];

  function recalculate() {
    const entries = rows();
    const sumCents = entries.reduce((acc, row) => {
      const n = Number(row.querySelector('.basket-amount')?.value || '0');
      return acc + (Number.isFinite(n) && n > 0 ? Math.round(n * 100) : 0);
    }, 0);
    total.textContent = money(sumCents / 100);
    count.textContent = entries.length + (entries.length === 1 ? ' item' : ' items');
    entries.forEach((row, index) => {
      row.querySelector('.basket-row-number').textContent = 'Item ' + (index + 1);
      row.querySelector('[data-basket-remove]').disabled = entries.length === 1;
    });
    add.disabled = entries.length >= 30;
  }

  function wireRow(row) {
    const name = row.querySelector('.basket-item-name');
    const amount = row.querySelector('.basket-amount');
    // The same autocomplete works for both the basket and single-item forms.
    window.LedgerItemSuggest?.attach(name);
    amount.addEventListener('input', recalculate);
    row.querySelector('[data-basket-remove]').addEventListener('click', () => {
      if (rows().length <= 1) return;
      row.remove();
      recalculate();
    });
  }

  rows().forEach(wireRow);
  add.addEventListener('click', () => {
    if (rows().length >= 30) return;
    const newRow = template.content.firstElementChild.cloneNode(true);
    holder.appendChild(newRow);
    wireRow(newRow);
    recalculate();
    newRow.querySelector('.basket-item-name').focus();
  });
  recalculate();
  form.addEventListener('submit', e => {
    const button = e.submitter;
    if (button && button.type === 'submit') {
      window.setTimeout(() => {
        button.disabled = true; button.textContent = 'Saving purchases…';
      }, 0);
    }
  });
})();