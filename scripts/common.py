"""Content, citations and public output discovery; never reads local raw files."""
from html import escape, unescape
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.build/deps'))
from urllib.parse import quote, unquote, urlsplit
import yaml

ROOT = Path(__file__).resolve().parents[1]
CITE = re.compile(r'\[@([^\]\r\n]*)\]')
LOCATOR = re.compile(r'[A-Za-z][A-Za-z0-9_-]*')
SUPPORT = {'assets', 'vendor', '_includes', '_internal', 'node_modules'}
EXTENSIONS = {'.html', '.pdf', '.pptx'}
PUBLIC_EXT = {'.html', '.css', '.js', '.json', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.pdf', '.pptx'}
MEDIA_TAG = re.compile(r'<(?:img|video|audio|source)\b(?:[^>\"\']|\"[^\"]*\"|\'[^\']*\')*>', re.I)
MEDIA_ATTR = re.compile(r'(\s+)([^\s=/>]+)(?:\s*=\s*(?:\"([^\"]*)\"|\'([^\']*)\'|([^\s>]+)))?', re.I)


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
        if not re.fullmatch(r'[A-Z]+', str(data.get('short_id', ''))) or not data.get('source_id'):
            raise ValueError('Source must have a source ID and uppercase short citation ID')
        kind = data.get('locator_type', 'pdf')
        if kind not in {'pdf', 'html'}:
            raise ValueError(f'Unknown source locator type: {kind}')
        if kind == 'html':
            validate_html_source(data)
        if data['short_id'] in sources or any(s['source_id'] == data['source_id'] for s in sources.values()):
            raise ValueError('Duplicate source ID or short citation ID')
        sources[data['short_id']] = data
    return sources


def validate_html_source(src):
    locators = src.get('locators')
    if not isinstance(locators, dict) or not locators:
        raise ValueError('HTML source requires a nonempty locator map')
    for key, label in locators.items():
        if not isinstance(key, str) or not LOCATOR.fullmatch(key) or not isinstance(label, str) or not label.strip():
            raise ValueError(f'Invalid HTML source locator: {key}')
    path = src.get('public_path')
    if path is not None and path != '' and (not isinstance(path, str) or not re.fullmatch(r'03_outputs/web/(?:[a-z0-9]+(?:-[a-z0-9]+)*/)*[a-z0-9]+(?:-[a-z0-9]+)*\.html', path)):
        raise ValueError('HTML source public_path must be a public output HTML route')


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
    if not re.fullmatch(r'[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*', spec):
        raise ValueError(f'Invalid citation page: {spec}')
    parts = []
    for item in spec.split(','):
        ends = list(map(int, item.split('-')))
        if len(ends) > 2 or any(n < 1 or n > src['pdf_pages'] for n in ends) or ends[-1] < ends[0]:
            raise ValueError(f'Invalid citation page: {spec}')
        values = [str(src.get('printed_prefix', '')) + str(src['printed_start'] + n - 1) for n in ends]
        parts.append('–'.join(values))
    return ', '.join(parts)


def render_citations(text, sources):
    if '[@' in CITE.sub('', text):
        raise ValueError('Malformed citation')
    def sub(match):
        key, separator, spec = match.group(1).partition(':')
        if not separator or not re.fullmatch(r'[A-Z]+', key):
            raise ValueError(f'Malformed citation: {match.group(0)}')
        if key not in sources:
            raise ValueError(f'Unknown source: {key}')
        src = sources[key]
        kind = src.get('locator_type', 'pdf')
        if kind == 'html':
            validate_html_source(src)
            if not LOCATOR.fullmatch(spec) or spec not in src['locators']:
                raise ValueError(f'Unknown or invalid HTML locator: {key}:{spec}')
            label = escape(src['locators'][spec])
            short = spec[1:] if re.fullmatch(r'd[0-9]+', spec) else spec
            return f'<button type="button" class="citation" data-source="{key}" data-locator="{escape(spec)}" data-kind="html" aria-label="查看來源 {key}，{label}" title="{label}">{key} · {escape(short)}</button>'
        if kind != 'pdf':
            raise ValueError(f'Unknown source locator type: {kind}')
        label = escape(printed_pages(src, spec))
        return f'<button type="button" class="citation" data-source="{key}" data-pages="{escape(spec)}" aria-label="查看來源 {key}，頁 {label}">{key} · {label}</button>'
    return CITE.sub(sub, text)


def media_url(value, root, source_path, current=None):
    """Validate a wiki-relative public media URL, optionally rebasing for output."""
    url = urlsplit(value)
    if url.netloc and url.scheme in {'', 'http', 'https'}:
        return value
    path = unquote(url.path)
    if url.scheme or not path or path.startswith('/') or '\\' in path:
        raise ValueError(f'Unsafe media URL: {value}')
    root = Path(root).resolve()
    target = (root / source_path).parent.joinpath(path).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f'Media escapes workspace: {value}')
    rel = target.relative_to(root)
    public = rel.parts[0] == 'assets' or rel.parts[:2] in {('03_outputs', 'web'), ('03_outputs', 'slides')}
    if not public or target.suffix.lower() not in PUBLIC_EXT or any(p.startswith('.') or p in {'node_modules', '_internal'} for p in rel.parts):
        raise ValueError(f'Non-public media: {value}')
    if not safe_file(target, root):
        raise ValueError(f'Missing or unsafe media: {value}')
    if current is None:
        return value
    return relative_url(rel.as_posix(), current) + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')


def rewrite_media(content, root, source_path, current=None):
    """Validate rendered Markdown media; preserve external URLs and prose."""
    def attribute(match):
        space, name = match.group(1, 2)
        if name.lower() not in {'src', 'poster', 'srcset'}:
            return match.group(0)
        raw_value = next((v for v in match.groups()[2:] if v is not None), '')
        value = unescape(raw_value)
        if name.lower() == 'srcset':
            candidates = []
            for item in value.split(','):
                parts = item.strip().split()
                if not parts or len(parts) > 2 or len(parts) == 2 and not re.fullmatch(r'(?:[1-9][0-9]*w|[0-9]+(?:\.[0-9]+)?x)', parts[1]):
                    raise ValueError(f'Invalid media srcset: {value}')
                candidates.append(media_url(parts[0], root, source_path, current) + (' ' + parts[1] if len(parts) == 2 else ''))
            value = ', '.join(candidates)
        else:
            value = media_url(value, root, source_path, current)
        return space + name + '="' + escape(value) + '"'
    return MEDIA_TAG.sub(lambda tag: MEDIA_ATTR.sub(attribute, tag.group(0)), content)


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
