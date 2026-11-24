// The small part of Markdown the content files are written in, as in skipcheck-tm1's api-site:
//
//   ---                      front matter: "key: value" lines between two --- lines
//   ## Heading               starts a section
//   1. text / - text         a numbered or bulleted item; indented lines continue it
//   ::name arg arg           a directive, alone on its line (indented, inside an item): the page
//                            builder replaces it with generated content, such as a recorded step
//   **bold**, `code`, [text](address)
//
// Commands and files are never typed into a content file: they come from a directive, which names
// a step of a session that the live tests run against TM1 (sessions.mjs). A fenced code block
// fails the build, naming its line.

import { escape } from './site.mjs';

/** Inline Markdown as HTML. */
export function inline(text) {
	return escape(text)
		.replace(/`([^`]+)`/g, '<code>$1</code>')
		.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
		.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2">$1</a>');
}

/** Inline Markdown as plain text, for the docs for agents and the search index. */
export const plain = (text) => text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '$1 ($2)');

/** A content file as { meta, sections }: each section { title, blocks }, the first (before any
 * heading) with a null title. A block is { type: 'p', text }, { type: 'ol' | 'ul', items: [blocks] }
 * or { type: 'directive', name, args }. */
export function parse(source) {
	const meta = {};
	let body = source.replaceAll('\r\n', '\n');
	const front = /^---\n([\s\S]*?)\n---\n/.exec(body);
	if (front) {
		for (const line of front[1].split('\n')) {
			const pair = /^([\w-]+):\s*(.*)$/.exec(line);
			if (pair) meta[pair[1]] = pair[2].trim();
		}
		body = body.slice(front[0].length);
	}
	const sections = [{ title: null, blocks: [] }];
	let list = null;
	let item = null;
	let paragraph = null;
	const target = () => item ?? sections.at(-1).blocks;
	const flush = () => {
		if (paragraph) target().push({ type: 'p', text: paragraph.join(' ') });
		paragraph = null;
	};
	const endList = () => {
		list = null;
		item = null;
	};
	const offset = source.replaceAll('\r\n', '\n').split('\n').length - body.split('\n').length;
	for (const [index, line] of body.split('\n').entries()) {
		if (/^\s*(```|~~~)/.test(line)) {
			throw new Error('line ' + (index + offset + 1) + ': a code block. Commands and files come from a directive (::step), never typed into a content file, so they are run against TM1');
		}
		const heading = /^## +(.+)$/.exec(line);
		const marker = /^(\d+\.|-) +(.*)$/.exec(line);
		const directive = /^\s*::([\w-]+)\s*(.*)$/.exec(line);
		if (heading) {
			flush();
			endList();
			sections.push({ title: heading[1].trim(), blocks: [] });
		} else if (line.trim() === '') {
			flush();
		} else if (marker) {
			flush();
			const type = marker[1] === '-' ? 'ul' : 'ol';
			if (!list || list.type !== type) {
				list = { type, items: [] };
				sections.at(-1).blocks.push(list);
			}
			item = [];
			list.items.push(item);
			paragraph = [marker[2].trim()];
		} else if (directive) {
			flush();
			if (!/^\s/.test(line)) endList();
			target().push({ type: 'directive', name: directive[1], args: directive[2].trim() === '' ? [] : directive[2].trim().split(/\s+/) });
		} else {
			if (item && !/^\s/.test(line)) {
				flush();
				endList();
			}
			(paragraph ??= []).push(line.trim());
		}
	}
	flush();
	return { meta, sections };
}

export const slug = (title) =>
	title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '');
