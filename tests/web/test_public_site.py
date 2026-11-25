"""ASGI regression checks: no external network, startup tasks, or account writes."""
import json
import struct
import unittest
from html_page import Page
from unittest.mock import patch
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx
from app.main import app
from app.config import Settings, settings
from app.services.seo_service import PUBLIC_PATHS
from app.content.guides import GUIDES


class PublicSiteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.origin = patch.object(settings, 'seo_site_url', 'https://formrefine.ai')
        self.indexable = patch.object(settings, 'seo_indexable', True)
        self.origin.start(); self.indexable.start()
        # ASGITransport deliberately does not enter the production lifespan.
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://formrefine.ai')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.origin.stop(); self.indexable.stop()

    async def test_public_pages_have_unique_rendered_metadata(self):
        titles, descriptions = set(), set()
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('noindex', response.headers.get('x-robots-tag', ''))
                self.assertIn('text/html', response.headers['content-type'])
                page = Page(response.text)
                self.assertEqual(len(page.titles), 1)
                self.assertEqual(len(page.h1s), 1)
                self.assertTrue(page.h1s[0].strip())
                self.assertNotIn(page.titles[0], titles)
                titles.add(page.titles[0])
                self.assertNotIn(page.meta['description'], descriptions)
                descriptions.add(page.meta['description'])
                self.assertEqual(page.canonicals, ['https://formrefine.ai' + path])
                self.assertEqual(page.meta['og:url'], page.canonicals[0])
                self.assertEqual(page.meta['og:title'], page.titles[0])
                self.assertEqual(page.schemas[0]['@context'], 'https://schema.org')
                self.assertNotIn('{{SEO_METADATA}}', response.text)
                self.assertNotIn('{{SUPABASE', response.text)
                if path.startswith('/guides/'):
                    self.assertIn('BreadcrumbList', json.dumps(page.schemas))
                    self.assertGreater(len(response.text), 5000)

    async def test_home_keeps_upload_login_and_results_controls(self):
        r = await self.client.get('/app')
        page = Page(r.text)
        self.assertTrue({'fileInput', 'uploadArea', 'analyzeBtn', 'authModal', 'authForm',
                         'resultsContainer', 'pendingVideoNotice', 'historyBtn', 'oneGuidesTitle'} <= page.ids)
        self.assertNotIn('<body class="loading-flash-prevent">', r.text)
        self.assertIn('<noscript>', r.text)
        self.assertIn('basketball shooting form', page.h1s[0].lower())
        self.assertIn('/guides', page.links)
        for slug in GUIDES:
            self.assertIn('/guides/' + slug, page.links)

    async def test_public_pages_reference_first_party_brand_assets(self):
        asset_root = '/static/brand/'
        share_path = asset_root + 'formrefine-share.png'
        icon_sizes = {'formrefine-icon-48.png': 48, 'formrefine-icon-180.png': 180}
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                page = Page((await self.client.get(path)).text)
                self.assertIn(asset_root + 'formrefine-icon.svg', page.icons)
                for name, size in icon_sizes.items():
                    self.assertEqual(page.icons[asset_root + name], f'{size}x{size}')
                self.assertEqual(page.meta['og:image'], 'https://formrefine.ai' + share_path)
                self.assertEqual(page.meta['twitter:image'], page.meta['og:image'])
                self.assertEqual(page.meta['twitter:card'], 'summary_large_image')
                self.assertEqual((page.meta['og:image:width'], page.meta['og:image:height']), ('1200', '630'))

        vector = await self.client.get(asset_root + 'formrefine-icon.svg')
        self.assertEqual(vector.status_code, 200)
        self.assertIn('image/svg+xml', vector.headers['content-type'])
        images = [(asset_root + name, (size, size)) for name, size in icon_sizes.items()]
        for path, dimensions in [*images, (share_path, (1200, 630))]:
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn('image/png', response.headers['content-type'])
            self.assertEqual(response.content[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', response.content[16:24]), dimensions)

    async def test_analyzer_uses_system_font_and_readable_small_labels(self):
        page = Page((await self.client.get('/app')).text)
        stylesheet = next(src for src in page.assets if urlsplit(src).path == '/static/one-page.css')
        css = (await self.client.get(stylesheet)).text
        self.assertRegex(css, r'--court-font:\s*system-ui,\s*sans-serif')
        self.assertNotRegex(css, r'font-size:\s*(?:[0-9]|1[01])(?:\.\d+)?px\b')

    async def test_staging_serves_product_ui_and_keeps_reports_private(self):
        with patch.object(settings, 'staging_engine_auth', True):
            home = await self.client.get('/app')
            self.assertEqual(home.status_code, 200)
            self.assertIn('<body data-engine-auth>', home.text)
            self.assertIn('historyBtn', Page(home.text).ids)
            for path in ('/guides', '/api/v1/templates/list', '/static/site-theme.css'):
                self.assertEqual((await self.client.get(path)).status_code, 200, path)
            self.assertEqual((await self.client.get('/api/v1/videos/history')).status_code, 401)
            self.assertEqual((await self.client.get('/admin')).status_code, 404)
            prefix = '/api/v1/videos/workspace'
            workspace = await self.client.get(prefix + '/app')
            self.assertEqual(workspace.status_code, 200)
            self.assertIn(prefix + '/static/one-page.css', workspace.text)
            self.assertIn(prefix + "/app#oneUpload", workspace.text)
            self.assertIn(prefix + '/api/v1/templates/list', workspace.text)
            for path in ('/guides', '/privacy', '/static/site-theme.css', '/api/v1/templates/list'):
                self.assertEqual((await self.client.get(prefix + path)).status_code, 200, path)
            self.assertEqual((await self.client.get(prefix + '/results/private.json')).status_code, 404)
            self.assertEqual((await self.client.post('/api/v1/templates/create')).status_code, 404)

    async def test_privacy_policy_is_public_and_linked_from_home(self):
        self.assertIn('/privacy', Page((await self.client.get('/app')).text).links)
        response = await self.client.get('/privacy')
        self.assertEqual(response.status_code, 200)
        page = Page(response.text)
        self.assertEqual(page.h1s, ['FormRefine Privacy Policy'])
        self.assertIn('mailto:ThisIsClark@163.com', page.links)
        self.assertIn('Your account and Google sign-in', response.text)

    async def test_formal_domain_engine_mode_preserves_public_urls(self):
        with patch.object(settings, 'engine_auth_origin', 'https://formrefine.ai'):
            for path in PUBLIC_PATHS:
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertEqual(Page(response.text).canonicals, ['https://formrefine.ai' + path])
                self.assertEqual(response.headers.get('x-formrefine-indexable'), '1')
            app_response = await self.client.get('/app')
            self.assertIn('<body data-engine-auth>', app_response.text)
            self.assertNotIn('/api/v1/videos/workspace/', app_response.text)
            privacy = await self.client.get('/privacy')
            self.assertIn('saved to your account after successful analysis', privacy.text)
            self.assertNotIn('Creem handles checkout', privacy.text)
            for path in ('/sitemap.xml', '/robots.txt'):
                self.assertEqual((await self.client.get(path)).status_code, 200, path)
            history = await self.client.get('/api/v1/videos/history')
            self.assertEqual(history.status_code, 401)
            self.assertNotIn('x-formrefine-indexable', history.headers)
            preview = await self.client.get('/app', headers={'Host': 'backend.example'})
            self.assertIn('noindex', preview.headers['x-robots-tag'])
            with patch.object(settings, 'seo_indexable', False):
                self.assertNotIn('x-formrefine-indexable', (await self.client.get('/app')).headers)

    def test_engine_origin_requires_bare_https(self):
        for value in ('http://formrefine.ai', 'https://formrefine.ai/_auth',
                      'https://user@formrefine.ai', 'https://formrefine.ai:8888'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings(engine_auth_origin=value, _env_file=None)
        self.assertEqual(Settings(engine_auth_origin='https://formrefine.ai/', _env_file=None)
                         .engine_session_origin, 'https://formrefine.ai')
        self.assertEqual(Settings(engine_auth_origin='', staging_engine_auth=True, _env_file=None)
                         .engine_session_origin, 'https://staging.formrefine.ai')

    async def test_home_form_topic_is_server_rendered_and_links_to_checklist(self):
        response = await self.client.get('/app')
        page = Page(response.text)
        self.assertIn('basketball shooting form', page.titles[0].lower())
        self.assertIn('basketball shooting form', page.meta['description'].lower())
        self.assertIn('Use the shooting form checker', response.text)
        # The educational section must be readable without executing JavaScript.
        start = response.text.index('<section class="one-how" id="shootingFormBasics"')
        section = response.text[start:response.text.index('</section>', start)]
        for phrase in ('Balance and body position', 'Ball dip and shooting rhythm',
                       'Release and follow-through', '/guides/basketball-shooting-form-check'):
            self.assertIn(phrase, section)
        self.assertNotIn('<script', section)
        self.assertEqual(page.canonicals, ['https://formrefine.ai/app'])

    async def test_internal_links_assets_and_fragments_resolve(self):
        cache = {}
        async def get(path):
            if path not in cache: cache[path] = await self.client.get(path)
            return cache[path]
        for path in PUBLIC_PATHS:
            page = Page((await get(path)).text)
            for link in page.links + page.assets:
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc: continue
                target = parsed.path or path
                response = await get(target + ('?' + parsed.query if parsed.query else ''))
                self.assertEqual(response.status_code, 200, (path, link))
                if parsed.fragment:
                    self.assertIn(parsed.fragment, Page(response.text).ids, (path, link))

    async def test_guides_share_brand_and_current_trial_offer(self):
        for path in PUBLIC_PATHS:
            response = await self.client.get(path)
            page = Page(response.text)
            self.assertIn('/static/site-theme.css', [urlsplit(x).path for x in page.assets])
            self.assertIn('public-header', response.text)
            self.assertIn('public-nav', response.text)
            for link in ('/app#oneExample', '/app#oneHow', '/guides'):
                self.assertIn(link, page.links)
            self.assertIn('site-brand', response.text)
            if path.startswith('/guides'):
                self.assertIn('1 free analysis without signup', response.text)
                self.assertNotIn('sign-in is required before upload', response.text)
                self.assertIn('/app#oneUpload', page.links)

    async def test_sitemap_matches_public_canonicals_only(self):
        response = await self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response.headers['content-type'])
        root = ET.fromstring(response.text)
        urls = [node.text for node in root.findall('.//{*}loc')]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(set(urls), {'https://formrefine.ai' + p for p in PUBLIC_PATHS})
        self.assertNotIn('lastmod', response.text)
        robots = await self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        self.assertIn('Sitemap: https://formrefine.ai/sitemap.xml', robots.text)
        self.assertNotIn('Disallow: /\n', robots.text)

    async def test_root_permanent_redirect_and_query_canonical(self):
        root = await self.client.get('/')
        self.assertEqual(root.status_code, 308)
        self.assertEqual(root.headers['location'], '/app')
        page = Page((await self.client.get('/app?utm_source=reddit')).text)
        self.assertEqual(page.canonicals, ['https://formrefine.ai/app'])

    async def test_one_motion_guide_publishes_practice_notes_and_upload_link(self):
        path = '/guides/one-motion-basketball-shot'
        with patch.object(settings, 'engine_auth_origin', 'https://formrefine.ai'):
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            page = Page(response.text)
            heading = 'One-Motion Basketball Shot: How to Tell on Video'
            self.assertEqual(page.h1s, [heading])
            self.assertEqual(page.titles, [heading])
            self.assertIn('been watching the NBA since around 2000', response.text)
            self.assertIn('three 90-degree angles', response.text)
            self.assertIn('I bend less at the hips', response.text)
            self.assertIn('/app#shotRhythmUpload', page.links)
            after_heading = response.text.split('</h1>', 1)[1].lstrip()
            self.assertTrue(after_heading.startswith('<figure id="practice-example"'))
            figure = after_heading.split('</figure>', 1)[0]
            self.assertIn('likely two-motion', figure)
            example = Page(figure)
            self.assertEqual(example.links, ['/static/practice-shot-result.webp', '/app#shotRhythmUpload'])
            self.assertEqual(example.assets, ['/static/practice-shot-result.webp'])
            poster = await self.client.get(example.assets[0])
            self.assertEqual(poster.status_code, 200)
            self.assertEqual(poster.headers['content-type'], 'image/webp')
            self.assertEqual(poster.content[8:12], b'WEBP')
            self.assertNotIn('/static/shot-rhythm-example.jpg', page.assets)
            self.assertNotIn('noindex', response.headers.get('x-robots-tag', ''))
            sitemap = await self.client.get('/sitemap.xml')
            urls = [node.text for node in ET.fromstring(sitemap.text).findall('.//{*}loc')]
            self.assertIn('https://formrefine.ai' + path, urls)

    async def test_unknown_guide_is_real_404_not_soft_404(self):
        response = await self.client.get('/guides/does-not-exist')
        self.assertEqual(response.status_code, 404)
        self.assertIn('noindex', response.headers['x-robots-tag'])

    async def test_preview_and_utility_pages_are_noindex(self):
        for path in ('/admin', '/feedback-share', '/video-test', '/health', '/docs',
                     '/api/v1/auth/credits', '/results/missing.json', '/template_images/index.html'):
            response = await self.client.get(path)
            self.assertIn('noindex', response.headers['x-robots-tag'], path)
        response = await self.client.get('http://localhost/app')
        self.assertIn('noindex', response.headers['x-robots-tag'])
        self.assertEqual(Page(response.text).canonicals, ['https://formrefine.ai/app'])
        with patch.object(settings, 'seo_indexable', False):
            self.assertIn('noindex', (await self.client.get('/guides')).headers['x-robots-tag'])

    async def test_host_header_cannot_poison_canonicals(self):
        response = await self.client.get('/app', headers={'Host': 'attacker.example'})
        self.assertEqual(Page(response.text).canonicals, ['https://formrefine.ai/app'])
        self.assertIn('noindex', response.headers['x-robots-tag'])

    def test_origin_validation(self):
        for value in ('javascript:alert(1)', 'https://example.com/path', 'https://user:pass@example.com',
                      'https://example.com?x=1', 'https://example.com/#section'):
            with self.assertRaises(ValueError): Settings(seo_site_url=value, _env_file=None)
        self.assertEqual(Settings(seo_site_url='https://example.com/', _env_file=None).seo_site_url, 'https://example.com')
