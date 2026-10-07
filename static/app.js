// Keep the category list in sync with income/expense selection.
const form = document.querySelector('#transaction-form');
if (form) {
  const category = form.querySelector('#category');
  function updateCategories() {
    const kind = form.querySelector('input[name="kind"]:checked').value;
    for (const group of category.querySelectorAll('optgroup')) {
      const enabled = group.dataset.kind === kind;
      group.disabled = !enabled;
      group.hidden = !enabled;
      for (const option of group.querySelectorAll('option')) option.disabled = !enabled;
    }
    if (category.selectedOptions[0]?.disabled) {
      category.value = category.querySelector('option:not([disabled])').value;
    }
  }
  form.querySelectorAll('input[name="kind"]').forEach(input => input.addEventListener('change', updateCategories));
  updateCategories();
}
document.querySelectorAll('.delete-form').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm('Delete this transaction? This cannot be undone.')) event.preventDefault();
  });
});
