/* Browser-local interactions only. No remote API, analytics or patient data. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const home = new URL(document.body.dataset.home, location.href);
  const base = new URL('.', home);
  const searchDialog = $('#search-dialog');
  const searchInput = $('#search-input');
  const results = $('#search-results');
  let searchData = JSON.parse($('#local-search-data')?.textContent || 'null');
  let lastFocus;
  const close = dialog => { dialog.close(); lastFocus?.focus(); };
  $$('[data-close-dialog]').forEach(b => b.addEventListener('click', () => close(b.closest('dialog'))));
  $$('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d && (e.offsetX < 0 || e.offsetY < 0 || e.offsetX > d.clientWidth || e.offsetY > d.clientHeight)) close(d); }));
  async function openSearch() {
    lastFocus = document.activeElement;
    searchDialog.showModal(); searchInput.focus();
    if (!searchData) {
      try { const r = await fetch(new URL('assets/site/search-index.json', base)); if (!r.ok) throw new Error('load'); searchData = await r.json(); search(); }
      catch { results.replaceChildren(Object.assign(document.createElement('p'), {textContent: '搜尋資料無法載入。請使用本機預覽伺服器或已發布網站。'})); }
    } else search();
  }
  $$('[data-open-search]').forEach(b => b.addEventListener('click', openSearch));
  document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {e.preventDefault(); if (!searchDialog.open) openSearch();} });
  function search() {
    if (!searchData) return;
    const words = searchInput.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const type = $('#search-type').value;
    results.replaceChildren();
    if (!words.length) { results.textContent = '輸入關鍵字開始搜尋。'; return; }
    const found = searchData.filter(p => !type || p.type === type).map(p => {
      const title = [p.title, ...(p.aliases || []), ...(p.tags || [])].join(' ').toLocaleLowerCase();
      const all = (title + ' ' + p.summary + ' ' + p.text).toLocaleLowerCase();
      return {p, score: words.every(w => all.includes(w)) ? words.reduce((n,w) => n + (title.includes(w) ? 5 : 1), 0) : 0};
    }).filter(x => x.score).sort((a,b) => b.score - a.score);
    if (!found.length) { results.textContent = '沒有找到符合的內容。試試英文、縮寫或較短的關鍵字。'; return; }
    const count = document.createElement('p'); count.className = 'small muted'; count.textContent = `${found.length} 筆結果 · 未經人工審閱的內容保留狀態`; results.append(count);
    found.forEach(({p}) => { const a = document.createElement('a'); a.href = new URL(p.url, base); a.className = 'search-result'; const h = document.createElement('strong'); h.textContent = p.title; const desc = document.createElement('p'); desc.textContent = p.summary; a.append(h, desc); results.append(a); });
  }
  searchInput.addEventListener('input', search);
  $('#search-type').addEventListener('change', search);
  const sourceData = $('#citation-data');
  if (sourceData) {
    const sources = JSON.parse(sourceData.textContent);
    $$('.citation').forEach(b => b.addEventListener('click', () => {
      lastFocus = b;
      const src = sources[b.dataset.source];
      const pages = b.dataset.pages.split(',').map(part => part.split('-').map(Number).map(n => `${src.printed_prefix || ''}${src.printed_start+n-1}`).join('–')).join(', ');
      $('#citation-title').textContent = src.short_title;
      $('#citation-full').textContent = src.title;
      $('#citation-locator').textContent = `期刊頁 ${pages} · PDF 頁 ${b.dataset.pages} · ${src.year}`;
      $('#citation-doi').href = src.url;
      $('#citation-doi').textContent = `doi: ${src.doi} ↗`;
      $('#citation-dialog').showModal();
    }));
  }
  $$('.prose table').forEach(t => { const wrap = document.createElement('div'); wrap.className = 'table-wrap'; wrap.tabIndex = 0; wrap.setAttribute('role','region'); wrap.setAttribute('aria-label','可橫向捲動的比較表格'); t.before(wrap); wrap.append(t); });
  const mobile = $('#mobile-menu');
  mobile?.addEventListener('click', () => {const open = $('#topic-sidebar').classList.toggle('open'); mobile.setAttribute('aria-expanded', String(open));});
  document.addEventListener('click', e => { if (mobile && !e.target.closest('#topic-sidebar') && !e.target.closest('#mobile-menu')) {$('#topic-sidebar').classList.remove('open'); mobile.setAttribute('aria-expanded','false');} });
  document.addEventListener('keydown', e => {if(e.key === 'Escape' && mobile){$('#topic-sidebar').classList.remove('open'); mobile.setAttribute('aria-expanded','false');}});
  $$('.topic-sidebar a').forEach(a => a.addEventListener('click',()=>{ $('#topic-sidebar').classList.remove('open'); mobile?.setAttribute('aria-expanded','false'); }));
  const backTop = $('.back-top');
  backTop?.addEventListener('click', () => { if (document.body.classList.contains('focus-mode')) {document.body.classList.remove('focus-mode');$$('#focus-toggle,#focus-inline').forEach(b=>b.setAttribute('aria-pressed','false')); backTop.textContent = '↑'; backTop.setAttribute('aria-label','返回頁首');} else window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}); });
  $$('#focus-toggle,#focus-inline').forEach(b=>b.addEventListener('click', () => {const active=document.body.classList.toggle('focus-mode');$$('#focus-toggle,#focus-inline').forEach(x=>x.setAttribute('aria-pressed',String(active))); backTop.textContent = active?'離開專注閱讀':'↑'; backTop.setAttribute('aria-label',active?'離開專注閱讀':'返回頁首');}));
  $('#print-page')?.addEventListener('click', () => window.print());
  $$('[data-output-tab]').forEach(b=>b.addEventListener('click',()=>{const pending=b.dataset.outputTab==='pending'; $('#completed-outputs').hidden=pending;$('#pending-outputs').hidden=!pending;$$('[data-output-tab]').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});}));
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries=>{const seen=entries.filter(e=>e.isIntersecting);if(seen.length){$$('.page-toc .toc a').forEach(a=>a.classList.toggle('current',decodeURIComponent(a.hash.slice(1))===seen[0].target.id));}},{rootMargin:'-110px 0px -60% 0px'});
    $$('.prose h2').forEach(h=>observer.observe(h));
  }
  $$('.prose img').forEach(img=>{ img.tabIndex=0; img.setAttribute('role','button');img.setAttribute('aria-label',`放大圖片：${img.alt}`);const show=()=>{lastFocus=img;const d=document.createElement('dialog');d.className='image-dialog';const b=document.createElement('button');b.textContent='關閉 ✕';b.onclick=()=>{d.close();d.remove();img.focus();};const copy=img.cloneNode();copy.removeAttribute('role');copy.removeAttribute('tabindex');const p=document.createElement('p');p.textContent=img.alt;d.append(b,copy,p);document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();};img.addEventListener('click',show);img.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show();}});});
})();
