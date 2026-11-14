"""Build small specialty-first views from public canonical-page metadata.

Clinical document storage and web-topic folders are not classification systems.
Only explicit specialty landings establish a registry; every displayed row keeps
the canonical URL and original review/source metadata.
"""
from pathlib import Path, PurePosixPath
import hashlib
import re
from urllib.parse import urlsplit

import common


ROUTES = dict(specialties='03_outputs/web/library/specialties.html',
              cross='03_outputs/web/clinical-reasoning/index.html',
              resources='03_outputs/web/library/resources.html',
              outputs='03_outputs/web/library/outputs.html')
SECTIONS = (('diseases', '疾病與主題'), ('reasoning', '臨床思路與比較'),
            ('projects', '圖譜與專題'), ('resources', '文獻資源'))
SOURCE_LABELS = dict(guideline='指引', guideline_supplement='指引補充',
                     systematic_review='系統性回顧', compiled_html='教學彙編',
                     research_article='研究論文', textbook='教科書', webpage='網頁',
                     lecture='教學投影片', notes='學習筆記')
PROCESSING_LABELS = dict(registered='已登錄', partial='部分處理',
                         complete='已完整處理', blocked='處理受阻')


def _public_url(value, output=False):
    """Reject external/root-relative/traversal paths before they enter controls."""
    if not isinstance(value, str):
        raise ValueError('Navigation URL must be a public project-relative path')
    parsed = urlsplit(value)
    parts = PurePosixPath(parsed.path).parts
    allowed = ('web', 'slides') if output else ('web',)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or
            '\\' in value or '%' in value or parsed.path.startswith('/') or
            len(parts) < (3 if output else 4) or parts[:1] != ('03_outputs',) or parts[1] not in allowed or
            any(part in {'.', '..'} or part.startswith('.') for part in parts) or
            PurePosixPath(value).suffix.lower() not in ({'.html', '.pdf', '.pptx'} if output else {'.html'})):
        raise ValueError('Navigation URL escapes the public output boundary: '+str(value))
    return value


