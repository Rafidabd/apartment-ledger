/* Lightweight, keyboard-friendly autocomplete for English and Bengali grocery names.
 * Item names come only from the locally stored catalog, with no external requests.
 */
(() => {
  const normal = value => String(value || '').normalize('NFC').trim().toLocaleLowerCase();
  let nextId = 0;
  const basketScript = document.getElementById('basket-catalog');
  let basketCatalog = [];
  try { basketCatalog = JSON.parse(basketScript?.textContent || '[]'); }
  catch (_e) { basketCatalog = []; }

  const shortcutsCatalog = () => [...document.querySelectorAll('.item-shortcut')].map(el => ({
    name: el.dataset.name, category_id: el.dataset.category
  }));
  const itemsFor = input => input.closest('[data-basket-row]') ? basketCatalog : shortcutsCatalog();

  function attach(input) {
    if (!input || input.dataset.suggestReady) return;
    input.dataset.suggestReady = '1';
    input.setAttribute('autocomplete', 'off');
    const parent = input.closest('.field');
    const category = input.closest('[data-basket-row]')?.querySelector('.basket-category') ||
                     document.getElementById('category');
    if (!parent || !category) return;
    parent.classList.add('has-item-suggestions');

    const menu = document.createElement('div');
    menu.className = 'item-suggestion-menu';
    menu.id = 'item-suggest-' + (++nextId);
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', 'Matching saved items');
    menu.hidden = true;
    parent.appendChild(menu);
    input.setAttribute('aria-controls', menu.id);
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-autocomplete', 'list');

    let matches = [];
    let selected = -1;
    let composing = false;

    function close() {
      menu.hidden = true;
      menu.replaceChildren();
      matches = [];
      selected = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function choose(index) {
      const item = matches[index];
      if (!item) return;
      input.value = item.name;
      close();
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.dispatchEvent(new Event('change', {bubbles: true}));
      const amount = input.closest('[data-basket-row]')?.querySelector('.basket-amount') ||
                     document.getElementById('amount');
      if (amount) amount.focus();
    }

    function highlight() {
      [...menu.children].forEach((el, i) => {
        el.classList.toggle('active', i === selected);
        el.setAttribute('aria-selected', i === selected ? 'true' : 'false');
      });
      if (selected >= 0) {
        const item = menu.children[selected];
        input.setAttribute('aria-activedescendant', item.id);
        item.scrollIntoView({block:'nearest'});
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    }

    function show() {
      if (composing) return;
      const q = normal(input.value);
      const categoryId = String(category.value);
      const available = itemsFor(input).filter(item => String(item.category_id) === categoryId);
      const seen = new Set();
      matches = available
        .filter(item => {
          const key = normal(item.name);
          if (seen.has(key)) return false;
          seen.add(key);
          return q ? key.includes(q) : true;
        })
        .sort((a, b) => {
          if (!q) return 0;  // Preserve the server's most-used ordering.
          const aStarts = normal(a.name).startsWith(q) ? 0 : 1;
          const bStarts = normal(b.name).startsWith(q) ? 0 : 1;
          return aStarts - bStarts;
        })
        .slice(0, 7);
      selected = -1;
      menu.replaceChildren();
      if (!matches.length) {
        close();
        return;
      }
      matches.forEach((item, i) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'item-suggestion-option';
        option.id = menu.id + '-' + i;
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');
        option.textContent = item.name;
        option.addEventListener('mousedown', e => e.preventDefault());
        option.addEventListener('click', () => choose(i));
        menu.appendChild(option);
      });
      // Anchor the floating results immediately under the typed field, not below its help text.
      menu.style.left = input.offsetLeft + 'px';
      menu.style.top = (input.offsetTop + input.offsetHeight + 4) + 'px';
      menu.style.width = input.offsetWidth + 'px';
      menu.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }

    input.addEventListener('input', show);
    input.addEventListener('focus', show);
    input.addEventListener('compositionstart', () => {composing = true;});
    input.addEventListener('compositionend', () => {composing = false; show();});
    input.addEventListener('keydown', event => {
      if (event.isComposing || composing || menu.hidden) return;
      if (event.key === 'Escape') { close(); event.preventDefault(); }
      else if (event.key === 'ArrowDown') {
        selected = (selected + 1) % matches.length; highlight(); event.preventDefault();
      } else if (event.key === 'ArrowUp') {
        selected = (selected - 1 + matches.length) % matches.length; highlight(); event.preventDefault();
      } else if (event.key === 'Enter' && selected >= 0) {
        choose(selected); event.preventDefault();
      }
    });
    input.addEventListener('blur', () => { window.setTimeout(close, 120); });
    category.addEventListener('change', () => { if (!menu.hidden) show(); });
  }

  window.LedgerItemSuggest = { attach };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-item-autocomplete]').forEach(attach);
  });
})();