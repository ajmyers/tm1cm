"""Records the docs' walkthroughs: runs each session in docs-site/sessions against TM1 in Docker,
started with IBM's SData sample, and writes what each step printed to
docs-site/example-output/<session>.json. The docs build (docs-site/scripts/sessions.mjs) shows it
under each step, and fails when a step has changed since it was recorded. So after changing a
session, run this (with a TM1 source, as for the other integration tests) and commit what it
writes.

A session is a project made from nothing, in an empty folder: its setup steps aren't shown, its
steps are. A step runs a shell command, writes a file, or shows one. What the pages show is what
the command printed, with what changes from run to run replaced by what a reader would see: the
server's address by the one the session shows, the temporary folder by ~/projects, and the time
in each log line by 09:00.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SESSIONS = os.path.join(REPO, 'docs-site', 'sessions')
OUTPUT = os.path.join(REPO, 'docs-site', 'example-output')
NAMES = sorted(f[:-5] for f in os.listdir(SESSIONS) if f.endswith('.yaml')) if os.path.isdir(SESSIONS) else []

pytestmark = pytest.mark.requires_tm1

# What a reader sees for the server: IBM's SData sample, as skipcheck.io's setup serves it
SHOWN = {'base_url': 'http://localhost:8011', 'user': 'admin', 'password': 'apple'}
TIME = re.compile(r'\b\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}\b')


def step_text(step):
    """What a step is, for its hash: the docs build works it out the same way (sessions.mjs)."""
    if 'run' in step:
        return 'run ' + step['run'].strip()
    if 'write' in step:
        return 'write ' + step['write'] + '\n' + step['content'].strip()
    return 'show ' + step['show']


def step_hash(step):
    return hashlib.sha256(step_text(step).encode('utf-8')).hexdigest()


@pytest.fixture(scope='module')
def sdata():
    from skipcheck_tm1_testcontainers import Tm1Seed
    from skipcheck_tm1_testcontainers import Tm1ServerContainer
    from skipcheck_tm1_testcontainers import Tm1Source

    container = Tm1ServerContainer(Tm1Source.discover()).with_seed(Tm1Seed.SDATA)
    container.start()
    yield container
    container.stop()


def fill(text, values):
    return text.format(**values)


def terminal(text):
    """What a terminal shows for the text: the interactive shell's spinner draws over itself with
    backspaces and carriage returns, which move back along the line (never past its start)."""
    lines = []
    for line in text.split('\n'):
        cells, at = [], 0
        for ch in line:
            if ch == '\b':
                at = max(0, at - 1)
            elif ch == '\r':
                at = 0
            else:
                if at < len(cells):
                    cells[at] = ch
                else:
                    cells.append(ch)
                at += 1
        lines.append(''.join(cells).rstrip())
    return '\n'.join(lines)


def shown(text, real, home):
    text = terminal(text)
    for folder in {home, os.path.realpath(home)}:
        text = text.replace(folder, '~/projects')
    for key in ('base_url',):
        text = text.replace(real[key] + '/api/v1', SHOWN[key] + '/api/v1').replace(real[key], SHOWN[key])
    return TIME.sub('2026-01-01 09:00:00,000', text)


@pytest.mark.parametrize('name', NAMES)
def test_record(name, sdata, tmp_path):
    with open(os.path.join(SESSIONS, name + '.yaml'), encoding='utf-8') as fp:
        session = yaml.safe_load(fp)
    real = {'base_url': sdata.rest_url.rstrip('/').removesuffix('/api/v1'), 'user': sdata.username, 'password': sdata.password}
    home = str(tmp_path / 'projects')
    os.makedirs(home)
    env = dict(os.environ, PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get('PATH', ''),
               GIT_AUTHOR_NAME='Ana', GIT_AUTHOR_EMAIL='ana@example.com', GIT_COMMITTER_NAME='Ana',
               GIT_COMMITTER_EMAIL='ana@example.com', NO_COLOR='1', TERM='dumb', COLUMNS='100')
    cwd = home
    recorded = {}
    for step in session.get('setup', []) + session['steps']:
        record = 'id' in step
        if 'run' in step:
            command = fill(step['run'], real)
            done = subprocess.run(['bash', '-c', command], cwd=cwd, env=env, capture_output=True, text=True, timeout=600,
                                  stdin=subprocess.DEVNULL if 'input' not in step else None, input=step.get('input'))
            output = shown(done.stdout + done.stderr, real, home)
            expected = step.get('exit', 0)
            assert done.returncode == expected, f'{name}: {step["run"]} exited {done.returncode}, not {expected}:\n{output}'
            moved = re.fullmatch(r'cd (\S+)', step['run'].strip())
            if moved:
                cwd = os.path.normpath(os.path.join(cwd, moved.group(1)))
            result = {'output': output.rstrip('\n').split('\n') if output.strip() else [], 'exit': done.returncode}
        elif 'write' in step:
            target = os.path.join(cwd, step['write'])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'w', encoding='utf-8') as fp:
                fp.write(fill(step['content'], real).strip() + '\n')
            result = {}
        else:
            with open(os.path.join(cwd, step['show']), encoding='utf-8') as fp:
                result = {'output': shown(fp.read(), real, home).rstrip('\n').split('\n')}
        if record:
            recorded[step['id']] = {'source': step_hash(step), **result}

    os.makedirs(OUTPUT, exist_ok=True)
    with open(os.path.join(OUTPUT, name + '.json'), 'w', encoding='utf-8') as fp:
        json.dump({'session': name, 'shown': SHOWN, 'steps': recorded}, fp, indent=1, ensure_ascii=False)
        fp.write('\n')
