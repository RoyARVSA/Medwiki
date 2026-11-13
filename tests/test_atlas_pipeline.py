"""HTML citation and public media behavior in isolated staged builds."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import common
import build_site
import lint
import yaml


class AtlasPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = {
            'source_id': 'src-atlas', 'short_id': 'A', 'title': 'Supplied atlas',
            'short_title': 'Atlas', 'locator_type': 'html',
            'locators': {'d01': '項目 01 <figure> & "caption"', 'c1': '鑑別章節'},
            'public_path': '03_outputs/web/resources/atlas.html',
            'processing_status': 'complete', 'original_access': 'local_only',
            'local_path': 'DO-NOT-PUBLISH',
        }

    def prepare_build(self, body, **extra):
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project / '04_templates/site', self.root / '04_templates/site')
        shutil.copytree(project / 'assets/site', self.root / 'assets/site')
        for name in ['medwiki-mark.svg', 'favicon-32.png']:
            asset = self.root / 'assets/images' / name
            asset.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project / 'assets/images' / name, asset)
        record = self.root / '02_sources/records/atlas.md'
        record.parent.mkdir(parents=True)
        record.write_text('---\n' + yaml.safe_dump(self.source, allow_unicode=True) + '---\n', encoding='utf-8')
        public = self.root / self.source['public_path']
        public.parent.mkdir(parents=True)
        public.write_text('<title>Atlas references</title><h1 id="d01">Item 01</h1><h2 id="c1">Comparison</h2>', encoding='utf-8')
        meta = dict(id='atlas-topic', title='Atlas topic', type='concept', created='2026-11-13',
                    updated='2026-11-13', summary='A source-backed topic', tags=['dermatology'],
                    source_ids=['src-atlas'], review_status='not_reviewed', conflict_status='none',
                    publish=True, web_topic='atlas', web_file='index.html', order=1)
        meta.update(extra)
        self.doc = self.root / '01_wiki/concepts/topic.md'
        self.doc.parent.mkdir(parents=True)
        self.doc.write_text('---\n' + yaml.safe_dump(meta, allow_unicode=True) + '---\n' + body, encoding='utf-8')

    def test_html_citation_renders_locator_and_escapes_label(self):
        rendered = common.render_citations('Claim [@A:d01]', {'A': self.source})
        self.assertIn('data-source="A"', rendered)
        self.assertIn('data-kind="html"', rendered)
        self.assertIn('data-locator="d01"', rendered)
        self.assertIn('aria-label="查看來源 A，項目 01 &lt;figure&gt; &amp; &quot;caption&quot;"', rendered)
        self.assertNotIn('<figure>', rendered)
        self.assertNotIn('data-pages', rendered)

    def test_html_citation_rejects_unknown_and_malformed_locators(self):
        for citation in ['[@A:missing]', '[@A:1]', '[@A:d01,c1]', '[@A:../d01]',
                         '[@A:d 01]', '[@A:]', '[@A]', '[@A:d01', '[@X:d01]']:
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                common.render_citations(citation, {'A': self.source})

    def test_pdf_citation_markup_and_printed_pages_are_unchanged(self):
        sources = {'H': {'pdf_pages': 9, 'printed_start': 34},
                   'W': {'pdf_pages': 14, 'printed_start': 88, 'printed_prefix': 'e'}}
        self.assertEqual(common.render_citations('[@H:1-3,9]', sources),
                         '<button type="button" class="citation" data-source="H" data-pages="1-3,9" aria-label="查看來源 H，頁 34–36, 42">H · 34–36, 42</button>')
        self.assertIn('W · e88–e89', common.render_citations('[@W:1-2]', sources))
        for citation in ['[@H:d01]', '[@H:1--2]', '[@W:15]']:
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                common.render_citations(citation, sources)

    def test_html_source_requires_valid_locators_and_safe_public_path(self):
        record = self.root / '02_sources/records/atlas.md'
        record.parent.mkdir(parents=True)
        for extra in [{'locators': {}}, {'locators': {'d01': ''}},
                      {'locators': {'../d01': 'Invalid'}},
                      {'public_path': 'private/atlas.html'},
                      {'public_path': '03_outputs/web/../../private/atlas.html'},
                      {'public_path': 'C:/private/atlas.html'}]:
            record.write_text('---\n' + yaml.safe_dump(dict(self.source, **extra)) + '---\n', encoding='utf-8')
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                common.load_sources(self.root)

    def test_metadata_only_html_source_can_omit_public_path(self):
        self.source.pop('public_path')
        record = self.root / '02_sources/records/atlas.md'
        record.parent.mkdir(parents=True)
        record.write_text('---\n' + yaml.safe_dump(self.source, allow_unicode=True) + '---\n', encoding='utf-8')
        loaded = common.load_sources(self.root)
        self.assertIn('data-locator="d01"', common.render_citations('[@A:d01]', loaded))

    def test_missing_public_reference_or_locator_preserves_existing_site(self):
        self.prepare_build('Claim [@A:d01]')
        public = self.root / self.source['public_path']
        target = self.root / '.build/site'
        target.mkdir(parents=True)
        (target / 'index.html').write_text('last-valid-site', encoding='utf-8')
        for contents in ['<h1 id="d01">Item 01</h1>', None]:
            if contents is None:
                public.unlink()
            else:
                public.write_text(contents, encoding='utf-8')
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                build_site.build_site(self.root)
            self.assertEqual((target / 'index.html').read_text(encoding='utf-8'), 'last-valid-site')

    def test_staged_build_rewrites_media_and_exports_only_public_citation_fields(self):
        self.prepare_build('## Topic\nClaim [@A:d01]\n\n![Description](../../assets/images/atlas%20figure.svg#detail)\n')
        image = self.root / 'assets/images/atlas figure.svg'
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_text('<svg xmlns="http://www.w3.org/2000/svg"><g id="detail"/></svg>', encoding='utf-8')
        target = build_site.build_site(self.root)
        page = (target / '03_outputs/web/atlas/index.html').read_text(encoding='utf-8')
        self.assertIn('src="../../../assets/images/atlas%20figure.svg#detail"', page)
        self.assertTrue((target / 'assets/images/atlas figure.svg').exists())
        parser = common.PlainHTML()
        parser.feed(page)
        self.assertIn('../../../assets/images/atlas%20figure.svg#detail', parser.links)
        import re
        payload = json.loads(re.search(r'id="citation-data">(.*?)</script>', page, re.S).group(1))['A']
        self.assertEqual(payload['locator_type'], 'html')
        self.assertEqual(payload['locators']['d01'], self.source['locators']['d01'])
        self.assertEqual(payload['public_path'], '03_outputs/web/resources/atlas.html')
        self.assertNotIn('local_path', payload)
        self.assertNotIn('DO-NOT-PUBLISH', page)
        self.assertEqual(lint.check_html(target), [])

    def test_external_public_image_url_is_preserved(self):
        self.prepare_build('![External](https://example.org/figure.png?size=2&mode=public)')
        target = build_site.build_site(self.root)
        page = (target / '03_outputs/web/atlas/index.html').read_text(encoding='utf-8')
        self.assertIn('src="https://example.org/figure.png?size=2&amp;mode=public"', page)

    def test_private_raw_missing_and_escaping_media_fail_lint_and_preserve_site(self):
        self.prepare_build('Initial content.')
        for folder in ['private', '02_sources/raw', '00_inbox']:
            path = self.root / folder / 'figure.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'PRIVATE-IMAGE')
        target = self.root / '.build/site'
        target.mkdir(parents=True)
        (target / 'index.html').write_text('last-valid-site', encoding='utf-8')
        original = self.doc.read_text(encoding='utf-8')
        for media in ['../../private/figure.png', '../../02_sources/raw/figure.png',
                      '../../00_inbox/figure.png', '../../assets/images/missing.png',
                      '../../../outside.png', 'file:///C:/private/figure.png']:
            self.doc.write_text(original + '\n![Image](' + media + ')', encoding='utf-8')
            with self.subTest(media=media):
                self.assertTrue(lint.lint(self.root, check_site=False))
                with self.assertRaises(ValueError):
                    build_site.build_site(self.root)
                self.assertEqual((target / 'index.html').read_text(encoding='utf-8'), 'last-valid-site')
                self.assertFalse(list(target.rglob('figure.png')))

    def test_unpublished_wiki_media_is_also_validated(self):
        self.prepare_build('![Image](../../private/missing.png)', publish=False)
        errors = lint.lint(self.root, check_site=False)
        self.assertTrue(errors)
        self.assertTrue(any('media' in e.lower() for e in errors))

    def test_rewriting_real_image_attributes_preserves_caption_text(self):
        image = self.root / 'assets/images/figure.svg'
        image.parent.mkdir(parents=True)
        image.write_text('<svg/>', encoding='utf-8')
        content = '<img alt="Text src=\'../../private/caption.png\'" data-src="placeholder" src=../../assets/images/figure.svg>'
        rendered = common.rewrite_media(content, self.root, '01_wiki/concepts/topic.md', '03_outputs/web/atlas/index.html')
        self.assertIn('alt="Text src=\'../../private/caption.png\'"', rendered)
        self.assertIn('data-src="placeholder"', rendered)
        self.assertIn('src="../../../assets/images/figure.svg"', rendered)

    def test_picture_srcset_is_rebased_and_private_candidates_are_rejected(self):
        image = self.root / 'assets/images/figure.svg'
        image.parent.mkdir(parents=True)
        image.write_text('<svg/>', encoding='utf-8')
        content = '<picture><source srcset="../../assets/images/figure.svg 1x, https://example.org/large.svg 2x"></picture>'
        rendered = common.rewrite_media(content, self.root, '01_wiki/concepts/topic.md', '03_outputs/web/atlas/index.html')
        self.assertIn('srcset="../../../assets/images/figure.svg 1x, https://example.org/large.svg 2x"', rendered)
        with self.assertRaises(ValueError):
            common.rewrite_media('<img srcset="../../private/figure.png 2x">', self.root, '01_wiki/concepts/topic.md')

    def test_approach_and_map_pages_can_be_published(self):
        for kind in ['approach', 'map']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                self.root = Path(temp)
                self.prepare_build('## Topic\nLearning route [@A:c1]', type=kind)
                target = build_site.build_site(self.root)
                index = json.loads((target / 'assets/site/search-index.json').read_text(encoding='utf-8'))
                self.assertEqual(index[0]['type'], kind)


if __name__ == '__main__':
    unittest.main()
