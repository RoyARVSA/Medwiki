"""Check provenance fields, citations, wiki links and deployed local links."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import common
import markdown


def check_html(root):
    errors = []
    for p in root.rglob('*.html'):
        parser = common.PlainHTML()
        parser.feed(p.read_text(encoding='utf-8'))
        for link in parser.links:
            u = urlsplit(link)
            if u.scheme or u.netloc:
                continue
            if u.path.startswith('/'):
                errors.append(f'{p.relative_to(root)}: root-relative link breaks project hosting: {link}')
                continue
            dest = p if not u.path else ((root / unquote(u.path).lstrip('/')) if u.path.startswith('/') else p.parent / unquote(u.path))
            dest = dest.resolve()
            if not dest.is_relative_to(root.resolve()) or not dest.exists():
                errors.append(f'{p.relative_to(root)}: missing/unsafe {link}')
            elif u.fragment and dest.suffix == '.html':
                other = common.PlainHTML()
                other.feed(dest.read_text(encoding='utf-8'))
                if unquote(u.fragment) not in other.ids:
                    errors.append(f'{p.relative_to(root)}: missing anchor {link}')
    return errors


def check_source_locators(root, sources):
    """Check every advertised HTML locator against the completed public tree."""
    errors = []
    for key, source in sources.items():
        path = source.get('public_path')
        if source.get('locator_type') != 'html' or not path:
            continue
        dest = root / path
        if not common.safe_file(dest, root):
            errors.append(f'{key}: missing/unsafe HTML source public_path: {path}')
            continue
        parser = common.PlainHTML()
        parser.feed(dest.read_text(encoding='utf-8'))
        for locator in source['locators']:
            if locator not in parser.ids:
                errors.append(f'{key}: missing HTML source locator: {path}#{locator}')
    return errors


def lint(root=common.ROOT, check_site=True):
    errors = []
    seen = set()
    sources = common.load_sources(root)
    source_ids = {s['source_id'] for s in sources.values()}
    for d in common.load_documents(root):
        for k in ['id', 'title', 'type', 'created', 'updated', 'summary', 'tags', 'source_ids', 'review_status', 'conflict_status']:
            if k not in d:
                errors.append(f"{d['path']}: missing {k}")
        if d.get('id') in seen:
            errors.append(f"Duplicate ID: {d['id']}")
        seen.add(d.get('id'))
        if set(d.get('source_ids', [])) - source_ids:
            errors.append(f"{d['path']}: unknown source")
        try:
            common.render_citations(d['body'], sources)
            common.rewrite_media(markdown.markdown(d['body'], extensions=['tables', 'fenced_code', 'attr_list']), root, d['path'])
        except ValueError as e:
            errors.append(f"{d['path']}: {e}")
        for val in re.findall(r'\]\(([^)]+\.md)(?:#[^)]*)?\)', d['body']):
            if not (root / d['path']).parent.joinpath(val).exists():
                errors.append(f"{d['path']}: missing {val}")
        if d.get('conflict_status') == 'open' and d.get('review_status') != 'not_reviewed':
            errors.append(f"{d['path']}: conflict must be not_reviewed")
    site = root / '.build/site'
    if check_site and site.exists():
        errors.extend(check_html(site))
        errors.extend(check_source_locators(site, sources))
        for bad in ['private', '02_sources/raw', '00_inbox', '.obsidian']:
            if (site / bad).exists():
                errors.append('Private directory in site: ' + bad)
    return errors


if __name__ == '__main__':
    errors = lint()
    print('\n'.join(errors) if errors else 'PASS: metadata, citations, wiki links, website links and private exclusions')
    raise SystemExit(bool(errors))
