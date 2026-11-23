"""ASGI regression checks: no external network, startup tasks, or account writes."""
import json
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
            self.assertEqual((await self.client.post('/api/v1/templates/create')).status_code, 404)

    async def test_privacy_policy_is_public_and_linked_from_home(self):
        self.assertIn('/privacy', Page((await self.client.get('/app')).text).links)
        response = await self.client.get('/privacy')
        self.assertEqual(response.status_code, 200)
        page = Page(response.text)
        self.assertEqual(page.h1s, ['FormRefine Privacy Policy'])
        self.assertIn('mailto:ThisIsClark@163.com', page.links)
        self.assertIn('Your account and Google sign-in', response.text)

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
