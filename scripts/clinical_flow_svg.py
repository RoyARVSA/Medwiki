"""Measured clinical cards and native standalone SVG, with build-time ELK routes.

Font metrics are deliberately conservative and deterministic: full-width CJK,
Latin glyph advance classes, and extra width for fallback symbols. No platform
font, browser, remote asset, or extra Python package is required to rebuild.
"""
from __future__ import annotations

from html import escape, unescape
import json
import math
from pathlib import Path
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET

import common

NS = 'http://www.w3.org/2000/svg'
FONT = 'Arial, "Noto Sans CJK TC", "Microsoft JhengHei", sans-serif'
ROLES = {'assessment': '評估', 'criteria': '準則核對', 'decision': '判斷',
         'action': '處置', 'safety': '安全注意', 'followup': '追蹤／重評',
         'uncertainty': '資訊不足', 'outcome': '結果'}
# Restrained colors retain explicit textual role labels; color never carries logic.
PALETTES = {'safety': ('#fff7f6', '#b34848', '#922f36'),
            'uncertainty': ('#fffbf0', '#b28a38', '#825f18'),
            'criteria': ('#edf4fb', '#91aec8', '#255d88'),
            'outcome': ('#f1f8f8', '#82aaa9', '#28696b'),
            'followup': ('#f1f8f8', '#82aaa9', '#28696b')}
DEFAULT_PALETTE = ('#ffffff', '#91aec8', '#255d88')
LEGEND = '實線：流程／選項 · 虛線：返回重評 · 虛線框：資訊不足'


def visible_text(text, sources):
    """Use exactly the same short citation labels as the HTML text equivalent."""
    rendered = common.render_citations(escape(text), sources)
    return unescape(re.sub(r'<[^>]+>', '', rendered))


def node_text(node, sources):
    return {'label': visible_text(node['label'], sources),
            'items': [visible_text(item, sources) for item in node.get('items', [])],
            'role': ROLES[node['role']],
            'citations': '  ·  '.join(visible_text(c, sources) for c in node.get('citations', []))}


def text_width(text, size, *, bold=False):
    """Conservative pixel advances used for wrapping and the ELK box dimensions."""
    width = 0
    for char in text:
        if unicodedata.combining(char) or unicodedata.category(char) in {'Cf', 'Cc'}:
            continue
        if unicodedata.east_asian_width(char) in {'W', 'F'}:
            advance = 1.03
        elif char in 'ilI.,:;!|\'`':
            advance = .34
        elif char.isspace():
            advance = .36
        elif char in 'WMwm@%&':
            advance = 1
        elif char.isascii():
            advance = .76 if char.isupper() else .65
        else:
            advance = 1.03
        width += size * advance * (1.04 if bold else 1)
    return width


def wrap_text(text, width, size, *, bold=False):
    """Wrap CJK and Latin without changing visible nonwhitespace glyphs.

    Keep comparison values and ordinary Latin terms together when they fit.
    Long tokens wrap at character boundaries instead of overflowing or shrinking.
    """
    lines = []
    for paragraph in text.split('\n'):
        current = ''
        tokens = re.findall(r'[<>≤≥]=?\s*\d+(?:\.\d+)?(?:\s*%|\s*[A-Za-z]+)?|'
                            r'[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*|\s+|.', paragraph)
        for token in tokens:
            if token.isspace():
                if current and not current.endswith(' '):
                    current += ' '
                continue
            if current.strip() and text_width(current + token, size, bold=bold) > width:
                # Avoid leaving closing punctuation alone on a new line.
                if token in '，。！？；：、）)］】%':
                    previous = current.rstrip()[-1:]
                    current = current.rstrip()[:-1]
                    lines.append(current.rstrip())
                    current = previous + token
                    continue
                lines.append(current.rstrip())
                current = ''
            for char in token:
                if current and text_width(current + char, size, bold=bold) > width:
                    lines.append(current.rstrip())
                    current = ''
                current += char
        if current.strip():
            lines.append(current.rstrip())
    return lines or ['']


