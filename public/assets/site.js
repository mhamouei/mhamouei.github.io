/* Progressive enhancement only: every publication exists in the HTML already. */
'use strict';
(() => {
  const form = document.querySelector('[data-publication-filters]');
  if (form) {
    form.hidden = false;
    const rows = [...document.querySelectorAll('[data-publication]')];
    const search = form.querySelector('input[type="search"]');
    const type = form.querySelector('[name="type"]');
    const year = form.querySelector('[name="year"]');
    const pdf = form.querySelector('[name="pdf"]');
    const count = document.getElementById('result-count');
    const empty = document.getElementById('empty-state');
    const normalized = value => value.normalize('NFKD').toLowerCase();
    function filter() {
      const tokens = normalized(search.value.trim()).split(/\s+/).filter(Boolean);
      let visible = 0;
      for (const row of rows) {
        const haystack = normalized(row.dataset.search);
        const show = tokens.every(token => haystack.includes(token)) &&
          (!type.value || row.dataset.type === type.value) &&
          (!year.value || row.dataset.year === year.value) &&
          (!pdf.checked || row.dataset.pdf === 'true');
        row.hidden = !show;
        if (show) visible++;
      }
      count.textContent = `${visible} ${visible === 1 ? 'publication' : 'publications'}`;
      empty.hidden = visible !== 0;
    }
    form.addEventListener('input', filter);
    form.addEventListener('change', filter);
    form.addEventListener('submit', event => event.preventDefault());
    filter();
  }
  let toastTimeout;
  for (const button of document.querySelectorAll('[data-copy]')) {
    button.hidden = false;
    button.addEventListener('click', async () => {
      const block = document.getElementById(button.dataset.copy);
      const toast = document.getElementById('copy-status');
      try {
        if (!navigator.clipboard) throw new Error('Clipboard not available.');
        await navigator.clipboard.writeText(block.textContent);
        toast.textContent = 'BibTeX copied.';
      } catch (_) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(block);
        selection.removeAllRanges();
        selection.addRange(range);
        toast.textContent = 'Citation selected. Press Ctrl+C or Command+C to copy.';
      }
      clearTimeout(toastTimeout);
      toastTimeout = setTimeout(() => { toast.textContent = ''; }, 4500);
    });
  }
})();
