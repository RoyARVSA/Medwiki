"""Regression tests for real catalog/build behavior in an isolated fixture repo."""
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    common = importlib.import_module('common')
    build = importlib.import_module('build_site')
except ModuleNotFoundError:
    common = build = None


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.web = self.root / '03_outputs/web/topic'
        self.web.mkdir(parents=True)
        (self.web / 'index.html').write_text('<html><title>Topic</title><h1>Topic</h1></html>', encoding='utf-8')

    def api(self):
        self.assertIsNotNone(common, 'catalog and safe build API must be implemented')

    def test_manual_files_are_found_but_support_assets_are_not(self):
        self.api()
        (self.web / 'assets').mkdir()
        (self.web / 'assets/support.html').write_text('<title>Support</title>')
        slides = self.root / '03_outputs/slides'
        slides.mkdir(parents=True)
        (slides / 'lecture.pptx').write_bytes(b'presentation-fixture')
        items = common.discover_outputs(self.root)
        self.assertEqual({x['path'] for x in items}, {'03_outputs/web/topic/index.html', '03_outputs/slides/lecture.pptx'})
        self.assertEqual(next(x['title'] for x in items if x['kind'] == 'html'), 'Topic')

    def test_rescan_reflects_rename_and_deletion_without_duplicate_entries(self):
        self.api()
        first = common.discover_outputs(self.root)
        self.assertEqual(first, common.discover_outputs(self.root))
        (self.web / 'index.html').rename(self.web / 'renamed.html')
        self.assertEqual([x['path'] for x in common.discover_outputs(self.root)], ['03_outputs/web/topic/renamed.html'])
        (self.web / 'renamed.html').unlink()
        self.assertEqual(common.discover_outputs(self.root), [])

    def test_bad_citation_page_is_rejected_instead_of_invented(self):
        self.api()
        src = {'H': {'pdf_pages': 9, 'printed_start': 34, 'source_id': 'h'}}
        with self.assertRaises(ValueError):
            common.render_citations('Claim [@H:10]', src)
        rendered = common.render_citations('Claim [@H:3]', src)
        self.assertIn('36', rendered)
        self.assertNotIn('raw/', rendered)

    def test_duplicate_source_identifier_is_rejected(self):
        self.api()
        p=self.root/'02_sources/records';p.mkdir(parents=True)
        (p/'one.md').write_text('---\nsource_id: same\nshort_id: A\n---\n')
        (p/'two.md').write_text('---\nsource_id: same\nshort_id: B\n---\n')
        with self.assertRaises(ValueError):common.load_sources(self.root)

    def test_cited_source_must_be_declared_for_provenance_and_footer(self):
        from lint import lint
        records = self.root / '02_sources/records'
        records.mkdir(parents=True)
        (records / 'source.md').write_text(
            '---\nsource_id: source-a\nshort_id: A\npdf_pages: 2\nprinted_start: 1\n---\n', encoding='utf-8')
        self.add_page('citation')
        page = self.root / '01_wiki/concepts/citation.md'
        page.write_text(page.read_text(encoding='utf-8') + '\nClaim [@A:1]\n', encoding='utf-8')
        self.assertTrue(any('cited source absent from source_ids: source-a' in error
                            for error in lint(self.root, check_site=False)))
        page.write_text(page.read_text(encoding='utf-8').replace('source_ids: []',
                        'source_ids: [source-a]'), encoding='utf-8')
        self.assertEqual(lint(self.root, check_site=False), [])

    def test_configured_output_format_is_respected(self):
        self.api()
        config = self.root / 'config'
        config.mkdir()
        (config / 'site.yml').write_text('formats: [pdf]\n', encoding='utf-8')
        self.assertEqual(common.discover_outputs(self.root), [])

    def prepare_templates(self):
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project / '04_templates/site', self.root / '04_templates/site', dirs_exist_ok=True)
        shutil.copytree(project / 'assets', self.root / 'assets', dirs_exist_ok=True)

    def add_page(self, name='topic', **extra):
        import yaml
        p = self.root / '01_wiki/concepts'
        p.mkdir(parents=True, exist_ok=True)
        meta = dict(id=name, title='Asthma topic', title_en='Asthma', type='concept', created='2026-11-12', updated='2026-11-12', summary='Airway learning', tags=['respiratory'], source_ids=[], review_status='not_reviewed', conflict_status='none', publish=True, web_topic='asthma', topic_title='氣喘', web_file=name+'.html', nav_title='評估', order=1, eyebrow='RESPIRATORY')
        meta.update(extra)
        (p / (name+'.md')).write_text('---\n'+yaml.safe_dump(meta, allow_unicode=True)+'---\n## Assessment\nLearning content.', encoding='utf-8')

    def test_build_uses_source_catalog_config(self):
        self.api(); self.prepare_templates()
        p=self.root/'config';p.mkdir()
        (p/'site.yml').write_text('formats: [pdf]\n',encoding='utf-8')
        build.build_site(self.root)
        text=(self.root/'.build/site/index.html').read_text(encoding='utf-8')
        self.assertNotIn('class="output-item"',text)

    def test_stale_manual_replacement_is_preserved_in_deployment(self):
        self.api();self.prepare_templates()
        manifest=self.root/'.build/generated-pages.json';manifest.parent.mkdir()
        manifest.write_text('["03_outputs/web/topic/index.html"]')
        build.build_site(self.root)
        self.assertTrue((self.root/'.build/site/03_outputs/web/topic/index.html').exists())

    def test_root_relative_asset_is_rejected_for_project_hosting(self):
        self.api()
        from lint import check_html
        (self.root/'app.js').write_text('')
        (self.web/'index.html').write_text('<script src="/app.js"></script>')
        self.assertTrue(check_html(self.root))

    def test_new_topic_has_own_labels_and_no_fabricated_comparison_link(self):
        self.api();self.prepare_templates()
        self.add_page(web_file='index.html',conflict_status='open')
        build.build_site(self.root)
        page=(self.root/'.build/site/03_outputs/web/asthma/index.html').read_text(encoding='utf-8')
        home=(self.root/'.build/site/index.html').read_text(encoding='utf-8')
        self.assertIn('氣喘',page)
        self.assertNotIn('SJS / TEN',page)
        self.assertNotIn('../sjs-ten/evidence.html',page)
        self.assertIn('03_outputs/web/asthma/index.html',home)

    def test_duplicate_id_fails_before_promoting_site(self):
        self.api();self.prepare_templates()
        self.add_page('first');self.add_page('second',id='first',order=2)
        dest=self.root/'.build/site';dest.mkdir(parents=True)
        (dest/'index.html').write_text('last-valid-site')
        with self.assertRaises(ValueError):build.build_site(self.root)
        self.assertEqual((dest/'index.html').read_text(),'last-valid-site')

    def test_layout_previews_reuse_content_without_changing_source(self):
        self.api();self.prepare_templates();self.add_page('treatment')
        config=self.root/'config';config.mkdir()
        (config/'layout-previews.yml').write_text('enabled: true\nsource_id: treatment\n')
        source=self.root/'01_wiki/concepts/treatment.md';before=source.read_bytes()
        build.build_site(self.root)
        import re
        original=(self.root/'.build/site/03_outputs/web/asthma/treatment.html').read_text(encoding='utf-8')
        content=re.search(r'<article class="prose">(.*?)</article>',original,re.S).group(1)
        for key in ['a','b','c']:
            p=self.root/'.build/site/03_outputs/web/layout-previews'/('style-'+key+'.html')
            self.assertTrue(p.exists())
            actual=re.search(r'<article class="prose">(.*?)</article>',p.read_text(encoding='utf-8'),re.S).group(1)
            self.assertEqual(content,actual)
        self.assertEqual(source.read_bytes(),before)
        self.assertTrue((self.root/'.build/site/03_outputs/web/layout-previews/index.html').exists())

    def test_preview_article_links_are_rebased_to_the_original_topic(self):
        self.api();self.prepare_templates();self.add_page('treatment');self.add_page('next',order=2)
        source=self.root/'01_wiki/concepts/treatment.md'
        source.write_text(source.read_text(encoding='utf-8')+'\n[Next](next.md)\n',encoding='utf-8')
        p=self.root/'config';p.mkdir()
        (p/'layout-previews.yml').write_text('enabled: true\nsource_id: treatment\n')
        build.build_site(self.root)
        page=(self.root/'.build/site/03_outputs/web/layout-previews/style-a.html').read_text(encoding='utf-8')
        self.assertIn('href="../asthma/next.html"',page)

    def test_missing_layout_preview_source_preserves_existing_site(self):
        self.api();self.prepare_templates()
        p=self.root/'config';p.mkdir()
        (p/'layout-previews.yml').write_text('enabled: true\nsource_id: missing\n')
        dest=self.root/'.build/site';dest.mkdir(parents=True)
        (dest/'index.html').write_text('last-valid-site')
        with self.assertRaises(ValueError):build.build_site(self.root)
        self.assertEqual((dest/'index.html').read_text(),'last-valid-site')

    def test_updated_stylesheet_gets_new_browser_cache_key(self):
        self.api();self.prepare_templates()
        import re
        build.build_site(self.root)
        home=self.root/'.build/site/index.html'
        old=re.search(r'href="([^"]*site\.css[^"]*)"',home.read_text(encoding='utf-8')).group(1)
        style=self.root/'assets/site/site.css'
        style.write_text(style.read_text(encoding='utf-8')+'\n/* changed style */',encoding='utf-8')
        build.build_site(self.root)
        new=re.search(r'href="([^"]*site\.css[^"]*)"',home.read_text(encoding='utf-8')).group(1)
        self.assertNotEqual(old,new)

    def test_local_fragments_must_resolve_to_existing_heading(self):
        self.api()
        from lint import check_html
        (self.web / 'index.html').write_text('<a href="#missing">Jump</a>', encoding='utf-8')
        self.assertTrue(check_html(self.root))

    def test_relative_urls_work_when_hosted_under_project_prefix(self):
        self.api()
        self.assertEqual(common.relative_url('assets/site/site.css', '03_outputs/web/topic/index.html'), '../../../assets/site/site.css')
        self.assertEqual(common.relative_url('03_outputs/web/topic/index.html', 'index.html'), '03_outputs/web/topic/index.html')

    def test_build_does_not_copy_private_raw_or_code_files(self):
        self.api()
        self.assertIsNotNone(build)
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project / '04_templates/site', self.root / '04_templates/site')
        shutil.copytree(project / 'assets', self.root / 'assets')
        for folder in ['private', '02_sources/raw', '00_inbox']:
            p = self.root / folder
            p.mkdir(parents=True, exist_ok=True)
            (p / 'secret.pdf').write_bytes(b'PRIVATE-CONTENT')
        (self.web / 'internal.py').write_text('secret = True')
        build.build_site(self.root)
        target = self.root / '.build/site'
        self.assertTrue((target / 'index.html').exists())
        self.assertTrue((target / '03_outputs/web/topic/index.html').exists())
        self.assertFalse(list(target.rglob('secret.pdf')))
        self.assertFalse(list(target.rglob('*.py')))
        self.assertNotIn('PRIVATE-CONTENT', (target / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('id="local-search-data"', (target / 'index.html').read_text(encoding='utf-8'))

    def test_existing_output_remains_when_new_page_has_invalid_citation(self):
        self.api()
        self.assertIsNotNone(build)
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project / '04_templates/site', self.root / '04_templates/site')
        dest = self.root / '.build/site'
        dest.mkdir(parents=True)
        (dest / 'index.html').write_text('last-valid-site')
        p = self.root / '01_wiki/concepts'
        p.mkdir(parents=True)
        (p / 'bad.md').write_text('---\nid: bad\ntitle: Bad\npublish: true\nweb_file: bad.html\n---\nBroken [@X:3]', encoding='utf-8')
        with self.assertRaises(ValueError):
            build.build_site(self.root)
        self.assertEqual((dest / 'index.html').read_text(), 'last-valid-site')


if __name__ == '__main__':
    unittest.main()
