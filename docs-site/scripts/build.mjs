// Builds tm1cm's pages into dist/tm1cm/: the landing page, the walkthroughs, the reference, the
// search index, the docs for agents, the sitemap and release.json; then checks every link. Fails, listing them,
// on a step that isn't recorded or changed since it was, and on a broken link.
//
//   PYTHON=<a python with tm1cm installed> node scripts/build.mjs

import { cp, mkdir, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { checkLinks } from './check-links.mjs';
import { llms } from './llms.mjs';
import { installRoutes, landing, walkthroughPages } from './pages.mjs';
import { referencePages } from './reference.mjs';
import { problems } from './sessions.mjs';
import { CANONICAL_ORIGIN, distDir, docsVersion, escape, extractReference, generatedDir, outDir, PROJECT, siteDir } from './site.mjs';

const stale = await problems();
if (stale.length) throw new Error(stale.length + " problem(s) with the walkthroughs' recordings (docs-site/example-output):\n  " + stale.join('\n  '));

await rm(distDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
await cp(path.join(siteDir, 'assets'), path.join(outDir, 'assets'), { recursive: true });

// Every page written, by its canonical address, for the sitemap
const written = [];
const write = async (relative, text) => {
	const file = path.join(outDir, relative);
	if (path.basename(relative) === 'index.html') written.push(CANONICAL_ORIGIN + '/' + path.posix.join(PROJECT.id, path.dirname(relative).split(path.sep).join('/'), '/'));
	await mkdir(path.dirname(file), { recursive: true });
	await writeFile(file, text);
};

await write('index.html', await landing());
for (const w of await walkthroughPages()) await write(path.join('walkthroughs', w.slug, 'index.html'), w.html);
const { pages, index, ref } = await referencePages(extractReference());
for (const p of pages) await write(path.join('docs', p.id, 'index.html'), p.html);
await write('search.json', JSON.stringify(index) + '\n');
const { short, full } = await llms(ref);
await write('llms.txt', short);
await write('llms-full.txt', full);
// Every page, for search engines: skipcheck.io's robots.txt names this sitemap
await write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + written.map((url) => '<url><loc>' + escape(url) + '</loc></url>\n').join('') + '</urlset>\n');
// The version these pages describe, for the site's home page badge
await write('release.json', JSON.stringify(docsVersion()) + '\n');

// The install commands the pages show, for the docs workflow to run on a fresh runner
await mkdir(generatedDir, { recursive: true });
await writeFile(path.join(generatedDir, 'install.json'), JSON.stringify(await installRoutes(), null, 1) + '\n');

const checked = await checkLinks();
console.log('Built ' + (2 + pages.length) + ' kinds of page into ' + path.relative(siteDir, outDir) + '; ' + checked + ' links checked');
