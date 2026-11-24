// The walkthroughs' commands, files and what they printed: the sessions in sessions/, as the live
// tests ran them against TM1 with IBM's SData sample (tests/tm1cm/docs_recordings_test.py), which
// records each step in example-output/<session>.json with a hash of the step.
//
// A step's windows: is the same command in PowerShell, shown on the Windows tab. It isn't part of the
// hash: the recording is of the command run on macOS, and the docs workflow runs the Windows ones
// that don't need TM1 on a Windows runner (scripts/windows-check.mjs).
//
// A page shows a step as it was run, with the values the reader would see ({base_url} as
// http://localhost:8011), and under a command what it printed. The build fails when a step has no
// recording, or has changed since it was recorded (its hash differs): run the live tests to record
// it, and commit what they write. A recording of a step that's no longer in its session fails too.

import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { load } from './yaml.mjs';
import { block, escape, siteDir, systemTabs, tabBox } from './site.mjs';

const sessionsDir = path.join(siteDir, 'sessions');
const outputDir = path.join(siteDir, 'example-output');

/** What a step is, for its hash, as the recorder works it out (step_text in the live test). */
export function stepText(step) {
	if ('shell' in step) return 'shell ' + step.shell.trim() + '\n' + step.type.join('\n');
	if ('run' in step) return 'run ' + step.run.trim();
	if ('write' in step) return 'write ' + step.write + '\n' + step.content.trim();
	return 'show ' + step.show;
}

export const stepHash = (step) => createHash('sha256').update(stepText(step), 'utf8').digest('hex');

const cache = new Map();

/** A session and its recording: { steps (by id), recording }. */
export async function session(name) {
	if (!cache.has(name)) {
		const file = path.join(sessionsDir, name + '.yaml');
		const definition = load(await readFile(file, 'utf8'));
		const recording = await readFile(path.join(outputDir, name + '.json'), 'utf8').then(JSON.parse, () => null);
		const steps = new Map((definition.steps ?? []).filter((s) => s.id).map((s) => [s.id, s]));
		cache.set(name, { steps, recording });
	}
	return cache.get(name);
}

/** The problems with every session's recording: missing, stale, or recording steps that are gone. */
export async function problems() {
	const found = [];
	for (const file of (await readdir(sessionsDir)).filter((f) => f.endsWith('.yaml'))) {
		const name = file.slice(0, -5);
		const { steps, recording } = await session(name);
		if (!recording) {
			found.push(name + ': not recorded. Run the live tests (docs_recordings_test) and commit docs-site/example-output/' + name + '.json');
			continue;
		}
		for (const [id, step] of steps) {
			const recorded = recording.steps[id];
			if (!recorded) found.push(name + '/' + id + ': not recorded');
			else if (recorded.source !== stepHash(step)) found.push(name + '/' + id + ': changed since it was recorded');
		}
		for (const id of Object.keys(recording.steps)) if (!steps.has(id)) found.push(name + '/' + id + ': recorded, but not in the session any more');
	}
	return found;
}

// What the recorder marks a typed line with in a shell transcript: U+2063, an invisible separator
const TYPED = String.fromCharCode(0x2063);

const fill = (text, shown) => text.replace(/\{(\w+)\}/g, (match, key) => (key in shown ? shown[key] : match));

/** What a step's output shows: all of it, or its first (head) or last (tail) lines, saying how many are left out. */
function trimmed(lines, step) {
	if (step.tail && lines.length > step.tail) return ['… ' + (lines.length - step.tail) + ' lines before', ...lines.slice(-step.tail)];
	if (step.head && lines.length > step.head) return [...lines.slice(0, step.head), '… ' + (lines.length - step.head) + ' more lines'];
	return lines;
}

const LANGUAGE = { '.yaml': 'yaml', '.yml': 'yaml', '.json': 'json' };

/** A step as HTML, in a tab box as skipcheck-tm1's examples are: a command and what it printed
 * (behind the system tabs when the command differs on Windows), a file written, or a file shown. */
export async function stepHtml(name, id) {
	const { steps, recording } = await session(name);
	const step = steps.get(id);
	if (!step) throw new Error('::step ' + name + ' ' + id + ': no such step in sessions/' + name + '.yaml');
	const recorded = recording?.steps[id];
	const shown = recording?.shown ?? {};
	if ('shell' in step) {
		// A transcript, as the terminal shows it: what was typed (marked by the recorder) in bold
		const typedLine = new RegExp(TYPED + '([^' + TYPED + ']*)' + TYPED, 'g');
		const html = trimmed(recorded?.output ?? [], step).map((line) => escape(line).replace(typedLine, '<strong class="typed">$1</strong>')).join('\n');
		return tabBox([{ id: 'any', label: '', html: block('Terminal', fill(step.shell.trim(), shown), 'sh') + '<p class="caption">Then type at its prompt (in bold)</p><pre class="output transcript"><code>' + html + '</code></pre>' }]);
	}
	if ('run' in step) {
		const lines = recorded?.output ?? [];
		const output = lines.length > 0
			? block('Output' + (recorded.exit ? '<span class="exit">exit code ' + recorded.exit + '</span>' : ''), trimmed(lines, step).join('\n'), null, 'output')
			: '';
		if (step.windows) {
			return systemTabs(
				block('Terminal', fill(step.run.trim(), shown), 'sh') + output,
				block('PowerShell', fill(step.windows.trim(), shown), 'powershell') + (output ? output.replace('>Output', '>Output, as on macOS') : ''),
			);
		}
		return tabBox([{ id: 'any', label: '', html: block('Terminal', fill(step.run.trim(), shown), 'sh') + output }]);
	}
	if ('write' in step) return tabBox([{ id: 'any', label: '', html: block(escape(step.write), fill(step.content.trim(), shown), LANGUAGE[path.extname(step.write)]) }]);
	return tabBox([{ id: 'any', label: '', html: block(escape(step.show), trimmed(recorded?.output ?? [], step).join('\n'), null, 'output') }]);
}

/** A step as Markdown text, for the docs for agents. */
export async function stepMarkdown(name, id) {
	const { steps, recording } = await session(name);
	const step = steps.get(id);
	const shown = recording?.shown ?? {};
	if ('shell' in step) return '```\n' + fill(step.shell.trim(), shown) + '\n```\n\nthen type, at its prompt:\n\n```\n' + step.type.join('\n') + '\n```';
	if ('run' in step) return '```\n' + fill(step.run.trim(), shown) + '\n```' + (step.windows ? '\n\nOn Windows (PowerShell):\n\n```\n' + fill(step.windows.trim(), shown) + '\n```' : '');
	if ('write' in step) return step.write + ':\n```\n' + fill(step.content.trim(), shown) + '\n```';
	return '(the file ' + step.show + ')';
}
