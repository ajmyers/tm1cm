// What tm1cm's pages are made of, shared by the page builders. Served under /tm1cm/:
//
//   /tm1cm/                       the landing page (content/tm1cm.md)
//   /tm1cm/walkthroughs/<slug>/   a task step by step (content/walkthroughs/<slug>.md), with what
//                                 each command printed when it ran against TM1 (sessions.mjs)
//   /tm1cm/docs/                  the reference, written from the code (reference.mjs)
//   /tm1cm/llms.txt, llms-full.txt  the docs for coding agents (llms.mjs)

import { execFileSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const PROJECT = { id: 'tm1cm', title: 'tm1cm', github: 'https://github.com/ajmyers/tm1cm', pypi: 'https://pypi.org/project/tm1cm/' };
export const siteDir = path.resolve(import.meta.dirname, '..');
export const repoDir = path.resolve(siteDir, '..');
export const distDir = path.join(siteDir, 'dist');
export const outDir = path.join(distDir, PROJECT.id);
export const generatedDir = path.join(siteDir, '.generated');
export const CANONICAL_ORIGIN = 'https://skipcheck.io';

export const escape = (text) => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

/** A code block the site's highlighter (/highlight.js) colours. */
export const codeBlock = (code, highlight) => '<pre><code' + (highlight ? ' class="lang-' + highlight + '"' : '') + '>' + escape(code) + '</code></pre>';

export const figure = (caption, html) => '<figure class="code">' + (caption ? '<figcaption>' + escape(caption) + '</figcaption>' : '') + html + '</figure>';

/** The version these pages describe: a tag's (DOCS_VERSION, set by the workflow), or none before
 * one. release is true for a final version only (1.2.3, not 1.3.0rc1), as skipcheck-tm1's pages
 * have it: the site's home page shows it on tm1cm's badge (/tm1cm/release.json). */
export function docsVersion() {
	const version = process.env.DOCS_VERSION || null;
	return { version, release: Boolean(version && /^\d+\.\d+\.\d+$/.test(version)) };
}

/** Python's version tm1cm needs, from setup.py's python_requires. */
export async function pythonNeeded() {
	const setup = await readFile(path.join(repoDir, 'setup.py'), 'utf8');
	const found = /python_requires\s*=\s*"([^"]+)"/.exec(setup);
	if (!found) throw new Error('setup.py has no python_requires');
	const minimum = />=\s*([\d.]+)/.exec(found[1]);
	return minimum ? minimum[1] : found[1];
}

/** The reference, read from the code by extract/reference.py with the Python that has tm1cm. */
export function extractReference() {
	const python = process.env.PYTHON ?? 'python3';
	const target = path.join(generatedDir, 'reference.json');
	execFileSync(python, [path.join(siteDir, 'extract', 'reference.py'), target], { stdio: 'inherit' });
	return target;
}

/** The head of a page. styles and scripts are addresses, in order. */
export function head({ title, description, canonical, styles, scripts = [] }) {
	return (
		'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
		'<title>' + escape(title) + '</title>' +
		(description ? '<meta name="description" content="' + escape(description) + '">' : '') +
		(canonical ? '<link rel="canonical" href="' + escape(canonical) + '">' : '') +
		'<link rel="icon" href="/favicon.svg" type="image/svg+xml"><meta name="color-scheme" content="light dark">' +
		styles.map((href) => '<link rel="stylesheet" href="' + href + '">').join('') +
		scripts.map((src) => '<script src="' + src + '" defer></script>').join('') +
		(description ? '<meta property="og:type" content="website"><meta property="og:title" content="' + escape(title) + '"><meta property="og:description" content="' + escape(description) + '">' : '') +
		(canonical ? '<meta property="og:url" content="' + escape(canonical) + '">' : '') +
		(description ? '<meta property="og:image" content="https://skipcheck.io/og.png"><meta name="twitter:card" content="summary_large_image">' : '') +
		'</head>'
	);
}

/** A page: its head, and its main. depth: how many folders below /tm1cm/ it is, for relative links. */
export function page({ title, description, pathname, main, mainClass = 'project', reference = false }) {
	const assets = '/' + PROJECT.id + '/assets/';
	return (
		head({
			title: title + ' · Skipcheck',
			description,
			canonical: CANONICAL_ORIGIN + '/' + PROJECT.id + '/' + pathname,
			// The landing page and walkthroughs are written in the site's styles; the reference in
			// skipcheck-tm1's docs layout, which loads the site's tokens itself
			styles: reference ? [assets + 'reference.css', assets + 'docs.css'] : ['/styles.css', assets + 'docs.css'],
			scripts: ['/highlight.js', assets + 'tabs.js', ...(reference ? [assets + 'search.js'] : [])],
		}) +
		(reference ? '<body>' + main + '</body></html>\n' : '<body><main id="main" class="' + mainClass + '">' + main + '</main></body></html>\n')
	);
}

export const section = (id, title, html) =>
	'<section id="' + id + '" class="section wrap" aria-labelledby="' + id + '-heading"><h2 id="' + id + '-heading" class="section-label">' + escape(title) + '</h2><div class="steps">' + html + '</div></section>';

/** A search box (assets/search.js), hidden until its script shows it. */
export const searchBox = () =>
	'<div class="search" role="search" hidden><label class="visually-hidden" for="docs-search">Search the tm1cm docs</label>' +
	'<input id="docs-search" type="search" autocomplete="off" spellcheck="false" placeholder="Search settings, filters, options…" data-index="/' + PROJECT.id + '/search.json">' +
	'<ul id="docs-search-results" class="search-results" hidden></ul></div>';

/** A box of panels behind the system tabs (assets/tabs.js), skipcheck-tm1's tab boxes: each panel
 * { id, label, html }. One panel is a box without tabs. The choice is the same everywhere, and kept. */
export function tabBox(panels) {
	const bar = panels.length > 1
		? '<div class="tablist" role="tablist" aria-label="System">' + panels.map((p) => '<button type="button" role="tab" data-tab="' + p.id + '">' + escape(p.label) + '</button>').join('') + '</div>'
		: '';
	return '<div class="tabs">' + bar + panels.map((p) => '<div role="tabpanel" data-tab="' + p.id + '">' + p.html + '</div>').join('') + '</div>';
}

export const systemTabs = (unix, windows) => tabBox([
	{ id: 'unix', label: 'macOS and Linux', html: unix },
	{ id: 'windows', label: 'Windows', html: windows },
]);

/** A labelled block inside a tab box: a caption, then the code. */
export const block = (caption, code, highlight, cls) => (caption ? '<p class="caption">' + caption + '</p>' : '') + '<pre' + (cls ? ' class="' + cls + '"' : '') + '><code' + (highlight ? ' class="lang-' + highlight + '"' : '') + '>' + escape(code) + '</code></pre>';
