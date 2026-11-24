// Runs what the pages tell a reader to type, on this system, in a fresh folder: the install routes
// (pages.mjs installRoutes: uv, then a virtual environment), and the walkthrough steps that don't
// need a TM1 server (OFFLINE below), Windows' PowerShell variants on Windows. The docs workflow runs
// it on Linux and on Windows, so the commands for both are tried on real systems; the steps that
// need TM1 are recorded on macOS by the live tests.
//
// The package the routes install is this checkout, not GitHub's master or PyPI's release: what's
// checked is that the commands work, for the code these pages describe.
//
//   node scripts/install-check.mjs [--shell powershell|pwsh] [--steps-only]
//
// --steps-only skips the install routes, for a machine whose own uv and tm1cm shouldn't change:
// tm1cm must be on the PATH already.

import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { installRoutes, packageSpec } from './pages.mjs';
import { session } from './sessions.mjs';
import { repoDir } from './site.mjs';

const windows = process.platform === 'win32';
const shell = process.argv.includes('--shell') ? process.argv[process.argv.indexOf('--shell') + 1] : windows ? 'powershell' : 'bash';
const home = mkdtempSync(path.join(os.tmpdir(), 'tm1cm-docs-'));

/** A new terminal's PATH: on Windows, the user's and the machine's as the registry has them now
 * (an installer may just have changed them); elsewhere, with ~/.local/bin, where uv puts tools. */
const stepsOnly = process.argv.includes('--steps-only');

function freshPath() {
	if (stepsOnly) return process.env.PATH;
	if (!windows) return [path.join(os.homedir(), '.local', 'bin'), process.env.PATH].join(path.delimiter);
	const read = (scope) => execFileSync('powershell', ['-NoProfile', '-Command', "[Environment]::GetEnvironmentVariable('Path','" + scope + "')"]).toString().trim();
	return [read('User'), read('Machine')].join(';');
}

/** The environment of a new terminal. PSModulePath is left out: a Windows PowerShell 5.1 started
 * from PowerShell 7 (as a CI step runs) inherits 7's, and then can't load its own modules. Each
 * PowerShell sets its own when it starts, as it does in a terminal a person opens. */
function terminalEnv() {
	const env = { ...process.env, PATH: freshPath() };
	for (const key of Object.keys(env)) if (key.toLowerCase() === 'psmodulepath') delete env[key];
	return env;
}

function run(command, cwd, input) {
	const args = shell === 'bash' ? ['-c', command] : ['-NoProfile', '-NonInteractive', '-Command', command];
	const done = spawnSync(shell, args, { cwd, encoding: 'utf8', env: terminalEnv(), input, stdio: [input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'], timeout: 600000, maxBuffer: 16 * 1024 * 1024 });
	const output = (done.stdout ?? '') + (done.stderr ?? '');
	console.log('> ' + command + '\n' + output.trimEnd().split('\n').slice(-6).join('\n'));
	if (done.status !== 0) throw new Error(command + ' exited ' + done.status);
	return output;
}

// The install routes, this checkout instead of the package the pages name
const spec = packageSpec();
const routes = await installRoutes();
for (const [name, route] of stepsOnly ? [] : Object.entries(routes)) {
	console.log('\n# Installing with ' + name);
	for (const command of route[windows ? 'windows' : 'unix']) {
		run(command.replaceAll(spec, JSON.stringify(repoDir)).replaceAll('~/.venvs', home + '/venvs').replaceAll('$HOME\\.venvs', home + '\\venvs'), home);
	}
}

// The steps that need no server, with what each must print
const OFFLINE = [
	['first-project', 'scaffold', 'created new scaffold at sales'],
	['first-project', 'cd', null],
	['first-project', 'tree', 'tm1cm.yaml'],
	['interactive', 'apps', 'sales.local'],
	['unattended', 'unreachable', 'exit code: 3'],
	// The hint, which every system's last lines have: Windows PowerShell 5.1 wraps the long lines it
	// redirects, so its last four can start below the message itself
	['unattended', 'unreachable-log', 'Check base_url'],
];
console.log('\n# Walkthrough steps, in ' + shell);
let cwd = path.join(home, 'project');
execFileSync(process.execPath, ['-e', 'require("fs").mkdirSync(process.argv[1], {recursive: true})', cwd]);
for (const [name, id, expected] of OFFLINE) {
	const step = (await session(name)).steps.get(id);
	if (step.shell) {
		const output = run(step.shell.trim(), cwd, step.type.map((line) => line + '\n').join(''));
		if (expected && !output.includes(expected)) throw new Error(name + '/' + id + ' printed no "' + expected + '"');
		continue;
	}
	const command = windows && step.windows ? step.windows.trim() : step.run.trim();
	const moved = /^cd (\S+)$/.exec(command);
	if (moved) {
		cwd = path.join(cwd, moved[1]);
		continue;
	}
	const output = run(command, cwd);
	if (expected && !output.includes(expected)) throw new Error(name + '/' + id + ' printed no "' + expected + '"');
}
console.log('\nEvery command worked.');
