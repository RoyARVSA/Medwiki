"""Render opt-in layout experiments from an already-rendered public article."""
import json
import posixpath
import re
from urllib.parse import unquote, urlsplit
import yaml
import common

VARIANTS = [
    {'key': 'a', 'name': '學術閱讀', 'english': 'ACADEMIC READER', 'summary': '三欄導覽、完整段落與頁內目錄。適合長時間閱讀與查找。', 'features': ['穩定的三欄結構', '段落連續閱讀', '引用隨文查閱']},
    {'key': 'b', 'name': '章節卡片', 'english': 'CHAPTER CARDS', 'summary': '每個章節獨立成卡，減少同一畫面中的視覺混雜。適合平板與分段複習。', 'features': ['分區卡片與編號', '較寬的閱讀區', '柔和藍灰層次']},
    {'key': 'c', 'name': '臨床筆記', 'english': 'CLINICAL NOTEBOOK', 'summary': '深色主題導覽配白色筆記紙，使用邊線與重點標記建立閱讀節奏。', 'features': ['深藍色章節導覽', '筆記式標題與邊線', '清楚的證據與限制標示']},
]


def render_previews(root, env, nav, rendered, sources, public_sources):
    config = root / 'config/layout-previews.yml'
    if not config.exists():
        return {}
    options = yaml.safe_load(config.read_text(encoding='utf-8')) or {}
    if not options.get('enabled'):
        return {}
    source_id = options.get('source_id')
    source = next((p for p in nav if p['id'] == source_id), None)
    if source is None or source_id not in rendered:
        raise ValueError('Layout preview source must be an existing published page')
    content, toc = rendered[source_id]
    topic_nav = [n for n in nav if n['web_topic'] == source['web_topic']]
    outputs = {}
    for variant in VARIANTS:
        current = '03_outputs/web/layout-previews/style-' + variant['key'] + '.html'
        page = dict(source, url=current, layout_variant=variant['key'], layout_name=variant['name'])
        def rebase(match):
            attr, value = match.groups()
            url = urlsplit(value)
            if url.scheme or url.netloc or not url.path:
                return match.group(0)
            target = posixpath.normpath(posixpath.join(posixpath.dirname(source['url']), unquote(url.path)))
            value = common.relative_url(target, current)
            if url.query:
                value += '?' + url.query
            if url.fragment:
                value += '#' + url.fragment
            return attr + '="' + value + '"'
        preview_content = re.sub(r'(href|src)="([^"]+)"', rebase, content)
        outputs[current] = env.get_template('reading.html').render(page=page, content=preview_content, toc=toc, nav=topic_nav, sources=sources, variants=VARIANTS, citations_json=json.dumps(public_sources, ensure_ascii=False).replace('<', '\\u003c'), current=current)
    hub = '03_outputs/web/layout-previews/index.html'
    outputs[hub] = env.get_template('layout-hub.html').render(current=hub, source=source, variants=VARIANTS)
    return outputs
