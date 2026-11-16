"""Technical fixtures for readable source-derived cards, never clinical advice."""
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import flows
from test_flows import SOURCE, definition
import yaml

NS = '{http://www.w3.org/2000/svg}'


def cards():
    graph = definition()
    graph['presentation'] = 'clinical-cards'
    graph['nodes'][0].update(role='criteria', card_width=360, items=[
        '第一項：時間窗 ≥ 2 weeks；保留完整條件。',
        'Second item: ≤ 10% & "quoted" <literal>.',
        'A long term with spaces and a considerably longer sentence wraps inside the card.'])
    graph['nodes'][1].update(role='outcome', items=['Keep the source limitations.'])
    graph['nodes'][2].update(role='uncertainty', items=['Collect missing data before reassessment.'])
    graph['edges'].append({'from': 'unknown', 'to': 'check', 'role': 'feedback',
                           'label': 'Return after gathering missing data'})
    return graph


class ClinicalCardsTests(unittest.TestCase):
    def test_closing_punctuation_keeps_short_acronyms_on_one_line(self):
        from clinical_flow_svg import wrap_text, text_width
        prefix = '取得結果後核對'
        for acronym in ['PE', 'IVIG', 'ALT', 'COMET']:
            with self.subTest(acronym=acronym):
                text = prefix + acronym + '。'
                width = text_width(prefix + acronym, 18) + text_width('。', 18) / 2
                lines = wrap_text(text, width, 18)
                self.assertTrue(any(acronym in line for line in lines), lines)
                self.assertEqual(''.join(lines), text)
                self.assertTrue(all(text_width(line, 18) <= width for line in lines))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config/flows'
        self.config.mkdir(parents=True)
        self.graph = cards()

    def save(self):
        (self.config / 'fixture-flow.yml').write_text(
            yaml.safe_dump(self.graph, allow_unicode=True, sort_keys=False), encoding='utf-8')

    def errors(self):
        self.save()
        return '\n'.join(flows.validate_flows(self.root, SOURCE, check_artifacts=False))

    def build(self):
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        return self.root / 'assets/figures/flows/fixture-flow'

    def test_unknown_feedback_requires_explicit_role_and_nonempty_label(self):
        self.assertEqual(self.errors(), '')
        for mutation in [dict(role='flow'), dict(role='option'), dict(role='feedback', label=''),
                         dict(role='feedback', label='   '), dict(role=None)]:
            with self.subTest(mutation=mutation):
                self.graph = cards()
                self.graph['edges'][-1].update(mutation)
                self.assertIn('feedback', self.errors())
        self.graph = cards()
        self.graph['edges'][-1]['from'] = 'done'
        self.assertIn('terminal', self.errors())

    def test_rich_schema_rejects_malformed_visible_content_and_roles(self):
        for field, value in [('items', 'not a list'), ('items', ['']), ('items', [3]),
                             ('role', 'urgent'), ('role', []), ('card_width', 319),
                             ('card_width', 721), ('card_width', True), ('card_width', '440')]:
            with self.subTest(field=field, value=value):
                self.graph = cards()
                self.graph['nodes'][0][field] = value
                self.assertIn(field, self.errors())
        self.graph = cards()
        self.graph['presentation'] = 'unknown'
        self.assertIn('presentation', self.errors())
        self.graph = cards()
        self.graph['edges'][0]['role'] = 'urgent'
        self.assertIn('role', self.errors())

    def test_rich_content_cannot_silently_disappear_in_legacy_presentation(self):
        self.graph.pop('presentation')
        self.graph['edges'].pop()
        self.assertIn('presentation', self.errors())

    def test_response_reassessment_can_branch_to_two_actions_without_unknown(self):
        """A response-based decision need not add a fabricated missing-data route."""
        self.graph['nodes'][0].update(
            role='decision', label='Have target symptoms improved at reassessment?',
            detail='Compare documented target symptoms with the previous assessment.',
            items=['Use the recorded symptom response.'])
        self.graph['nodes'][1].update(
            role='followup', label='Continue the planned follow-up',
            detail='Follow the existing plan after documented symptom improvement.',
            items=['Continue the planned follow-up.'])
        self.graph['nodes'][2].update(
            id='review', kind='terminal', role='action', label='Review the management plan',
            detail='Review symptoms and treatment when improvement is absent.',
            items=['Reassess symptoms and current treatment.'])
        self.graph['edges'] = [
            {'from': 'check', 'to': 'done', 'label': 'Target symptoms improved'},
            {'from': 'check', 'to': 'review', 'label': 'Target symptoms did not improve'},
        ]
        self.assertEqual(self.errors(), '')

    def test_return_cycles_cannot_silently_reverse_the_forward_graph(self):
        self.graph['nodes'][1]['kind'] = 'step'
        self.graph['edges'].append({'from': 'done', 'to': 'check', 'label': 'Return to assessment'})
        self.assertIn('feedback', self.errors())

    def test_mermaid_fallback_includes_every_visible_item_as_literal_text(self):
        source = flows.mermaid_source(self.graph)
        self.assertIn('第一項：時間窗 ≥ 2 weeks', source)
        self.assertIn('Second item: ≤ 10%', source)
        self.assertNotIn('<literal>', source)
        self.assertIn('Return after gathering missing data', source)

    def test_feedback_label_does_not_cover_a_forward_corner_or_its_branch_label(self):
        # Technical geometry reproduces the strategy diagram's edge-11/edge-12
        # collision. Labels must clear routes as well as other measured boxes.
        import clinical_flow_svg
        forward = {'id': 'edge-12', 'sections': [{
            'startPoint': {'x': 1218, 'y': 1511},
            'bendPoints': [{'x': 1218, 'y': 1563}, {'x': 1513, 'y': 1563}],
            'endPoint': {'x': 1513, 'y': 1681}}],
            'labels': [{'id': 'label-12', 'x': 1231, 'y': 1575, 'width': 279.56, 'height': 66}]}
        feedback = {'id': 'edge-11', 'sources': ['followup'], 'targets': ['strategy'],
                    'labels': [{'id': 'label-11', 'width': 279.56, 'height': 66, 'text': 'Return after reassessment'}]}
        layout = {'width': 2723, 'height': 2000, 'children': [
            {'id': 'strategy', 'x': 1076, 'y': 24, 'width': 620, 'height': 400},
            {'id': 'followup', 'x': 970, 'y': 1200, 'width': 620, 'height': 311},
            {'id': 'further', 'x': 1283, 'y': 1681, 'width': 460, 'height': 200}],
            'edges': [forward]}
        clinical_flow_svg._feedback_routes(layout, [feedback])
        label = layout['edges'][-1]['labels'][0]
        left, top = label['x'], label['y']
        right, bottom = left + label['width'], top + label['height']
        # Independently hand-checked forward label bounds.
        self.assertFalse(left < 1510.56 and right > 1231 and top < 1641 and bottom > 1575)
        # All three segments of the forward route, including its visible corner.
        self.assertFalse(left < 1513 and right > 1218 and top < 1563 < bottom)
        self.assertFalse(left < 1218 < right and top < 1563 and bottom > 1511)
        self.assertFalse(left < 1513 < right and top < 1681 and bottom > 1563)
        self.assertLess(right, layout['width'])

    def test_feedback_return_does_not_cross_forward_labels_or_neighboring_cards(self):
        # The former fixed y=723 return crossed a forward label at y=702..741.
        # The same measured rectangle can be occupied by a neighboring card.
        import clinical_flow_svg
        for obstacle_kind in ['label', 'card']:
            with self.subTest(obstacle_kind=obstacle_kind):
                obstacle = {'x': 1137, 'y': 702, 'width': 186.86, 'height': 39}
                forward = {'id': 'edge-5', 'sections': [{
                    'startPoint': {'x': 1000, 'y': 600},
                    'endPoint': {'x': 1000, 'y': 757}}],
                    'labels': [dict(obstacle, id='label-5')] if obstacle_kind == 'label' else []}
                layout = {'width': 1600, 'height': 1600, 'children': [
                    {'id': 'response', 'x': 600, 'y': 757, 'width': 460, 'height': 200},
                    {'id': 'repeat', 'x': 1100, 'y': 1200, 'width': 460, 'height': 200}],
                    'edges': [forward]}
                if obstacle_kind == 'card':
                    layout['children'].append(dict(obstacle, id='neighbor'))
                original_nodes, original_forward = deepcopy(layout['children']), deepcopy(forward)
                feedback = {'id': 'edge-10', 'sources': ['repeat'], 'targets': ['response'],
                            'labels': []}
                clinical_flow_svg._feedback_routes(layout, [feedback])
                section = layout['edges'][-1]['sections'][0]
                points = [section['startPoint'], *section['bendPoints'], section['endPoint']]
                for start, end in zip(points, points[1:]):
                    if start['y'] == end['y']:
                        self.assertFalse(702 < start['y'] < 741 and
                                         min(start['x'], end['x']) < 1323.86 and
                                         max(start['x'], end['x']) > 1137)
                    else:
                        self.assertFalse(1137 < start['x'] < 1323.86 and
                                         min(start['y'], end['y']) < 741 and
                                         max(start['y'], end['y']) > 702)
                self.assertEqual(layout['children'], original_nodes)
                self.assertEqual(layout['edges'][0], original_forward)
                self.assertEqual(points[-1], {'x': 830, 'y': 757})
                for point in points:
                    self.assertGreaterEqual(point['x'], 0)
                    self.assertLess(point['x'], layout['width'])
                    self.assertGreaterEqual(point['y'] + layout['top_offset'], 0)
                    self.assertLess(point['y'] + layout['top_offset'], layout['height'])

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_real_cards_svg_preserves_text_citations_hooks_and_orthogonal_routes(self):
        prefix = self.build()
        raw = prefix.with_suffix('.svg').read_text(encoding='utf-8')
        tree = flows.validate_svg(raw)
        self.assertNotIn('var(', raw)
        self.assertNotIn('foreignObject', raw)
        self.assertNotIn('<script', raw)
        self.assertIsNotNone(tree.find(NS + 'title'))
        self.assertIsNotNone(tree.find(NS + 'desc'))
        nodes = {g.get('data-flow-node'): g for g in tree.iter(NS + 'g') if g.get('data-flow-node')}
        self.assertEqual(set(nodes), {'check', 'done', 'unknown'})
        for node in self.graph['nodes']:
            group = nodes[node['id']]
            self.assertEqual(group.get('role'), 'button')
            self.assertEqual(group.get('tabindex'), '0')
            texts = [t for t in group.iter(NS + 'text')]
            label = next(t for t in texts if t.get('data-flow-label') is not None)
            self.assertEqual(re.sub(r'\s', '', ''.join(label.itertext())), re.sub(r'\s', '', node['label']))
            self.assertEqual(label.get('font-size'), '22')
            items = [t for t in texts if t.get('data-flow-item') is not None]
            self.assertEqual(len(items), len(node['items']))
            for text, item in zip(items, node['items']):
                self.assertEqual(re.sub(r'\s', '', ''.join(text.itertext())), re.sub(r'\s', '', item))
                self.assertEqual(text.get('font-size'), '18')
            self.assertTrue(any('W · ' in ''.join(t.itertext()) for t in texts))
            self.assertIsNotNone(group.find(NS + 'rect'))  # Decisions use compact cards too.
            self.assertEqual(group.find(NS + 'rect').get('width'), str(node.get('card_width', 440)))
        for path in tree.iter(NS + 'path'):
            if path.get('data-flow-edge'):
                coords = list(map(float, re.findall(r'-?\d+(?:\.\d+)?', path.get('d'))))
                points = list(zip(coords[::2], coords[1::2]))
                self.assertTrue(all(x == xx or y == yy for (x, y), (xx, yy) in zip(points, points[1:])))
        arrows = [p for p in tree.iter(NS + 'polygon') if p.get('data-flow-arrow')]
        self.assertEqual(len(arrows), len(self.graph['edges']))
        # Standalone renderers can ignore stroke-dasharray; draw actual segments.
        returns = [g for g in tree.iter(NS + 'g') if g.get('data-flow-feedback-dashes')]
        self.assertEqual(len(returns), 1)
        self.assertGreater(len(list(returns[0].iter(NS + 'line'))), 5)
        unknown_outline = next(g for g in nodes['unknown'].iter(NS + 'g') if g.get('data-flow-unknown-outline'))
        self.assertGreater(len(list(unknown_outline.iter(NS + 'line'))), 5)
        self.assertEqual(flows.validate_flows(self.root, SOURCE, tools_root=ROOT), [])
        html = flows.render_flow(self.root, 'fixture-flow', 'web/test.html', SOURCE, tools_root=ROOT)
        self.assertIn('data-flow-presentation="clinical-cards"', html)
        self.assertIn('開啟完整圖</a>', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('../assets/figures/flows/fixture-flow.svg', html)
        for item in self.graph['nodes'][0]['items']:
            self.assertIn(flows.escape(item), html)
        self.assertIn(self.graph['nodes'][0]['detail'], html)
        self.assertNotIn('<literal>', html)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_feedback_cannot_move_entry_below_the_main_forward_path(self):
        start = {'id': 'start', 'kind': 'step', 'role': 'assessment', 'label': 'Begin with supplied records',
                 'detail': 'The entry must precede the subsequent check.', 'items': ['Prepare the inputs.'],
                 'citations': ['[@W:1]']}
        self.graph['nodes'].insert(0, start)
        gather = dict(start, id='gather', label='Gather supporting context')
        retry = dict(start, id='retry', role='action', label='Reassess changed records')
        self.graph['nodes'].insert(1, gather)
        self.graph['nodes'].insert(-1, retry)
        self.graph['entry'] = 'start'
        self.graph['edges'].insert(0, {'from': 'gather', 'to': 'check', 'label': 'Then check the condition'})
        self.graph['edges'].insert(0, {'from': 'start', 'to': 'gather', 'label': 'Collect context'})
        self.graph['edges'][-1]['to'] = 'start'
        self.graph['edges'].extend([{'from': 'check', 'to': 'retry', 'label': 'Records changed'},
                                    {'from': 'retry', 'to': 'start', 'label': 'Reassess after updating records', 'role': 'feedback'}])
        prefix = self.build()
        tree = ET.fromstring(prefix.with_suffix('.svg').read_text(encoding='utf-8'))
        positions = {g.get('data-flow-node'): tuple(map(float, re.findall(r'-?\d+(?:\.\d+)?', g.get('transform'))))
                     for g in tree.iter(NS + 'g') if g.get('data-flow-node')}
        self.assertLess(positions['start'][1], positions['gather'][1])
        self.assertLess(positions['gather'][1], positions['check'][1])
        self.assertLess(positions['check'][1], positions['done'][1])
        self.assertLess(positions['check'][1], positions['unknown'][1])
        svg_text = ''.join(tree.itertext())
        self.assertIn('虛線：返回重評', svg_text)
        html = flows.render_flow(self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=ROOT)
        self.assertIn('虛線：返回重評', html)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_layout_geometry_is_stable_across_fresh_process_clocks(self):
        """A measured branch/rejoin topology must rebuild identically over time."""
        # Captured measured geometry, with technical IDs/labels and no clinical
        # content dependency. ELK documents seed 0 as time-derived; controlling
        # the clock makes that regression deterministic instead of probabilistic.
        dimensions = [(600, 281), (520, 281), (620, 391), (520, 308),
                      (600, 254), (620, 281), (560, 335), (520, 281)]
        branches = [(0, 0, 1, 279.55999999999995, 66),
                    (1, 0, 2, 279.55999999999995, 39),
                    (2, 0, 6, 279.55999999999995, 66),
                    (3, 2, 3, 223.93999999999994, 39),
                    (4, 2, 4, 282.25999999999993, 39),
                    (5, 2, 6, 186.85999999999996, 39),
                    (6, 4, 5, 223.93999999999994, 39),
                    (8, 5, 7, 279.55999999999995, 66),
                    (9, 5, 6, 279.55999999999995, 66)]
        graph = {'id': 'clinical-flow',
                 'children': [{'id': f'node-{i}', 'width': width, 'height': height}
                              for i, (width, height) in enumerate(dimensions)],
                 'edges': [{'id': f'edge-{i}', 'sources': [f'node-{source}'],
                            'targets': [f'node-{target}'],
                            'labels': [{'id': f'label-{i}', 'text': 'Technical branch label',
                                        'width': width, 'height': height,
                                        'layoutOptions': {'elk.edgeLabels.placement': 'CENTER'}}]}
                           for i, source, target, width, height in branches]}
        script = (ROOT / 'tools/diagrams/layout-clinical.mjs').read_text(encoding='utf-8')
        layouts = []
        for clock in [1000, 3000]:
            process = subprocess.run(
                ['node', '--input-type=module', '-e', f'Date.now = () => {clock};\n' + script],
                cwd=ROOT / 'tools/diagrams', input=json.dumps(graph),
                text=True, encoding='utf-8', capture_output=True, check=True, timeout=60)
            layouts.append(json.loads(process.stdout))
        self.assertEqual(layouts[0], layouts[1], 'Identical measured geometry changed with the build clock')

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_cards_are_deterministic_and_cannot_hide_changed_item_glyphs(self):
        prefix = self.build()
        snapshots = {suffix: prefix.with_suffix(suffix).read_bytes() for suffix in ['.svg', '.mmd', '.json']}
        self.build()
        for suffix, before in snapshots.items():
            self.assertEqual(prefix.with_suffix(suffix).read_bytes(), before)
        # A rehashed artifact still cannot change a condition, item, or branch.
        for old, new in [('第一項', '第三項'), ('Check supplied', 'Check altered'),
                         ('Condition present', 'Condition absent')]:
            with self.subTest(altered=old):
                raw = snapshots['.svg'].decode('utf-8').replace(old, new)
                self.assertNotEqual(raw.encode('utf-8'), snapshots['.svg'])
                prefix.with_suffix('.svg').write_bytes(raw.encode('utf-8'))
                manifest = json.loads(snapshots['.json'])
                manifest['svg_sha256'] = flows._hash(raw.encode('utf-8'))
                prefix.with_suffix('.json').write_text(json.dumps(manifest), encoding='utf-8')
                self.assertIn('SVG/text', '\n'.join(flows.validate_flows(self.root, SOURCE, tools_root=ROOT)))

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_long_card_text_stays_within_measured_boxes_at_width_boundaries(self):
        self.graph['nodes'][0].update(card_width=320, label='保留很長的中文標題與治療情境的每個字',
                                      items=['LongUnbrokenTechnicalTerm' * 5, '保留很長的中文條件' * 9,
                                             'Literal <script>alert(1)</script> & **stars**.'])
        self.graph['nodes'][1]['card_width'] = 720
        prefix = self.build()
        tree = ET.fromstring(prefix.with_suffix('.svg').read_text(encoding='utf-8'))
        for group in tree.iter(NS + 'g'):
            if not group.get('data-flow-node'):
                continue
            box = group.find(NS + 'rect')
            width, height = float(box.get('width')), float(box.get('height'))
            for text in group.iter(NS + 'text'):
                for line in text:
                    self.assertGreaterEqual(float(line.get('x')), 24)
                    self.assertLess(float(line.get('x')), width - 20)
                    self.assertGreater(float(line.get('y')), 10)
                    self.assertLess(float(line.get('y')), height - 8)
        self.assertEqual(flows.validate_flows(self.root, SOURCE, tools_root=ROOT), [])
        html = flows.render_flow(self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=ROOT)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/elkjs').is_dir(), 'Install pinned elkjs')
    def test_source_caption_and_renderer_changes_invalidate_cards_without_node_runtime(self):
        self.build()
        source = deepcopy(SOURCE)
        source['W']['printed_start'] = 101
        self.assertIn('stale', '\n'.join(flows.validate_flows(self.root, source, tools_root=ROOT)))
        clone = self.root / 'renderer-clone'
        for relative in [*flows.RENDERER_FILES, 'scripts/clinical_flow_svg.py', 'tools/diagrams/layout-clinical.mjs']:
            target = clone / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertEqual(flows.validate_flows(self.root, SOURCE, tools_root=clone), [])
        with (clone / 'tools/diagrams/layout-clinical.mjs').open('a') as stream:
            stream.write('\n// Renderer changed\n')
        self.assertIn('stale', '\n'.join(flows.validate_flows(self.root, SOURCE, tools_root=clone)))


if __name__ == '__main__':
    unittest.main()
