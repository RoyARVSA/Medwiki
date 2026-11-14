"""Validate evidence graphs and render prebuilt Pele SVG with a text equivalent.

Definitions are public YAML, never private clinical input. Normal site builds
only verify/consume checked-in artifacts; Node/Pele is needed for --build only.
The graph is an educational navigation aid and contains no executable rules.
"""
from __future__ import annotations

import argparse
from html import escape
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET

import common
import yaml

ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r'^[a-z][a-z0-9-]*$')
CITATION = re.compile(r'^\[@([A-Z][A-Z0-9]*):([^\[\]\s]+)\]$')
SVG_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG_NS)
RENDERER_FILES = ('scripts/flows.py', 'tools/diagrams/render-flows.mjs',
                  'tools/diagrams/package.json', 'tools/diagrams/package-lock.json')
NODE_KINDS = ('step', 'decision', 'terminal', 'unknown')
KIND_LABELS = {'criteria': '診斷準則圖', 'differential': '鑑別思路圖', 'management': '處置流程圖'}
REVIEW_LABELS = {'not_reviewed': '尚未人工審閱', 'reviewed': '已人工審閱'}
BLUE_DEFAULTS = ('--pele-bg:#f8fbff;--pele-fg:#193954;--pele-muted:#536c81;'
                 '--pele-line:#547da1;--pele-surface:#edf4fb;'
                 '--pele-surface-alt:#f6f9fd;--pele-border:#8eabc4;'
                 '--pele-accent:#285f91;')
SVG_TAGS = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line',
            'polyline', 'polygon', 'text', 'tspan', 'title', 'desc',
            'defs', 'marker', 'clipPath'}


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _safe_id(value):
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def _load(root, flow_id):
    if not _safe_id(flow_id):
        raise ValueError('Invalid flow id')
    path = Path(root) / 'config/flows' / (flow_id + '.yml')
    if not common.safe_file(path, Path(root)):
        raise ValueError(f'Flow definition is missing or unsafe: {flow_id}')
    data = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'Flow definition must be a mapping: {flow_id}')
    return data


def _citation_errors(citations, sources, source_ids):
    errors = []
    if not isinstance(citations, list):
        return ['citations must be a list']
    for citation in citations:
        match = CITATION.fullmatch(citation) if isinstance(citation, str) else None
        if not match:
            errors.append(f'Invalid citation: {citation!r}')
            continue
        key = match[1]
        if key not in sources:
            errors.append(f'Unknown source in citation: {key}')
            continue
        if sources[key].get('source_id') not in source_ids:
            errors.append(f'Cited source {key} is not declared in source_ids')
        try:
            rendered = common.render_citations(citation, sources)
            if rendered == citation:
                raise ValueError('unsupported source locator')
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f'Invalid citation {citation}: {exc}')
    return errors


def _inline_citation_errors(text, sources, source_ids):
    try:
        common.render_citations(text, sources)
    except (ValueError, KeyError, TypeError) as exc:
        return [f'Invalid inline citation: {exc}']
    return _citation_errors(re.findall(r'\[@[^\]\r\n]*\]', text), sources, source_ids)