def measure_card(node, sources):
    text = node_text(node, sources)
    width = node.get('card_width', 440)
    label = wrap_text(text['label'], width - 48, 22, bold=True)
    items = [wrap_text(item, width - 68, 18) for item in text['items']]
    citations = wrap_text(text['citations'], width - 48, 14) if text['citations'] else []
    # Baselines and padding are measured before layout; SVG never scales text to fit.
    divider = 61 + (len(label) - 1) * 29 + 17
    cursor = divider + 28
    positions = []
    for lines in items:
        positions.append(cursor)
        cursor += len(lines) * 27 + 9
    citation_y = cursor + (8 if items else 0)
    height = (citation_y + len(citations) * 20 + 12) if citations else cursor + 8
    return {'id': node['id'], 'width': width, 'height': max(140, height),
            'text': text, 'label': label, 'items': items, 'citations': citations,
            'divider': divider, 'positions': positions, 'citation_y': citation_y}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid clinical layout geometry')
    return str(int(value)) if value == int(value) else f'{value:.3f}'.rstrip('0').rstrip('.')


def _element(parent, tag, attrs=None, text=None):
    child = ET.SubElement(parent, '{' + NS + '}' + tag,
                          {key: str(value) for key, value in (attrs or {}).items()})
    if text is not None:
        child.text = text
    return child


def _text(parent, lines, x, y, size, *, color='#193954', bold=False, attrs=None, leading=None):
    attributes = {'x': _number(x), 'y': _number(y), 'font-size': str(size),
                  'fill': color, 'stroke': 'none', 'font-family': FONT}
    if bold:
        attributes['font-weight'] = '700'
    attributes.update(attrs or {})
    block = _element(parent, 'text', attributes)
    for index, line in enumerate(lines):
        _element(block, 'tspan', {'x': _number(x), 'y': _number(y + index * (leading or size * 1.5))}, line)
    return block


def _dashed_lines(parent, points, color, *, stroke_width=2):
    """Native dash segments also work in renderers without SVG dash support."""
    for start, end in zip(points, points[1:]):
        dx, dy = end['x'] - start['x'], end['y'] - start['y']
        length = math.hypot(dx, dy)
        if not length:
            continue
        dx, dy = dx / length, dy / length
        for offset in range(0, math.ceil(length), 14):
            stop = min(offset + 8, length)
            _element(parent, 'line', {'x1': _number(start['x'] + offset * dx),
                                      'y1': _number(start['y'] + offset * dy),
                                      'x2': _number(start['x'] + stop * dx),
                                      'y2': _number(start['y'] + stop * dy),
                                      'stroke': color, 'stroke-width': str(stroke_width),
                                      'stroke-linecap': 'round', 'fill': 'none'})


