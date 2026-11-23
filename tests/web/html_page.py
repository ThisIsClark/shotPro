"""Small shared HTML inspector for local and deployed pages."""
import json
from html.parser import HTMLParser


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.titles, self.h1s, self.links, self.assets, self.schemas = [], [], [], [], []
        self.meta, self.ids, self.canonicals, self.icons = {}, set(), [], {}
        self.capture = None
        self.buffer = ''
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'meta':
            self.meta[a.get('name') or a.get('property')] = a.get('content')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonicals.append(a['href'])
        if tag == 'link' and a.get('rel') in ('icon', 'apple-touch-icon') and a.get('href'):
            self.icons[a['href']] = a.get('sizes')
            self.assets.append(a['href'])
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        if tag in ('script', 'img') and a.get('src'):
            self.assets.append(a['src'])
        if tag == 'link' and a.get('rel') == 'stylesheet':
            self.assets.append(a['href'])
        if tag in ('title', 'h1') or (tag == 'script' and a.get('type') == 'application/ld+json'):
            self.capture, self.buffer = tag, ''

    def handle_data(self, data):
        if self.capture:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == self.capture:
            if tag == 'title': self.titles.append(self.buffer)
            elif tag == 'h1': self.h1s.append(self.buffer)
            elif tag == 'script': self.schemas.append(json.loads(self.buffer))
            self.capture = None