def _definition_errors(data, flow_id, sources):
    errors = []
    if data.get('id') != flow_id or not _safe_id(data.get('id')):
        errors.append('id must match the safe definition filename')
    for key in ('title', 'population', 'version'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f'{key} is required and must be nonempty text')
    if data.get('kind') not in ('criteria', 'differential', 'management'):
        errors.append('kind must be criteria, differential or management')
    if data.get('review_status') not in ('not_reviewed', 'reviewed'):
        errors.append('Invalid review_status')
    if data.get('conflict_status') not in ('none', 'open', 'resolved'):
        errors.append('Invalid conflict_status')
    if data.get('conflict_status') == 'open' and data.get('review_status') != 'not_reviewed':
        errors.append('An open conflict requires review_status: not_reviewed')
    source_ids = data.get('source_ids', [])
    if not isinstance(source_ids, list) or not source_ids or any(not isinstance(s, str) for s in source_ids):
        errors.append('source_ids must be a nonempty list of stable source IDs')
        source_ids = []
    known = {s.get('source_id') for s in sources.values()}
    for source_id in source_ids:
        if source_id not in known:
            errors.append(f'Unknown source_ids entry: {source_id}')
    notes = data.get('notes', [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        errors.append('notes must be a list of text')
    else:
        for note in notes:
            errors.extend(_inline_citation_errors(note, sources, source_ids))
    nodes, edges = data.get('nodes'), data.get('edges')
    if not isinstance(nodes, list) or not nodes or any(not isinstance(n, dict) for n in nodes):
        return errors + ['nodes must be a nonempty list of mappings']
    if not isinstance(edges, list) or any(not isinstance(e, dict) for e in edges):
        return errors + ['edges must be a list of mappings']
    ids = set()
    by_id = {}
    for node in nodes:
        node_id = node.get('id')
        if not _safe_id(node_id):
            errors.append('Invalid node id')
            continue
        if node_id in ids:
            errors.append(f'Duplicate node id: {node_id}')
        ids.add(node_id)
        by_id[node_id] = node
        if node.get('kind') not in NODE_KINDS:
            errors.append(f'{node_id}: invalid node kind')
        for key in ('label', 'detail'):
            if not isinstance(node.get(key), str) or not node[key].strip():
                errors.append(f'{node_id}: {key} is required')
            else:
                errors.extend(_inline_citation_errors(node[key], sources, source_ids))
        citations = node.get('citations', [])
        errors.extend(f'{node_id}: {e}' for e in _citation_errors(citations, sources, source_ids))
        if node.get('kind') == 'decision' and not citations:
            errors.append(f'{node_id}: decision nodes require source evidence')
    entry = data.get('entry')
    if not isinstance(entry, str) or entry not in ids:
        errors.append('entry must refer to an existing node')
    outgoing = {node_id: [] for node_id in ids}
    for edge in edges:
        start, end = edge.get('from'), edge.get('to')
        if not isinstance(start, str) or not isinstance(end, str) or start not in ids or end not in ids:
            errors.append(f'Edge references unknown node: {start!r} -> {end!r}')
            continue
        if not isinstance(edge.get('label', ''), str):
            errors.append(f'{start} -> {end}: edge label must be text')
            continue
        outgoing[start].append(edge)
    for node_id, node in by_id.items():
        routes = outgoing[node_id]
        if not routes and node.get('kind') not in ('terminal', 'unknown'):
            errors.append(f'{node_id}: leaf must explicitly be terminal or unknown')
        if routes and node.get('kind') in ('terminal', 'unknown'):
            errors.append(f'{node_id}: terminal/unknown nodes cannot have outgoing edges')
        if node.get('kind') == 'decision':
            if any(not e.get('label', '').strip() for e in routes):
                errors.append(f'{node_id}: all decision branch labels must be nonempty')
            if not any(by_id[e['to']].get('kind') == 'unknown' for e in routes):
                errors.append(f'{node_id}: decision requires an explicit unknown exit')
    if isinstance(entry, str) and entry in ids:
        reached, pending = set(), [entry]
        while pending:
            node_id = pending.pop()
            if node_id in reached:
                continue
            reached.add(node_id)
            pending.extend(e['to'] for e in outgoing[node_id])
        if ids - reached:
            errors.append('Unreachable nodes from entry: ' + ', '.join(sorted(ids - reached)))
    return errors


def _label(text):
    # Numeric Mermaid entities keep labels inert inside quoted node syntax.
    return ''.join(f'#{ord(c)};' if c in '&<>"\\\n\r' else c for c in text)


def mermaid_source(data):
    """Generate the drawing from exactly the same labels/edges as the prose."""
    lines = ['flowchart TD']
    indexes = {node['id']: f'n{i}' for i, node in enumerate(data['nodes'])}
    for node in data['nodes']:
        label = '"' + _label(node['label']) + '"'
        if node['kind'] == 'decision':
            shape = '{' + label + '}'
        elif node['kind'] in {'terminal', 'unknown'}:
            shape = '([' + label + '])'
        else:
            shape = '[' + label + ']'
        lines.append(f'  {indexes[node["id"]]}{shape}')
    for edge in data['edges']:
        middle = f' -->|"{_label(edge["label"])}"| ' if edge.get('label') else ' --> '
        lines.append('  ' + indexes[edge['from']] + middle + indexes[edge['to']])
    return '\n'.join(lines) + '\n'


def validate_svg(svg):
    """Fail closed on executable/remote content before inline SVG is emitted."""
    if re.search(r'<!|<\?', svg):
        raise ValueError('Unsafe SVG declarations')
    try:
        tree = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError('Invalid SVG XML') from exc
    if tree.tag != f'{{{SVG_NS}}}svg':
        raise ValueError('Expected an SVG root')
    all_ids = set()
    for element in tree.iter():
        if not element.tag.startswith('{' + SVG_NS + '}') or element.tag.rsplit('}', 1)[-1] not in SVG_TAGS:
            raise ValueError('Unsafe SVG element')
        for key, value in element.attrib.items():
            local_key = key.rsplit('}', 1)[-1].lower()
            if (local_key.startswith('on') or local_key in {'href', 'src'} or
                    re.search(r'(?:javascript|vbscript|data|https?|file)\s*:|@import|expression\s*\(', value, re.I)):
                raise ValueError('Unsafe SVG attribute')
            if local_key == 'style' and ('\\' in value or '/*' in value):
                raise ValueError('Unsafe SVG CSS escape/comment')
            for target in re.findall(r'url\s*\((.*?)\)', value, re.I):
                if not re.fullmatch(r'[\s\'\"]*#[A-Za-z][A-Za-z0-9_-]*[\s\'\"]*', target):
                    raise ValueError('Unsafe SVG URL')
            if local_key == 'id':
                if value in all_ids or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', value):
                    raise ValueError('Unsafe or duplicate SVG id')
                all_ids.add(value)
    return tree


def _balance_cjk_lines(group, original):
    """Balance existing CJK line breaks without changing geometry or glyphs.

    Pele may leave one final ideograph on a new line. Reuse its tspan positions
    and measured maximum width; keep ASCII medical terms/thresholds together.
    The canonical Mermaid source retains the exact original label.
    """
    def width(text):
        return sum(2 if unicodedata.east_asian_width(c) in {'W', 'F'} else 1 for c in text)
    if sum(unicodedata.east_asian_width(c) in {'W', 'F'} for c in original) < 8:
        return
    text = next((e for e in group.iter(f'{{{SVG_NS}}}text')
                 if 'pele-label' in e.get('class', '').split()), None)
    spans = list(text) if text is not None else []
    if len(spans) < 2 or any(s.tag != f'{{{SVG_NS}}}tspan' or len(s) for s in spans):
        return
    tokens = re.findall(r'[<>≤≥]=?\s*\d+(?:\.\d+)?%?|[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*%?|.', original, re.S)
    lines = []
    for remaining in range(len(spans), 1, -1):
        target = width(''.join(tokens)) / remaining
        candidates = [i for i in range(1, len(tokens) - remaining + 2)
                      if tokens[i][0] not in '，。！？；：、）)］】%'
                      and tokens[i - 1][-1] not in '（(［【']
        if not candidates:
            return
        cut = min(candidates, key=lambda i: abs(width(''.join(tokens[:i])) - target))
        lines.append(''.join(tokens[:cut]).strip())
        tokens = tokens[cut:]
    lines.append(''.join(tokens).strip())
    # Never overflow the measured shape by widening any line.
    if any(not line for line in lines) or max(map(width, lines)) > max(width(s.text or '') for s in spans):
        return
    for span, line in zip(spans, lines):
        span.text = line


def _resolve_svg_value(value, variables, trail=()):
    """Resolve Pele's inline custom properties, including nested fallbacks."""
    while match := re.search(r'\bvar\(', value):
        start, depth, quote, comma = match.end(), 1, None, None
        for end in range(start, len(value)):
            char = value[end]
            if quote:
                if char == quote:
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if not depth:
                    break
            elif char == ',' and depth == 1 and comma is None:
                comma = end
        else:
            raise ValueError('Malformed SVG variable')
        name = value[start:comma if comma is not None else end].strip()
        if not re.fullmatch(r'--[A-Za-z0-9_-]+', name):
            raise ValueError('Malformed SVG variable name')
        if name in trail:
            raise ValueError(f'Cyclic SVG variable: {name}')
        if name in variables:
            replacement = _resolve_svg_value(variables[name], variables, trail + (name,))
        elif comma is not None:
            replacement = _resolve_svg_value(value[comma + 1:end].strip(), variables, trail)
        else:
            raise ValueError(f'Unresolved SVG variable: {name}')
        value = value[:match.start()] + replacement + value[end + 1:]
    return value


def _materialize_svg_style(tree):
    """Keep standalone SVG readable in renderers without CSS variable support.

    Inline presentation styles become attributes so page selection/focus CSS
    can still override them. Geometry and source text are otherwise untouched.
    """
    presentation = {'color', 'direction', 'fill', 'font-family', 'font-size',
                    'font-style', 'font-weight', 'letter-spacing', 'word-spacing',
                    'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-linecap',
                    'stroke-linejoin', 'text-anchor', 'rx', 'ry'}

    def visit(element, inherited):
        declarations = []
        for declaration in element.get('style', '').split(';'):
            if declaration.strip():
                key, separator, value = declaration.partition(':')
                if not separator:
                    raise ValueError('Malformed SVG style declaration')
                declarations.append((key.strip(), value.strip()))
        variables = dict(inherited)
        variables.update((key, value) for key, value in declarations if key.startswith('--'))
        variables = {key: _resolve_svg_value(value, variables, (key,))
                     for key, value in variables.items()}
        for key in presentation & element.attrib.keys():
            element.set(key, _resolve_svg_value(element.get(key), variables))
        styles = []
        for key, value in declarations:
            value = _resolve_svg_value(value, variables)
            if key == 'font':
                # The pinned renderer emits a simple measured font shorthand.
                font = re.fullmatch(r'(\d+(?:\.\d+)?px)\s+(.+)', value)
                if not font:
                    raise ValueError('Unsupported SVG font shorthand')
                element.set('font-size', font[1])
                element.set('font-family', font[2])
            elif key in presentation:
                element.set(key, value)
            else:
                styles.append(key + ':' + value)
        if styles:
            element.set('style', ';'.join(styles))
        else:
            element.attrib.pop('style', None)
        for child in element:
            visit(child, variables)

    visit(tree, {})


def _decorate_svg(svg, data):
    tree = validate_svg(svg)
    tree.set('style', BLUE_DEFAULTS + tree.get('style', ''))
    prefix = 'flow-' + data['id']
    title_id, desc_id = prefix + '-title', prefix + '-desc'
    tree.set('role', 'img')
    tree.set('aria-labelledby', title_id + ' ' + desc_id)
    title = ET.Element(f'{{{SVG_NS}}}title', {'id': title_id})
    title.text = data['title']
    desc = ET.Element(f'{{{SVG_NS}}}desc', {'id': desc_id})
    desc.text = '文字步驟與每個節點的來源列於圖後。' + '；'.join(n['label'] for n in data['nodes'])
    tree.insert(0, title)
    tree.insert(1, desc)
    expected = {f'n{i}': node for i, node in enumerate(data['nodes'])}
    seen = set()
    for group in tree.iter(f'{{{SVG_NS}}}g'):
        if 'pele-node' not in group.get('class', '').split():
            continue
        internal_id = group.get('data-id')
        if internal_id not in expected:
            raise ValueError('Pele returned an unexpected diagram node')
        node = expected[internal_id]
        _balance_cjk_lines(group, node['label'])
        drawn = ''.join(group.itertext()).strip()
        # Pele wraps labels into tspans, dropping the space at a line break.
        # Compare all non-whitespace glyphs; the full original stays in aria-label.
        if re.sub(r'\s+', '', drawn) != re.sub(r'\s+', '', node['label']):
            raise ValueError(f'SVG/text label mismatch: {node["id"]}')
        group.set('data-flow-node', node['id'])
        group.set('id', prefix + '-node-' + node['id'])
        group.set('tabindex', '0')
        group.set('role', 'button')
        annotation = '資訊不足出口：' if node['kind'] == 'unknown' else ''
        group.set('aria-label', annotation + node['label'] + '：查看節點說明')
        group.set('aria-controls', prefix + '-detail-' + node['id'])
        if node['kind'] == 'unknown':
            group.set('class', group.get('class', '') + ' flow-node-unknown')
            for shape in group:
                if shape.tag.rsplit('}', 1)[-1] in {'rect', 'polygon', 'path', 'ellipse', 'circle'}:
                    shape.set('stroke-dasharray', '6 4')
                    shape.set('fill', 'var(--pele-surface-alt)')
                    shape.set('stroke', 'var(--pele-accent)')
        seen.add(internal_id)
    if seen != set(expected):
        raise ValueError('Pele omitted diagram nodes')
    _materialize_svg_style(tree)
    result = ET.tostring(tree, encoding='unicode', short_empty_elements=True)
    validate_svg(result)
    return result + '\n'


def _renderer_identity(tools_root):
    tools_root = Path(tools_root)
    files = {}
    for name in RENDERER_FILES:
        path = tools_root / name
        if not common.safe_file(path, tools_root):
            raise ValueError(f'Missing renderer identity file: {name}')
        # Git's text normalization must not invalidate a public Linux clone.
        files[name] = _hash(path.read_text(encoding='utf-8').encode('utf-8'))
    package = json.loads((tools_root / 'tools/diagrams/package.json').read_text(encoding='utf-8'))
    lock = json.loads((tools_root / 'tools/diagrams/package-lock.json').read_text(encoding='utf-8'))
    version = package.get('dependencies', {}).get('pele')
    locked = lock.get('packages', {}).get('node_modules/pele', {})
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(version)) or locked.get('version') != version:
        raise ValueError('Pele must be pinned to the exact lockfile version')
    return {'name': 'pele', 'version': version, 'integrity': locked.get('integrity'),
            'files': files, 'sha256': _hash(_canonical(files))}


def _artifact_paths(root, flow_id):
    folder = Path(root) / 'assets/figures/flows'
    return {suffix: folder / (flow_id + '.' + suffix) for suffix in ('svg', 'mmd', 'json')}


def _verified_svg(root, data, tools_root):
    paths = _artifact_paths(root, data['id'])
    if any(not common.safe_file(p, Path(root)) for p in paths.values()):
        raise ValueError('Missing or unsafe flow artifact; run python scripts/flows.py --build')
    try:
        manifest = json.loads(paths['json'].read_text(encoding='utf-8'))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('Invalid flow artifact manifest') from exc
    svg_bytes, source_bytes = paths['svg'].read_bytes(), paths['mmd'].read_bytes()
    if (manifest.get('definition_sha256') != _hash(_canonical(data)) or
            manifest.get('renderer') != _renderer_identity(tools_root) or
            manifest.get('svg_sha256') != _hash(svg_bytes) or
            manifest.get('mermaid_sha256') != _hash(source_bytes) or
            source_bytes != mermaid_source(data).encode('utf-8')):
        raise ValueError('Flow artifacts are stale; run python scripts/flows.py --build')
    svg = svg_bytes.decode('utf-8')
    tree = validate_svg(svg)
    expected = {n['id']: n['label'] for n in data['nodes']}
    drawn = {}
    for group in tree.iter(f'{{{SVG_NS}}}g'):
        if group.get('data-flow-node'):
            node_id = group.get('data-flow-node')
            if node_id in drawn:
                raise ValueError('Duplicate flow node in SVG artifact')
            drawn[node_id] = ''.join(group.itertext()).strip()
    if ({k: re.sub(r'\s+', '', v) for k, v in drawn.items()} !=
            {k: re.sub(r'\s+', '', v) for k, v in expected.items()}):
        raise ValueError('SVG/text nodes differ')
    return svg


def validate_flows(root, sources, *, check_artifacts=True, tools_root=None):
    """Return errors with stable definition names; no raw files are opened."""
    root = Path(root)
    tools_root = Path(tools_root or root)
    errors = []
    for path in sorted((root / 'config/flows').glob('*.yml')):
        try:
            data = _load(root, path.stem)
            found = _definition_errors(data, path.stem, sources)
            if not found and check_artifacts:
                _verified_svg(root, data, tools_root)
            errors.extend(f'{path.name}: {error}' for error in found)
        except (ValueError, OSError, yaml.YAMLError) as exc:
            errors.append(f'{path.name}: {exc}')
    return errors


def build_flows(root, sources, *, tools_root=None):
    """Regenerate checked-in .mmd/.svg/manifests with the local pinned Pele."""
    root = Path(root)
    tools_root = Path(tools_root or root)
    errors = validate_flows(root, sources, check_artifacts=False, tools_root=tools_root)
    if errors:
        raise ValueError('\n'.join(errors))
    renderer = _renderer_identity(tools_root)
    for path in sorted((root / 'config/flows').glob('*.yml')):
        data = _load(root, path.stem)
        source = mermaid_source(data)
        request = {'source': source, 'idPrefix': 'flow-' + data['id']}
        try:
            process = subprocess.run(['node', str(tools_root / 'tools/diagrams/render-flows.mjs')],
                                     input=json.dumps(request, ensure_ascii=False),
                                     text=True, encoding='utf-8', capture_output=True,
                                     check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError('Local Pele renderer failed; install with npm ci --prefix tools/diagrams --ignore-scripts') from exc
        svg = _decorate_svg(process.stdout, data)
        manifest = {'flow_id': data['id'], 'definition_sha256': _hash(_canonical(data)),
                    'renderer': renderer, 'svg_sha256': _hash(svg.encode('utf-8')),
                    'mermaid_sha256': _hash(source.encode('utf-8'))}
        paths = _artifact_paths(root, data['id'])
        common.atomic_text(paths['mmd'], source)
        common.atomic_text(paths['svg'], svg)
        common.atomic_text(paths['json'], json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _text_citations(text, sources):
    return common.render_citations(escape(text), sources)


def _inline_svg(svg, prefix):
    tree = validate_svg(svg)
    id_map = {e.attrib['id']: prefix + '-' + e.attrib['id'] for e in tree.iter() if 'id' in e.attrib}
    for element in tree.iter():
        for key, value in list(element.attrib.items()):
            if key == 'id':
                element.set(key, id_map[value])
            elif key in {'aria-labelledby', 'aria-describedby', 'aria-controls'}:
                element.set(key, ' '.join(id_map.get(word, prefix + '-' + word) for word in value.split()))
            else:
                for old, new in id_map.items():
                    value = value.replace('url(#' + old + ')', 'url(#' + new + ')')
                element.set(key, value)
    return ET.tostring(tree, encoding='unicode', short_empty_elements=True)


def render_flow(root, flow_id, current, sources, *, tools_root=None):
    """Return escaped accessible HTML; graphics and prose share one definition."""
    root = Path(root)
    data = _load(root, flow_id)
    errors = _definition_errors(data, flow_id, sources)
    if errors:
        raise ValueError('\n'.join(errors))
    svg = _verified_svg(root, data, tools_root or root)
    page_prefix = 'p' + _hash(str(current).encode('utf-8'))[:10]
    prefix = page_prefix + '-flow-' + flow_id
    svg = _inline_svg(svg, page_prefix)
    context = [data['population'], data['version'], KIND_LABELS[data['kind']], REVIEW_LABELS[data['review_status']]]
    if data['conflict_status'] == 'open':
        context.append('保留來源差異')
    parts = [f'<figure class="flow-figure" data-flow-id="{flow_id}" aria-labelledby="{prefix}-heading">',
             f'<figcaption id="{prefix}-heading"><strong>{escape(data["title"])}</strong></figcaption>',
             '<p class="flow-context">' + ' · '.join(escape(item) for item in context) + '</p>',
             '<div class="flow-controls" aria-label="流程圖操作">']
    for action, label in [('zoom-in', '放大'), ('zoom-out', '縮小'), ('reset', '重設'),
                          ('fullscreen', '全螢幕'), ('diagram', '流程圖'), ('steps', '文字步驟')]:
        parts.append(f'<button type="button" data-flow-action="{action}">{label}</button>')
    parts.extend(['</div>', '<div class="flow-viewport" tabindex="0" aria-label="可縮放流程圖">',
                  svg, '</div>', '<div class="flow-steps"><h3>文字步驟與節點說明</h3>',
                  '<p>此圖呈現來源支持的學習關係；未知資訊有獨立出口。</p>', '<ol>'])
    labels = {node['id']: node['label'] for node in data['nodes']}
    outgoing = {node_id: [] for node_id in labels}
    for edge in data['edges']:
        outgoing[edge['from']].append(edge)
    for node in data['nodes']:
        node_id = node['id']
        detail_id = prefix + '-detail-' + node_id
        parts.append(f'<li><details class="flow-node-panel" data-flow-node-panel="{node_id}" id="{detail_id}" open>')
        parts.append('<summary>' + escape(node['label']) + '</summary>')
        if node['kind'] == 'unknown':
            parts.append('<p class="flow-node-kind">資訊不足出口</p>')
        parts.append(f'<button type="button" data-flow-select="{node_id}" aria-controls="{detail_id}">定位：{escape(node["label"])}</button>')
        parts.append('<p>' + _text_citations(node['detail'], sources) + '</p>')
        if node.get('citations'):
            parts.append('<p class="flow-evidence">' + ' '.join(common.render_citations(c, sources) for c in node['citations']) + '</p>')
        if outgoing[node_id]:
            parts.append('<ul class="flow-branches">')
            for edge in outgoing[node_id]:
                route = (edge.get('label') + ' → ') if edge.get('label') else '→ '
                parts.append('<li>' + escape(route) + f'<a href="#{prefix}-detail-{edge["to"]}">' + escape(labels[edge['to']]) + '</a></li>')
            parts.append('</ul>')
        parts.append('</details></li>')
    parts.append('</ol></div>')
    if data.get('notes'):
        parts.append('<div class="flow-notes">' + ''.join('<p>' + _text_citations(n, sources) + '</p>' for n in data['notes']) + '</div>')
    parts.append('</figure>')
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='regenerate all diagrams using local pinned Pele')
    args = parser.parse_args()
    sources = common.load_sources(ROOT)
    if args.build:
        build_flows(ROOT, sources)
    errors = validate_flows(ROOT, sources)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Flow definitions and artifacts verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
