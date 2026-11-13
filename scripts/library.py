"""Derive public browsing views from published canonical pages and atlas metadata."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import common
import yaml


class FirstImage(HTMLParser):
    def __init__(self):
        super().__init__();self.image='';self.alt=''

    def handle_starttag(self,tag,attrs):
        if tag=='img' and not self.image:
            a=dict(attrs);self.image=a.get('src','');self.alt=a.get('alt','')


def plain(text):
    text=common.CITE.sub('',text)
    parser=common.PlainHTML();parser.feed(text)
    text=' '.join(parser.text)
    text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
    return re.sub(r'\s+',' ',text.replace('**','').replace('###','')).strip()


def _section(body,anchor):
    match=re.search(r'^## [^\n]*\{#'+re.escape(anchor)+r'\}\s*$',body,re.M)
    if not match:
        raise ValueError('Atlas canonical anchor is missing: '+anchor)
    remaining=body[match.end():]
    return re.split(r'^## ',remaining,maxsplit=1,flags=re.M)[0]


def _atlas(root,nav,sources,current):
    path=Path(root)/'config/atlas.yml'
    if not path.exists():return [],[]
    data=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    groups=data.get('groups',[]);entries=data.get('entries',[])
    if not isinstance(groups,list) or not isinstance(entries,list):
        raise ValueError('Atlas groups and entries must be lists')
    group_ids={g['id'] for g in groups};by_id={p['id']:p for p in nav}
    seen=set();result=[]
    for entry in entries:
        identity=(entry['source'],entry['id'])
        if identity in seen:raise ValueError('Duplicate atlas entry')
        seen.add(identity)
        page=by_id.get(entry['page_id'])
        if not page:raise ValueError('Atlas target is not a published canonical page: '+entry['page_id'])
        if entry['group'] not in group_ids:raise ValueError('Unknown atlas group')
        citation=f'[@{entry["source"]}:{entry["id"]}]'
        common.render_citations(citation,sources)
        section=_section(page['body'],entry['anchor'])
        # One canonical page can contain several source cards (e.g. syphilis stages).
        heading=re.search(r'^## (.*?) \{#'+re.escape(entry['anchor'])+r'\}',page['body'],re.M)
        title=heading[1] if heading else page['title']
        focus=re.search(r'\*\*(.*?)\*\*',section,re.S)
        verification=re.search(r'^### 驗證方法\s*\n(.*?)(?=^### |\Z)',section,re.S|re.M)
        rebased=common.rewrite_media(section,root,page['path'],current)
        parser=FirstImage();parser.feed(rebased)
        credit={}
        if parser.image:
            filename=Path(parser.image).stem
            record=Path(root)/'assets/records'/('dermatology-'+filename+'.yml')
            if record.exists():
                asset=yaml.safe_load(record.read_text(encoding='utf-8'))
                if not asset.get('public_allowed'):raise ValueError('Atlas preview asset is not public')
                authors=asset.get('authors_as_provided',[])
                attribution=asset.get('attribution_as_provided',[])
                credit=dict(attribution=(' · '.join(attribution)).replace(' · 原圖／出處',''),source_url=asset.get('source_url',''),licence=asset.get('licence',''),licence_url=asset.get('licence_url',''))
                if asset.get('licence')=='CC BY-SA 3.0':credit['attribution']='Elizabeth M. Dugan, Adam M. Huber, Frederick W. Miller, Lisa G. Rider / IMACS Group'
        result.append(dict(id=entry['id'],source=entry['source'],page_id=page['id'],title=title,title_en=page.get('title_en',''),group=entry['group'],url=page['url']+'#'+entry['anchor'],focus=plain(focus[1]) if focus else page['summary'],verification=plain(verification[1]) if verification else '',image=parser.image,image_alt=parser.alt,credit=credit,search=plain(title+' '+page.get('title_en','')+' '+' '.join(page.get('aliases',[]))+' '+section)))
    return result,groups


def library_context(root,nav,sources,current='index.html'):
    entries,groups=_atlas(root,nav,sources,current)
    concepts=[p for p in nav if p.get('type')=='concept' and p.get('content_kind')!='chapter']
    reasoning=[p for p in nav if p.get('type') in ('approach','comparison')]
    resources=[p for p in nav if p.get('type')=='source_summary']
    specialties={}
    for page in nav:
        keys=page.get('specialties') or (['dermatology'] if page.get('web_topic')=='sjs-ten' else [])
        for key in keys:specialties.setdefault(key,[]).append(page)
    cards=[]
    for key,pages in specialties.items():
        entry=next((p for p in pages if p.get('content_kind')=='specialty' and p.get('web_file')=='index.html'),None)
        if not entry:entry=next((p for p in pages if p.get('web_file')=='index.html'),pages[0])
        cards.append(dict(id=key,title=entry.get('specialty_label',key),url=entry['url'],count=len(pages),summary=entry.get('summary','')))
    indexes={name:next((p for p in nav if p.get('view')==view),None) for name,view in [('concept_index','concept-library'),('reasoning_index','reasoning'),('atlas_index','atlas')]}
    return dict(concepts=concepts,reasoning=reasoning,resources=resources,specialties=cards,atlas_entries=entries,atlas_groups=groups,**indexes)
