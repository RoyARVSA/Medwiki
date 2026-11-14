"""Navigation contracts use canonical metadata, never the physical clinical folder."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import yaml
import json
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    navigation = importlib.import_module('navigation')
except ModuleNotFoundError:
    navigation = None


def landing(key, number=0):
    return dict(id='map-'+key, title=key+'學習導航', type='map', content_kind='specialty',
                specialties=[key], specialty_label=key, title_en=key.title(),
                summary='科別入口', view='specialty', order=number,
                url='03_outputs/web/'+key+'/index.html')


def page(identity, specialties, **extra):
    result = dict(id=identity, title=identity, title_en=identity.title(), type='concept',
                  content_kind='disease', specialties=specialties, summary='範圍',
                  url='03_outputs/web/shared/'+identity+'.html')
    result.update(extra)
    return result


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def model(self, pages, catalog=None):
        self.assertIsNotNone(navigation, 'specialty navigation model must exist')
        return navigation.build_navigation(self.root, pages, catalog)

    def test_twenty_specialties_and_hundreds_of_diseases_have_bounded_home_input(self):
        pages = [landing('specialty-'+str(i), i) for i in range(20)]
        pages += [page('disease-'+str(i), ['specialty-'+str(i % 20)]) for i in range(600)]
        model = self.model(pages)
        self.assertEqual(len(model['specialties']), 20)
        self.assertEqual([len(chunk) for chunk in model['specialty_pages']], [8, 8, 4])
        self.assertEqual(len(model['home_specialties']), 8)
        self.assertEqual([s['count'] for s in model['specialties']], [30] * 20)

    def test_large_library_home_renders_eight_visible_tiles_and_slim_return_registry(self):
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        import common
        pages = [landing('specialty-'+str(i), i) for i in range(20)]
        pages += [page('disease-'+str(i), ['specialty-'+str(i % 20)], body='MEDICAL-BODY-SENTINEL') for i in range(600)]
        model = self.model(pages)
        project = Path(__file__).resolve().parents[1]
        env = Environment(loader=FileSystemLoader(project/'04_templates/site'), autoescape=select_autoescape(['html']))
        env.globals.update(rel=common.relative_url, asset=lambda target, current: target, browse=model)
        html = env.get_template('home.html').render(current='index.html')
        tiles = re.findall(r'<a\b[^>]*data-specialty-card\b[^>]*>', html)
        self.assertEqual(len(tiles), 20)
        self.assertEqual(sum(not re.search(r'\bhidden\b', tile) for tile in tiles), 8)
        self.assertNotIn('MEDICAL-BODY-SENTINEL', html)
        registry = json.loads(re.search(r'<script[^>]*id="specialty-registry"[^>]*>(.*?)</script>', html, re.S)[1])
        self.assertEqual(len(registry), 20)
        self.assertTrue(all(set(value) == {'title', 'url'} for value in registry.values()))

    def test_shared_disease_reuses_canonical_url_without_becoming_cross_complaint(self):
        disease = page('shared-disease', ['dermatology', 'rheumatology'])
        model = self.model([landing('dermatology'), landing('rheumatology'), disease])
        for key in disease['specialties']:
            entries = model['by_specialty'][key]['sections'][0]['pages']
            self.assertEqual([(p['id'], p['url']) for p in entries], [(disease['id'], disease['url'])])
        self.assertEqual(model['shared'], [])

    def test_unknown_or_malformed_specialty_does_not_fabricate_a_landing(self):
        with self.assertRaisesRegex(ValueError, 'Unknown specialty'):
            self.model([landing('dermatology'), page('topic', ['psychiatry'])])
        with self.assertRaises(ValueError):
            self.model([landing('dermatology'), page('topic', 'dermatology')])
        unclassified = page('without-specialty', [])
        self.assertEqual(self.model([unclassified])['specialties'], [])

    def test_specialty_identifiers_match_browser_context_validation(self):
        with self.assertRaises(ValueError):
            self.model([landing('1-specialty')])

    def test_explicit_chapter_parents_must_exist_and_not_point_to_self(self):
        parent = page('parent', [], web_topic='topic')
        for identity in ['missing', 'child']:
            child = page('child', [], content_kind='chapter', parent_id=identity, web_topic='topic')
            with self.assertRaises(ValueError):
                self.model([parent, child])

    def test_sections_are_scoped_unique_and_sources_do_not_become_diseases(self):
        disease = page('disease', ['dermatology'], catalog_role='work', web_topic='topic')
        chapter = page('chapter', ['dermatology'], content_kind='chapter')
        approach = page('approach', ['dermatology'], type='approach', cross_specialty=True)
        resource = page('resource', ['psychiatry'], type='source_summary')
        model = self.model([landing('dermatology'), landing('psychiatry'), disease, chapter, approach, resource])
        derm = model['by_specialty']['dermatology']
        sections = {s['id']: [p['id'] for p in s['pages']] for s in derm['sections']}
        self.assertEqual(sections['diseases'], ['disease'])
        self.assertEqual(sections['reasoning'], ['approach'])
        self.assertEqual(sections['projects'], ['disease'])
        self.assertEqual(sections['resources'], [])
        self.assertEqual(derm['count'], 2, 'A work also listed as disease is counted once; reading chapters do not inflate the directory')
        self.assertEqual([p['id'] for p in model['shared']], ['approach'])

    def test_source_publication_year_and_guideline_version_stay_distinct(self):
        folder = self.root / '02_sources/records'
        folder.mkdir(parents=True)
        (folder/'example.md').write_text('---\nsource_id: source-guideline\nshort_id: C\nsource_type: guideline\nyear: 2024\nversion: 2023 update\nprocessing_status: complete\nprocessed_ranges: [PDF 1-20]\n---\n', encoding='utf-8')
        resource = page('resource', ['psychiatry'], type='source_summary', source_ids=['source-guideline'])
        entry = self.model([landing('psychiatry'), resource])['resources'][0]
        self.assertEqual(entry['year_label'], 2024)
        self.assertEqual(entry['version_label'], '2023 update')
        self.assertEqual(entry['processing_label'], '已完整處理')
        self.assertEqual(entry['processed_ranges'], ['PDF 1-20'])

    def test_generated_chapters_are_not_works_and_manual_formats_group(self):
        work = page('topic', ['dermatology'], url='03_outputs/web/topic/index.html', web_topic='topic', catalog_role='work')
        chapter = page('chapter', ['dermatology'], url='03_outputs/web/topic/chapter.html', web_topic='topic', content_kind='chapter')
        catalog = [
            dict(path=work['url'], kind='html', title='Work'),
            dict(path=chapter['url'], kind='html', title='Chapter'),
            dict(path='03_outputs/slides/topic/topic.pdf', kind='pdf', title='topic'),
            dict(path='03_outputs/web/lecture/index.html', kind='html', title='Manual lecture'),
            dict(path='03_outputs/slides/lecture/lecture.pptx', kind='pptx', title='lecture'),
            dict(path='03_outputs/slides/lecture/lecture.pdf', kind='pdf', title='lecture'),
            dict(path='03_outputs/web/layout-previews/index.html', kind='html', title='Previews'),
        ]
        works = self.model([landing('dermatology'), work, chapter], catalog)['outputs']
        self.assertEqual(len(works), 2)
        known = next(w for w in works if w['id'] == 'topic')
        self.assertEqual({f['kind'] for f in known['formats']}, {'html', 'pdf'})
        manual = next(w for w in works if w['title'] == 'Manual lecture')
        self.assertEqual({f['kind'] for f in manual['formats']}, {'html', 'pdf', 'pptx'})
        self.assertEqual(manual['specialties'], [], 'Manual file names do not imply a medical specialty')
        self.assertFalse(any(f['url'] == chapter['url'] for w in works for f in w['formats']))

    def test_manual_rename_delete_and_format_config_are_respected(self):
        entry = dict(path='03_outputs/web/manual/index.html', kind='html', title='Manual')
        self.assertEqual(len(self.model([], [entry])['outputs']), 1)
        self.assertEqual(self.model([], [])['outputs'], [])
        renamed = dict(entry, path='03_outputs/web/renamed/index.html')
        self.assertNotEqual(self.model([], [entry])['outputs'][0]['id'], self.model([], [renamed])['outputs'][0]['id'])
        work = page('work', [], catalog_role='work')
        self.assertEqual(self.model([work], [])['outputs'], [])

    def test_standalone_manual_formats_are_grouped_without_required_metadata(self):
        catalog = [dict(path='03_outputs/web/lecture.html', kind='html', title='Lecture'),
                   dict(path='03_outputs/slides/lecture.pdf', kind='pdf', title='lecture')]
        works = self.model([], catalog)['outputs']
        self.assertEqual(len(works), 1)
        self.assertEqual({fmt['kind'] for fmt in works[0]['formats']}, {'html', 'pdf'})

    def test_nested_manual_work_folders_do_not_collapse_into_their_parent_course(self):
        catalog = [dict(path='03_outputs/web/course/unit-a/index.html', kind='html', title='Unit A'),
                   dict(path='03_outputs/slides/course/unit-a/unit-a.pdf', kind='pdf', title='unit-a'),
                   dict(path='03_outputs/web/course/unit-b/index.html', kind='html', title='Unit B')]
        works = self.model([], catalog)['outputs']
        self.assertEqual(len(works), 2)
        unit_a = next(w for w in works if w['title'] == 'Unit A')
        self.assertEqual({f['kind'] for f in unit_a['formats']}, {'html', 'pdf'})

    def test_reusable_questions_are_discoverable_with_specialty_reasoning(self):
        question = page('question', ['psychiatry'], type='question')
        specialty = self.model([landing('psychiatry'), question])['specialties'][0]
        self.assertEqual([p['id'] for p in specialty['sections'][1]['pages']], ['question'])

    def test_untrusted_routes_cannot_enter_registry_or_formats(self):
        malicious = landing('dermatology')
        malicious['url'] = 'https://outside.example/index.html'
        with self.assertRaises(ValueError):
            self.model([malicious])
        with self.assertRaises(ValueError):
            self.model([], [dict(path='private/patient.pdf', kind='pdf', title='Private')])

    def test_legacy_concept_directory_keeps_unclassified_canonical_pages_accessible(self):
        topic = page('unclassified', [])
        model = self.model([topic])
        descriptor = navigation.directory_for_page(dict(id='legacy', title='舊目錄', view='concept-library'), model)
        self.assertEqual([p['id'] for p in descriptor['pages']], ['unclassified'])

    def test_sidebar_groups_only_explicit_chapters_instead_of_all_diseases(self):
        disease = page('one', ['dermatology'], web_topic='dermatology')
        other = page('two', ['dermatology'], web_topic='dermatology')
        self.assertEqual(navigation.topic_navigation([disease, other], disease), [disease])
        child = page('one-child', ['dermatology'], web_topic='shared', content_kind='chapter', parent_id='one')
        self.assertEqual({p['id'] for p in navigation.topic_navigation([disease, other, child], child)}, {'one', 'one-child'})


class NavigationBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project = Path(__file__).resolve().parents[1]
        shutil.copytree(project/'04_templates/site', self.root/'04_templates/site')
        shutil.copytree(project/'assets', self.root/'assets')

    def write_page(self, data, body='## 內容\n\n學習內容。'):
        metadata = dict(created='2026-11-14', updated='2026-11-14', summary='範圍',
                        tags=[], source_ids=[], review_status='not_reviewed', conflict_status='none', publish=True)
        metadata.update(data)
        p = self.root/'01_wiki/maps'/(metadata['id']+'.md')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('---\n'+yaml.safe_dump(metadata, allow_unicode=True)+'---\n\n'+body, encoding='utf-8')

    def test_global_directories_exist_and_work_catalog_does_not_list_generated_chapters(self):
        self.write_page(dict(id='dermatology', title='皮膚科', type='map', content_kind='specialty',
                             specialties=['dermatology'], specialty_label='皮膚科', view='specialty',
                             web_topic='dermatology', web_file='index.html'))
        self.write_page(dict(id='project', title='共同專題', type='concept', specialties=['dermatology'],
                             catalog_role='work', web_topic='project', web_file='index.html'))
        self.write_page(dict(id='chapter', title='章節不另列作品', type='concept', specialties=['dermatology'],
                             content_kind='chapter', web_topic='project', web_file='chapter.html', order=2))
        import build_site
        build_site.build_site(self.root)
        import re
        target = self.root/'.build/site'
        for route in navigation.ROUTES.values():
            self.assertTrue((target/route).exists(), route)
        output = (target/navigation.ROUTES['outputs']).read_text(encoding='utf-8')
        output_without_scripts = re.sub(r'<script\b.*?</script>', '', output, flags=re.S)
        self.assertIn('共同專題', output_without_scripts)
        self.assertNotIn('章節不另列作品', output_without_scripts)

    def test_reserved_directory_never_overwrites_manual_page_or_promotes_failure(self):
        route = self.root/'03_outputs/web/library/resources.html'
        route.parent.mkdir(parents=True)
        route.write_text('<title>Manual resources</title>', encoding='utf-8')
        prior = self.root/'.build/site/index.html'
        prior.parent.mkdir(parents=True)
        prior.write_text('last-valid-site', encoding='utf-8')
        import build_site
        with self.assertRaisesRegex(ValueError, 'overwrite manual output'):
            build_site.build_site(self.root)
        self.assertEqual(route.read_text(encoding='utf-8'), '<title>Manual resources</title>')
        self.assertEqual(prior.read_text(encoding='utf-8'), 'last-valid-site')


if __name__ == '__main__':
    unittest.main()
