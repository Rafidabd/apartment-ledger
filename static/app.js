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

  // A few taps are faster than typing the same grocery names every day.
  const category = document.getElementById('category');
  const input = document.getElementById('item-name');
  const itemPicker = document.querySelector('[data-item-picker]');
  const savedList = document.getElementById('saved-items');
  if (category && input && itemPicker && savedList) {
    const buttons = [...itemPicker.querySelectorAll('.item-shortcut')];
    const empty = itemPicker.querySelector('.item-shortcuts-empty');
    const refreshSelection = () => {
      buttons.forEach(button => {
        button.classList.toggle('is-selected',
          !button.hidden && button.dataset.name.toLocaleLowerCase() === input.value.trim().toLocaleLowerCase());
      });
    };
    const refresh = () => {
      savedList.replaceChildren();
      let visible = 0;
      buttons.forEach(button => {
        const show = button.dataset.category === category.value;
        button.hidden = !show;
        if (show) {
          visible++;
          const option = document.createElement('option');
          option.value = button.dataset.name;
          savedList.appendChild(option);
        }
      });
      if (empty) empty.hidden = visible !== 0;
      refreshSelection();
    };
    buttons.forEach(button => {
      button.addEventListener('click', () => {
        input.value = button.dataset.name;
        refreshSelection();
        document.getElementById('amount')?.focus();
      });
    });
    category.addEventListener('change', refresh);
    input.addEventListener('input', refreshSelection);
    refresh();
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
  if (entry) entry.addEventListener('submit', (e) => {
    const button = e.submitter;
    if (button && button.tagName === 'BUTTON') {
      // Defer disabling until after form fields (including the clicked button) serialize.
      window.setTimeout(() => { button.disabled = true; button.textContent = 'Saving…'; }, 0);
    }
  });
})();
