/* Stateless learning controls. Source text and graph relationships stay in HTML. */
(() => {
  'use strict';
  document.documentElement.classList.add('learning-ready');
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const home = new URL(document.body.dataset.home || 'index.html', location.href);
  const base = new URL('.', home);
  const atlasRoute = '03_outputs/web/dermatology-atlas/index.html';
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const text = value => Array.isArray(value) ? value.map(text).join('；') : String(value ?? '');
  const normalise = value => text(value).normalize('NFKC').toLocaleLowerCase();
  const safeId = value => typeof value === 'string' && /^[a-z][a-z0-9-]{0,79}$/.test(value);
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function safeHttpUrl(value) {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch { return null; }
  }

  function siteUrl(value) {
    if (typeof value !== 'string' || !value || value.includes('\\')) return null;
    try {
      const url = new URL(value, base);
      return url.protocol === base.protocol && url.origin === base.origin &&
        url.pathname.startsWith(base.pathname) && !url.username && !url.password ? url : null;
    } catch { return null; }
  }

  function contextUrl(params) {
    const id = params.get('atlas');
    if (!safeId(id)) return null;
    const url = new URL(atlasRoute, base);
    const group = (params.get('group') || '').slice(0, 100);
    const query = (params.get('q') || '').slice(0, 256);
    if (group && group !== 'all') url.searchParams.set('category', group);
    if (query) url.searchParams.set('q', query);
    url.hash = 'entry-' + id;
    return url;
  }

  function atlasState(url, categories) {
    const category = url.searchParams.get('category') || 'all';
    const view = url.searchParams.get('view') || 'grid';
    return {
      category: categories.includes(category) ? category : 'all',
      query: (url.searchParams.get('q') || '').slice(0, 256),
      view: ['grid', 'list', 'practice'].includes(view) ? view : 'grid'
    };
  }

  function matchesAtlas(entry, state) {
    const words = normalise(state.query).trim().split(/\s+/).filter(Boolean);
    return (state.category === 'all' || entry.category === state.category) &&
      words.every(word => normalise(entry.search).includes(word));
  }

  function creditContent(container, credit) {
    if (!container) return;
    container.replaceChildren();
    const attribution = text(credit?.attribution);
    if (attribution) container.append(document.createTextNode(attribution));
    const link = (label, value) => {
      const href = safeHttpUrl(value);
      if (container.childNodes.length) container.append(document.createTextNode(' · '));
      if (href) {
        const anchor = document.createElement('a');
        anchor.href = href;
        anchor.target = '_blank';
        anchor.rel = 'noopener noreferrer';
        anchor.textContent = label;
        container.append(anchor);
      } else if (label) container.append(document.createTextNode(label));
    };
    if (credit?.source_url) link('圖像來源', credit.source_url);
    if (credit?.licence) link(text(credit.licence), credit.licence_url);
    if (!container.childNodes.length) container.textContent = '圖像署名與使用條件未提供。';
  }

  function imageUrl(value) {
    if (typeof value !== 'string' || !value) return null;
    try { return siteUrl(new URL(value, location.href).href)?.href || safeHttpUrl(value); }
    catch { return null; }
  }

  function showImage(image, entry) {
    if (!image?.src || typeof HTMLDialogElement === 'undefined') return;
    const dialog = document.createElement('dialog');
    dialog.className = 'image-dialog learning-image-dialog';
    dialog.setAttribute('aria-label', '檢視圖片與來源');
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '關閉 ✕';
    const copy = document.createElement('img');
    copy.src = image.src;
    copy.alt = image.alt;
    copy.style.objectFit = 'contain';
    copy.style.width = 'auto';
    copy.style.height = 'auto';
    const caption = document.createElement('p');
    caption.textContent = image.alt;
    const credit = document.createElement('p');
    creditContent(credit, entry?.credit);
    dialog.append(close, copy, caption, credit);
    document.body.append(dialog);
    const remove = () => { dialog.remove(); image.focus({preventScroll: true}); };
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', remove, {once: true});
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    });
    try { dialog.showModal(); close.focus(); }
    catch { dialog.remove(); }
  }

  function enhanceImage(image, entryForImage) {
    if (!image || image.dataset.learningImage) return;
    image.dataset.learningImage = 'true';
    image.tabIndex = 0;
    image.setAttribute('role', 'button');
    image.setAttribute('aria-label', '放大圖片：' + image.alt);
    image.addEventListener('click', () => showImage(image, entryForImage()));
    image.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        showImage(image, entryForImage());
      }
    });
  }

  function enhanceAtlas(root) {
    const search = $('#atlas-search', root);
    const categorySelect = $('#atlas-category', root);
    const grid = $('#atlas-grid', root);
    const practice = $('#atlas-practice', root);
    const entries = $$('[data-atlas-entry]', grid || root).map(element => ({
      element, id: element.dataset.entryId, category: element.dataset.category || '', search: element.dataset.search || ''
    }));
    const categories = ['all', ...new Set(entries.map(entry => entry.category))];
    const buttons = $$('[data-atlas-filter]', root);
    let state = atlasState(new URL(location.href), categories);
    let practiceData = [];
    try {
      const data = JSON.parse($('#atlas-practice-data')?.textContent || '[]');
      if (Array.isArray(data)) practiceData = data.filter(entry => entry && safeId(entry.id));
    } catch { /* Source cards remain readable when optional practice data is absent. */ }
    const byId = new Map(practiceData.map(entry => [entry.id, entry]));
    const originalLinks = new Map();
    entries.forEach(entry => {
      const links = [...(entry.element.matches('a[href]') ? [entry.element] : []), ...$$('a[href]', entry.element)];
      links.forEach(anchor => {
        const url = siteUrl(anchor.href);
        if (url && url.pathname.endsWith('.html') && url.pathname.includes('/03_outputs/web/')) originalLinks.set(anchor, {url, id: entry.id});
      });
      $$('img', entry.element).forEach(image => enhanceImage(image, () => byId.get(entry.id)));
    });
    let available = [];
    let practiceIndex = 0;
    let activeEntry;
    const hook = name => $('[data-practice-' + name + ']', practice || root);
    const pictureHook = hook('image');
    const picture = pictureHook?.tagName === 'IMG' ? pictureHook : pictureHook ? $('img', pictureHook) : null;
    enhanceImage(picture, () => activeEntry);

    function renderPractice() {
      activeEntry = available[practiceIndex];
      const answer = hook('answer');
      if (answer) answer.hidden = true;
      const reveal = hook('reveal');
      if (reveal) { reveal.disabled = !activeEntry; reveal.setAttribute('aria-expanded', 'false'); }
      const position = hook('position');
      if (position) { position.textContent = activeEntry ? `${practiceIndex + 1} / ${available.length}` : '目前條件下沒有練習項目。'; position.setAttribute('aria-live', 'polite'); }
      ['title', 'focus', 'verification'].forEach(name => {
        const element = hook(name);
        if (element) element.textContent = activeEntry ? text(name === 'title' ? [activeEntry.title, activeEntry.title_en].filter(Boolean).join(' · ') : activeEntry[name]) : '';
      });
      if (picture) {
        const src = activeEntry && imageUrl(activeEntry.image);
        picture.hidden = !src;
        if (src) picture.src = src; else picture.removeAttribute('src');
        picture.alt = text(activeEntry?.image_alt);
        picture.setAttribute('aria-label', '放大圖片：' + picture.alt);
      }
      const credit = hook('credit');
      if (credit) { credit.hidden = !activeEntry?.image; creditContent(credit, activeEntry?.credit); }
      const link = hook('link');
      const destination = activeEntry && siteUrl(activeEntry.url);
      if (link) {
        link.hidden = !destination;
        if (destination) {
          addContext(destination, activeEntry.id);
          link.href = destination.href;
        } else link.removeAttribute('href');
      }
      if (hook('prev')) hook('prev').disabled = !activeEntry || practiceIndex === 0;
      if (hook('next')) hook('next').disabled = !activeEntry || practiceIndex === available.length - 1;
    }

    function addContext(url, id) {
      if (!safeId(id)) return;
      url.searchParams.set('atlas', id);
      if (state.category !== 'all') url.searchParams.set('group', state.category); else url.searchParams.delete('group');
      if (state.query.trim()) url.searchParams.set('q', state.query.trim()); else url.searchParams.delete('q');
      if (!url.hash) url.hash = 'atlas-' + id;
    }

    function update(writeUrl = true) {
      const activeId = activeEntry?.id;
      const visible = entries.filter(entry => {
        const match = matchesAtlas(entry, state);
        entry.element.hidden = !match;
        return match;
      });
      available = visible.map(entry => byId.get(entry.id)).filter(Boolean);
      practiceIndex = Math.max(0, available.findIndex(entry => entry.id === activeId));
      if (search) search.value = state.query;
      if (categorySelect) categorySelect.value = state.category;
      buttons.forEach(button => { const active = button.dataset.atlasFilter === state.category; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', String(active)); });
      const count = $('#atlas-count', root);
      if (count) { count.textContent = `${visible.length} / ${entries.length}`; count.setAttribute('aria-live', 'polite'); }
      const empty = $('#atlas-empty', root);
      if (empty) empty.hidden = visible.length > 0;
      root.dataset.view = state.view;
      if (grid) grid.hidden = state.view === 'practice';
      if (practice) practice.hidden = state.view !== 'practice';
      $$('[data-atlas-view]', root).forEach(button => { const active = button.dataset.atlasView === state.view; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', String(active)); });
      originalLinks.forEach(({url, id}, anchor) => { const destination = new URL(url); addContext(destination, id); anchor.href = destination.href; });
      renderPractice();
      if (writeUrl) {
        const url = new URL(location.href);
        [['q', state.query.trim()], ['category', state.category === 'all' ? '' : state.category], ['view', state.view === 'grid' ? '' : state.view]].forEach(([key, value]) => {
          if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
        });
        try { history.replaceState(null, '', url); } catch { /* Offline file reading can disallow URL replacement. */ }
      }
    }

    search?.addEventListener('input', () => { state.query = search.value.slice(0, 256); update(); });
    categorySelect?.addEventListener('change', () => { state.category = categories.includes(categorySelect.value) ? categorySelect.value : 'all'; update(); });
    buttons.forEach(button => button.addEventListener('click', () => { state.category = categories.includes(button.dataset.atlasFilter) ? button.dataset.atlasFilter : 'all'; update(); }));
    $$('[data-atlas-view]', root).forEach(button => button.addEventListener('click', () => { if (['grid', 'list', 'practice'].includes(button.dataset.atlasView)) { state.view = button.dataset.atlasView; update(); } }));
    hook('reveal')?.addEventListener('click', () => { if (activeEntry && hook('answer')) { hook('answer').hidden = false; hook('reveal').setAttribute('aria-expanded', 'true'); } });
    [['prev', -1], ['next', 1]].forEach(([name, direction]) => hook(name)?.addEventListener('click', () => { practiceIndex = clamp(practiceIndex + direction, 0, Math.max(0, available.length - 1)); renderPractice(); }));
    window.addEventListener('popstate', () => { state = atlasState(new URL(location.href), categories); update(false); });
    update(false);
  }

  function enhanceFlow(figure) {
    const viewport = $('.flow-viewport', figure);
    const svg = $('svg', viewport || figure);
    if (!viewport || !svg || figure.classList.contains('flow-enhanced')) return;
    const nodes = $$('g[data-flow-node]', svg);
    const panels = $$('details[data-flow-node-panel]', figure);
    const controls = $$('[data-flow-action]', figure);
    const box = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    const width = box[2] || parseFloat(svg.getAttribute('width')) || 800;
    const height = box[3] || parseFloat(svg.getAttribute('height')) || 600;
    let scale = 1;
    let textMode = matchMedia('(max-width: 760px)').matches;
    let selected = nodes[0]?.dataset.flowNode;
    let drag;
    let suppressClick = false;
    const status = document.createElement('p');
    status.className = 'flow-status';
    status.setAttribute('aria-live', 'polite');
    $('.flow-controls', figure)?.after(status);
    figure.classList.add('flow-enhanced');
    viewport.setAttribute('aria-label', '流程圖：方向鍵捲動，加減鍵縮放，0 重設；節點按 Enter 查看說明。');
    panels.forEach(panel => { panel.open = true; });

    function zoom(next, centre = true) {
      const previous = scale;
      const x = (viewport.scrollLeft + viewport.clientWidth / 2) / previous;
      const y = (viewport.scrollTop + viewport.clientHeight / 2) / previous;
      scale = clamp(next, 0.5, 4);
      svg.style.width = width * scale + 'px';
      svg.style.height = height * scale + 'px';
      svg.style.maxWidth = 'none';
      if (centre) { viewport.scrollLeft = x * scale - viewport.clientWidth / 2; viewport.scrollTop = y * scale - viewport.clientHeight / 2; }
    }

    function panTo(node) {
      if (!node || textMode) return;
      const nodeRect = node.getBoundingClientRect();
      const rect = viewport.getBoundingClientRect();
      viewport.scrollTo({
        left: viewport.scrollLeft + nodeRect.left - rect.left - (viewport.clientWidth - nodeRect.width) / 2,
        top: viewport.scrollTop + nodeRect.top - rect.top - (viewport.clientHeight - nodeRect.height) / 2,
        behavior: motion.matches ? 'auto' : 'smooth'
      });
    }

    function mode(value) {
      textMode = value;
      figure.classList.toggle('flow-text-mode', value);
      controls.forEach(button => {
        if (['diagram', 'steps'].includes(button.dataset.flowAction)) button.setAttribute('aria-pressed', String(button.dataset.flowAction === (value ? 'steps' : 'diagram')));
      });
    }

    function select(id, locate = false) {
      const node = nodes.find(item => item.dataset.flowNode === id);
      if (!node) return;
      selected = id;
      nodes.forEach(item => { const active = item === node; item.classList.toggle('is-selected', active); item.setAttribute('aria-pressed', String(active)); });
      panels.forEach(panel => { const active = panel.dataset.flowNodePanel === id; panel.closest('li')?.classList.toggle('is-selected', active); if (active) panel.open = true; });
      $$('[data-flow-select]', figure).forEach(button => button.setAttribute('aria-pressed', String(button.dataset.flowSelect === id)));
      if (locate) { mode(false); panTo(node); }
    }

    function reset() {
      zoom(Math.max(1, Math.min(1.25, (viewport.clientWidth || figure.clientWidth || width) / width)), false);
      viewport.scrollLeft = 0;
      viewport.scrollTop = 0;
    }

    async function fullscreen() {
      try {
        if (document.fullscreenElement === figure) await document.exitFullscreen();
        else if (figure.requestFullscreen) { mode(false); await figure.requestFullscreen(); }
        else throw new Error('unsupported');
        status.textContent = '';
      } catch {
        status.textContent = '無法開啟全螢幕；仍可使用圖內縮放、捲動及 SVG 下載。';
        viewport.focus({preventScroll: true});
      }
    }

    nodes.forEach(node => {
      node.setAttribute('tabindex', '0');
      node.setAttribute('role', 'button');
      node.setAttribute('aria-label', '查看節點：' + node.textContent.trim());
      node.addEventListener('click', () => select(node.dataset.flowNode));
      node.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); select(node.dataset.flowNode, true); } });
    });
    $$('[data-flow-select]', figure).forEach(button => button.addEventListener('click', () => select(button.dataset.flowSelect, true)));
    $$('.flow-branches a[href^="#"]', figure).forEach(anchor => anchor.addEventListener('click', event => {
      if (event.button > 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const panel = panels.find(item => '#' + item.id === anchor.getAttribute('href'));
      if (!panel) return;
      const nativeNavigation = textMode;
      if (!nativeNavigation) event.preventDefault();
      select(panel.dataset.flowNodePanel, !nativeNavigation);
      const focusDestination = () => {
        if (selected === panel.dataset.flowNodePanel) $('summary', panel)?.focus({preventScroll: true});
      };
      if (nativeNavigation) requestAnimationFrame(focusDestination);
      else focusDestination();
    }));
    controls.forEach(button => button.addEventListener('click', () => {
      const action = button.dataset.flowAction;
      if (action === 'zoom-in' || action === 'zoom-out') { mode(false); zoom(scale * (action === 'zoom-in' ? 1.2 : 1 / 1.2)); }
      else if (action === 'reset') reset();
      else if (action === 'fullscreen') fullscreen();
      else if (action === 'diagram') { mode(false); panTo(nodes.find(node => node.dataset.flowNode === selected)); }
      else if (action === 'steps') mode(true);
    }));
    document.addEventListener('fullscreenchange', () => controls.filter(button => button.dataset.flowAction === 'fullscreen').forEach(button => button.setAttribute('aria-pressed', String(document.fullscreenElement === figure))));
    controls.filter(button => button.dataset.flowAction === 'fullscreen').forEach(button => button.setAttribute('aria-pressed', 'false'));
    viewport.addEventListener('keydown', event => {
      const moves = {ArrowLeft: [-80, 0], ArrowRight: [80, 0], ArrowUp: [0, -80], ArrowDown: [0, 80]};
      if (moves[event.key]) { event.preventDefault(); viewport.scrollLeft += moves[event.key][0]; viewport.scrollTop += moves[event.key][1]; }
      else if (['+', '=', '-', '0', 'Home'].includes(event.key)) { event.preventDefault(); if (event.key === '0' || event.key === 'Home') reset(); else zoom(scale * (event.key === '-' ? 1 / 1.2 : 1.2)); }
    });
    viewport.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'mouse' || event.button !== 0) return;
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop, moved: false};
      suppressClick = false;
    });
    viewport.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (!drag.moved && Math.abs(dx) + Math.abs(dy) > 4) {
        drag.moved = true;
        try { viewport.setPointerCapture(event.pointerId); } catch { /* Native scrolling remains available. */ }
      }
      if (!drag.moved) return;
      event.preventDefault();
      viewport.classList.add('is-panning');
      viewport.scrollLeft = drag.left - dx;
      viewport.scrollTop = drag.top - dy;
    });
    const stopDrag = event => {
      if (!drag || drag.id !== event.pointerId) return;
      suppressClick = drag.moved;
      drag = null;
      viewport.classList.remove('is-panning');
      try { viewport.releasePointerCapture(event.pointerId); } catch { /* Capture may already have ended. */ }
    };
    viewport.addEventListener('pointerup', stopDrag);
    viewport.addEventListener('pointercancel', stopDrag);
    viewport.addEventListener('click', event => { if (suppressClick) { event.preventDefault(); event.stopPropagation(); suppressClick = false; } }, true);
    if (safeId(figure.dataset.flowId)) {
      const download = document.createElement('a');
      download.className = 'flow-download';
      download.href = new URL('assets/figures/flows/' + figure.dataset.flowId + '.svg', base).href;
      download.download = figure.dataset.flowId + '.svg';
      download.textContent = '下載 SVG';
      $('.flow-controls', figure)?.append(download);
    }
    mode(textMode);
    reset();
    select(selected, !textMode);
  }

  const returnUrl = contextUrl(new URL(location.href).searchParams);
  $$('[data-context-return]').forEach(anchor => { anchor.hidden = !returnUrl; if (returnUrl) anchor.href = returnUrl.href; });
  $$('[data-atlas]').forEach(enhanceAtlas);
  $$('.flow-figure[data-flow-id]').forEach(enhanceFlow);
  const reveals = $$('[data-reveal]');
  if (motion.matches || !('IntersectionObserver' in window)) reveals.forEach(element => element.classList.add('is-visible'));
  else {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), {rootMargin: '0px 0px 40px 0px', threshold: 0.06});
    reveals.forEach(element => observer.observe(element));
    motion.addEventListener?.('change', event => { if (event.matches) { observer.disconnect(); reveals.forEach(element => element.classList.add('is-visible')); } });
  }
})();
