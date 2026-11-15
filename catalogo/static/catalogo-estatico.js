// Catálogo estático (Netlify): busca, categoria e "mostrar mais" no navegador, a partir de /catalogo/produtos.json.
// Os cards repetem a marcação de _card_produto.html; o pedido por loja continua no catalogo.js.
(function () {
  var POR_PAGINA = 48;
  var grid = document.getElementById('grid');
  var resumo = document.getElementById('resumo');
  var vazio = document.getElementById('vazio');
  var mais = document.getElementById('mais');
  var form = document.getElementById('form-busca');
  var campo = document.getElementById('busca');
  var chips = Array.prototype.slice.call(document.querySelectorAll('#cats .chip'));
  if (!grid || !window.fetch) return;   // sem fetch: ficam as 48 primeiras peças já renderizadas

  var dados = null, filtrados = [], mostrados = 0;
  var estado = lerUrl();
  campo.value = estado.busca;

  function norm(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function lerUrl() {
    var q = new URLSearchParams(location.search);
    return { busca: (q.get('busca') || '').slice(0, 80), categoria: q.get('categoria') || '' };
  }
  function gravarUrl() {
    var q = new URLSearchParams();
    if (estado.busca) q.set('busca', estado.busca);
    if (estado.categoria) q.set('categoria', estado.categoria);
    var s = q.toString();
    history.replaceState(null, '', location.pathname + (s ? '?' + s : ''));
  }
  function el(tag, cls, texto) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto != null) e.textContent = texto;
    return e;
  }
  function preco(p) { return 'R$ ' + Number(p).toFixed(2).replace('.', ','); }
  function milhar(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

  function iconeWhats() {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    [['viewBox', '0 0 24 24'], ['width', '18'], ['height', '18'], ['fill', 'none'], ['stroke', 'currentColor'],
     ['stroke-width', '2'], ['stroke-linecap', 'round'], ['stroke-linejoin', 'round'], ['aria-hidden', 'true']]
      .forEach(function (a) { svg.setAttribute(a[0], a[1]); });
    var path = document.createElementNS(ns, 'path');
    path.setAttribute('d', 'M21 12a9 9 0 0 1-13.5 7.8L3 21l1.3-4.4A9 9 0 1 1 21 12z');
    svg.appendChild(path);
    return svg;
  }

  function card(p) {
    var cat = dados.categorias[p.c] || { nome: '', slug: '' };
    var codigos = p.k.join(' · ');
    var art = el('article', 'card');
    if (p.f) {
      var fig = el('figure', 'card-foto');
      var img = el('img');
      img.src = '/fotos/' + encodeURIComponent(p.f) + '.webp';
      img.alt = p.d; img.loading = 'lazy'; img.decoding = 'async'; img.width = 400; img.height = 400;
      fig.appendChild(img);
      fig.appendChild(el('figcaption', null, 'Imagem ilustrativa'));
      art.appendChild(fig);
    }
    var body = el('div', 'card-body');
    var topo = el('div', 'card-top');
    if (!p.f) {
      var ico = el('span', 'card-ico');
      ico.setAttribute('aria-hidden', 'true');
      var tpl = document.getElementById('ico-' + cat.slug);
      if (tpl) ico.appendChild(tpl.content.cloneNode(true));
      topo.appendChild(ico);
    }
    topo.appendChild(el('span', 'card-cat', cat.nome));
    body.appendChild(topo);
    body.appendChild(el('h3', 'card-nome', p.d));
    var meta = el('dl', 'card-meta');
    [[p.k.length === 1 ? 'Cód.' : 'Códigos', codigos], ['Ref.', p.r], ['EAN', p.e], ['Marca', p.m]].forEach(function (par) {
      if (!par[1]) return;
      var linha = el('div');
      linha.appendChild(el('dt', null, par[0]));
      linha.appendChild(el('dd', null, par[1]));
      meta.appendChild(linha);
    });
    body.appendChild(meta);
    if (p.a) body.appendChild(el('p', 'card-aplic', p.a));
    art.appendChild(body);

    var pe = el('div', 'card-foot');
    var temPreco = typeof p.p === 'number';
    pe.appendChild(el('span', 'card-preco' + (temPreco ? '' : ' consulte'), temPreco ? preco(p.p) : 'Consulte o preço'));
    var texto = 'Olá! Quero consultar a peça: ' + p.d + ' (cód. ' + p.k.join(', ') + ')' + (temPreco ? ' — ' + preco(p.p) : '');
    var botao = el('a', 'btn btn-wa js-pedir');
    botao.href = 'https://wa.me/' + dados.matriz + '?text=' + encodeURIComponent(texto);   // sem JS do diálogo: matriz
    botao.target = '_blank'; botao.rel = 'noopener';
    botao.dataset.codigo = p.k.join(', ');
    botao.dataset.desc = p.d;
    botao.dataset.preco = temPreco ? String(p.p) : '';
    botao.appendChild(iconeWhats());
    botao.appendChild(document.createTextNode(' Pedir no WhatsApp'));
    pe.appendChild(botao);
    art.appendChild(pe);
    return art;
  }

  function casa(p, termos) {
    return termos.every(function (alternativas) {
      return alternativas.some(function (t) { return p._txt.indexOf(t) !== -1; });
    });
  }

  function aplicar(rolarTopo) {
    var termos = norm(estado.busca).split(/[\s\/,]+/).filter(Boolean).map(function (t) {
      return [t].concat(dados.sinonimos[t] || []);
    });
    var catIdx = -1;
    dados.categorias.forEach(function (c, i) { if (c.slug === estado.categoria) catIdx = i; });
    if (catIdx === -1) estado.categoria = '';

    var porCat = {}, daBusca = termos.length ? dados.produtos.filter(function (p) { return casa(p, termos); }) : dados.produtos;
    daBusca.forEach(function (p) { porCat[p.c] = (porCat[p.c] || 0) + 1; });
    filtrados = catIdx === -1 ? daBusca : daBusca.filter(function (p) { return p.c === catIdx; });

    chips.forEach(function (chip) {
      var slugChip = chip.dataset.cat, n;
      if (!slugChip) n = daBusca.length;
      else {
        var i = -1;
        dados.categorias.forEach(function (c, j) { if (c.slug === slugChip) i = j; });
        n = porCat[i] || 0;
      }
      var b = chip.querySelector('b');
      if (b) b.textContent = milhar(n);
      chip.hidden = !!slugChip && n === 0 && slugChip !== estado.categoria;
      chip.classList.toggle('on', slugChip === estado.categoria);
    });

    resumo.textContent = '';
    resumo.appendChild(el('strong', null, milhar(filtrados.length)));
    var txt = ' ' + (filtrados.length === 1 ? 'peça' : 'peças');
    if (estado.busca) txt += ' para “' + estado.busca + '”';
    if (catIdx !== -1) txt += ' em ' + dados.categorias[catIdx].nome;
    resumo.appendChild(document.createTextNode(txt));

    grid.replaceChildren();
    mostrados = 0;
    mostrarMais();
    vazio.hidden = filtrados.length > 0;
    gravarUrl();
    if (rolarTopo) resumo.scrollIntoView({ block: 'nearest' });
  }

  function mostrarMais() {
    var frag = document.createDocumentFragment();
    filtrados.slice(mostrados, mostrados + POR_PAGINA).forEach(function (p) { frag.appendChild(card(p)); });
    grid.appendChild(frag);
    mostrados = Math.min(mostrados + POR_PAGINA, filtrados.length);
    mais.hidden = mostrados >= filtrados.length;
    mais.textContent = 'Mostrar mais peças (' + milhar(filtrados.length - mostrados) + ' restantes)';
  }

  var espera;
  campo.addEventListener('input', function () {
    clearTimeout(espera);
    espera = setTimeout(function () {
      estado.busca = campo.value.trim().slice(0, 80);
      if (dados) aplicar(false);
    }, 180);
  });
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    estado.busca = campo.value.trim().slice(0, 80);
    if (dados) aplicar(true);
    campo.blur();
  });
  chips.forEach(function (chip) {
    chip.addEventListener('click', function (ev) {
      if (!dados) return;   // ainda carregando: o link recarrega a página já filtrada
      ev.preventDefault();
      estado.categoria = chip.dataset.cat;
      aplicar(true);
    });
  });
  document.getElementById('limpar').addEventListener('click', function (ev) {
    if (!dados) return;
    ev.preventDefault();
    estado = { busca: '', categoria: '' };
    campo.value = '';
    aplicar(true);
  });
  mais.addEventListener('click', mostrarMais);

  fetch('/catalogo/produtos.json')
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (json) {
      dados = json;
      dados.produtos.forEach(function (p) {
        var cat = dados.categorias[p.c];
        p._txt = ' ' + norm([p.d, p.k.join(' '), p.r, p.e, p.m, p.a, cat && cat.nome].join(' ')) + ' ';
      });
      if (estado.busca || estado.categoria) aplicar(false);
      else { filtrados = dados.produtos; mostrados = grid.children.length; mais.hidden = mostrados >= filtrados.length;
             mais.textContent = 'Mostrar mais peças (' + milhar(filtrados.length - mostrados) + ' restantes)'; }
    })
    .catch(function () { /* sem a lista: ficam as peças já renderizadas */ });
})();
