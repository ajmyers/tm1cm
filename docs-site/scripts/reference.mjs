// The reference, /tm1cm/docs/, written from the code by extract/reference.py: every connection
// setting (tm1.SETTING_DOCS), tm1cm.yaml's settings (the commented default the scaffold writes),
// the command line (__main__.parser), the exit codes (errors.EXIT_CODES) and the project's files
// (each type's folder and extension, and files.PARTS). Nothing here is typed by hand: the
// extractor fails when any of them isn't described, and so does this build.
//
// The pages are laid out as skipcheck-tm1's docs are (assets/reference.css is its docs.css): a
// sidebar of the reference, a bar with where you are and the search box, then a table to scan
// and each entry in full. Also the search index, /tm1cm/search.json.

import { readFile } from 'node:fs/promises';
import { inline, slug } from './markdown.mjs';
import { walkthroughs } from './pages.mjs';
import { escape, page, searchBox } from './site.mjs';

export const PAGES = [
	{ id: 'settings', title: 'Connection settings', summary: 'connect.yaml and credentials.yaml: the server, logging in, certificates.' },
	{ id: 'tm1cm-yaml', title: 'tm1cm.yaml', summary: 'Which objects tm1cm moves: the filters for each type, and the other settings.' },
	{ id: 'command-line', title: 'Command line', summary: "The tm1cm command's options and modes." },
	{ id: 'exit-codes', title: 'Exit codes', summary: 'What each exit code means, for scripts and CI.' },
	{ id: 'files', title: 'Project files', summary: "Where each object's file is in a project, and how it's named." },
];

const DOCS = '/tm1cm/docs/';
const firstSentence = (text) => (/^(.*?[.:])(\s|$)/.exec(text)?.[1] ?? text);
const defaultText = (v) => (v === null || v === undefined || v === '' ? "''" : Array.isArray(v) ? v.join('\n') : typeof v === 'string' ? v : String(v));

function layout(current, title, lead, sections, body, list) {
	const nav =
		'<nav class="sidebar" aria-label="tm1cm reference"><p><a href="' + DOCS + '">tm1cm docs</a></p>' +
		'<p class="area">Reference</p><ul>' +
		PAGES.map((p) =>
			'<li' + (p.id === current ? ' class="here"' : '') + '><a href="' + DOCS + p.id + '/"' + (p.id === current ? ' aria-current="page"' : '') + '>' + escape(p.title) + '</a></li>' +
			(p.id === current ? sections.map((s) => '<li class="nested"><a href="#' + s.id + '">' + escape(s.title) + '</a></li>').join('') : ''),
		).join('') +
		'</ul><p class="area">Walkthroughs</p><ul>' +
		list.map((w) => '<li><a href="/tm1cm/walkthroughs/' + w.slug + '/">' + escape(w.meta.title) + '</a></li>').join('') +
		'</ul><p class="area">tm1cm</p><ul><li><a href="/tm1cm/">Overview</a></li><li><a href="https://github.com/ajmyers/tm1cm">Source on GitHub</a></li></ul></nav>';
	const crumbs = '<p class="crumbs"><a href="/tm1cm/">tm1cm</a> · ' + (current ? '<a href="' + DOCS + '">Reference</a> · ' + escape(title) : 'Reference') + '</p>';
	return '<div class="docs">' + nav + '<main id="main" class="guide"><div class="toolbar">' + crumbs + searchBox() + '</div><h1>' + escape(title) + '</h1>' + (lead ? '<p class="lead">' + lead + '</p>' : '') + body + '</main></div>';
}

const member = (id, name, html, tags = []) =>
	'<section class="member" id="' + id + '"><header><h3><a href="#' + id + '">' + escape(name) + '</a></h3>' + tags.map((t) => '<span class="tag">' + escape(t) + '</span>').join('') + '</header><div class="member-body">' + html + '</div></section>';

const scan = (rows) => '<table class="members"><tbody>' + rows.map(([id, name, text]) => '<tr><td><a href="#' + id + '"><code>' + escape(name) + '</code></a></td><td>' + escape(text) + '</td></tr>').join('') + '</tbody></table>';

