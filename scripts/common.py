"""Content, citations and public output discovery; never reads local raw files."""
from html import escape, unescape
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.build/deps'))
from urllib.parse import quote
import yaml

ROOT = Path(__file__).resolve().parents[1]
CITE = re.compile(r'\[@([A-Z]+):([0-9,\-]+)\]')
SUPPORT = {'assets', 'vendor', '_includes', '_internal', 'node_modules'}
EXTENSIONS = {'.html', '.pdf', '.pptx'}


def read_document(path):
    text = path.read_text(encoding='utf-8-sig')
    if text.startswith('---\n'):
        _, front, body = text.split('---', 2)
        return yaml.safe_load(front) or {}, body.lstrip()
    return {}, text


def load_documents(root):
    docs = []
    for folder in ['01_wiki', '02_sources/summaries']:
        for path in sorted((root / folder).rglob('*.md')):
            if not safe_file(path, root):
                continue
            data, body = read_document(path)
            docs.append(dict(data, body=body, path=path.relative_to(root).as_posix()))
    return docs


def load_sources(root):
    sources = {}
    for path in sorted((root / '02_sources/records').glob('*.md')):
        data, _ = read_document(path)
        if data['short_id'] in sources or any(s['source_id'] == data['source_id'] for s in sources.values()):
            raise ValueError('Duplicate source ID or short citation ID')
        sources[data['short_id']] = data
    return sources


def safe_file(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return path.is_file() and not any(p.is_symlink() for p in [path, *path.parents] if p != root.parent)
    except ValueError:
        return False


def relative_url(target, current):
    return quote(os.path.relpath(target, str(Path(current).parent)).replace('\\', '/'), safe='/#')


def asset_url(root, target, current):
    key = hashlib.sha256((root / target).read_bytes()).hexdigest()[:12]
    return relative_url(target, current) + '?v=' + key


def printed_pages(src, spec):
    parts = []
    for item in spec.split(','):
        ends = list(map(int, item.split('-')))
        if len(ends) > 2 or any(n < 1 or n > src['pdf_pages'] for n in ends) or ends[-1] < ends[0]:
            raise ValueError(f'Invalid citation page: {spec}')
        values = [str(src.get('printed_prefix', '')) + str(src['printed_start'] + n - 1) for n in ends]
        parts.append('–'.join(values))
    return ', '.join(parts)


def render_citations(text, sources):
    def sub(match):
        key, spec = match.groups()
        if key not in sources:
            raise ValueError(f'Unknown source: {key}')
        label = printed_pages(sources[key], spec)
        return f'<button type="button" class="citation" data-source="{key}" data-pages="{escape(spec)}" aria-label="查看來源 {key}，頁 {label}">{key} · {label}</button>'
    return CITE.sub(sub, text)


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.in_title = False
        self.text = []
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if a.get('id'):
            self.ids.add(a['id'])
        for k in ['href', 'src']:
            if a.get(k):
                self.links.append(a[k])

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_title:
            self.title += data


def discover_outputs(root, config_root=None):
    items = []
    config_path = (config_root or root) / 'config/site.yml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    formats = {'.' + x for x in (config or {}).get('formats', ['html', 'pdf', 'pptx'])}
    folders = (config or {}).get('public_output_roots', ['03_outputs/web', '03_outputs/slides'])
    for folder in folders:
        if folder not in {'03_outputs/web', '03_outputs/slides'}:
            raise ValueError('Output catalog roots must remain inside the public output boundary')
        for path in sorted((root / folder).rglob('*')):
            rel = path.relative_to(root)
            if path.suffix.lower() not in EXTENSIONS.intersection(formats) or any(p in SUPPORT or p.startswith('.') for p in rel.parts) or not safe_file(path, root):
                continue
            title = path.stem.replace('-', ' ')
            if path.suffix.lower() == '.html':
                parser = PlainHTML()
                parser.feed(path.read_text(encoding='utf-8', errors='replace'))
                title = parser.title.strip().split(' | ')[0] or title
            items.append({'title': unescape(title), 'path': rel.as_posix(), 'kind': path.suffix[1:].lower(), 'group': path.parent.relative_to(root).as_posix()})
    return items


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='utf-8', newline='\n')
    tmp.replace(path)
