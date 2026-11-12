(() => {
  const form = document.getElementById('basket-form');
  const holder = document.getElementById('basket-rows');
  const template = document.getElementById('basket-template');
  if (!form || !holder || !template) return;

  let catalog = [];
  try { catalog = JSON.parse(document.getElementById('basket-catalog')?.textContent || '[]'); }
  catch (_err) { catalog = []; }

  const total = document.getElementById('basket-total');
  const count = document.getElementById('basket-count');
  const add = document.getElementById('basket-add');
  const money = value => '৳' + value.toLocaleString('en-BD', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const rows = () => [...holder.querySelectorAll('[data-basket-row]')];

  function recalculate() {
    const entries = rows();
    const sumCents = entries.reduce((acc, row) => {
      const input = row.querySelector('.basket-amount');
      const n = Number(input?.value || '0');
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

  function syncSavedPicker(row) {
    const category = row.querySelector('.basket-category').value;
    const picker = row.querySelector('.basket-pick');
    const name = row.querySelector('.basket-item-name');
    picker.replaceChildren();
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = 'Choose a saved item...';
    picker.appendChild(empty);
    catalog.filter(item => String(item.category_id) === category).forEach(item => {
      const option = document.createElement('option');
      option.value = item.name;
      option.textContent = item.name;
      picker.appendChild(option);
    });
    picker.value = [...picker.options].some(x => x.value === name.value) ? name.value : '';
  }

  function wireRow(row) {
    const category = row.querySelector('.basket-category');
    const picker = row.querySelector('.basket-pick');
    const name = row.querySelector('.basket-item-name');
    category.addEventListener('change', () => syncSavedPicker(row));
    picker.addEventListener('change', () => {
      if (!picker.value) return;
      name.value = picker.value;
      row.querySelector('.basket-amount').focus();
    });
    name.addEventListener('input', () => { picker.value = name.value; });
    row.querySelector('.basket-amount').addEventListener('input', recalculate);
    row.querySelector('[data-basket-remove]').addEventListener('click', () => {
      if (rows().length <= 1) return;
      row.remove();
      recalculate();
    });
    syncSavedPicker(row);
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
      window.setTimeout(() => { button.disabled = true; button.textContent = 'Saving purchases…'; }, 0);
    }
  });
})();
