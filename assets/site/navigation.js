/* Specialty navigation. URL state only; no personal learning records. */
(() => {
  'use strict';
  const normalise = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase();
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const validId = value => typeof value === 'string' && /^[a-z][a-z0-9-]{0,79}$/.test(value);

  function siteUrl(value, base) {
    if (typeof value !== 'string' || !value || value.includes('\\')) return null;
    try {
      const boundary = new URL(base);
      const url = new URL(value, boundary);
      return url.origin === boundary.origin && url.protocol === boundary.protocol &&
        !url.username && !url.password && url.pathname.startsWith(boundary.pathname) ? url : null;
    } catch { return null; }
  }

  function matchesRow(row, state) {
    const words = normalise(state.query).trim().split(/\s+/).filter(Boolean);
    return (!state.group || row.group === state.group) &&
      (!state.specialty || (row.specialties || []).includes(state.specialty)) &&
      words.every(word => normalise(row.search).includes(word));
  }

  function pageSlice(items, requested, size) {
    const perPage = Math.max(1, Math.floor(Number(size) || 15));
    const pages = Math.max(1, Math.ceil(items.length / perPage));
    const requestedNumber = Number(requested);
    const page = Math.max(1, Math.min(pages, Number.isFinite(requestedNumber) ? Math.floor(requestedNumber) || 1 : 1));
    const offset = (page - 1) * perPage;
    return {items: items.slice(offset, offset + perPage), page, pages, total: items.length,
      start: items.length ? offset + 1 : 0, end: Math.min(offset + perPage, items.length)};
  }

  function readState(url, tabs, groups, specialties) {
    const params = url.searchParams;
    const requested = Number(params.get('page') || 1);
    return {
      tab: tabs.includes(params.get('tab')) ? params.get('tab') : (tabs[0] || ''),
      query: (params.get('q') || '').slice(0, 256),
      group: groups.includes(params.get('group')) ? params.get('group') : '',
      specialty: specialties.includes(params.get('specialty')) ? params.get('specialty') : '',
      page: Number.isFinite(requested) && requested > 0 ? Math.min(1000000, Math.floor(requested)) : 1
    };
  }

  function stateUrl(url, state, defaultTab = '') {
    const result = new URL(url.href);
    for (const [key, value] of Object.entries({tab: state.tab === defaultTab ? '' : state.tab,
      q: state.query, group: state.group, specialty: state.specialty, page: state.page > 1 ? String(state.page) : ''})) {
      if (value) result.searchParams.set(key, value); else result.searchParams.delete(key);
    }
    return result;
  }

  function specialtyContext(id, registry, base, membership) {
    if (!validId(id) || !own(registry, id) || (membership && !membership.includes(id))) return null;
    const entry = registry[id];
    const url = siteUrl(entry.url, base);
    return url ? {id, title: String(entry.title || id), url: url.href} : null;
  }

  function scopedUrl(value, id, registry, base) {
    const context = specialtyContext(id, registry, base);
    const url = siteUrl(value, base);
    if (!context || !url) return null;
    url.searchParams.set('specialty', id);
    return url.href;
  }

  function preferredContext(url, registry, base, membership) {
    if (/^d\d{2}$/.test(url.searchParams.get('atlas') || '')) return null;
    const context = specialtyContext(url.searchParams.get('specialty'), registry, base, membership);
    if (!context) return null;
    const destination = new URL(context.url);
    const tab = url.searchParams.get('from_tab');
    if (['diseases', 'reasoning', 'projects', 'resources'].includes(tab)) destination.searchParams.set('tab', tab);
    const query = (url.searchParams.get('from_q') || '').slice(0, 256);
    const group = (url.searchParams.get('from_group') || '').slice(0, 120);
    if (query) destination.searchParams.set('q', query);
    if (group) destination.searchParams.set('group', group);
    const page = Number(url.searchParams.get('from_page'));
    if (Number.isFinite(page) && page > 1) destination.searchParams.set('page', String(Math.min(1000000, Math.floor(page))));
    context.url = destination.href;
    return context;
  }

  function applyAtlasReturn(links, value, base) {
    const url = siteUrl(value, base);
    if (!url || url.pathname !== new URL('03_outputs/web/dermatology-atlas/index.html', base).pathname) return false;
    links.forEach(link => {
      if (link.hasAttribute('data-mobile-return')) {
        link.href = url.href; link.textContent = '← 返回圖譜'; link.hidden = false;
      } else link.hidden = true;
    });
    return true;
  }

  const api = {normalise, siteUrl, matchesRow, pageSlice, readState, stateUrl, specialtyContext, scopedUrl, preferredContext, applyAtlasReturn};
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const home = new URL(document.body.dataset.home || 'index.html', location.href);
  const base = new URL('.', home).href;
  let registry = {};
  try { registry = JSON.parse($('#specialty-registry')?.textContent || '{}'); } catch { /* ordinary links remain usable */ }
  const currentUrl = () => new URL(location.href);
  const quietMotion = matchMedia('(prefers-reduced-motion: reduce)');
  document.documentElement.classList.add('navigation-ready');

  function keepUrl(url, push = false) {
    if (url.href !== location.href) history[push ? 'pushState' : 'replaceState']({}, '', url.href);
  }

  $$('[data-specialty-browser]').forEach(browser => {
    const cards = $$('[data-specialty-card]', browser);
    const previous = $('[data-specialty-prev]', browser);
    const next = $('[data-specialty-next]', browser);
    const status = $('[data-specialty-status]', browser);
    const grid = $('[data-specialty-grid]', browser);
    if (!cards.length || !previous || !next || !status || !grid) return;
    let page = Number(currentUrl().searchParams.get('specialty_page')) || 1;
    const size = () => matchMedia('(max-width: 600px)').matches ? 4 : matchMedia('(max-width: 1000px)').matches ? 6 : 8;
    function render(push = false) {
      const slice = pageSlice(cards, page, size()); page = slice.page;
      const visible = new Set(slice.items);
      cards.forEach(card => { card.hidden = !visible.has(card); });
      previous.disabled = page === 1; next.disabled = page === slice.pages;
      browser.classList.toggle('single-specialty-page', slice.pages === 1);
      status.textContent = `${slice.start}–${slice.end} / ${slice.total} 科別 · ${page} / ${slice.pages} 頁`;
      const url = currentUrl();
      if (page > 1) url.searchParams.set('specialty_page', String(page)); else url.searchParams.delete('specialty_page');
      keepUrl(url, push);
    }
    function turn(delta) { page += delta; render(true); }
    previous.addEventListener('click', () => turn(-1)); next.addEventListener('click', () => turn(1));
    grid.addEventListener('keydown', event => {
      if (event.altKey || event.ctrlKey || event.metaKey || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      if ((direction < 0 && previous.disabled) || (direction > 0 && next.disabled)) return;
      event.preventDefault(); turn(direction); $('[data-specialty-card]:not([hidden])', grid)?.focus();
    });
    let touch = null;
    grid.addEventListener('touchstart', event => { const p = event.changedTouches[0]; touch = [p.clientX, p.clientY]; }, {passive: true});
    grid.addEventListener('touchend', event => {
      if (!touch) return;
      const p = event.changedTouches[0]; const dx = p.clientX - touch[0]; const dy = p.clientY - touch[1]; touch = null;
      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
      if (dx < 0 && !next.disabled) turn(1); else if (dx > 0 && !previous.disabled) turn(-1);
    }, {passive: true});
    window.addEventListener('resize', () => render());
    window.addEventListener('popstate', () => { page = Number(currentUrl().searchParams.get('specialty_page')) || 1; render(); });
    render();
  });

  $$('[data-directory]').forEach(directory => {
    const tabs = $$('[data-directory-tab]', directory);
    const panels = $$('[data-directory-panel]', directory);
    const query = $('[data-directory-search]', directory);
    const group = $('[data-directory-group]', directory);
    const specialty = $('[data-directory-specialty]', directory);
    const status = $('[data-directory-status]', directory);
    const previous = $('[data-directory-prev]', directory);
    const next = $('[data-directory-next]', directory);
    const empty = $('[data-directory-empty]', directory);
    const counts = new Map();
    const tabIds = panels.map(panel => panel.dataset.directoryPanel);
    const groupIds = group ? [...group.options].map(option => option.value).filter(Boolean) : [];
    const specialtyIds = specialty ? [...specialty.options].map(option => option.value).filter(Boolean) : [];
    let state = readState(currentUrl(), tabIds, groupIds, specialtyIds);
    const entries = panels.flatMap(panel => $$('[data-directory-row]', panel).map(element => ({element, tab: panel.dataset.directoryPanel,
      search: element.dataset.search || element.textContent, group: element.dataset.group || '',
      specialties: (element.dataset.specialties || '').split(',').filter(Boolean)})));
    const originalLinks = new WeakMap();
    entries.forEach(entry => $$('a[data-learning-link]', entry.element).forEach(link => originalLinks.set(link, link.href)));
    panels.forEach(panel => counts.set(panel.dataset.directoryPanel, $$('[data-directory-row]', panel).length));
    const scopeId = directory.dataset.specialtyId || '';
    function linkContext(entry) {
      const effectiveSpecialty = scopeId || (entry.specialties.includes(state.specialty) ? state.specialty : '');
      $$('a[data-learning-link]', entry.element).forEach(link => {
        link.href = originalLinks.get(link);
        if (!effectiveSpecialty) return;
        const urlValue = scopedUrl(originalLinks.get(link), effectiveSpecialty, registry, base);
        if (!urlValue) return;
        const url = new URL(urlValue);
        if (scopeId) {
          url.searchParams.set('from_tab', state.tab);
          if (state.query) url.searchParams.set('from_q', state.query); else url.searchParams.delete('from_q');
          if (state.group) url.searchParams.set('from_group', state.group); else url.searchParams.delete('from_group');
          if (state.page > 1) url.searchParams.set('from_page', String(state.page)); else url.searchParams.delete('from_page');
        }
        link.href = url.href;
      });
    }
    function render(push = false) {
      const activeGroups = new Set(entries.filter(entry => entry.tab === state.tab).map(entry => entry.group).filter(Boolean));
      if (!activeGroups.has(state.group)) state.group = '';
      if (group) {
        [...group.options].forEach(option => { option.hidden = !!option.value && !activeGroups.has(option.value); });
        group.parentElement.hidden = activeGroups.size === 0;
      }
      query.value = state.query; if (group) group.value = state.group; if (specialty) specialty.value = state.specialty;
      panels.forEach(panel => { panel.hidden = panel.dataset.directoryPanel !== state.tab; });
      if (tabs.length) panels.forEach(panel => { panel.setAttribute('role', 'tabpanel'); panel.tabIndex = 0; });
      tabs.forEach(tab => {
        const active = tab.dataset.directoryTab === state.tab;
        tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
      });
      const matches = entries.filter(entry => entry.tab === state.tab && matchesRow(entry, state));
      const slice = pageSlice(matches, state.page, 15); state.page = slice.page;
      const visible = new Set(slice.items);
      entries.forEach(entry => { entry.element.hidden = !visible.has(entry); if (visible.has(entry)) linkContext(entry); });
      previous.disabled = state.page === 1; next.disabled = state.page === slice.pages;
      const label = tabs.find(tab => tab.dataset.directoryTab === state.tab)?.dataset.label || directory.dataset.scopeLabel || '';
      const total = counts.get(state.tab) || 0;
      status.textContent = `${label ? label + ' · ' : ''}${slice.total ? `${slice.start}–${slice.end}` : '0'} / ${slice.total} 項${slice.total !== total ? `（本類共 ${total} 項）` : ''} · ${slice.page} / ${slice.pages} 頁`;
      empty.hidden = slice.total !== 0;
      empty.textContent = total ? '沒有符合目前搜尋或篩選條件的內容。可清除篩選後重新查找。' : (empty.dataset.emptyText || '目前尚無此類內容，將隨資料逐步加入。');
      keepUrl(stateUrl(currentUrl(), state, tabIds[0] || ''), push);
    }
    function tabChange(id, push = true) { state.tab = id; state.page = 1; render(push); }
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', event => { event.preventDefault(); tabChange(tab.dataset.directoryTab); });
      tab.addEventListener('keydown', event => {
        let nextIndex = index;
        if (event.key === ' ') { event.preventDefault(); tabChange(tab.dataset.directoryTab); return; }
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
        else if (event.key === 'ArrowLeft') nextIndex = (index + tabs.length - 1) % tabs.length;
        else if (event.key === 'Home') nextIndex = 0;
        else if (event.key === 'End') nextIndex = tabs.length - 1;
        else return;
        event.preventDefault(); tabChange(tabs[nextIndex].dataset.directoryTab); tabs[nextIndex].focus();
      });
    });
    if (tabs.length) tabs[0].parentElement.setAttribute('role', 'tablist');
    const queryChange = () => { state.query = query.value.slice(0, 256); state.page = 1; render(); };
    query.addEventListener('input', event => { if (!event.isComposing) queryChange(); });
    query.addEventListener('compositionend', queryChange);
    group?.addEventListener('change', () => { state.group = group.value; state.page = 1; render(true); });
    specialty?.addEventListener('change', () => { state.specialty = specialty.value; state.page = 1; render(true); });
    $('[data-directory-clear]', directory)?.addEventListener('click', () => { state.query = ''; state.group = ''; state.specialty = ''; state.page = 1; render(true); query.focus(); });
    previous.addEventListener('click', () => { state.page -= 1; render(true); status.focus({preventScroll: true}); status.scrollIntoView({block:'nearest',behavior:quietMotion.matches?'auto':'smooth'}); });
    next.addEventListener('click', () => { state.page += 1; render(true); status.focus({preventScroll: true}); status.scrollIntoView({block:'nearest',behavior:quietMotion.matches?'auto':'smooth'}); });
    window.addEventListener('popstate', () => { state = readState(currentUrl(), tabIds, groupIds, specialtyIds); render(); });
    render();
  });

  const membership = (document.body.dataset.specialties || '').split(',').filter(Boolean);
  const context = preferredContext(currentUrl(), registry, base, membership);
  const atlasReturn = $('[data-context-return]:not([hidden])');
  if (/^d\d{2}$/.test(currentUrl().searchParams.get('atlas') || '') && atlasReturn && applyAtlasReturn($$('[data-specialty-return]'), atlasReturn.href, base)) {
    // The phone keeps its visible upper-left return; duplicate specialty links hide.
  } else if (context) {
    $$('[data-specialty-return], [data-specialty-breadcrumb]').forEach(link => {
      link.href = context.url;
      link.textContent = link.hasAttribute('data-specialty-return') ? `← 返回${context.title}` : context.title;
      link.hidden = false;
    });
    const scope = specialtyContext(context.id, registry, base);
    $$('[data-specialty-label]').forEach(label => { label.textContent = context.title; });
    $$('[data-specialty-directory]').forEach(link => { link.href = scope.url; link.textContent = `${context.title}目錄 ↗`; });
    $$('[data-specialty-reasoning]').forEach(link => { const url = new URL(scope.url); url.searchParams.set('tab', 'reasoning'); link.href = url.href; });
    $$('[data-reading-link]').forEach(link => {
      const allowed = (link.dataset.specialties || '').split(',').filter(Boolean);
      if (!allowed.includes(context.id)) return;
      const value = scopedUrl(link.href, context.id, registry, base);
      if (!value) return;
      const url = new URL(value);
      const returnUrl = new URL(context.url);
      for (const [key, target] of Object.entries({tab:'from_tab',q:'from_q',group:'from_group',page:'from_page'})) {
        if (returnUrl.searchParams.has(key)) url.searchParams.set(target, returnUrl.searchParams.get(key));
        else url.searchParams.delete(target);
      }
      link.href = url.href;
    });
  }
})();
