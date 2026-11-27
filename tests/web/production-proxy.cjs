const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const source = fs.readFileSync('deploy/staging/proxy.js', 'utf8');
const proxy = import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const env = {
    PUBLIC_HOST: 'formrefine.ai',
    FASTAPI_ORIGIN: 'https://backend.example',
    USE_ENGINE_ORIGIN: 'true',
    INDEX_PUBLIC_PAGES: 'true',
};

test('production proxy separates public pages, private reports and engine auth', async () => {
    const { default: worker } = await proxy;
    const original = global.fetch;
    const calls = [];
    global.fetch = async (target, init) => {
        calls.push({ target: String(target.url || target), headers: init?.headers ?? target.headers });
        return new Response('response', {
            headers: { 'X-Robots-Tag': 'noindex, nofollow', 'X-FormRefine-Indexable': '1' },
        });
    };
    try {
        const request = path => new Request('https://formrefine.ai' + path, { headers: { Cookie: 'test=value' } });
        for (const path of ['/app?utm_source=test', '/guides/shot', '/privacy', '/sitemap.xml', '/robots.txt']) {
            const result = await worker.fetch(request(path), env);
            const upstream = calls.at(-1);
            assert.equal(upstream.target, env.FASTAPI_ORIGIN + path);
            assert.equal(upstream.headers.has('cookie'), false);
            assert.equal(result.headers.has('x-robots-tag'), false);
            assert.equal(result.headers.has('x-formrefine-indexable'), false);
        }
        const report = await worker.fetch(request('/api/v1/videos/history'), env);
        assert.equal(calls.at(-1).headers.get('cookie'), 'test=value');
        assert.equal(report.headers.get('x-robots-tag'), 'noindex, nofollow');
        assert.equal(report.headers.get('cache-control'), 'private, no-store');

        await worker.fetch(request('/_auth/google/callback'), env);
        assert.equal(calls.at(-1).target, 'https://formrefine.ai/_auth/google/callback');
        const count = calls.length;
        assert.equal((await worker.fetch(request('/admin'), env)).status, 404);
        assert.equal((await worker.fetch(new Request('https://staging.formrefine.ai/app'), env)).status, 404);
        assert.equal((await worker.fetch(request('/app'), { ...env, FASTAPI_ORIGIN: '' })).status, 503);
        assert.equal(calls.length, count);
        const adminConfig = { ...env, ADMIN_ENABLED: 'true' };
        for (const path of ['/admin', '/api/v1/admin/operations']) {
            const admin = await worker.fetch(request(path), adminConfig);
            assert.equal(calls.at(-1).target, env.FASTAPI_ORIGIN + path);
            assert.equal(calls.at(-1).headers.get('cookie'), 'test=value');
            assert.equal(admin.headers.get('x-robots-tag'), 'noindex, nofollow');
        }
        assert.equal((await worker.fetch(request('/api/v1/auth/local-login'), adminConfig)).status, 404);
        const loginPath = '/api/v1/admin/session';
        await worker.fetch(new Request('https://formrefine.ai' + loginPath, {
            method: 'POST',
            headers: { Origin: 'https://formrefine.ai', 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: 'admin', password: 'test-only' })
        }), adminConfig);
        assert.equal(calls.at(-1).target, env.FASTAPI_ORIGIN + loginPath);
        assert.equal(calls.at(-1).headers.get('origin'), 'https://formrefine.ai');
        const analyticsPath = '/api/v1/videos/telemetry/visit';
        await worker.fetch(new Request('https://formrefine.ai' + analyticsPath, {
            method: 'POST', headers: { Origin: 'https://formrefine.ai' }, body: '{}'
        }), env);
        assert.equal(calls.at(-1).target, env.FASTAPI_ORIGIN + analyticsPath);
        assert.equal((await worker.fetch(new Request('https://formrefine.ai/api/v1/audit/event', {
            method: 'POST', body: '{}'
        }), env)).status, 404);

        const noindex = await worker.fetch(request('/app'), { ...env, INDEX_PUBLIC_PAGES: 'false' });
        assert.equal(noindex.headers.get('x-robots-tag'), 'noindex, nofollow');
    } finally {
        global.fetch = original;
    }
});
