(function () {
  var configEl = document.getElementById('caisse-config');
  if (!configEl) return;
  var searchUrl = configEl.dataset.searchUrl;
  var lotsUrlTemplate = configEl.dataset.lotsUrlTemplate; // contains /0/

  var searchInput = document.getElementById('recherche-medicament');
  var resultsBox = document.getElementById('resultats-recherche');
  var cartBody = document.getElementById('panier-body');
  var totalEl = document.getElementById('total-general');
  var lignesInput = document.getElementById('id_lignes_json') || document.querySelector('input[name="lignes_json"]');
  var form = document.getElementById('vente-form');
  var btnValider = document.getElementById('btn-valider');

  var cart = []; // {key, medicament_id, medicament_label, lot_id, lots, quantite, prix}
  var searchTimer = null;

  function asNumber(v) { var n = parseFloat(String(v).replace(',', '.')); return isNaN(n) ? 0 : n; }
  function money(n) { return asNumber(n).toFixed(2); }

  function clearEmptyRow() {
    var empty = document.getElementById('panier-vide');
    if (empty) empty.remove();
  }
  function ensureEmptyRow() {
    if (cart.length === 0) {
      cartBody.innerHTML = '<tr id="panier-vide"><td colspan="6" class="text-muted">Panier vide.</td></tr>';
    }
  }

  function recalc() {
    var total = 0;
    cart.forEach(function (item) {
      var st = asNumber(item.prix) * (parseInt(item.quantite, 10) || 0);
      item._subtotal = st;
      total += st;
    });
    if (totalEl) totalEl.textContent = money(total);
    if (lignesInput) {
      lignesInput.value = JSON.stringify(cart.map(function (i) { return { lot_id: i.lot_id, quantite: parseInt(i.quantite, 10) || 0 }; }));
    }
  }

  function render() {
    if (cart.length === 0) { ensureEmptyRow(); recalc(); return; }
    clearEmptyRow();
    cartBody.innerHTML = '';
    cart.forEach(function (item, idx) {
      var tr = document.createElement('tr');
      var lotOptions = (item.lots || []).map(function (l) {
        var sel = String(l.id) === String(item.lot_id) ? ' selected' : '';
        return '<option value="' + l.id + '" data-dispo="' + l.quantite_disponible + '"' + sel + '>' + l.label + '</option>';
      }).join('');
      if (!item.lots || item.lots.length === 0) {
        lotOptions = '<option value="">Aucun lot valide</option>';
      }
      tr.innerHTML =
        '<td>' + escapeHtml(item.medicament_label) + '<div class="small text-muted">PU: ' + money(item.prix) + '</div></td>' +
        '<td><select class="form-select form-select-sm lot-select" data-idx="' + idx + '">' + lotOptions + '</select></td>' +
        '<td><input type="number" min="1" class="form-control form-control-sm text-end qte-input" data-idx="' + idx + '" value="' + (item.quantite || 1) + '"></td>' +
        '<td class="text-end">' + money(item.prix) + '</td>' +
        '<td class="text-end subtotal">' + money(item._subtotal || 0) + '</td>' +
        '<td class="text-center"><button type="button" class="btn btn-sm btn-outline-danger remove-item" data-idx="' + idx + '"><i class="bi bi-x-lg"></i></button></td>';
      cartBody.appendChild(tr);
    });
    bindCartEvents();
    recalc();
    // update subtotal cells
    Array.prototype.forEach.call(cartBody.querySelectorAll('tr'), function (row, i) {
      var sub = row.querySelector('.subtotal');
      if (sub && cart[i]) sub.textContent = money(cart[i]._subtotal || 0);
    });
  }

  function bindCartEvents() {
    cartBody.querySelectorAll('.lot-select').forEach(function (el) {
      el.addEventListener('change', function () {
        var i = parseInt(el.dataset.idx, 10);
        if (!cart[i]) return;
        cart[i].lot_id = el.value ? parseInt(el.value, 10) : null;
      });
    });
    cartBody.querySelectorAll('.qte-input').forEach(function (el) {
      el.addEventListener('input', function () {
        var i = parseInt(el.dataset.idx, 10);
        if (!cart[i]) return;
        var v = parseInt(el.value, 10);
        cart[i].quantite = v > 0 ? v : 1;
        recalc();
        var row = el.closest('tr');
        if (row) { var sub = row.querySelector('.subtotal'); if (sub) sub.textContent = money(cart[i]._subtotal || 0); }
      });
    });
    cartBody.querySelectorAll('.remove-item').forEach(function (el) {
      el.addEventListener('click', function () {
        var i = parseInt(el.dataset.idx, 10);
        cart.splice(i, 1);
        render();
      });
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]; });
  }

  function lotsUrlFor(medId) {
    return lotsUrlTemplate.replace('/0/', '/' + medId + '/');
  }

  function addMedicament(med) {
    fetch(lotsUrlFor(med.id), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var lots = data.lots || [];
        if (lots.length === 0) {
          alert('Aucun lot valide (FEFO) disponible pour ce médicament.');
          return;
        }
        // lot proposé automatiquement selon FEFO = premier (déjà trié)
        cart.push({
          medicament_id: med.id,
          medicament_label: data.medicament ? data.medicament.label : med.label,
          lot_id: lots[0].id,
          lots: lots,
          quantite: 1,
          prix: asNumber(data.medicament ? data.medicament.prix_vente : med.prix_vente)
        });
        render();
        if (searchInput) { searchInput.value = ''; searchInput.focus(); }
        if (resultsBox) resultsBox.innerHTML = '';
      })
      .catch(function () { alert('Erreur lors du chargement des lots.'); });
  }

  function showResults(results) {
    if (!resultsBox) return;
    resultsBox.innerHTML = '';
    if (!results || results.length === 0) return;
    results.forEach(function (med) {
      var a = document.createElement('a');
      a.href = '#';
      a.className = 'list-group-item list-group-item-action';
      a.textContent = med.label + (med.code_barres ? ' [' + med.code_barres + ']' : '') + ' - ' + money(med.prix_vente);
      a.addEventListener('click', function (e) { e.preventDefault(); addMedicament(med); });
      resultsBox.appendChild(a);
    });
  }

  function doSearch(q) {
    if (!q || q.length < 1) { showResults([]); return; }
    fetch(searchUrl + '?q=' + encodeURIComponent(q), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var results = data.results || [];
        showResults(results);
        // scan code-barres: si un résultat correspond exactement au code-barres, ajout auto
        var exact = results.find(function (m) { return m.code_barres && m.code_barres.toLowerCase() === q.toLowerCase(); });
        if (exact) { addMedicament(exact); }
      })
      .catch(function () { showResults([]); });
  }

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      var q = searchInput.value.trim();
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { doSearch(q); }, 200);
    });
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var q = searchInput.value.trim();
        if (q) doSearch(q);
      }
    });
  }

  if (form) {
    form.addEventListener('submit', function (e) {
      recalc();
      var payload = [];
      cart.forEach(function (i) {
        var qte = parseInt(i.quantite, 10) || 0;
        if (i.lot_id && qte > 0) payload.push({ lot_id: i.lot_id, quantite: qte });
      });
      if (payload.length === 0) {
        e.preventDefault();
        alert('Ajoutez au moins un médicament au panier.');
        return;
      }
      lignesInput.value = JSON.stringify(payload);
      if (btnValider) { btnValider.disabled = true; btnValider.textContent = 'Validation en cours...'; }
    });
  }

  render();
  if (searchInput) searchInput.focus();
})();
