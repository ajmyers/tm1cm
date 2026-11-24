// tm1cm's entry for the project store, which skipcheck.io and ajmyers.net draw the projects' cards
// from (see ajmyers/skipcheck.io's README, "The project store"). Written to
// .generated/project-entry.json; the docs workflow checks it on every change and publishes it when
// it deploys a release (docs.yml).
//
//   summary, description   content/tm1cm.md's front matter: card and description
//   version, release       the version the pages describe (docsVersion): a tag's
//   visual                 a terminal: a model fetched into files, reviewed with git, and put on
//                          the next server, with the commands the walkthroughs use
//
//   DOCS_VERSION=1.2.3 node scripts/project.mjs

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { parse } from './markdown.mjs';
import { CANONICAL_ORIGIN, docsVersion, generatedDir, PROJECT, siteDir } from './site.mjs';

// tm1cm comes after skipcheck-tm1's projects (10 to 40) in the lists
const ORDER = 50;

const VISUAL = {
	kind: 'terminal',
	lines: [
		{ text: 'tm1cm --mode get --environment test', prompt: true },
		{ text: '… one file per object, written to data/', tone: 'output' },
		{ text: 'git diff --stat', prompt: true },
		{ text: ' data/process/create_Y2Ksales_cube.process | 4 ++--', tone: 'output' },
		{ text: 'tm1cm --mode put --environment prod', prompt: true },
	],
};

/** tm1cm's entry. */
export async function projectEntry() {
	const { meta } = parse(await readFile(path.join(siteDir, 'content', PROJECT.id + '.md'), 'utf8'));
	for (const key of ['card', 'description']) if (!meta[key]) throw new Error('content/' + PROJECT.id + '.md has no ' + key + ' in its front matter');
	const { version, release } = docsVersion();
	return {
		id: PROJECT.id,
		name: PROJECT.title,
		summary: meta.card,
		description: meta.description,
		kind: 'tool',
		status: 'available',
		version,
		release,
		order: ORDER,
		sites: ['skipcheck.io', 'ajmyers.net'],
		links: [
			{ label: 'Overview', href: CANONICAL_ORIGIN + '/' + PROJECT.id + '/' },
			{ label: 'Docs', href: CANONICAL_ORIGIN + '/' + PROJECT.id + '/docs/' },
			{ label: 'Source', href: PROJECT.github },
		],
		visual: VISUAL,
	};
}

if (import.meta.url === 'file://' + process.argv[1]) {
	const entry = await projectEntry();
	await mkdir(generatedDir, { recursive: true });
	await writeFile(path.join(generatedDir, 'project-entry.json'), JSON.stringify(entry, null, '\t') + '\n');
	console.log('Project entry: ' + entry.id + ' ' + (entry.version ?? '(no version)') + (entry.release ? '' : ', not a release'));
}
