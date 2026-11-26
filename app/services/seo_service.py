"""Public metadata and server-rendered guides; never derive canonicals from Host."""
import json
from html import escape
from string import Template
from urllib.parse import urlsplit

from ..config import settings
from ..content.guides import GUIDES

HOME_TITLE = 'Basketball Shooting Form Check & Analyzer | FormRefine'
HOME_DESCRIPTION = ('Check your basketball shooting form with video analysis. Review your ball dip, release and '
                    'follow-through, then compare attempts. Try one analysis free.')
RHYTHM_GUIDE_SLUG = 'one-motion-basketball-shot'
RHYTHM_GUIDE_TITLE = 'One-Motion Basketball Shot: How to Tell on Video'
RHYTHM_GUIDE_DESCRIPTION = (
    'Learn what a one-motion basketball shot looks like, how it differs from a two-motion shot, '
    'and how to check your own release in slow motion.'
)
PUBLIC_PATHS = (
    '/', '/app', '/privacy', '/guides', *(f'/guides/{slug}' for slug in GUIDES),
    f'/guides/{RHYTHM_GUIDE_SLUG}',
)


def site_url(path=''):
    return settings.seo_site_url.rstrip('/') + path


def indexable_host(hostname):
    return settings.seo_indexable and hostname == urlsplit(settings.seo_site_url).hostname


def metadata(path, title, description, *, article=False, share_image_alt="FormRefine basketball shooting form analysis"):
    url = site_url(path)
    share_image = escape(site_url('/static/brand/formrefine-share.png'), quote=True)
    schema = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebSite', '@id': site_url('/#website'), 'url': site_url('/'), 'name': 'FormRefine'},
        {'@type': 'WebPage', '@id': url + '#page', 'url': url, 'name': title,
         'description': description, 'inLanguage': 'en-US', 'isPartOf': {'@id': site_url('/#website')}},
    ]}
    if article:
        schema['@graph'].append({'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'FormRefine', 'item': site_url('/app')},
            {'@type': 'ListItem', 'position': 2, 'name': 'Shooting guides', 'item': site_url('/guides')},
            {'@type': 'ListItem', 'position': 3, 'name': title, 'item': url},
        ]})
    safe_json = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')
    return f'''<title>{escape(title)}</title>
<meta name="description" content="{escape(description, quote=True)}">
<link rel="canonical" href="{escape(url, quote=True)}">
<link rel="icon" href="/static/brand/formrefine-icon.svg" type="image/svg+xml">
<link rel="icon" href="/static/brand/formrefine-icon-48.png" type="image/png" sizes="48x48">
<link rel="apple-touch-icon" href="/static/brand/formrefine-icon-180.png" sizes="180x180">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FormRefine">
<meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:description" content="{escape(description, quote=True)}">
<meta property="og:url" content="{escape(url, quote=True)}">
<meta property="og:image" content="{share_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{share_image_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{share_image}">
<meta name="twitter:image:alt" content="{share_image_alt}">
<script type="application/ld+json">{safe_json}</script>'''


def cards(slugs=GUIDES):
    return ''.join(f'<article><h2><a href="/guides/{slug}">{escape(GUIDES[slug]["title"])}</a></h2>'
                   f'<p>{escape(GUIDES[slug]["summary"])}</p></article>' for slug in slugs)


def render_guide(slug=None):
    if slug is None:
        title = 'Basketball Shooting Form Guides | FormRefine'
        description = 'Practical guides to checking basketball shooting form, filming a clear clip, reviewing the shooting dip, and finding the release point.'
        heading = 'Basketball shooting form guides'
        content = '<p class="lede">Start with a question about your shot. Learn what to film, which moments to review, and what a single-camera measurement can tell you.</p><div class="guide-cards">' + cards() + '</div>'
        path = '/guides'
    elif slug == RHYTHM_GUIDE_SLUG:
        title = heading = RHYTHM_GUIDE_TITLE
        description = RHYTHM_GUIDE_DESCRIPTION
        path = f'/guides/{slug}'
        content = (settings.templates_dir / 'guides' / f'{slug}.html').read_text(encoding='utf-8')
    else:
        guide = GUIDES[slug]
        title, description, heading = guide['title'] + ' | FormRefine', guide['description'], guide['title']
        content = '<p class="lede">' + escape(guide['summary']) + '</p><p class="byline">By the FormRefine team · Video review guide</p>'
        content += '<nav class="toc" aria-label="On this page"><strong>On this page</strong><ul>' + ''.join(
            f'<li><a href="#section-{i}">{escape(h)}</a></li>' for i, (h, _) in enumerate(guide['sections'])) + '</ul></nav>'
        for i, (h, paragraphs) in enumerate(guide['sections']):
            content += f'<section id="section-{i}"><h2>{escape(h)}</h2>' + ''.join(f'<p>{escape(p)}</p>' for p in paragraphs) + '</section>'
        content += '<section><h2>Common questions</h2>' + ''.join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q, a in guide['faqs']) + '</section>'
        if guide['sources']:
            content += '<section class="sources"><h2>Further reading</h2><ul>' + ''.join(f'<li><a href="{escape(url, quote=True)}">{escape(label)}</a></li>' for label, url in guide['sources']) + '</ul></section>'
        content += '<aside><h2>Continue your review</h2><div class="guide-cards">' + cards(guide['related']) + '</div></aside>'
        path = '/guides/' + slug
    template = Template((settings.templates_dir / 'guide.html').read_text(encoding='utf-8'))
    html = template.substitute(metadata=metadata(path, title, description, article=slug is not None),
                               heading=escape(heading), content=content)
    if settings.engine_session_origin:
        html = html.replace(
            "Try 1 free analysis without signup. Create a free account to save your report and get 3 more analyses.",
            "Sign in with Google to save your video and analysis report.")
        html = html.replace('<script src="/static/operations-tracking.js"></script>', "")
    return html
