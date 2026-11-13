"""Public navigation derives views from canonical pages, never source originals."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import yaml

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    library=importlib.import_module('library')
except ModuleNotFoundError:
    library=None


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'config').mkdir()
        self.page=dict(id='concept-example',title='範例',type='concept',content_kind='disease',specialties=['dermatology'],summary='學習範圍',aliases=['Example'],tags=['dermatology'],path='01_wiki/concepts/example.md',url='03_outputs/web/dermatology/example.html',body='## 範例 {#atlas-d01}\n\n**辨認線索。** [@A:d01]\n\n### 驗證方法\n\n需其他證據。 [@A:d01]\n')
        self.sources={'A':dict(source_id='source-a',locator_type='html',locators={'d01':'主題 01'})}

    def context(self,nav=None):
        self.assertIsNotNone(library,'library context module must exist')
        return library.library_context(self.root,nav or [self.page],self.sources,'03_outputs/web/dermatology-atlas/index.html')

    def config(self,**extra):
        entry=dict(id='d01',source='A',page_id='concept-example',path='01_wiki/concepts/example.md',anchor='atlas-d01',group='group-a')
        entry.update(extra)
        (self.root/'config/atlas.yml').write_text(yaml.safe_dump(dict(groups=[dict(id='group-a',label='分組')],entries=[entry]),allow_unicode=True),encoding='utf-8')

    def test_same_canonical_url_in_disease_and_atlas_views(self):
        self.config();ctx=self.context()
        self.assertEqual(ctx['concepts'][0]['url'],self.page['url'])
        self.assertEqual(ctx['atlas_entries'][0]['url'],self.page['url']+'#atlas-d01')
        self.assertEqual(ctx['atlas_entries'][0]['focus'],'辨認線索。')

    def test_missing_page_or_anchor_rejected(self):
        self.config(page_id='missing')
        with self.assertRaises(ValueError):self.context()
        self.config(anchor='absent')
        with self.assertRaises(ValueError):self.context()

    def test_unknown_source_and_duplicate_entries_rejected(self):
        self.config(source='UNKNOWN')
        with self.assertRaises(ValueError):self.context()
        self.config();p=self.root/'config/atlas.yml';v=yaml.safe_load(p.read_text(encoding='utf-8'));v['entries']*=2;p.write_text(yaml.safe_dump(v),encoding='utf-8')
        with self.assertRaises(ValueError):self.context()

    def test_image_url_rebased_to_atlas_and_not_replaced_by_private_original(self):
        self.config();p=self.root/'assets/images/example.jpg';p.parent.mkdir(parents=True);p.write_bytes(b'fixture')
        self.page['body']+='\n<img src="../../assets/images/example.jpg" alt="可見外觀">\n'
        entry=self.context()['atlas_entries'][0]
        self.assertEqual(entry['image'],'../../../assets/images/example.jpg')
        self.assertEqual(entry['image_alt'],'可見外觀')
        self.page['body']=self.page['body'].replace('../../assets/images/example.jpg','../../private/patient.jpg')
        with self.assertRaises(ValueError):self.context()

    def test_no_config_still_builds_other_specialties_and_reasoning(self):
        other=dict(self.page,id='approach-example',type='approach',content_kind='approach',specialties=['medicine','dermatology'])
        ctx=self.context([self.page,other])
        self.assertEqual(ctx['atlas_entries'],[])
        self.assertEqual(len(ctx['reasoning']),1)
        self.assertEqual(ctx['reasoning'][0]['id'],'approach-example')

    def test_specialized_directory_omits_toc_for_replaced_markdown(self):
        project=Path(__file__).resolve().parents[1]
        shutil.copytree(project/'04_templates/site',self.root/'04_templates/site')
        shutil.copytree(project/'assets',self.root/'assets')
        page=self.root/'01_wiki/maps/library.md';page.parent.mkdir(parents=True)
        meta=dict(id='library',title='目錄',type='map',created='2026-11-13',updated='2026-11-13',summary='目錄',tags=[],source_ids=[],review_status='not_reviewed',conflict_status='none',publish=True,view='concept-library',web_topic='library',web_file='concepts.html',order=1)
        page.write_text('---\n'+yaml.safe_dump(meta,allow_unicode=True)+'---\n\n## Hidden navigation section\n\nNavigation body is replaced by the generated directory.',encoding='utf-8')
        import build_site
        build_site.build_site(self.root)
        html=(self.root/'.build/site/03_outputs/web/library/concepts.html').read_text(encoding='utf-8')
        self.assertNotIn('href="#hidden-navigation-section"',html)

    def test_conflict_banner_requires_an_explicit_relevant_target(self):
        project=Path(__file__).resolve().parents[1]
        shutil.copytree(project/'04_templates/site',self.root/'04_templates/site')
        shutil.copytree(project/'assets',self.root/'assets')
        folder=self.root/'01_wiki/concepts';folder.mkdir(parents=True)
        meta=dict(id='topic',title='主題',type='concept',created='2026-11-13',updated='2026-11-13',summary='範圍',tags=[],source_ids=[],review_status='not_reviewed',conflict_status='open',publish=True,web_topic='topic',web_file='index.html',order=1)
        (folder/'topic.md').write_text('---\n'+yaml.safe_dump(meta,allow_unicode=True)+'---\n\n## Content\n\nClaim.',encoding='utf-8')
        other=dict(meta,id='unrelated',title='其他比較',type='comparison',conflict_status='none',web_file='other.html',order=2)
        (folder/'other.md').write_text('---\n'+yaml.safe_dump(other,allow_unicode=True)+'---\n\n## Other\n\nDifferent topic.',encoding='utf-8')
        import build_site
        build_site.build_site(self.root)
        html=(self.root/'.build/site/03_outputs/web/topic/index.html').read_text(encoding='utf-8')
        self.assertNotIn('查看比較 →',html,'An unrelated first comparison must not become a conflict resolution link')

    def test_generated_ignore_preserves_user_rules_and_releases_removed_outputs(self):
        import build_site
        helper=getattr(build_site,'update_generated_ignores',None)
        self.assertIsNotNone(helper,'Generated public HTML must be ignored without ignoring manual outputs')
        p=self.root/'.gitignore';p.write_text('/private/\n# user rule\ncustom-cache/\n',encoding='utf-8')
        helper(self.root,['03_outputs/web/topic/generated.html'])
        first=p.read_text(encoding='utf-8')
        self.assertIn('/private/',first);self.assertIn('custom-cache/',first)
        self.assertIn('/03_outputs/web/topic/generated.html',first)
        self.assertNotIn('/03_outputs/web/topic/manual.html',first)
        helper(self.root,[])
        second=p.read_text(encoding='utf-8')
        self.assertNotIn('/03_outputs/web/topic/generated.html',second)
        self.assertEqual(second.count('# BEGIN MEDWIKI GENERATED OUTPUTS'),1)


if __name__=='__main__':unittest.main()