export async function referencePages(file) {
	const ref = JSON.parse(await readFile(file, 'utf8'));
	const list = await walkthroughs();
	const index = [];
	const pages = [];
	const add = (pageId, id, name, summary) => index.push({ title: name, page: PAGES.find((p) => p.id === pageId).title, summary, url: DOCS + pageId + '/#' + id });
	const emit = (id, title, description, html) => pages.push({ id, html: page({ title: title + ' · tm1cm', description, pathname: 'docs/' + (id ? id + '/' : ''), main: html, reference: true }) });

	// Connection settings
	{
		const groups = [
			{ id: 'connect', title: 'connect.yaml', file: 'connect.yaml', lead: 'The server, and how to reach it: <code>config/&lt;environment&gt;/connect.yaml</code>, or <code>config/default/</code> for every environment.' },
			{ id: 'credentials', title: 'credentials.yaml', file: 'credentials.yaml', lead: "Who logs in: <code>config/default/credentials.yaml</code>, or an environment's own. The scaffold's <code>.gitignore</code> keeps these files out of git." },
		];
		let body = '';
		for (const g of groups) {
			const settings = ref.settings.filter((s) => s.file === g.file && !s.ignored);
			body += '<section id="' + g.id + '"><h2>' + escape(g.title) + '</h2><p>' + g.lead + '</p>' + scan(settings.map((s) => ['setting-' + s.name, s.name, firstSentence(s.description)])) +
				settings.map((s) => {
					add('settings', 'setting-' + s.name, s.name, s.description);
					return member('setting-' + s.name, s.name, '<p>' + escape(s.description) + '</p>', [...(s.secret ? ['secret'] : []), ...(s.unsupported ? ['not supported'] : [])]);
				}).join('') + '</section>';
		}
		const ignored = ref.settings.filter((s) => s.ignored).map((s) => '<code>' + escape(s.name) + '</code>');
		body += '<section id="ignored"><h2>Accepted and ignored</h2><p>Settings of TM1py, which tm1cm used before 1.0, that skipcheck-tm1 manages itself: ' + ignored.join(', ') + '. A project that has them works as before.</p></section>';
		emit('settings', 'Connection settings', 'Every setting of connect.yaml and credentials.yaml for tm1cm, the TM1 model migration tool.',
			layout('settings', 'Connection settings', 'What tm1cm reads from <code>connect.yaml</code> and <code>credentials.yaml</code>, for each environment. Any of them can go in either file, and <code>--connect KEY=VALUE</code> (<code>-c</code>) on the command line wins over both.',
				[...groups, { id: 'ignored', title: 'Accepted and ignored' }], body, list));
	}

	// tm1cm.yaml
	{
		const sections = ref.tm1cm_yaml.map((s) => ({ id: slug(s.title), title: s.title, s }));
		const body = sections.map(({ id, title, s }) => {
			let html = '<section id="' + id + '"><h2>' + escape(title) + '</h2>' + s.text.paragraphs.map((p) => '<p>' + escape(p) + '</p>').join('');
			if (s.text.format) html += '<p class="format">Format: <code>' + escape(s.text.format) + '</code></p>';
			if (s.text.examples.length) html += '<ul class="examples">' + s.text.examples.map((e) => '<li><code>' + escape(e.value) + '</code>' + (e.meaning ? ': ' + escape(e.meaning) : '') + '</li>').join('') + '</ul>';
			html += '<table class="members"><thead><tr><th>Setting</th><th>Default</th></tr></thead><tbody>' + s.settings.map((x) => {
				add('tm1cm-yaml', x.name, x.name, title + ': ' + (s.text.paragraphs[0] ?? ''));
				return '<tr id="' + x.name + '"><td><code>' + escape(x.name) + '</code></td><td class="default"><code>' + escape(defaultText(x.default)) + '</code></td></tr>';
			}).join('') + '</tbody></table></section>';
			return html;
		}).join('');
		emit('tm1cm-yaml', 'tm1cm.yaml', "tm1cm.yaml's filters and settings: which TM1 objects tm1cm moves.",
			layout('tm1cm-yaml', 'tm1cm.yaml', "Which objects tm1cm moves, and how it writes them. <code>config/default/tm1cm.yaml</code> holds every setting, with these defaults, and an environment's own <code>tm1cm.yaml</code> overrides any of them. Section by section, as the scaffold writes it.", sections, body, list));
	}

	// Command line
	{
		const cl = ref.command_line;
		const rows = cl.arguments.map((a) => ({ id: 'option-' + a.flags[0].replace(/^-+/, ''), name: a.flags.join(', ') + (a.metavar ? ' ' + a.metavar : ''), a }));
		const body = '<section id="usage"><h2>Usage</h2><pre><code>' + escape(cl.usage) + '</code></pre></section>' +
			'<section id="options"><h2>Options</h2>' + scan(rows.map((r) => [r.id, r.name, r.a.help])) +
			rows.map(({ id, name, a }) => {
				add('command-line', id, a.flags.join(', '), a.help);
				let html = '<p>' + escape(a.help[0].toUpperCase() + a.help.slice(1)) + '.</p>';
				if (a.choices) html += '<p>One of ' + a.choices.map((c) => '<code>' + escape(c) + '</code>').join(', ') + (a.default ? '; <code>' + escape(a.default) + '</code> unless given.' : '.') + '</p>';
				if (a.repeat) html += '<p>Give it as many times as needed.</p>';
				return member(id, name, html);
			}).join('') + '</section>';
		emit('command-line', 'Command line', "The tm1cm command's options: get, put, scaffold and the interactive shell.",
			layout('command-line', 'Command line', escape(cl.description) + " Run it in a project's folder, or give one with <code>--path</code>.", [{ id: 'usage', title: 'Usage' }, { id: 'options', title: 'Options' }], body, list));
	}

	// Exit codes
	{
		const body = '<section id="codes"><h2>Exit codes</h2><table class="members"><thead><tr><th>Code</th><th>Meaning</th></tr></thead><tbody>' + ref.exit_codes.map((c) => {
			add('exit-codes', 'code-' + c.code, 'exit code ' + c.code, c.meaning);
			return '<tr id="code-' + c.code + '"><td><code>' + c.code + '</code></td><td>' + escape(c.meaning) + '</td></tr>';
		}).join('') + '</tbody></table><p>The message says more, and the log has a full report: <a href="/tm1cm/walkthroughs/unattended/">Run tm1cm unattended</a>.</p></section>';
		emit('exit-codes', 'Exit codes', "What tm1cm's exit codes mean.", layout('exit-codes', 'Exit codes', "What the <code>tm1cm</code> command's exit code means, so a script or a CI job can tell what went wrong.", [{ id: 'codes', title: 'Exit codes' }], body, list));
	}

	// Files
	{
		const body = '<section id="types"><h2>Object files</h2><table class="members"><thead><tr><th>Type</th><th>File</th></tr></thead><tbody>' + ref.files.map((f) => {
			add('files', 'type-' + f.type, f.type.replaceAll('_', ' ') + ' files', f.pattern);
			return '<tr id="type-' + f.type + '"><td>' + escape(f.type.replaceAll('_', ' ')) + '</td><td><code>' + escape(f.pattern) + '</code></td></tr>';
		}).join('') + '</tbody></table>' +
			"<p>An application's documents (a spreadsheet, say) are kept as they are, beside the <code>.application</code> files of its folder. A character a file name can't hold is percent-encoded, as TM1's REST API does.</p></section>" +
			"<section id=\"config\"><h2>Settings and the log</h2><table class=\"members\"><tbody><tr><td><code>config/default/</code></td><td>What every environment shares: <code>tm1cm.yaml</code>, and <code>connect.yaml</code> and <code>credentials.yaml</code> when they're the same everywhere.</td></tr><tr><td><code>config/&lt;environment&gt;/</code></td><td>An environment's own settings (test, prod...), each winning over the default.</td></tr><tr><td><code>&lt;project&gt;.log</code></td><td>The log, in the folder tm1cm runs in. <code>--log</code> names another.</td></tr></tbody></table></section>";
		emit('files', 'Project files', "Where tm1cm writes each TM1 object's file in a project.",
			layout('files', 'Project files', "Where each object's file is, under the project's folder. The folders and extensions are tm1cm.yaml's, and these are their defaults.", [{ id: 'types', title: 'Object files' }, { id: 'config', title: 'Settings and the log' }], body, list));
	}

	// The reference's home
	{
		const body = '<ul class="start">' + PAGES.map((p) => '<li><a href="' + DOCS + p.id + '/"><strong>' + escape(p.title) + '</strong>' + escape(p.summary) + '</a></li>').join('') + '</ul>' +
			'<h2 id="walkthroughs">Walkthroughs</h2><ul class="areas">' + list.map((w) => '<li><a href="/tm1cm/walkthroughs/' + w.slug + '/">' + escape(w.meta.title) + '</a><span>' + inline(w.meta.summary) + '</span></li>').join('') + '</ul>';
		emit('', 'Reference', "tm1cm's reference: connection settings, tm1cm.yaml, the command line and exit codes.",
			layout(null, 'tm1cm docs', 'Everything tm1cm reads and does, written from its code: the settings, the filters, the command line, and what its exit codes mean. New to tm1cm? Start with <a href="/tm1cm/walkthroughs/first-project/">the first walkthrough</a>.', [], body, list));
		for (const w of list) index.push({ title: w.meta.title, page: 'Walkthrough', summary: w.meta.summary, url: '/tm1cm/walkthroughs/' + w.slug + '/' });
	}
	return { pages, index, ref };
}
