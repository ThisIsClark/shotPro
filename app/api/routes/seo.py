"""Crawlable public pages and discovery endpoints."""
from html import escape
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse
from ...services.seo_service import PUBLIC_PATHS, render_guide, site_url

router = APIRouter(tags=['public'], include_in_schema=False)


@router.get('/guides', response_class=HTMLResponse)
async def guide_index():
    return render_guide()


@router.get('/guides/{slug}', response_class=HTMLResponse)
async def guide_detail(slug: str):
    if f'/guides/{slug}' not in PUBLIC_PATHS:
        raise HTTPException(404, 'Guide not found')
    return render_guide(slug)


@router.get('/sitemap.xml')
async def sitemap():
    # No fabricated lastmod timestamps: only public canonical pages belong here.
    urls = ''.join(f'<url><loc>{escape(site_url(path))}</loc></url>' for path in PUBLIC_PATHS)
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    + urls + '</urlset>', media_type='application/xml')


@router.get('/robots.txt')
async def robots():
    # Permit fetching so crawlers can read noindex headers on non-public pages.
    # Authentication, not robots.txt, protects private data.
    return Response('User-agent: *\nAllow: /\n\nSitemap: ' + site_url('/sitemap.xml') + '\n', media_type='text/plain')
