// Serves tm1cm's pages (built into dist/ by scripts/build.mjs) at skipcheck.io/tm1cm/. They are
// dressed as part of the site: every page gets the site's masthead and footer, fetched from
// skipcheck.io/partials/ and cached, so a change to the site's nav reaches these pages without a
// rebuild. Each page names its skipcheck.io address as canonical, whatever host served it (under
// `wrangler dev`, localhost).
// The same as skipcheck-tm1's api-site Worker, for one project and without Javadoc.

// A Worker module exports only its handlers
const PROJECT = 'tm1cm';

const SECURITY_HEADERS = {
	// The pages have no inline script or style
	'Content-Security-Policy': [
		"default-src 'self'",
		"img-src 'self' data:",
		"style-src 'self'",
		"script-src 'self'",
		"frame-ancestors 'none'",
		"base-uri 'self'",
		"form-action 'none'",
	].join('; '),
	'X-Content-Type-Options': 'nosniff',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

// How long the site's partials are cached at the edge before the pages pick up a change
const PARTIAL_TTL_SECONDS = 300;

export default {
	async fetch(request, env) {
		const url = new URL(request.url);
		const mine = url.pathname === '/' + PROJECT || url.pathname.startsWith('/' + PROJECT + '/');
		// In production only /tm1cm is routed here. Under `wrangler dev` everything is, so pass the
		// rest (the site's styles, its other pages, links home) through to the site.
		if (!mine) return fetch(new URL(url.pathname + url.search, env.SITE_ORIGIN), request);

		// A page is an .html file or a folder (served as its index.html); a path with no extension
		// is taken for a folder and gets its trailing slash
		const isPage = !/\.(?!html$)[^/.]+$/.test(url.pathname);
		if (isPage && !url.pathname.endsWith('/') && !url.pathname.endsWith('.html')) {
			return Response.redirect(`${url.origin}${url.pathname}/${url.search}`, 301);
		}
		const asset = new URL(url);
		if (asset.pathname.endsWith('/')) asset.pathname += 'index.html';
		const response = await env.ASSETS.fetch(new Request(asset, isPage ? unconditional(request) : request));
		if (response.status === 404) return notFound(env);
		if (asset.pathname.endsWith('.xml')) {
			// The sitemap, as XML whatever type the assets give it
			const xml = withSecurityHeaders(response);
			xml.headers.set('Content-Type', 'application/xml; charset=utf-8');
			return xml;
		}
		if (!(response.headers.get('Content-Type') ?? '').startsWith('text/html')) return withSecurityHeaders(response);

		const [masthead, footer] = await Promise.all([partial(env, 'masthead'), partial(env, 'footer')]);
		const page = new HTMLRewriter()
			// The site's colour mode, set before the page is drawn, and its Copy buttons
			.on('head', {
				element(head) {
					head.prepend('<script src="/theme.js"></script>', { html: true });
					head.append('<script src="/copy.js" defer></script>', { html: true });
				},
			})
			.on('body', {
				element(body) {
					if (masthead) body.prepend(masthead, { html: true });
					if (footer) body.append(footer, { html: true });
				},
			})
			.transform(response);
		// A page is the file plus the site's partials, so the file's validators don't identify it
		const secured = withSecurityHeaders(page);
		secured.headers.delete('ETag');
		secured.headers.delete('Last-Modified');
		secured.headers.set('Cache-Control', 'no-cache');
		secured.headers.set('Link', `<${new URL(url.pathname, env.SITE_ORIGIN)}>; rel="canonical"`);
		return secured;
	},
};

/** The site's masthead or footer as HTML, or null if the site can't be reached: the pages still work. */
async function partial(env, name) {
	try {
		const response = await fetch(new URL(`/partials/${name}`, env.SITE_ORIGIN), { cf: { cacheEverything: true, cacheTtl: PARTIAL_TTL_SECONDS } });
		return response.ok ? await response.text() : null;
	} catch {
		return null;
	}
}

function unconditional(request) {
	const headers = new Headers(request.headers);
	headers.delete('If-None-Match');
	headers.delete('If-Modified-Since');
	return new Request(request, { headers });
}

async function notFound(env) {
	const page = await fetch(new URL('/404', env.SITE_ORIGIN)).catch(() => null);
	return withSecurityHeaders(
		new Response(page?.ok ? page.body : 'Not found', { status: 404, headers: { 'Content-Type': page?.headers.get('Content-Type') ?? 'text/plain' } }),
	);
}

function withSecurityHeaders(response) {
	const secured = new Response(response.body, response);
	for (const [name, value] of Object.entries(SECURITY_HEADERS)) secured.headers.set(name, value);
	return secured;
}
