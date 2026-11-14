"""Deterministic static pages, public-only staging and local generated outputs."""
import argparse
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.build/deps'))
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
import common

PUBLIC_EXT = common.PUBLIC_EXT


def update_generated_ignores(root, paths):
    """Keep reproducible HTML local while leaving manually added outputs trackable."""
    path = Path(root) / '.gitignore'
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    text = re.sub(r'\n?# BEGIN MEDWIKI GENERATED OUTPUTS\n.*?# END MEDWIKI GENERATED OUTPUTS\n?', '', text, flags=re.S)
    owned = sorted({'index.html', 'assets/site/search-index.json', *paths})
    block = '\n# BEGIN MEDWIKI GENERATED OUTPUTS\n' + '\n'.join('/' + p for p in owned) + '\n# END MEDWIKI GENERATED OUTPUTS\n'
    common.atomic_text(path, text.rstrip() + '\n' + block)


def checked_rmtree(path, root):
    if path.is_symlink() or not path.resolve().is_relative_to((root / '.build').resolve()):
        raise ValueError('Refusing unsafe build cleanup')
    if path.exists():
        shutil.rmtree(path)


def build_site(root=common.ROOT):
    root = Path(root).resolve()
    from lint import lint, check_html, check_source_locators
    content_errors = lint(root, check_site=False)
    if content_errors:
        raise ValueError('\n'.join(content_errors))
    docs = common.load_documents(root)
    published = sorted([d for d in docs if d.get('publish')], key=lambda d: d.get('order', 100))
    sources = common.load_sources(root)
    env = Environment(loader=FileSystemLoader(root / '04_templates/site'), autoescape=select_autoescape(['html']))
    env.globals['rel'] = common.relative_url
    env.globals['asset'] = lambda target, current: common.asset_url(root, target, current)
    stage = root / '.build/site-next'
    target = root / '.build/site'
    checked_rmtree(stage, root)
    stage.mkdir(parents=True)
    nav = []
    for d in published:
        d['order'] = d.get('order', 100)
        d['nav_title'] = d.get('nav_title') or d['title']
        name = d.get('web_file', '')
        if not re.fullmatch(r'[a-z0-9-]+\.html', name):
            raise ValueError('web_file must be an English HTML filename')
        topic_slug = d.get('web_topic', 'sjs-ten')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', topic_slug):
            raise ValueError('web_topic must be a lowercase English slug')
        d['web_topic'] = topic_slug
        d['topic_title'] = d.get('topic_title', 'SJS / TEN' if topic_slug == 'sjs-ten' else topic_slug)
        d['specialty_label'] = d.get('specialty_label', '皮膚科' if topic_slug == 'sjs-ten' else '醫學主題')
        d['specialty_en'] = d.get('specialty_en', str(d.get('tags', ['MEDICINE'])[0] if d.get('tags') else 'MEDICINE').upper())
        src = next((s for s in sources.values() if s['source_id'] in d.get('source_ids', [])), {})
        d['author_label'] = src.get('short_title', '')
        d['year_label'] = src.get('year', '')
        d['source_label'] = {'compiled_html':'教學彙編','guideline':'指引','systematic_review':'系統性回顧'}.get(src.get('source_type'), str(src.get('source_type', 'SOURCE SUMMARY')).replace('_', ' ').upper())
        d['url'] = '03_outputs/web/' + topic_slug + '/' + name
        if d['url'] in [n['url'] for n in nav]:
            raise ValueError('Duplicate published route')
        nav.append(d)
    route_map = {d['path']: d['url'] for d in published}
    from library import library_context
    import flows
    flow_errors = flows.validate_flows(root, sources)
    if flow_errors:
        raise ValueError('\n'.join(flow_errors))
    library = library_context(root, nav, sources, '03_outputs/web/dermatology-atlas/index.html')
    env.globals['library'] = library
    import navigation
    browse = navigation.build_navigation(root, nav)
    env.globals['browse'] = browse
    by_id = {d['id']: d for d in published}
    for d in published:
        d['related_pages'] = [by_id[key] for key in d.get('related_ids', []) if key in by_id and key != d['id']]
        d['specialty_options'] = [navigation.specialty_link(browse['by_specialty'][key]) for key in d.get('specialties', [])]
        d['primary_specialty'] = d['specialty_options'][0] if d['specialty_options'] else None
    search = []
    generated = {}
    rendered = {}
    public_sources = {k: {f: v for f, v in s.items() if f in ['title', 'short_title', 'year', 'doi', 'url', 'pdf_pages', 'printed_start', 'printed_prefix', 'locator_type', 'locators', 'public_path']} for k, s in sources.items()}
    for d in published:
        text = common.render_citations(d['body'], sources)
        # Obsidian reads the native SVG fallback; the website adds evidence and text steps.
        text = re.sub(r'<!-- flow:([a-z][a-z0-9-]*) -->\s*!\[[^\]]*\]\([^\n)]+\)', lambda m: flows.render_flow(root, m[1], d['url'], sources), text)
        md = markdown.Markdown(extensions=['tables', 'toc', 'fenced_code', 'attr_list'], extension_configs={'toc': {'slugify': lambda s, sep: re.sub(r'[^\w\-]+', '-', s.lower()).strip('-')}})
        content = md.convert(text)
        content = common.rewrite_media(content, root, d['path'], d['url'])
        def fix_link(m):
            val = m.group(1)
            if '.md' not in val or '://' in val:
                return m.group(0)
            file, _, anchor = val.partition('#')
            dest = (root / d['path']).parent.joinpath(file).resolve()
            if not dest.is_relative_to(root):
                raise ValueError('Wiki link escapes workspace')
            mapped = route_map.get(dest.relative_to(root).as_posix())
            if not mapped:
                raise ValueError(f'Unpublished wiki link: {file}')
            return 'href="' + common.relative_url(mapped, d['url']) + ('#' + anchor if anchor else '') + '"'
        content = re.sub(r'href="([^"]+)"', fix_link, content)
        topic_nav = navigation.topic_navigation(nav, d)
        conflict_id = d.get('conflict_page_id')
        if conflict_id and (conflict_id not in by_id or by_id[conflict_id].get('type') != 'comparison'):
            raise ValueError('Conflict target must be a published comparison page: ' + str(conflict_id))
        d['comparison_url'] = by_id[conflict_id]['url'] if conflict_id and conflict_id != d['id'] else None
        directory = navigation.directory_for_page(d, browse)
        template = 'directory.html' if directory else 'reading.html'
        page = env.get_template(template).render(page=d, directory=directory, content=content, toc=md.toc, nav=topic_nav, sources=sources, citations_json=json.dumps(public_sources, ensure_ascii=False).replace('<', '\\u003c'), current=d['url'])
        generated[d['url']] = page
        rendered[d['id']] = (content, md.toc)
        parser = common.PlainHTML()
        parser.feed(content)
        search.append({'title': d['title'], 'summary': d.get('summary', ''), 'tags': d.get('tags', []), 'aliases': d.get('aliases', []), 'url': d['url'], 'text': ' '.join(parser.text), 'type': d.get('type'), 'review': d.get('review_status')})
    from build_previews import render_previews
    previews = render_previews(root, env, nav, rendered, sources, public_sources)
    if set(previews).intersection(generated):
        raise ValueError('Layout previews conflict with a published route')
    generated.update(previews)
    search_json = json.dumps(search, ensure_ascii=False, sort_keys=True).replace('<', '\\u003c')
    search_script = '<script type="application/json" id="local-search-data">' + search_json + '</script>'
    generated = {url: html.replace('<!-- SEARCH_DATA -->', search_script) for url, html in generated.items()}
    # Copy only whitelisted public assets and user-created outputs; never raw/private.
    for folder in ['assets', '03_outputs/web', '03_outputs/slides']:
        for path in sorted((root / folder).rglob('*')):
            if path.suffix.lower() in PUBLIC_EXT and common.safe_file(path, root):
                rel = path.relative_to(root)
                if any(x.startswith('.') or x in {'node_modules', '_internal'} for x in rel.parts):
                    continue
                out = stage / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, out)
    old_manifest = root / '.build/generated-pages.json'
    old = json.loads(old_manifest.read_text()) if old_manifest.exists() else []
    for stale in set(old) - set(generated):
        if stale.startswith('03_outputs/web/'):
            p = stage / stale
            if p.exists() and 'medwiki-generated' in p.read_text(encoding='utf-8', errors='replace'):
                p.unlink()
    for url, html in generated.items():
        existing = root / url
        if existing.exists() and 'medwiki-generated' not in existing.read_text(encoding='utf-8', errors='replace'):
            raise ValueError(f'Refusing to overwrite manual output: {url}')
        common.atomic_text(stage / url, html)
    catalog = common.discover_outputs(stage, config_root=root)
    browse = navigation.build_navigation(root, nav, catalog)
    env.globals['browse'] = browse
    directory_definitions = {
        'specialties': dict(kind='specialties', title='科別瀏覽', summary='依正在學習的科別查找疾病、臨床思路、圖譜與文獻。', pages=browse['specialties']),
        'resources': dict(kind='resources', title='文獻資源', summary='依科別與來源類型查找論文、指引及教學資料整理。', pages=browse['resources']),
        'outputs': dict(kind='outputs', title='學習成果', summary='以完整專題、圖譜與簡報為單位，閱讀或下載已完成的成果。', works=browse['outputs']),
        'cross': dict(kind='cross', title='主訴與跨科', summary='從跨科問題出發，查找已整理的評估、鑑別與處置思路。', pages=browse['shared']),
    }
    for kind, descriptor in directory_definitions.items():
        url = browse['routes'][kind]
        if url in generated:
            if kind == 'cross' and any(p['url'] == url and p.get('view') == 'reasoning' for p in published):
                continue
            raise ValueError('Published page conflicts with a reserved directory route: '+url)
        existing = root / url
        if existing.exists() and 'medwiki-generated' not in existing.read_text(encoding='utf-8', errors='replace'):
            raise ValueError('Refusing to overwrite manual output: '+url)
        html = env.get_template('directory.html').render(directory=descriptor, current=url, sources=sources).replace('<!-- SEARCH_DATA -->', search_script)
        generated[url] = html
        common.atomic_text(stage / url, html)
    catalog_groups = {}
    topic_names = {n['web_topic']: n['topic_title'] for n in nav}
    for item in catalog:
        slug = Path(item['group']).name
        label = topic_names.get(slug, '版型比較' if slug == 'layout-previews' else slug.replace('-', ' '))
        catalog_groups.setdefault(label, []).append(item)
    homepage = env.get_template('home.html').render(current='index.html', catalog=catalog, catalog_groups=catalog_groups, nav=nav, topic=published[0] if published else None, topic_entries=[n for n in nav if n['web_file'] == 'index.html'], topic_count=len({n['web_topic'] for n in nav}), count=len(published), sources=sources).replace('<!-- SEARCH_DATA -->', search_script)
    common.atomic_text(stage / 'index.html', homepage)
    common.atomic_text(stage / 'assets/site/search-index.json', json.dumps(search, ensure_ascii=False, sort_keys=True))
    common.atomic_text(stage / '.nojekyll', '')
    from lint import check_html
    errors = check_html(stage)
    errors.extend(check_source_locators(stage, sources))
    if errors:
        raise ValueError('\n'.join(errors))
    # Keep prior site until the staged site passes link checks.
    backup = root / '.build/site-old'
    checked_rmtree(backup, root)
    if target.exists():
        target.rename(backup)
    try:
        stage.rename(target)
    except Exception:
        if backup.exists():
            backup.rename(target)
        raise
    checked_rmtree(backup, root)
    for url, html in generated.items():
        common.atomic_text(root / url, html)
    for stale in set(old) - set(generated):
        p = (root / stale).resolve()
        if p.is_relative_to((root / '03_outputs/web').resolve()) and p.exists() and 'medwiki-generated' in p.read_text(encoding='utf-8', errors='replace'):
            p.unlink()
    common.atomic_text(root / 'index.html', homepage)
    common.atomic_text(root / 'assets/site/search-index.json', json.dumps(search, ensure_ascii=False, sort_keys=True))
    common.atomic_text(old_manifest, json.dumps(sorted(generated)))
    from update_indexes import update_markdown
    update_markdown(root)
    update_generated_ignores(root, generated.keys())
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=common.ROOT)
    args = parser.parse_args()
    print('Built:', build_site(args.root))
