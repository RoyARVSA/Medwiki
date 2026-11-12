"""Update wiki index and rescan/rebuild completed outputs, including manual files."""
from collections import defaultdict
import common


def update_markdown(root=common.ROOT):
    groups = defaultdict(list)
    for d in common.load_documents(root):
        groups[d.get('type', 'other')].append(d)
    lines = ['# Medwiki 內容索引', '', '主題、來源與學習路徑；網站成果入口見 [index.html](index.html)。', '']
    labels = {'map': '學習導航', 'concept': '概念頁', 'comparison': '比較頁', 'question': '學習問答', 'source_summary': '來源摘要'}
    for key in ['map', 'concept', 'comparison', 'question', 'source_summary']:
        lines.extend(['## ' + labels[key], ''])
        for d in groups[key]:
            lines.append(f"- [{d['title']}]({d['path']})：{d.get('summary', '')}（{d.get('review_status', 'not_reviewed')}）")
        if not groups[key]:
            lines.append('目前尚無內容。')
        lines.append('')
    lines.extend(['## 來源紀錄', ''])
    for p in sorted((root / '02_sources/records').glob('*.md')):
        d, _ = common.read_document(p)
        lines.append(f"- [{d['short_title']}]({p.relative_to(root).as_posix()})：{d['processing_status']}；原始檔本機保存。")
    common.atomic_text(root / 'index.md', '\n'.join(lines) + '\n')


if __name__ == '__main__':
    from build_site import build_site
    print('Updated:', build_site())
