// The landing page, /tm1cm/, from content/tm1cm.md, and each walkthrough,
// /tm1cm/walkthroughs/<slug>/, from content/walkthroughs/<slug>.md. The content files hold the
// words; what can be read from the repository is a directive:
//
//   ::install                 how to install tm1cm with uv, which gets the Python it needs
//                             (setup.py's newest Python classifier), per system
//   ::install-venv            the same in a virtual environment, with a Python of the reader's own
//   ::step <session> <step>   a step of a session: a command and what it printed when the live
//                             tests ran it against TM1, or a file it wrote (sessions.mjs)
//   ::walkthroughs            the walkthroughs, as a list of links
//   ::prompt                  the prompt for a coding agent (content/prompt.md), collapsed, with a
//                             copy button
//
// The look is the site's own (its /styles.css, at view time): the same classes as skipcheck-tm1's
// landing pages.

import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { inline, parse, slug } from './markdown.mjs';
import { stepHtml } from './sessions.mjs';
import { AUTHOR, block, CANONICAL_ORIGIN, codeBlock, docsVersion, escape, page, PROJECT, pythonNeeded, repoDir, section, siteDir, systemTabs, WEBSITE } from './site.mjs';

/** The walkthroughs, in their order: { slug, meta, sections }. */
export async function walkthroughs() {
	const dir = path.join(siteDir, 'content', 'walkthroughs');
	const list = [];
	for (const file of (await readdir(dir)).filter((f) => f.endsWith('.md')).sort()) {
		const content = parse(await readFile(path.join(dir, file), 'utf8'));
		for (const key of ['title', 'summary', 'description', 'order']) {
			if (!content.meta[key]) throw new Error('content/walkthroughs/' + file + ' has no ' + key + ' in its front matter');
		}
		list.push({ slug: file.slice(0, -3), ...content });
	}
	return list.sort((a, b) => Number(a.meta.order) - Number(b.meta.order));
}

/** What pip or uv installs: tm1cm from PyPI once 1.0 is released; until then, from GitHub (PyPI's
 * tm1cm is 0.9, and these pages describe 1.0). */
export function packageSpec() {
	const { version, release } = docsVersion();
	// A pre-release's pages install that pre-release: uv and pip take only final versions unasked
	return release ? 'tm1cm' : version ? 'tm1cm==' + version : '"tm1cm @ git+' + PROJECT.github + '"';
}

export async function installCommand() {
	return 'uv tool install --python ' + (await pythonLatest()) + ' ' + packageSpec();
}

