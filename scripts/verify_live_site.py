"""Read-only deployment smoke check. Does not sign in, upload, or consume credits."""
import sys
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/web'))
from html_page import Page


def main(base):
    origin = urlsplit(base)
    if origin.scheme not in ('http', 'https') or not origin.hostname or origin.username or origin.password:
        raise ValueError('Pass an http(s) origin without credentials')
    with httpx.Client(base_url=base.rstrip('/'), timeout=30, follow_redirects=False) as client:
        root = client.get('/')
        assert root.status_code == 308 and root.headers['location'] == '/app'
        assert client.get('/health').json()['status'] == 'healthy'
        sitemap = client.get('/sitemap.xml'); sitemap.raise_for_status()
        urls = [x.text for x in ET.fromstring(sitemap.text).findall('.//{*}loc')]
        assert len(urls) >= 6 and len(urls) == len(set(urls))
        for canonical in urls:
            path = urlsplit(canonical).path
            response = client.get(path); response.raise_for_status()
            page = Page(response.text)
            assert page.canonicals == [canonical] and len(page.h1s) == 1
            assert len(page.titles) == 1 and page.meta.get('description') and page.schemas
            if origin.hostname == urlsplit(canonical).hostname:
                assert 'noindex' not in response.headers.get('x-robots-tag', ''), path
            else:
                assert 'noindex' in response.headers.get('x-robots-tag', ''), path
            for asset in page.assets:
                if asset.startswith('/static/'):
                    assert client.get(asset).status_code == 200, asset
        assert client.get('/guides/not-a-real-guide').status_code == 404
        assert 'Sitemap:' in client.get('/robots.txt').text
        print(f'PASS: {len(urls)} live pages, metadata, assets, sitemap, redirect, health and 404')


if __name__ == '__main__': main(sys.argv[1])
