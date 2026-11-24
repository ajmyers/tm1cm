import assert from 'node:assert/strict';
import { test } from 'node:test';

// The Workers runtime's HTMLRewriter, stood in for: it passes the page through
globalThis.HTMLRewriter = class {
	on() {
		return this;
	}
	transform(response) {
		return response;
	}
};
const { default: worker } = await import('../src/worker.js');

const env = (files) => ({
	SITE_ORIGIN: 'https://skipcheck.io',
	ASSETS: {
		fetch: async (request) => {
			const body = files[new URL(request.url).pathname];
			return body === undefined ? new Response('', { status: 404 }) : new Response(body, { headers: { 'Content-Type': body.startsWith('<') ? 'text/html; charset=utf-8' : 'text/css' } });
		},
	},
});
const site = [];
globalThis.fetch = async (url) => {
	site.push(String(url));
	return new Response(String(url).endsWith('/404') ? '<h1>Not found</h1>' : '<nav>site</nav>', { headers: { 'Content-Type': 'text/html' } });
};

test('a page is served from its folder, with the security headers and its canonical address', async () => {
	const response = await worker.fetch(new Request('http://127.0.0.1:8787/tm1cm/docs/'), env({ '/tm1cm/docs/index.html': '<html><body>Docs</body></html>' }));
	assert.equal(response.status, 200);
	assert.match(response.headers.get('Content-Security-Policy'), /script-src 'self'/);
	assert.equal(response.headers.get('Link'), '<https://skipcheck.io/tm1cm/docs/>; rel="canonical"');
	assert.equal(response.headers.get('Cache-Control'), 'no-cache');
});

test('the sitemap is served as XML', async () => {
	const response = await worker.fetch(new Request('https://skipcheck.io/tm1cm/sitemap.xml'), env({ '/tm1cm/sitemap.xml': 'urlset' }));
	assert.equal(response.status, 200);
	assert.equal(response.headers.get('Content-Type'), 'application/xml; charset=utf-8');
	assert.equal(await response.text(), 'urlset');
});

test('a folder without its slash is sent to it', async () => {
	const response = await worker.fetch(new Request('https://skipcheck.io/tm1cm/docs'), env({}));
	assert.equal(response.status, 301);
	assert.equal(response.headers.get('Location'), 'https://skipcheck.io/tm1cm/docs/');
});

test("a page that isn't there is the site's 404", async () => {
	const response = await worker.fetch(new Request('https://skipcheck.io/tm1cm/nothing/'), env({}));
	assert.equal(response.status, 404);
	assert.equal(await response.text(), '<h1>Not found</h1>');
});

test("anything outside /tm1cm goes to the site (under wrangler dev; in production it isn't routed here)", async () => {
	site.length = 0;
	await worker.fetch(new Request('http://127.0.0.1:8787/styles.css'), env({}));
	assert.deepEqual(site, ['https://skipcheck.io/styles.css']);
});