/** The newest Python tm1cm supports, from setup.py's classifiers: what uv installs it with. */
export async function pythonLatest() {
	const setup = await readFile(path.join(repoDir, 'setup.py'), 'utf8');
	const versions = [...setup.matchAll(/Programming Language :: Python :: (3\.\d+)"/g)].map((m) => m[1]);
	if (!versions.length) throw new Error('setup.py lists no Python 3.x classifiers');
	return versions.sort((a, b) => Number(a.split('.')[1]) - Number(b.split('.')[1])).at(-1);
}

/** Every way the pages install tm1cm, per system: the commands, in order. The docs workflow runs the
 * Linux ones on a fresh runner, so what the pages say works (.generated/install.json). */
export async function installRoutes() {
	const latest = await pythonLatest();
	const spec = packageSpec();
	return {
		uv: {
			unix: ['curl -LsSf https://astral.sh/uv/install.sh | sh', 'uv tool install --python ' + latest + ' ' + spec, 'uv tool update-shell', 'tm1cm --help'],
			windows: ['powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"', 'uv tool install --python ' + latest + ' ' + spec, 'uv tool update-shell', 'tm1cm --help'],
		},
		venv: {
			unix: ['python3 -m venv ~/.venvs/tm1cm', 'source ~/.venvs/tm1cm/bin/activate', 'python -m pip install ' + spec, 'tm1cm --help'],
			// Run by path rather than activated: PowerShell blocks Activate.ps1 unless its execution policy allows scripts
			windows: ['py -' + latest + ' -m venv $HOME\\.venvs\\tm1cm', '& $HOME\\.venvs\\tm1cm\\Scripts\\python -m pip install ' + spec, '& $HOME\\.venvs\\tm1cm\\Scripts\\tm1cm --help'],
		},
	};
}

const terminal = (lines, label) => block(label, lines.join('\n'), label === 'PowerShell' ? 'powershell' : 'sh');

/** Installing with uv: it gets the Python tm1cm needs and keeps tm1cm apart from any other. */
export async function installHtml() {
	const routes = await installRoutes();
	const version = docsVersion();
	return (
		'<p>The easiest way is <a href="https://docs.astral.sh/uv/">uv</a>: one command installs it, and it downloads the Python tm1cm needs and gives tm1cm an environment of its own, apart from your computer\'s Python. Then the <code>tm1cm</code> command works in any terminal.</p>' +
		systemTabs(terminal(routes.uv.unix, 'Terminal'), terminal(routes.uv.windows, 'PowerShell')) +
		'<p><code>uv tool update-shell</code> puts uv\'s tools on your PATH: open a new terminal after it. Later, <code>uv tool upgrade tm1cm</code> updates tm1cm. ' +
		(version.release ? 'This installs the latest release, ' + escape(version.version) + '.' : version.version ? 'This installs the pre-release ' + escape(version.version) + '.' : 'Until 1.0 is on PyPI, this installs it from GitHub.') +
		' Rather use a Python you have? <a href="walkthroughs/first-project/#install">Install it in a virtual environment</a>.</p>'
	);
}

/** Installing into a virtual environment, with a Python of the reader's own. */
export async function installVenvHtml() {
	const routes = await installRoutes();
	const python = await pythonNeeded();
	return (
		'<p>With a Python ' + escape(python) + ' or newer of your own (from <a href="https://www.python.org/downloads/">python.org</a>, say), make a virtual environment for tm1cm, so it doesn\'t touch your system\'s Python or its packages, and install it there:</p>' +
		systemTabs(terminal(routes.venv.unix, 'Terminal'), terminal(routes.venv.windows, 'PowerShell')) +
		'<p>On macOS and Linux, activate the environment in each new terminal before you run <code>tm1cm</code> (the second line). On Windows, run it by its path, <code>$HOME\\.venvs\\tm1cm\\Scripts\\tm1cm</code>, or add <code>$HOME\\.venvs\\tm1cm\\Scripts</code> to your PATH. <code>py</code> is the launcher python.org\'s installer puts on Windows.</p>'
	);
}

export async function promptText() {
	const text = await readFile(path.join(siteDir, 'content', 'prompt.md'), 'utf8');
	const list = await walkthroughs();
	const values = {
		install: await installCommand(),
		python: await pythonNeeded(),
		docs: 'https://skipcheck.io/' + PROJECT.id + '/docs/',
		walkthroughs: list.map((w) => '- ' + w.meta.title + ': https://skipcheck.io/' + PROJECT.id + '/walkthroughs/' + w.slug + '/').join('\n'),
		'llms-full': 'https://skipcheck.io/' + PROJECT.id + '/llms-full.txt',
	};
	return text.replace(/\{\{([\w-]+)\}\}/g, (match, key) => {
		if (!(key in values)) throw new Error('content/prompt.md: no value for {{' + key + '}}');
		return values[key];
	}).trim();
}

/** The prompt, collapsed in the site's <details class="prompt"> with its Copy button, and the links
 * that open it in Claude, as skipcheck-tm1's landing pages and the setup page have them:
 * claude://code/new?q= opens Claude Desktop's Code tab, claude-cli://open?q= the Claude Code CLI
 * (once claude has run interactively). Both fill the prompt in without sending it. */
function promptHtml(text) {
	const q = encodeURIComponent(text);
	return (
		'<details class="prompt"><summary>Prompt <span class="prompt-toggle"><span class="prompt-show">Show the full prompt</span><span class="prompt-hide">Hide the prompt</span></span></summary>' +
		codeBlock(text, null) +
		'</details>' +
		'<p class="actions"><a class="button primary" href="' + escape('claude://code/new?q=' + q) + '">Open in Claude Desktop</a>' +
		'<a class="button" href="' + escape('claude-cli://open?q=' + q) + '">Open in Claude Code</a></p>' +
		'<p class="needs">Either link fills in the prompt, and you press Enter to send it. "Open in Claude Code" is for the terminal app, and works once you\'ve run <code>claude</code> on this computer. ' +
		'Another agent, such as Codex, Cursor or Gemini CLI? Copy the prompt.</p>'
	);
}

async function directive({ name, args }, links) {
	if (name === 'install') return installHtml();
	if (name === 'install-venv') return installVenvHtml();
	if (name === 'step') {
		const [sessionName, id] = args;
		if (!sessionName || !id) throw new Error('::step needs a session and a step');
		return stepHtml(sessionName, id);
	}
	if (name === 'walkthroughs') {
		const list = await walkthroughs();
		return '<ul class="points">' + list.map((w) => '<li><a href="' + links + 'walkthroughs/' + w.slug + '/"><strong>' + escape(w.meta.title) + '</strong></a>: ' + inline(w.meta.summary) + '</li>').join('') + '</ul>';
	}
	if (name === 'prompt') return '<div class="tabs"><div role="tabpanel">' + promptHtml(await promptText()) + '</div></div>';
	throw new Error('no such directive ::' + name);
}

async function blocks(list, links, { inItem = false } = {}) {
	let html = '';
	for (const block of list) {
		if (block.type === 'p') html += '<p' + (inItem ? '' : ' class="more"') + '>' + inline(block.text) + '</p>';
		else if (block.type === 'directive') html += await directive(block, links);
		else {
			let items = '';
			for (const item of block.items) {
				const single = item.length === 1 && item[0].type === 'p';
				items += '<li>' + (single ? inline(item[0].text) : await blocks(item, links, { inItem: true })) + '</li>';
			}
			html += block.type === 'ol' ? '<ol class="numbered">' + items + '</ol>' : '<ul class="points">' + items + '</ul>';
		}
	}
	return html;
}

const HOME = CANONICAL_ORIGIN + '/' + PROJECT.id + '/';
// The landing page's SoftwareApplication, which each walkthrough is about
const SOFTWARE = HOME + '#software';

/** The landing page's structured data: tm1cm as a SoftwareApplication. The license is LICENSE's (and
 * setup.py's), as its SPDX address. A version only once the pages describe one. */
async function softwareData(description) {
	const { version } = docsVersion();
	return {
		'@type': 'SoftwareApplication',
		'@id': SOFTWARE,
		name: PROJECT.title,
		description,
		url: HOME,
		applicationCategory: 'DeveloperApplication',
		// A Python command-line tool: it runs wherever its Python does, and the pages show all three
		operatingSystem: 'Windows, macOS, Linux',
		softwareRequirements: 'Python ' + (await pythonNeeded()) + ' or newer',
		...(version ? { softwareVersion: version } : {}),
		offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
		license: 'https://spdx.org/licenses/GPL-3.0-or-later.html',
		// SoftwareApplication has no codeRepository (that's SoftwareSourceCode's), so the source and the
		// PyPI project are sameAs
		sameAs: [PROJECT.github, PROJECT.pypi],
		author: AUTHOR,
		isPartOf: WEBSITE,
	};
}

/** A walkthrough's structured data: a TechArticle about tm1cm. */
const articleData = (w) => ({
	'@type': 'TechArticle',
	headline: w.meta.title,
	description: w.meta.description,
	url: HOME + 'walkthroughs/' + w.slug + '/',
	inLanguage: 'en',
	about: { '@id': SOFTWARE },
	author: AUTHOR,
	isPartOf: WEBSITE,
});

/** Links in a page two folders down (a walkthrough) are written as from the landing page. */
const rebase = (html, prefix) => (prefix ? html.replace(/(\s(?:href|src)=")(?![a-z][a-z0-9+.-]*:|\/|#)/gi, '$1' + prefix) : html);

export async function landing() {
	const { meta, sections } = parse(await readFile(path.join(siteDir, 'content', PROJECT.id + '.md'), 'utf8'));
	for (const key of ['tagline', 'description', 'kicker']) if (!meta[key]) throw new Error('content/tm1cm.md has no ' + key + ' in its front matter');
	const [lead, ...rest] = sections;
	const version = docsVersion();
	const note = version.release
		? '<p class="release-note"><span class="badge version">v' + escape(version.version) + '</span><span>The latest release.</span></p>'
		: version.version
			? '<p class="release-note" role="note"><span class="badge">Pre-release</span><span>These pages describe ' + escape(version.version) + ', a pre-release.</span></p>'
			: '<p class="release-note" role="note"><span class="badge">Pre-release</span><span>tm1cm 1.0 isn\'t on PyPI yet: the install step gets it from GitHub.</span></p>';
	let main =
		'<section class="hero wrap" aria-labelledby="title"><p class="kicker">' + escape(meta.kicker) + '</p><h1 id="title">' + escape(PROJECT.title) + '</h1>' +
		'<p class="role-line">' + inline(meta.tagline) + '</p>' +
		lead.blocks.map((b) => '<p class="lead">' + inline(b.text) + '</p>').join('') +
		'<p class="actions"><a class="button primary" href="#quick-start">Quick start</a><a class="button" href="#walkthroughs">Walkthroughs</a><a class="button" href="' + PROJECT.github + '">Source on GitHub</a></p>' +
		note + '</section>';
	for (const s of rest) main += section(slug(s.title), s.title, await blocks(s.blocks, ''));
	// The reference last: the landing page is for starting, the reference for looking things up
	const { PAGES } = await import('./reference.mjs');
	main += '<section id="reference" class="section wrap" aria-labelledby="reference-heading"><h2 id="reference-heading" class="section-label">Reference</h2><ul class="cards">' +
		PAGES.map((p) => '<li class="card"><div class="card-head"><h3><a href="docs/' + p.id + '/">' + escape(p.title) + '</a></h3></div><p>' + escape(p.summary) + '</p></li>').join('') + '</ul></section>';
	return page({ title: PROJECT.title, description: meta.description, pathname: '', main, data: await softwareData(meta.description) });
}

export async function walkthroughPages() {
	const list = await walkthroughs();
	const pages = [];
	for (const [index, w] of list.entries()) {
		const [lead, ...rest] = w.sections;
		let main =
			'<section class="hero wrap" aria-labelledby="title"><p class="kicker"><a href="../../">tm1cm</a> · Walkthrough ' + (index + 1) + ' of ' + list.length + '</p>' +
			'<h1 id="title">' + escape(w.meta.title) + '</h1>' + lead.blocks.map((b) => '<p class="lead">' + inline(b.text) + '</p>').join('') + '</section>';
		for (const s of rest) main += section(slug(s.title), s.title, await blocks(s.blocks, ''));
		const next = list[index + 1];
		const others = list.filter((o) => o !== w);
		main += section('more', next ? 'Next' : 'More walkthroughs',
			'<ul class="points">' + (next ? [next] : others).map((o) => '<li><a href="walkthroughs/' + o.slug + '/"><strong>' + escape(o.meta.title) + '</strong></a>: ' + inline(o.meta.summary) + '</li>').join('') + '</ul>' +
			'<p class="more">All the settings, filters, options and exit codes are in <a href="docs/">the reference</a>.</p>');
		pages.push({ slug: w.slug, html: rebase(page({ title: w.meta.title + ' · tm1cm', description: w.meta.description, pathname: 'walkthroughs/' + w.slug + '/', main, mainClass: 'project walkthrough', data: articleData(w) }), '../../') });
	}
	return pages;
}
