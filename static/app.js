(() => {
  const type = document.querySelector('[data-toggle="member-money"]');
  const box = document.getElementById('member-money');
  const member = document.getElementById('money-member');
  if (type && box) {
    const update = () => {
      const show = type.value === 'contribution';
      box.hidden = !show;
      if (member) { member.required = show; member.disabled = !show; }
    };
    type.addEventListener('change', update);
    update();
  }

  const category = document.getElementById('category');
  const input = document.getElementById('item-name');
  const itemPicker = document.querySelector('[data-item-picker]');
  const savedList = document.getElementById('saved-items');
  if (category && input && itemPicker && savedList) {
    const buttons = [...itemPicker.querySelectorAll('.item-shortcut')];
    const search = document.getElementById('saved-item-search');
    const showAll = document.getElementById('show-all-items');
    const count = document.getElementById('shortcut-count');
    const empty = itemPicker.querySelector('.item-shortcuts-empty');
    const rememberRow = document.getElementById('remember-item-row');
    const remember = document.getElementById('remember-item');
    const lastPrice = document.getElementById('last-price-hint');
    const lastPriceText = document.getElementById('last-price-text');
    const useLast = document.getElementById('use-last-price');
    const amount = document.getElementById('amount');
    const shortListLimit = 12;
    let expanded = false;
    const norm = value => String(value || '').normalize('NFC').trim().toLocaleLowerCase();

    // A new item is always allowed as an expense. Adding it to favorites is optional.
    const updateSelected = () => {
      const current = norm(input.value);
      const match = buttons.find(b => b.dataset.category === category.value &&
        norm(b.dataset.name) === current);
      buttons.forEach(b => b.classList.toggle('is-selected', !!match && match === b));
      const isNew = current.length > 0 && !match;
      if (rememberRow && remember) {
        rememberRow.hidden = !isNew;
        remember.disabled = !isNew;
      }
      const cents = match ? Number(match.dataset.lastCents) : NaN;
      const hasLast = match && match.dataset.lastCents !== '' &&
        Number.isFinite(cents) && cents > 0;
      if (lastPrice) lastPrice.hidden = !hasLast;
      if (hasLast && lastPriceText) {
        lastPriceText.textContent = 'Last paid: ৳' + (cents / 100).toLocaleString('en-BD', {
          minimumFractionDigits: 0, maximumFractionDigits: 2
        });
      }
      if (useLast) useLast.dataset.amount = hasLast ? (cents / 100).toFixed(2) : '';
    };

    const refresh = () => {
      const selected = buttons.filter(b => b.dataset.category === category.value);
      const query = norm(search?.value);
      const filtered = query ? selected.filter(b => norm(b.dataset.name).includes(query)) : selected;
      const visible = (expanded || query) ? filtered : filtered.slice(0, shortListLimit);
      const shown = new Set(visible);
      buttons.forEach(b => { b.hidden = !shown.has(b); });
      savedList.replaceChildren();
      selected.forEach(b => {
        const option = document.createElement('option');
        option.value = b.dataset.name;
        savedList.appendChild(option);
      });
      if (empty) empty.hidden = filtered.length !== 0;
      if (showAll) {
        showAll.hidden = !!query || selected.length <= shortListLimit;
        showAll.textContent = expanded ? 'Show fewer' : 'Show all (' + selected.length + ')';
      }
      if (count) count.textContent = filtered.length > 0
        ? (visible.length === filtered.length ? filtered.length + ' items available'
          : 'Showing ' + visible.length + ' of ' + filtered.length + ' saved items')
        : '';
      updateSelected();
    };

    buttons.forEach(b => b.addEventListener('click', () => {
      input.value = b.dataset.name;
      updateSelected();
      if (amount) amount.focus();
    }));
    category.addEventListener('change', () => {
      expanded = false;
      if (search) search.value = '';
      // Preserve typed names when switching categories; recheck saved items for the new category.
      refresh();
    });
    input.addEventListener('input', updateSelected);
    search?.addEventListener('input', refresh);
    showAll?.addEventListener('click', () => { expanded = !expanded; refresh(); });
    useLast?.addEventListener('click', () => {
      if (amount && useLast.dataset.amount) {
        amount.value = useLast.dataset.amount;
        amount.focus();
        amount.select();
      }
    });
    refresh();
    if (document.getElementById('entry-form')?.dataset.repeat === '1') input.focus();
  }

  const entryDate = document.getElementById('tx_date');
  const entryTime = document.getElementById('tx_time');
  if (entryDate && entryTime) {
    entryDate.addEventListener('change', () => {
      const now = new Date();
      const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'),
        String(now.getDate()).padStart(2, '0')].join('-');
      entryTime.value = entryDate.value === today
        ? [String(now.getHours()).padStart(2, '0'), String(now.getMinutes()).padStart(2, '0')].join(':') : '';
    });
  }

  const entry = document.getElementById('entry-form');
  if (entry) entry.addEventListener('submit', e => {
    const button = e.submitter;
    if (button && button.tagName === 'BUTTON') {
      window.setTimeout(() => { button.disabled = true; button.textContent = 'Saving…'; }, 0);
    }
  });
})();