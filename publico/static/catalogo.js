// Pedido por loja: o botão de cada card abre uma escolha entre as 5 lojas e monta o link wa.me.
(function () {
  var dlg = document.getElementById('dlg-loja');
  if (!dlg || typeof dlg.showModal !== 'function') return; // sem <dialog>: o href do botão (matriz) segue valendo
  var peca = document.getElementById('dlg-peca');
  var opcoes = Array.prototype.slice.call(dlg.querySelectorAll('.loja-op'));
  var CHAVE = 'carreiro:ultima-loja';

  function lembrada() { try { return localStorage.getItem(CHAVE); } catch (e) { return null; } }
  function lembrar(slug) { try { localStorage.setItem(CHAVE, slug); } catch (e) {} }
  function reais(v) {
    return 'R$ ' + Number(v).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  document.addEventListener('click', function (ev) {
    var botao = ev.target.closest('.js-pedir');
    if (!botao) return;
    ev.preventDefault();
    var codigo = botao.dataset.codigo, desc = botao.dataset.desc, preco = botao.dataset.preco, precos = botao.dataset.precos;
    var texto;
    if (precos) {
      var pares = precos.split('|').map(function (item) {
        var idx = item.lastIndexOf('=');
        var c = idx !== -1 ? item.slice(0, idx) : item;
        var v = idx !== -1 ? item.slice(idx + 1) : '';
        return v !== '' ? c + ' — ' + reais(v) : c;
      });
      texto = 'Olá! Quero consultar a peça: ' + desc + ' (cód. ' + pares.join('; ') + ')';
    } else {
      texto = 'Olá! Quero consultar a peça: ' + desc + ' (cód. ' + codigo + ')';
      if (preco) texto += ' — ' + reais(preco);
    }
    peca.textContent = desc + ' · cód. ' + codigo;
    var ultima = lembrada();
    opcoes.forEach(function (a) {
      a.href = 'https://wa.me/' + a.dataset.wa + '?text=' + encodeURIComponent(texto);
      a.classList.toggle('ultima', a.dataset.slug === ultima);
    });
    dlg.showModal();
  });

  opcoes.forEach(function (a) {
    a.addEventListener('click', function () { lembrar(a.dataset.slug); dlg.close(); });
  });
  dlg.addEventListener('click', function (ev) { if (ev.target === dlg) dlg.close(); }); // clique no fundo fecha
})();