def _specialty_ids(page):
    values = page.get('specialties', [])
    if not isinstance(values, list) or any(not isinstance(v, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', v) for v in values):
        raise ValueError('specialties must be a list of English identifiers: '+str(page.get('id')))
    if len(values) != len(set(values)):
        raise ValueError('Duplicate specialty reference: '+str(page.get('id')))
    return values


def _sort_key(page):
    return (page.get('order', 100), str(page.get('title_en') or page.get('title', '')).casefold(), page['id'])


def _section_ids(page):
    result = []
    if page.get('type') == 'concept' and page.get('content_kind') != 'chapter':
        result.append('diseases')
    if page.get('type') in {'approach', 'comparison', 'question'}:
        result.append('reasoning')
    if page.get('catalog_role') == 'work' or (page.get('type') == 'map' and page.get('content_kind') != 'specialty' and page.get('view') not in {'concept-library', 'reasoning'}):
        result.append('projects')
    if page.get('type') == 'source_summary':
        result.append('resources')
    return result


def _source_rows(root, pages):
    records = common.load_sources(root)
    by_id = {s['source_id']: s for s in records.values()}
    result = []
    for page in pages:
        row = dict(page)
        source = next((by_id[key] for key in page.get('source_ids', []) if key in by_id), {})
        row.update(source_label=SOURCE_LABELS.get(source.get('source_type'), page.get('source_label', '來源整理')),
                   year_label=source.get('year', page.get('year_label', '')),
                   version_label=source.get('version', ''),
                   processing_label=PROCESSING_LABELS.get(source.get('processing_status'), ''),
                   processed_ranges=source.get('processed_ranges', []),
                   unprocessed_ranges=source.get('unprocessed_ranges', []))
        result.append(row)
    return result


def _work_key(url):
    path = PurePosixPath(url)
    # Conventional output folders give a conservative same-work format key.
    # A standalone lecture.html and lecture.pdf share a stem; index.html uses
    # its project folder's name. Unrelated manual HTMLs remain visible.
    parts = path.parts[2:]
    project = '/'.join(parts[:-1]) or path.stem
    name = PurePosixPath(project).name if path.stem == 'index' else path.stem
    return (project, name)


def _outputs(nav, catalog):
    available = None if catalog is None else {entry['path'] for entry in catalog}
    generated = {page['url'] for page in nav}
    works, keys = [], {}
    for page in nav:
        if page.get('catalog_role') != 'work':
            continue
        formats = [] if available is not None and page['url'] not in available else [dict(url=page['url'], kind='html')]
        item = dict(id=page['id'], title=page['title'], summary=page.get('summary', ''),
                    specialties=list(page.get('specialties', [])), formats=formats)
        key = _work_key(page['url'])
        if key in keys:
            raise ValueError('Duplicate complete-work route group: '+str(key))
        keys[key] = item
        works.append(item)
    if catalog is None:
        return works
    manual = []
    for entry in catalog:
        url = _public_url(entry['path'], output=True)
        if url in generated or url in ROUTES.values() or url.startswith('03_outputs/web/layout-previews/'):
            continue
        manual.append(entry)
    # HTML supplies the human title when a manually-created work also has
    # PDF/PPTX exports; no dates, specialties or medical summaries are inferred.
    for entry in sorted(manual, key=lambda e: (e['kind'] != 'html', e['path'])):
        url = entry['path']
        key = _work_key(url)
        if key not in keys:
            identity = hashlib.sha256('/'.join(key).encode('utf-8')).hexdigest()[:12]
            item = dict(id='manual-'+identity, title=entry['title'], summary='', specialties=[], formats=[])
            keys[key] = item
            works.append(item)
        item = keys[key]
        if not any(fmt['url'] == url for fmt in item['formats']):
            item['formats'].append(dict(url=url, kind=entry['kind']))
    return [work for work in works if work['formats']]


def build_navigation(root, nav, catalog=None):
    """Return the public navigation contract without duplicating clinical prose."""
    root = Path(root)
    nav = sorted(nav, key=_sort_key)
    registry = {}
    seen = set()
    for page in nav:
        if page['id'] in seen:
            raise ValueError('Duplicate canonical navigation ID: '+page['id'])
        seen.add(page['id'])
        _public_url(page['url'])
        specialties = _specialty_ids(page)
        if 'cross_specialty' in page and not isinstance(page['cross_specialty'], bool):
            raise ValueError('cross_specialty must be a boolean: '+page['id'])
        if page.get('content_kind') == 'specialty' or page.get('view') == 'specialty':
            if len(specialties) != 1:
                raise ValueError('A specialty landing declares exactly one specialty: '+page['id'])
            identity = specialties[0]
            if identity in registry:
                raise ValueError('Duplicate specialty landing: '+identity)
            registry[identity] = dict(id=identity, title=page.get('specialty_label') or page['title'],
                                      title_en=page.get('title_en', ''), url=page['url'],
                                      summary=page.get('summary', ''), count=0,
                                      sections=[dict(id=key, label=label, pages=[]) for key, label in SECTIONS])
    resources = _source_rows(root, [p for p in nav if p.get('type') == 'source_summary'])
    resource_by_id = {p['id']: p for p in resources}
    for page in nav:
        if page.get('parent_id'):
            parent_id = page['parent_id']
            if not isinstance(parent_id, str) or parent_id not in seen or parent_id == page['id']:
                raise ValueError('Chapter parent must reference another published page: '+page['id'])
            chain = {page['id']}
            parent = next(p for p in nav if p['id'] == parent_id)
            while parent.get('parent_id'):
                if parent['id'] in chain:
                    raise ValueError('Cyclic chapter parents: '+page['id'])
                chain.add(parent['id'])
                parent = next((p for p in nav if p['id'] == parent['parent_id']), {})
                if not parent:
                    raise ValueError('Chapter parent must reference a published page: '+page['id'])
        for specialty in _specialty_ids(page):
            if specialty not in registry:
                raise ValueError('Unknown specialty without a landing: '+specialty+' ('+page['id']+')')
            row = resource_by_id.get(page['id'], page)
            for section in registry[specialty]['sections']:
                if section['id'] in _section_ids(page):
                    section['pages'].append(row)
    specialties = list(registry.values())
    for specialty in specialties:
        specialty['count'] = len({p['id'] for section in specialty['sections'] for p in section['pages']})
    return dict(routes=dict(ROUTES), specialties=specialties, by_specialty=registry,
                home_specialties=specialties[:8], specialty_pages=[specialties[i:i+8] for i in range(0, len(specialties), 8)],
                concepts=[p for p in nav if p.get('type') == 'concept' and p.get('content_kind') != 'chapter'],
                shared=[p for p in nav if p.get('cross_specialty') is True],
                resources=resources, outputs=_outputs(nav, catalog))


def directory_for_page(page, browse):
    """Describe existing directory URLs; ordinary clinical pages return None."""
    view = page.get('view')
    common_fields = dict(title=page['title'], summary=page.get('summary', ''))
    if view == 'specialty':
        specialty = browse['by_specialty'][page['specialties'][0]]
        return dict(common_fields, kind='specialty', specialty=specialty, sections=specialty['sections'])
    if view == 'reasoning':
        return dict(common_fields, kind='cross', pages=browse['shared'])
    if view == 'concept-library':
        return dict(common_fields, kind='concepts', pages=browse['concepts'])
    return None


def specialty_link(specialty):
    """Slim breadcrumb/return data: never introduce model-reference cycles."""
    return {key: specialty[key] for key in ('id', 'title', 'title_en', 'url')}


def topic_navigation(nav, page):
    """Show authored chapters, not every disease sharing a storage/web folder."""
    parent_id = page.get('parent_id') or page['id']
    explicit = [p for p in nav if p['id'] == parent_id or p.get('parent_id') == parent_id]
    if any(p.get('parent_id') == parent_id for p in explicit):
        return sorted(explicit, key=_sort_key)
    group = [p for p in nav if p['web_topic'] == page['web_topic'] and not p.get('view')]
    cores = [p for p in group if p.get('type') == 'concept' and p.get('content_kind') != 'chapter']
    if len(cores) == 1 and any(p.get('content_kind') == 'chapter' for p in group):
        return sorted(group, key=_sort_key)
    return [page]
