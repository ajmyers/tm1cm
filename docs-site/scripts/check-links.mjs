// Checks every link of the pages built into dist/: a link under /tm1cm/ must be a file there (and
// an anchor an id on its page); any other local link must be one of the site's own addresses
// below, since those pages live in ajmyers/skipcheck.io. Every address in llms.txt, llms-full.txt
// and sitemap.xml under /tm1cm/ too. Fails with the list of broken links.

import { readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { distDir, PROJECT } from './site.mjs';

// What these pages may link to on the site itself. Add an address after checking the site serves it.
const SITE_PATHS = new Set(['/', '/styles.css', '/highlight.js', '/favicon.svg', '/pa-docker/setup/', '/docs/']);

const exists = (file) => stat(file).then((s) => s.isFile(), () => false);

async function* files(dir) {
	for (const entry of await readdir(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) yield* files(full);
		else yield full;
	}
}

async function target(pathname) {
	const file = path.join(distDir, decodeURIComponent(pathname));
	return (await exists(file)) ? file : (await exists(path.join(file, 'index.html'))) ? path.join(file, 'index.html') : null;
}

export async function checkLinks() {
	const broken = [];
	const ids = new Map();
	const idsOf = async (file) => {
		if (!ids.has(file)) ids.set(file, new Set([...(await readFile(file, 'utf8')).matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])));
		return ids.get(file);
	};
	let checked = 0;
	for await (const file of files(distDir)) {
		const page = '/' + path.relative(distDir, file).split(path.sep).join('/');
		if (file.endsWith('.html')) {
			const html = await readFile(file, 'utf8');
			for (const [, raw] of html.matchAll(/<(?:a|link|script|img)\b[^>]*?\s(?:href|src)="([^"]*)"/g)) {
				const link = raw.replaceAll('&amp;', '&');
				if (/^[a-z][a-z0-9+.-]*:/i.test(link)) continue;
				checked++;
				const url = new URL(link, 'https://site.invalid' + page);
				if (url.pathname.startsWith('/' + PROJECT.id + '/') || url.pathname === '/' + PROJECT.id) {
					const found = await target(url.pathname);
					if (!found) broken.push(page + ': ' + link + ' (no such page)');
					else if (url.hash && !(await idsOf(found)).has(decodeURIComponent(url.hash.slice(1)))) broken.push(page + ': ' + link + ' (no ' + url.hash + ' there)');
				} else if (!SITE_PATHS.has(url.pathname)) broken.push(page + ': ' + link + " (not one of the site's addresses this check knows)");
			}
		} else if (file.endsWith('.txt') || file.endsWith('.xml')) {
			for (const [address] of (await readFile(file, 'utf8')).matchAll(/https:\/\/skipcheck\.io\/[^\s)<]*/g)) {
				checked++;
				const url = new URL(address);
				if (url.pathname.startsWith('/' + PROJECT.id + '/') && !(await target(url.pathname))) broken.push(page + ': ' + address);
			}
		}
	}
	if (broken.length) throw new Error(broken.length + ' broken link(s):\n  ' + broken.join('\n  '));
	return checked;
}
