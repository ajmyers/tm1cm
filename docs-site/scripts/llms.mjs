// The docs for coding agents, as the llms.txt convention has them (https://llmstxt.org), at
// /tm1cm/llms.txt (the pages, each with a line saying what's there) and /tm1cm/llms-full.txt (the
// landing page, the walkthroughs with their commands, and the reference, as Markdown). Written from
// the same sources as the pages.

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { parse, plain } from './markdown.mjs';
import { installCommand, promptText, walkthroughs } from './pages.mjs';
import { PAGES } from './reference.mjs';
import { stepMarkdown } from './sessions.mjs';
import { PROJECT, siteDir } from './site.mjs';

const BASE = 'https://skipcheck.io/' + PROJECT.id + '/';

async function blocksText(blocks) {
	const out = [];
	for (const block of blocks) {
		if (block.type === 'p') out.push(plain(block.text));
		else if (block.type === 'directive') {
			if (block.name === 'step') out.push(await stepMarkdown(block.args[0], block.args[1]));
			else if (block.name === 'install') out.push('```\n$ ' + (await installCommand()) + '\n```');
		} else {
			for (const [i, item] of block.items.entries()) out.push((block.type === 'ol' ? i + 1 + '. ' : '- ') + (await blocksText(item)).replaceAll('\n', '\n   '));
		}
	}
	return out.join('\n\n');
}

export async function llms(ref) {
	const landing = parse(await readFile(path.join(siteDir, 'content', PROJECT.id + '.md'), 'utf8'));
	const list = await walkthroughs();
	const short =
		'# tm1cm\n\n> ' + landing.meta.description + '\n\n' +
		'## Docs\n\n- [Overview](' + BASE + '): what tm1cm does, and a quick start\n' +
		list.map((w) => '- [' + w.meta.title + '](' + BASE + 'walkthroughs/' + w.slug + '/): ' + plain(w.meta.summary)).join('\n') + '\n' +
		PAGES.map((p) => '- [' + p.title + '](' + BASE + 'docs/' + p.id + '/): ' + p.summary).join('\n') + '\n\n' +
		'## Optional\n\n- [Everything above in one file](' + BASE + 'llms-full.txt)\n- [Source](' + PROJECT.github + ')\n';

	let full = '# tm1cm\n\n> ' + landing.meta.description + '\n\n';
	for (const s of landing.sections) full += (s.title ? '## ' + s.title + '\n\n' : '') + (await blocksText(s.blocks)) + '\n\n';
	full += '## A prompt for a coding agent\n\n' + (await promptText()) + '\n\n';
	for (const w of list) {
		full += '# Walkthrough: ' + w.meta.title + '\n\n' + BASE + 'walkthroughs/' + w.slug + '/\n\n';
		for (const s of w.sections) full += (s.title ? '## ' + s.title + '\n\n' : '') + (await blocksText(s.blocks)) + '\n\n';
	}
	full += '# Reference: connection settings\n\n' + ref.settings.map((s) => '- `' + s.name + '` (' + s.file + '): ' + s.description).join('\n') + '\n\n';
	full += '# Reference: tm1cm.yaml\n\n' + ref.tm1cm_yaml.map((s) => '## ' + s.title + '\n\n' + s.text.paragraphs.join('\n\n') + (s.text.format ? '\n\nFormat: `' + s.text.format + '`' : '') + '\n\n' + s.settings.map((x) => '- `' + x.name + '`: ' + JSON.stringify(x.default)).join('\n')).join('\n\n') + '\n\n';
	full += '# Reference: command line\n\n```\n' + ref.command_line.usage + '\n```\n\n' + ref.command_line.arguments.map((a) => '- `' + a.flags.join(', ') + '`: ' + a.help).join('\n') + '\n\n';
	full += '# Reference: exit codes\n\n' + ref.exit_codes.map((c) => '- ' + c.code + ': ' + c.meaning).join('\n') + '\n\n';
	full += '# Reference: project files\n\n' + ref.files.map((f) => '- ' + f.type + ': `' + f.pattern + '`').join('\n') + '\n';
	return { short, full };
}
