(function () {
  function asNumber(value) {
    var n = parseFloat(String(value).replace(',', '.'));
    return isNaN(n) ? 0 : n;
  }

  function updateRowTotal(row) {
    var q = row.querySelector('.quantite-input, input[name$="-quantite"]');
    var p = row.querySelector('.prix-input, input[name$="-prix_unitaire"]');
    var totalEl = row.querySelector('.line-total');
    if (!q || !p || !totalEl) return;
    var total = asNumber(q.value) * asNumber(p.value);
    totalEl.textContent = total.toFixed(2);
  }

  function visibleRows() {
    return Array.prototype.filter.call(document.querySelectorAll('#formset-body tr.ligne-form'), function (row) {
      return row.style.display !== 'none';
    });
  }

  function updateGrandTotal() {
    var sum = 0;
    visibleRows().forEach(function (row) {
      var totalEl = row.querySelector('.line-total');
      if (totalEl) sum += asNumber(totalEl.textContent);
    });
    var grand = document.getElementById('grand-total');
    if (grand) grand.textContent = sum.toFixed(2);
  }

  function recalcAll() {
    document.querySelectorAll('#formset-body tr.ligne-form').forEach(updateRowTotal);
    updateGrandTotal();
  }

  function wireRow(row) {
    row.querySelectorAll('input, select').forEach(function (el) {
      el.addEventListener('input', function () { updateRowTotal(row); updateGrandTotal(); });
      el.addEventListener('change', function () { updateRowTotal(row); updateGrandTotal(); });
    });
    var removeBtn = row.querySelector('.remove-line');
    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        var deleteInput = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
        var idInput = row.querySelector('input[name$="-id"]');
        if (deleteInput && idInput && idInput.value) {
          deleteInput.checked = true;
          row.style.display = 'none';
        } else {
          row.parentNode.removeChild(row);
        }
        // ensure at least one visible row remains
        if (visibleRows().length === 0) {
          addLine();
        }
        updateGrandTotal();
      });
    }
  }

  function addLine() {
    var totalForms = document.getElementById('id_lignes-TOTAL_FORMS');
    var template = document.getElementById('empty-form-template');
    var body = document.getElementById('formset-body');
    if (!totalForms || !template || !body) return;
    var index = parseInt(totalForms.value, 10);
    var html = template.innerHTML.replace(/__prefix__/g, index);
    var temp = document.createElement('tbody');
    temp.innerHTML = html.trim();
    var row = temp.firstElementChild;
    body.appendChild(row);
    totalForms.value = index + 1;
    wireRow(row);
    updateRowTotal(row);
    updateGrandTotal();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var addBtn = document.getElementById('add-line');
    if (addBtn) addBtn.addEventListener('click', addLine);
    document.querySelectorAll('#formset-body tr.ligne-form').forEach(wireRow);
    recalcAll();
  });
})();