def _layout(cards, edges, tools_root):
    graph = {'id': 'clinical-flow',
             'children': [{key: card[key] for key in ('id', 'width', 'height')} for card in cards],
             'edges': edges}
    try:
        process = subprocess.run(['node', str(Path(tools_root) / 'tools/diagrams/layout-clinical.mjs')],
                                 input=json.dumps(graph, ensure_ascii=False),
                                 text=True, encoding='utf-8', capture_output=True,
                                 check=True, timeout=60)
        layout = json.loads(process.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise ValueError('Local clinical-card layout failed; install with npm ci --prefix tools/diagrams --ignore-scripts') from exc
    for key in ('width', 'height'):
        if float(_number(layout.get(key))) <= 0:
            raise ValueError('Invalid clinical layout size')
    expected = {card['id']: card for card in cards}
    nodes = layout.get('children', [])
    if len(nodes) != len(expected) or {node.get('id') for node in nodes} != set(expected):
        raise ValueError('Clinical layout omitted or duplicated nodes')
    for node in nodes:
        for key in ('x', 'y', 'width', 'height'):
            if float(_number(node.get(key))) < 0:
                raise ValueError('Invalid clinical layout node position')
        if any(node[key] != expected[node['id']][key] for key in ('width', 'height')):
            raise ValueError('Clinical layout changed measured node dimensions')
    if len(layout.get('edges', [])) != len(edges) or {e.get('id') for e in layout['edges']} != {e['id'] for e in edges}:
        raise ValueError('Clinical layout omitted or duplicated routes')
    return layout


def _boxes_overlap(a, b, padding=8):
    return (a['x'] < b['x'] + b['width'] + padding and a['x'] + a['width'] > b['x'] - padding and
            a['y'] < b['y'] + b['height'] + padding and a['y'] + a['height'] > b['y'] - padding)


def _segment_hits_box(start, end, box, padding=4):
    left, right = box['x'] - padding, box['x'] + box['width'] + padding
    top, bottom = box['y'] - padding, box['y'] + box['height'] + padding
    if start['x'] == end['x']:
        return left < start['x'] < right and min(start['y'], end['y']) < bottom and max(start['y'], end['y']) > top
    return top < start['y'] < bottom and min(start['x'], end['x']) < right and max(start['x'], end['x']) > left


def _feedback_routes(layout, edges):
    """Route explicit returns outside the forward DAG without changing its ranks.

    ELK measures/routes the forward graph. Feedback returns use a separate gutter
    with measured label boxes, exiting below the whole source layer and entering
    above the target layer so that they never cut through a neighboring card.
    """
    positions = {node['id']: node for node in layout['children']}
    right = layout['width']
    forward = list(layout['edges'])
    returns = []
    for index, edge in enumerate(edges):
        source, target = positions[edge['sources'][0]], positions[edge['targets'][0]]
        same_layer = [node for node in layout['children'] if node['y'] == source['y']]
        bottom = max(node['y'] + node['height'] for node in same_layer) + 34 + index * 24
        top = target['y'] - 34 - index * 24
        lane = right + 26 + index * 24
        source_x, target_x = source['x'] + source['width'] / 2, target['x'] + target['width'] / 2
        points = [{'x': source_x, 'y': source['y'] + source['height']},
                  {'x': source_x, 'y': bottom}, {'x': lane, 'y': bottom},
                  {'x': lane, 'y': top}, {'x': target_x, 'y': top},
                  {'x': target_x, 'y': target['y']}]
        routed = dict(edge, sections=[{'startPoint': points[0], 'bendPoints': points[1:-1], 'endPoint': points[-1]}])
        returns.append((routed, source_x + 18, bottom + 10))
        layout['edges'].append(routed)
    # Place labels only after every return route exists: a later return must not
    # run through an earlier label. Try the nearby source exit first, then use a
    # reserved gutter beyond all cards, forward labels and route sections.
    all_points = [p for e in layout['edges'] for s in e.get('sections', [])
                  for p in [s['startPoint'], *s.get('bendPoints', []), s['endPoint']]]
    segments = [(a, b) for edge in layout['edges'] for section in edge.get('sections', [])
                for a, b in zip([section['startPoint'], *section.get('bendPoints', [])],
                                [*section.get('bendPoints', []), section['endPoint']])]
    boxes = [*layout['children'], *[label for edge in forward for label in edge.get('labels', [])]]
    gutter_x = max([right, *[p['x'] for p in all_points],
                    *[box['x'] + box['width'] for box in boxes]]) + 18
    for routed, x, y in returns:
        labels = []
        for label in routed.get('labels', []):
            candidate = dict(label, x=x, y=y, externalFeedback=True)
            if (any(_boxes_overlap(candidate, box) for box in boxes) or
                    any(_segment_hits_box(a, b, candidate) for a, b in segments)):
                candidate['x'] = gutter_x
                # The outside gutter clears all static geometry. Stack only
                # when an already placed label occupies the desired y range.
                while overlaps := [box for box in boxes if _boxes_overlap(candidate, box)]:
                    candidate['y'] = max(box['y'] + box['height'] for box in overlaps) + 14
            boxes.append(candidate)
            labels.append(candidate)
        routed['labels'] = labels
    # Bounds include every route and external label. Translate the complete graph
    # below its heading if return lanes extend above the original ELK padding.
    all_points = [p for e in layout['edges'] for s in e.get('sections', [])
                  for p in [s['startPoint'], *s.get('bendPoints', []), s['endPoint']]]
    labels = [label for edge in layout['edges'] for label in edge.get('labels', [])]
    min_y = min([0, *[p['y'] for p in all_points]])
    layout['top_offset'] = -min_y + 10
    layout['width'] = max([layout['width'], *[p['x'] + 16 for p in all_points],
                           *[label['x'] + label['width'] + 24 for label in labels]])
    layout['height'] = max([layout['height'], *[p['y'] + 20 for p in all_points],
                            *[label['y'] + label['height'] + 20 for label in labels]]) + layout['top_offset']


def build_svg(data, sources, tools_root):
    """Lay out measured cards using pinned ELK, emit only native SVG elements."""
    cards = [measure_card(node, sources) for node in data['nodes']]
    edges = []
    for index, edge in enumerate(data['edges']):
        label = visible_text(edge.get('label', ''), sources)
        lines = wrap_text(label, 270, 18) if label else []
        edges.append({'id': f'edge-{index}', 'sources': [edge['from']], 'targets': [edge['to']],
                      'labels': [{'id': f'label-{index}', 'text': label,
                                  'width': max(text_width(line, 18) for line in lines) + 20,
                                  'height': len(lines) * 27 + 12,
                                  'layoutOptions': {'elk.edgeLabels.placement': 'CENTER'}}] if lines else []})
    forward = [edge for edge in edges if data['edges'][int(edge['id'].removeprefix('edge-'))].get('role') != 'feedback']
    feedback = [edge for edge in edges if edge not in forward]
    layout = _layout(cards, forward, tools_root)
    _feedback_routes(layout, feedback)
    width = max(560, layout['width'] + 48)
    title_lines = wrap_text(data['title'], width - 64, 26, bold=True)
    population_lines = wrap_text(data['population'], width - 64, 14)
    graph_y = 52 + len(title_lines) * 35 + len(population_lines) * 21
    footer = data['version'] + ' · ' + ('尚未人工審閱' if data['review_status'] == 'not_reviewed' else '已人工審閱')
    if data['conflict_status'] == 'open':
        footer += ' · 保留來源差異'
    footer_lines = [*wrap_text(LEGEND, width - 64, 14), *wrap_text(footer, width - 64, 14)]
    height = graph_y + layout['height'] + 24 + len(footer_lines) * 21 + 24
    prefix = 'flow-' + data['id']
    svg = ET.Element('{' + NS + '}svg', {'width': _number(width), 'height': _number(height),
                     'viewBox': f'0 0 {_number(width)} {_number(height)}', 'role': 'img',
                     'aria-labelledby': prefix + '-title ' + prefix + '-desc',
                     'font-family': FONT, 'fill': '#193954', 'stroke': 'none'})
    _element(svg, 'title', {'id': prefix + '-title'}, data['title'])
    _element(svg, 'desc', {'id': prefix + '-desc'}, '文字步驟與來源列於圖後。' +
             '；'.join(card['text']['label'] + '：' + '；'.join(card['text']['items']) for card in cards))
    _element(svg, 'rect', {'width': _number(width), 'height': _number(height), 'fill': '#f6f9fd', 'stroke': 'none'})
    _text(svg, title_lines, 32, 43, 26, bold=True, leading=35)
    _text(svg, population_lines, 32, 43 + len(title_lines) * 35, 14, color='#536c81', leading=21)
    graph = _element(svg, 'g', {'transform': f'translate(24,{_number(graph_y + layout["top_offset"])})'})
    edge_layer = _element(graph, 'g', {'class': 'flow-edges', 'fill': 'none'})
    for routed in layout['edges']:
        index = int(routed['id'].removeprefix('edge-'))
        edge = data['edges'][index]
        feedback = edge.get('role') == 'feedback'
        color = '#8c7136' if feedback else '#547da1'
        sections = routed.get('sections', [])
        if not sections:
            raise ValueError('Clinical layout returned an unrouted edge')
        for section in sections:
            points = [section['startPoint'], *section.get('bendPoints', []), section['endPoint']]
            if any(a['x'] != b['x'] and a['y'] != b['y'] for a, b in zip(points, points[1:])):
                raise ValueError('Clinical layout returned a nonorthogonal route')
            path = 'M' + 'L'.join(_number(p['x']) + ' ' + _number(p['y']) for p in points)
            attributes = {'d': path, 'fill': 'none', 'stroke': color, 'stroke-width': '2',
                          'stroke-linejoin': 'round', 'data-flow-edge': routed['id'],
                          'data-flow-edge-role': edge.get('role', 'flow')}
            if feedback:
                attributes['stroke'] = 'none'
            _element(edge_layer, 'path', attributes)
            if feedback:
                dashes = _element(edge_layer, 'g', {'data-flow-feedback-dashes': routed['id']})
                _dashed_lines(dashes, points, color)
            # Explicit triangles are visible in MuPDF too, where SVG markers may
            # be omitted. They share the route's endpoint and direction.
            last = points[-1]
            previous = next((p for p in reversed(points[:-1]) if p != last), None)
            if previous is None:
                raise ValueError('Clinical layout returned a zero-length route')
            dx, dy = last['x'] - previous['x'], last['y'] - previous['y']
            length = math.hypot(dx, dy)
            dx, dy = dx / length, dy / length
            back_x, back_y = last['x'] - 16 * dx, last['y'] - 16 * dy
            triangle = [(last['x'], last['y']), (back_x - dy * 7, back_y + dx * 7),
                        (back_x + dy * 7, back_y - dx * 7)]
            _element(edge_layer, 'polygon', {'points': ' '.join(_number(x) + ',' + _number(y) for x, y in triangle),
                                            'fill': color, 'stroke': 'none', 'data-flow-arrow': routed['id']})
        for label in routed.get('labels', []):
            x, y = label['x'], label['y']
            lines = wrap_text(visible_text(edge.get('label', ''), sources), 270, 18)
            group = _element(edge_layer, 'g', {'data-flow-edge-label': routed['id']})
            _element(group, 'rect', {'x': _number(x), 'y': _number(y), 'width': _number(label['width']),
                                     'height': _number(label['height']), 'rx': '5', 'fill': '#f6f9fd', 'stroke': 'none'})
            _text(group, lines, x + 10, y + 23, 18, color=color, leading=27)
    by_id = {node['id']: node for node in data['nodes']}
    positions = {node['id']: node for node in layout['children']}
    for card in cards:
        node = by_id[card['id']]
        pos = positions[card['id']]
        fill, stroke, accent = PALETTES.get(node['role'], DEFAULT_PALETTE)
        group = _element(graph, 'g', {'id': prefix + '-node-' + node['id'], 'class': 'flow-card',
                                     'transform': f'translate({_number(pos["x"])},{_number(pos["y"])})',
                                     'data-flow-node': node['id'], 'data-flow-role': node['role'],
                                     'tabindex': '0', 'role': 'button',
                                     'aria-label': card['text']['role'] + '：' + card['text']['label'] + '：查看節點說明',
                                     'aria-controls': prefix + '-detail-' + node['id']})
        attrs = {'width': card['width'], 'height': card['height'], 'rx': '10', 'fill': fill,
                 'stroke': stroke, 'stroke-width': '1.5'}
        if node['kind'] == 'unknown':
            attrs['stroke'] = 'none'
        _element(group, 'rect', attrs)
        if node['kind'] == 'unknown':
            outline = _element(group, 'g', {'data-flow-unknown-outline': node['id']})
            w, h = card['width'], card['height']
            for a, b in [((10, 0), (w - 10, 0)), ((w, 10), (w, h - 10)),
                         ((w - 10, h), (10, h)), ((0, h - 10), (0, 10))]:
                _dashed_lines(outline, [dict(x=a[0], y=a[1]), dict(x=b[0], y=b[1])], stroke, stroke_width=1.5)
            for corner in [f'M0 10Q0 0 10 0', f'M{w - 10} 0Q{w} 0 {w} 10',
                           f'M{w} {h - 10}Q{w} {h} {w - 10} {h}', f'M10 {h}Q0 {h} 0 {h - 10}']:
                _element(outline, 'path', {'d': corner, 'stroke': stroke, 'stroke-width': '1.5', 'fill': 'none'})
        _element(group, 'rect', {'x': '0', 'y': '17', 'width': '4', 'height': _number(card['height'] - 34),
                                 'rx': '2', 'fill': accent, 'stroke': 'none'})
        _text(group, [card['text']['role']], 24, 29, 14, color=accent, bold=True, attrs={'data-flow-role-label': ''})
        _text(group, card['label'], 24, 61, 22, color=accent, bold=True,
              attrs={'data-flow-label': ''}, leading=29)
        _element(group, 'line', {'x1': '24', 'y1': card['divider'], 'x2': card['width'] - 24,
                                 'y2': card['divider'], 'stroke': '#d9e3ed', 'stroke-width': '1'})
        for index, (lines, y) in enumerate(zip(card['items'], card['positions'])):
            _element(group, 'circle', {'cx': '27', 'cy': y - 6, 'r': '2.5', 'fill': accent, 'stroke': 'none'})
            _text(group, lines, 42, y, 18, attrs={'data-flow-item': str(index)}, leading=27)
        if card['citations']:
            _text(group, card['citations'], 24, card['citation_y'], 14, color='#536c81',
                  attrs={'data-flow-citations': ''}, leading=20)
    _text(svg, footer_lines, 32, graph_y + layout['height'] + 28, 14, color='#536c81', leading=21)
    return ET.tostring(svg, encoding='unicode', short_empty_elements=True) + '\n'


def verify_text(tree, data, sources):
    """Reject omitted/altered titles, items, citation glyphs and duplicate nodes."""
    expected = {node['id']: node_text(node, sources) for node in data['nodes']}
    seen = set()
    normalized = lambda text: re.sub(r'\s+', '', text)
    for group in tree.iter('{' + NS + '}g'):
        node_id = group.get('data-flow-node')
        if node_id is None:
            continue
        if node_id not in expected or node_id in seen:
            raise ValueError('SVG/text clinical nodes differ or duplicate')
        seen.add(node_id)
        texts = list(group.iter('{' + NS + '}text'))
        actual = {}
        for key, marker in [('label', 'data-flow-label'), ('role', 'data-flow-role-label'), ('citations', 'data-flow-citations')]:
            found = [t for t in texts if marker in t.attrib]
            if len(found) != (1 if expected[node_id][key] else 0):
                raise ValueError('SVG/text clinical ' + key + ' differs')
            actual[key] = ''.join(found[0].itertext()) if found else ''
        items = [t for t in texts if 'data-flow-item' in t.attrib]
        if [t.get('data-flow-item') for t in items] != [str(i) for i in range(len(expected[node_id]['items']))]:
            raise ValueError('SVG/text clinical items differ')
        actual['items'] = [''.join(t.itertext()) for t in items]
        if any(normalized(actual[key]) != normalized(expected[node_id][key]) for key in ('label', 'role', 'citations')) or [normalized(s) for s in actual['items']] != [normalized(s) for s in expected[node_id]['items']]:
            raise ValueError('SVG/text clinical glyphs differ: ' + node_id)
    if seen != set(expected):
        raise ValueError('SVG/text clinical nodes differ')
    expected_edges = {f'edge-{index}': visible_text(edge.get('label', ''), sources)
                      for index, edge in enumerate(data['edges']) if edge.get('label')}
    actual_edges = {}
    for group in tree.iter('{' + NS + '}g'):
        edge_id = group.get('data-flow-edge-label')
        if edge_id is not None:
            if edge_id in actual_edges:
                raise ValueError('SVG/text duplicate clinical branch label')
            actual_edges[edge_id] = ''.join(group.itertext())
    if {key: normalized(text) for key, text in expected_edges.items()} != {key: normalized(text) for key, text in actual_edges.items()}:
        raise ValueError('SVG/text clinical branch labels differ')
