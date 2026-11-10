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
  const entry = document.getElementById('entry-form');
  if (entry) entry.addEventListener('submit', (e) => {
    const button = e.submitter;
    if (button && button.tagName === 'BUTTON') {
      // Defer disabling until after form fields (including the clicked button) serialize.
      window.setTimeout(() => { button.disabled = true; button.textContent = 'Saving…'; }, 0);
    }
  });
})();
