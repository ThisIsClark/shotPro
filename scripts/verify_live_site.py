"""Read-only deployment smoke check. Does not sign in, upload, or consume credits."""
import sys
from pathlib import Path
import struct
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
        share_path = '/static/brand/formrefine-share.png'
        share = client.get(share_path); share.raise_for_status()
        assert share.headers['content-type'].startswith('image/png')
        assert share.content[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', share.content[16:24]) == (1200, 630)
        for canonical in urls:
            parsed = urlsplit(canonical)
            path = parsed.path
            response = client.get(path); response.raise_for_status()
            page = Page(response.text)
            assert page.canonicals == [canonical] and len(page.h1s) == 1
            assert len(page.titles) == 1 and page.meta.get('description') and page.schemas
            assert page.meta.get('og:image') == f'{parsed.scheme}://{parsed.netloc}{share_path}'
            assert page.meta.get('twitter:card') == 'summary_large_image'
            assert '/static/brand/formrefine-icon.svg' in page.icons
            if origin.hostname == parsed.hostname:
                assert 'noindex' not in response.headers.get('x-robots-tag', ''), path
            else:
                assert 'noindex' in response.headers.get('x-robots-tag', ''), path
            for asset in page.assets:
                if asset.startswith('/static/'):
                    assert client.get(asset).status_code == 200, asset
        assert client.get('/guides/not-a-real-guide').status_code == 404
        assert 'Sitemap:' in client.get('/robots.txt').text
        print(f'PASS: {len(urls)} live pages, metadata, brand assets, sitemap, redirect, health and 404')


if __name__ == '__main__': main(sys.argv[1])
