"""Technical graph fixtures only; no fixture is a medical recommendation."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common
try:
    import flows
except ModuleNotFoundError:
    flows = None
import yaml


SOURCE = {'W': {'source_id': 'fixture-source', 'pdf_pages': 3,
                'printed_start': 11, 'printed_prefix': ''}}


def definition():
    return {
        'id': 'fixture-flow', 'title': 'Technical evidence graph',
        'kind': 'criteria', 'population': 'Technical fixture only',
        'version': 'fixture 1', 'source_ids': ['fixture-source'],
        'review_status': 'not_reviewed', 'conflict_status': 'none',
        'entry': 'check',
        'nodes': [
            {'id': 'check', 'label': 'Check supplied condition', 'kind': 'decision',
             'detail': 'Read the complete condition before following a branch.',
             'citations': ['[@W:1]']},
            {'id': 'done', 'label': 'Recorded endpoint', 'kind': 'terminal',
             'detail': 'An endpoint in the supplied fixture.', 'citations': ['[@W:2]']},
            {'id': 'unknown', 'label': 'Information missing', 'kind': 'unknown',
             'detail': 'Unknown is a separate outcome.', 'citations': ['[@W:1]']},
        ],
        'edges': [{'from': 'check', 'to': 'done', 'label': 'Condition present'},
                  {'from': 'check', 'to': 'unknown', 'label': 'Not known'}],
        'notes': ['A source-backed educational graph, not a patient calculator.'],
    }


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(flows, 'The source-backed flow renderer must exist')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config/flows'
        self.config.mkdir(parents=True)
        self.graph = definition()

    def save(self):
        (self.config / 'fixture-flow.yml').write_text(
            yaml.safe_dump(self.graph, allow_unicode=True, sort_keys=False), encoding='utf-8')

    def errors(self):
        self.save()
        return '\n'.join(flows.validate_flows(self.root, SOURCE, check_artifacts=False))

    def test_valid_evidence_graph_and_educational_sequence_are_accepted(self):
        self.assertEqual(self.errors(), '')
        self.graph['kind'] = 'differential'
        self.graph['nodes'][0]['kind'] = 'step'
        self.graph['edges'][0]['label'] = 'Read next'
        self.assertEqual(self.errors(), '')

    def test_unknown_sources_and_locators_are_rejected(self):
        self.graph['nodes'][0]['citations'] = ['[@Z:1]']
        self.assertIn('Unknown source', self.errors())
        self.graph['nodes'][0]['citations'] = ['[@W:9]']
        self.assertIn('citation', self.errors().lower())
        self.graph['nodes'][0]['citations'] = ['[@W:missing-locator]']
        self.assertIn('citation', self.errors().lower())

    def test_cited_sources_must_be_declared(self):
        self.graph['source_ids'] = ['different-source']
        self.assertIn('source_ids', self.errors())

    def test_duplicate_nodes_and_missing_edge_or_entry_refs_are_rejected(self):
        self.graph['nodes'].append(deepcopy(self.graph['nodes'][0]))
        self.assertIn('duplicate node', self.errors().lower())
        self.graph = definition()
        self.graph['edges'][0]['to'] = 'absent'
        self.assertIn('unknown node', self.errors().lower())
        self.graph = definition()
        self.graph['entry'] = 'absent'
        self.assertIn('entry', self.errors().lower())

    def test_unreachable_nodes_are_rejected(self):
        self.graph['edges'].pop()
        self.assertIn('unreachable', self.errors().lower())

    def test_decisions_require_evidence_and_explicit_unknown_exit(self):
        self.graph['nodes'][0]['citations'] = []
        self.assertIn('evidence', self.errors().lower())
        self.graph = definition()
        self.graph['nodes'][2]['kind'] = 'terminal'
        self.assertIn('unknown', self.errors().lower())
        self.graph = definition()
        self.graph['edges'][0]['label'] = ''
        self.assertIn('label', self.errors().lower())

    def test_leaf_nodes_must_explicitly_be_terminal_or_unknown(self):
        self.graph['nodes'][1]['kind'] = 'step'
        self.assertIn('terminal', self.errors().lower())

    def test_malformed_field_types_return_validation_errors(self):
        for field in ['kind', 'review_status', 'conflict_status']:
            with self.subTest(field=field):
                self.graph = definition()
                self.graph[field] = []
                self.assertIn(field, self.errors())
        self.graph = definition()
        self.graph['nodes'][0]['kind'] = []
        self.assertIn('kind', self.errors())
        self.graph = definition()
        self.graph['edges'][0]['label'] = 3
        self.assertIn('label', self.errors())

    def test_inline_note_evidence_is_validated_and_conflict_cannot_be_reviewed(self):
        self.graph['notes'] = ['Note with invalid evidence [@W:9].']
        self.assertIn('citation', self.errors().lower())
        self.graph = definition()
        self.graph['conflict_status'] = 'open'
        self.graph['review_status'] = 'reviewed'
        self.assertIn('not_reviewed', self.errors())

    def test_paths_and_markup_cannot_escape_the_definition_boundary(self):
        self.graph['id'] = '../fixture-flow'
        self.assertIn('id', self.errors().lower())
        with self.assertRaises(ValueError):
            flows.render_flow(self.root, '../fixture-flow', 'index.html', SOURCE)
        self.graph = definition()
        self.graph['nodes'][0]['label'] = '<script>alert(1)</script>'
        source = flows.mermaid_source(self.graph)
        self.assertNotIn('<script>', source)
        self.assertNotIn('click ', source)

    def test_stale_missing_and_unsafe_svg_fail_closed(self):
        self.save()
        self.assertIn('artifact', '\n'.join(flows.validate_flows(self.root, SOURCE)).lower())
        with self.assertRaises(ValueError):
            flows.validate_svg('<svg xmlns="http://www.w3.org/2000/svg"><script /></svg>')
        for unsafe in [
            '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
            '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://invalid.example/x"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:url(https://invalid.example/x)"/></svg>',
            '<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:u\\72l(//invalid.example/x)"/></svg>',
            '<!DOCTYPE svg [<!ENTITY x "bad">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        ]:
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    flows.validate_svg(unsafe)

    def test_standalone_svg_materializes_colors_fonts_and_radii(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180"
          style="--_fg:var(--pele-fg,#111);--_s:var(--pele-surface,#eee);
          --_b:var(--pele-border,#888);--_l:var(--pele-line,#222);
          --_r:var(--pele-radius,var(--missing-radius,4px));
          color:var(--_fg);font:18px sans-serif;font-family:var(--pele-font,sans-serif)"
          fill="var(--_fg)">
          <g class="pele-edges" fill="none" stroke="var(--_l)">
            <path d="M0 0L10 10"/><path fill="var(--_l)" stroke="none" d="M1 1L2 2Z"/>
          </g>
          <g class="pele-node" data-id="n0" transform="translate(80,30)">
            <rect x="-60" y="-20" width="120" height="40" fill="var(--_s)"
              stroke="var(--_b)" style="rx:var(--_r)"/>
            <text>Check supplied condition</text>
          </g>
          <g class="pele-node" data-id="n1"><rect fill="var(--_s)" stroke="var(--_b)"/>
            <text>Recorded endpoint</text></g>
          <g class="pele-node" data-id="n2"><rect fill="var(--_s)" stroke="var(--_b)"/>
            <text>Information missing</text></g>
        </svg>'''
        result = flows._decorate_svg(svg, self.graph)
        self.assertNotIn('var(', result)
        tree = ET.fromstring(result)
        self.assertEqual(tree.get('fill'), '#193954')
        self.assertEqual(tree.get('font-size'), '18px')
        self.assertEqual(tree.get('font-family'), 'sans-serif')
        self.assertEqual(tree.get('viewBox'), '0 0 240 180')
        edges = tree.find('{http://www.w3.org/2000/svg}g')
        self.assertEqual(edges.get('stroke'), '#547da1')
        self.assertEqual(edges[1].get('fill'), '#547da1')
        nodes = {g.get('data-flow-node'): g for g in tree.iter('{http://www.w3.org/2000/svg}g')
                 if g.get('data-flow-node')}
        shape = nodes['check'][0]
        self.assertEqual((shape.get('fill'), shape.get('stroke'), shape.get('rx')),
                         ('#edf4fb', '#8eabc4', '4px'))
        self.assertNotIn('style', shape.attrib)  # Presentation attributes allow selection CSS to win.
        self.assertEqual(nodes['check'].get('transform'), 'translate(80,30)')
        self.assertEqual(''.join(nodes['check'].itertext()).strip(), 'Check supplied condition')
        self.assertEqual((nodes['unknown'][0].get('fill'), nodes['unknown'][0].get('stroke')),
                         ('#f6f9fd', '#285f91'))
        self.assertEqual(nodes['unknown'][0].get('stroke-dasharray'), '6 4')

    def test_unresolved_or_cyclic_svg_variables_fail_closed(self):
        nodes = ''.join(f'<g class="pele-node" data-id="n{i}"><text>{node["label"]}</text></g>'
                        for i, node in enumerate(self.graph['nodes']))
        for style in ['--_fg:var(--missing)', '--_fg:var(--loop);--loop:var(--_fg)']:
            with self.subTest(style=style):
                svg = f'<svg xmlns="http://www.w3.org/2000/svg" style="{style}" fill="var(--_fg)">{nodes}</svg>'
                with self.assertRaisesRegex(ValueError, 'SVG variable'):
                    flows._decorate_svg(svg, self.graph)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_unicode_labels_and_markup_remain_literal_and_html_locators_work(self):
        self.graph['nodes'][0]['label'] = '中文條件 ≤ 10% & "quoted" <literal>'
        self.graph['nodes'][0]['detail'] = 'Literal <script> is displayed as text.'
        source = deepcopy(SOURCE)
        source['A'] = {'source_id': 'html-fixture', 'locator_type': 'html',
                       'locators': {'d01': 'Fixture card 1'}}
        self.graph['source_ids'].append('html-fixture')
        self.graph['nodes'][0]['citations'].append('[@A:d01]')
        self.save()
        flows.build_flows(self.root, source, tools_root=ROOT)
        html = flows.render_flow(self.root, 'fixture-flow', 'index.html', source, tools_root=ROOT)
        self.assertIn('data-locator="d01"', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('≤ 10%', html)
        self.graph['nodes'][0]['citations'][-1] = '[@A:d02]'
        self.save()
        self.assertIn('locator', '\n'.join(flows.validate_flows(self.root, source, check_artifacts=False)).lower())

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_real_pele_exports_consistent_deterministic_svg_and_text(self):
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        self.assertEqual(flows.validate_flows(self.root, SOURCE, tools_root=ROOT), [])
        prefix = self.root / 'assets/figures/flows/fixture-flow'
        snapshots = {suffix: prefix.with_suffix(suffix).read_bytes()
                     for suffix in ['.svg', '.mmd', '.json']}
        self.assertNotIn(b'var(', snapshots['.svg'])
        html = flows.render_flow(self.root, 'fixture-flow', '03_outputs/web/test/index.html',
                                 SOURCE, tools_root=ROOT)
        for node in self.graph['nodes']:
            self.assertIn(node['label'], html)
            self.assertIn(f'data-flow-node="{node["id"]}"', html)
            self.assertIn(f'data-flow-select="{node["id"]}"', html)
            self.assertIn(node['detail'], html)
        self.assertIn('class="citation"', html)
        self.assertIn('role="img"', html)
        self.assertIn('<title', html)
        self.assertIn('<desc', html)
        self.assertIn('文字步驟', html)
        self.assertIn('尚未人工審閱', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('onclick=', html)
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        for suffix, before in snapshots.items():
            self.assertEqual(prefix.with_suffix(suffix).read_bytes(), before)
        prefix.with_suffix('.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding='utf-8')
        self.assertIn('stale', '\n'.join(flows.validate_flows(self.root, SOURCE, tools_root=ROOT)))
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        self.graph['nodes'][0]['label'] = 'Changed condition'
        self.save()
        self.assertIn('stale', '\n'.join(flows.validate_flows(self.root, SOURCE, tools_root=ROOT)))
        with self.assertRaises(ValueError):
            flows.render_flow(self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=ROOT)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_same_label_nodes_keep_distinct_controls_and_svg_ids_are_page_scoped(self):
        self.graph['nodes'][1]['label'] = self.graph['nodes'][2]['label']
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        html = flows.render_flow(self.root, 'fixture-flow', 'one/index.html', SOURCE, tools_root=ROOT)
        html2 = flows.render_flow(self.root, 'fixture-flow', 'two/index.html', SOURCE, tools_root=ROOT)
        self.assertIn('data-flow-node="done"', html)
        self.assertIn('data-flow-node="unknown"', html)
        self.assertNotEqual(html, html2)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_product_labels_and_standalone_theme_preserve_unknown_annotation(self):
        self.graph['conflict_status'] = 'open'
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        html = flows.render_flow(self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=ROOT)
        self.assertIn('診斷準則圖', html)
        self.assertIn('尚未人工審閱', html)
        self.assertIn('保留來源差異', html)
        self.assertNotIn('conflict_status:', html)
        self.assertNotIn('not_reviewed', html)
        svg = ET.fromstring((self.root / 'assets/figures/flows/fixture-flow.svg').read_text(encoding='utf-8'))
        self.assertIn('--pele-accent:', svg.get('style'))
        unknown = next(g for g in svg.iter('{http://www.w3.org/2000/svg}g')
                       if g.get('data-flow-node') == 'unknown')
        self.assertIn('資訊不足出口', unknown.get('aria-label'))
        self.assertTrue(any(element.get('stroke-dasharray') for element in unknown))
        self.assertIn('資訊不足出口', html)
        self.graph['conflict_status'] = 'none'
        self.graph['kind'] = 'differential'
        self.graph['review_status'] = 'reviewed'
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        html = flows.render_flow(self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=ROOT)
        self.assertIn('鑑別思路圖', html)
        self.assertIn('已人工審閱', html)
        self.assertNotIn('保留來源差異', html)

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_cjk_labels_wrap_without_losing_or_changing_glyphs(self):
        for label in ['全部五項主準則是否已確認符合？', '描述病灶、分布與剝脫外觀', '資料不足，保留未確認項目']:
            with self.subTest(label=label):
                self.graph['nodes'][0]['label'] = label
                self.save()
                flows.build_flows(self.root, SOURCE, tools_root=ROOT)
                svg = ET.fromstring((self.root / 'assets/figures/flows/fixture-flow.svg').read_text(encoding='utf-8'))
                group = next(g for g in svg.iter('{http://www.w3.org/2000/svg}g')
                             if g.get('data-flow-node') == 'check')
                lines = [s.text for s in group.iter('{http://www.w3.org/2000/svg}tspan')]
                self.assertGreater(len(lines), 1)
                self.assertEqual(''.join(lines), label)
                self.assertTrue(all(4 <= len(line) <= 12 for line in lines))

    @unittest.skipUnless((ROOT / 'tools/diagrams/node_modules/pele').is_dir(),
                         'npm ci --prefix tools/diagrams is required for renderer integration')
    def test_verified_artifacts_work_without_node_modules_and_across_git_line_endings(self):
        self.save()
        flows.build_flows(self.root, SOURCE, tools_root=ROOT)
        clone = self.root / 'public-clone'
        for relative in ['scripts/flows.py', 'tools/diagrams/render-flows.mjs',
                         'tools/diagrams/package.json', 'tools/diagrams/package-lock.json']:
            target = clone / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertFalse((clone / 'tools/diagrams/node_modules').exists())
        self.assertEqual(flows.validate_flows(self.root, SOURCE, tools_root=clone), [])
        self.assertIn('Technical evidence graph', flows.render_flow(
            self.root, 'fixture-flow', 'index.html', SOURCE, tools_root=clone))


if __name__ == '__main__':
    unittest.main()
