import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { test } from 'node:test';
import { parse } from '../scripts/markdown.mjs';
import { installRoutes, packageSpec, pythonLatest } from '../scripts/pages.mjs';
import { problems, stepHash } from '../scripts/sessions.mjs';
import { siteDir } from '../scripts/site.mjs';
import { load } from '../scripts/yaml.mjs';

const sessionsDir = path.join(siteDir, 'sessions');
const sessionFiles = (await readdir(sessionsDir)).filter((f) => f.endsWith('.yaml'));

test('a code block in a content file fails, naming its line', () => {
	assert.throws(() => parse('Text\n\n```\ntm1cm --help\n```\n'), /line 3: a code block/);
});

test('the content parser reads front matter, sections, lists and directives', () => {
	const { meta, sections } = parse('---\ntitle: T\n---\nLead.\n\n## Steps\n\n1. **One.**\n   ::step s a\n2. Two.\n');
	assert.equal(meta.title, 'T');
	assert.equal(sections[1].title, 'Steps');
	assert.deepEqual(sections[1].blocks[0].items[0][1], { type: 'directive', name: 'step', args: ['s', 'a'] });
});

test('every session reads the same with this loader as with PyYAML, which the live tests use', () => {
	const python = process.env.PYTHON ?? 'python3';
	for (const file of sessionFiles) {
		const full = path.join(sessionsDir, file);
		let theirs;
		try {
			theirs = JSON.parse(execFileSync(python, ['-c', 'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))', full]).toString());
		} catch {
			return; // no Python with PyYAML here: the docs workflow has one
		}
		assert.deepEqual(load(execFileSync('cat', [full]).toString()), theirs, file);
	}
});

test("every step is recorded, and hasn't changed since", async () => {
	assert.deepEqual(await problems(), []);
});

test("a step's hash is the recorder's: what it runs, not its Windows variant or how much is shown", () => {
	const step = { id: 'x', run: 'tm1cm --help\n', tail: 3 };
	assert.equal(stepHash(step), stepHash({ ...step, windows: 'tm1cm --help', tail: 9 }));
	assert.notEqual(stepHash(step), stepHash({ ...step, run: 'tm1cm --version' }));
});

test('the install steps name the newest Python setup.py lists, and the same package on every system', async () => {
	assert.equal(await pythonLatest(), '3.14');
	const routes = await installRoutes();
	for (const route of Object.values(routes)) {
		for (const system of ['unix', 'windows']) assert.ok(route[system].some((c) => c.includes(packageSpec())), system);
	}
});

test('a Windows variant is only where the command differs, and every walkthrough command that uses a Unix tool has one', async () => {
	const unixOnly = /(\bfind\b|\bls\b|\btail\b|\bprintf\b|\bxargs\b|\becho\b|2>&1|<\s*\/dev\/null|&&)/;
	for (const file of sessionFiles) {
		const { steps } = load(await readFile(path.join(sessionsDir, file), 'utf8'));
		for (const step of steps.filter((s) => s.run)) {
			if (unixOnly.test(step.run)) assert.ok(step.windows, file + '/' + step.id + ' needs a Windows variant');
			if (step.windows) assert.notEqual(step.windows.trim(), step.run.trim(), file + '/' + step.id);
		}
	}
});
