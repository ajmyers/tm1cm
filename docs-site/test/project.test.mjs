import assert from 'node:assert/strict';
import { test } from 'node:test';
import { projectEntry } from '../scripts/project.mjs';

test("the entry's card is the landing page's, with its links on skipcheck.io and the source", async () => {
	const entry = await projectEntry();
	assert.equal(entry.id, 'tm1cm');
	assert.match(entry.summary, /^A command-line tool/);
	assert.deepEqual(entry.links.map((l) => l.href), ['https://skipcheck.io/tm1cm/', 'https://skipcheck.io/tm1cm/docs/', 'https://github.com/ajmyers/tm1cm']);
	assert.equal(entry.visual.kind, 'terminal');
});

test("a tag's version is a release; without one, it isn't", async () => {
	const before = process.env.DOCS_VERSION;
	try {
		process.env.DOCS_VERSION = '1.2.3';
		assert.deepEqual(await projectEntry().then(({ version, release }) => ({ version, release })), { version: '1.2.3', release: true });
		process.env.DOCS_VERSION = '1.3.0rc1';
		assert.equal((await projectEntry()).release, false);
		delete process.env.DOCS_VERSION;
		assert.deepEqual(await projectEntry().then(({ version, release }) => ({ version, release })), { version: null, release: false });
	} finally {
		if (before === undefined) delete process.env.DOCS_VERSION;
		else process.env.DOCS_VERSION = before;
	}
});
