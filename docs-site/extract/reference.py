"""Reads tm1cm's reference from its code, for the docs site: the connection settings, tm1cm.yaml's
settings, the command line, the exit codes and the project's files. Writes it as JSON to the path
given (docs-site/.generated/reference.json), and fails, naming what's missing, when any of them
isn't described, so the reference can't fall behind the code.

    python docs-site/extract/reference.py docs-site/.generated/reference.json
    python docs-site/extract/reference.py --check

It reads the tm1cm that's imported: the checkout, when it's installed with pip install -e.
"""
import argparse
import json
import os
import re
import sys

import yaml

from tm1cm import __main__ as cli
from tm1cm import errors
from tm1cm import files
from tm1cm import tm1

INCLUDE = os.path.join(os.path.dirname(cli.__file__), 'include')


def settings():
    found = []
    for name, (where, description) in tm1.SETTING_DOCS.items():
        found.append({
            'name': name,
            'file': where + '.yaml',
            'description': description,
            'secret': name in errors.SECRET_KEYS,
            'ignored': name in tm1._IGNORED,
            'unsupported': description.startswith('Not supported'),
        })
    return found


def tm1cm_yaml():
    """tm1cm.yaml's sections, from the commented default the scaffold writes: each comment block
    and the settings under it, with their defaults."""
    path = os.path.join(INCLUDE, 'tm1cm.yaml')
    text = open(path, encoding='utf-8').read()
    defaults = yaml.safe_load(text)
    sections = []
    comment, keys = [], []

    def close():
        if keys:
            lines = [line[1:].rstrip() for line in comment]
            title = lines[0].strip().rstrip(':') if lines else ''
            body = [line[1:] if line.startswith(' ') else line for line in lines[1:]]
            sections.append({'title': title, 'text': _comment_text(body), 'raw': '\n'.join(body).strip('\n'),
                             'settings': [{'name': k, 'default': defaults.get(k)} for k in keys]})

    for line in text.split('\n'):
        if line.startswith('#'):
            if keys:
                close()
                comment, keys = [], []
            comment.append(line)
        elif re.match(r'^[a-z_]+:', line):
            keys.append(line.split(':', 1)[0])
    close()
    return sections


def _comment_text(lines):
    """The prose of a comment block, joined into paragraphs; its Format and Examples parts kept apart."""
    prose, examples, format_ = [], [], None
    mode = 'prose'
    for raw in lines:
        line = raw.strip()
        if line.lower().startswith('format:'):
            format_, mode = line.split(':', 1)[1].strip(), 'prose'
            continue
        if line.lower().startswith('example'):
            mode = 'examples'
            rest = line.split(':', 1)[1].strip() if ':' in line else ''
            if rest:
                examples.append({'value': rest, 'meaning': ''})
            continue
        if mode == 'examples' and line.startswith('- '):
            value, _, meaning = line[2:].partition(' -- ')
            examples.append({'value': value.strip(), 'meaning': meaning.strip()})
            continue
        prose.append(line)
    paragraphs, current = [], []
    for line in prose:
        if not line:
            if current:
                paragraphs.append(' '.join(current))
            current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))
    return {'paragraphs': paragraphs, 'format': format_, 'examples': examples}


def command_line():
    found = []
    for action in cli.parser()._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        found.append({
            'flags': action.option_strings or [action.metavar or action.dest],
            'metavar': action.metavar if action.option_strings else None,
            'choices': list(action.choices) if action.choices else None,
            'default': action.default if action.default not in (None, [], False) else None,
            'repeat': isinstance(action, argparse._AppendAction) or action.nargs == '*',
            'help': action.help or '',
        })
    return {'usage': cli.parser().format_usage().strip(), 'description': cli.parser().description, 'arguments': found}


def exit_codes():
    named = {getattr(errors, n) for n in ('OK', 'CONFIG', 'UNREACHABLE', 'LOGIN', 'TM1', 'BUG', 'CANCELLED')}
    return [{'code': code, 'meaning': meaning} for code, meaning in sorted(errors.EXIT_CODES.items())], named


def project_files():
    defaults = yaml.safe_load(open(os.path.join(INCLUDE, 'tm1cm.yaml'), encoding='utf-8'))
    found = []
    for key in defaults:
        if not key.endswith('_path'):
            continue
        kind = key[:-len('_path')]
        ext = defaults.get(kind + '_ext', '')
        parts = files.PARTS.get(kind, ('name',))
        if kind == 'application':
            pattern = defaults[key] + '/<folder>/.../<name>' + ext
        else:
            pattern = defaults[key] + '/' + '/'.join(f'<{p}>' for p in parts) + ext
        found.append({'type': kind, 'folder': defaults[key], 'ext': ext, 'pattern': pattern})
    return found


def problems(reference, named_codes):
    found = []
    for s in reference['settings']:
        if not s['description'].strip():
            found.append(f'the connection setting {s["name"]} has no description (tm1.SETTING_DOCS)')
    for a in reference['command_line']['arguments']:
        if not a['help'].strip():
            found.append(f'the argument {a["flags"][0]} has no help (__main__.parser)')
    for code in sorted(named_codes - set(errors.EXIT_CODES)):
        found.append(f'the exit code {code} has no meaning (errors.EXIT_CODES)')
    for section in reference['tm1cm_yaml']:
        if not section['title']:
            found.append('tm1cm.yaml settings without a comment: ' + ', '.join(s['name'] for s in section['settings']))
    return found


def build():
    codes, named = exit_codes()
    reference = {
        'settings': settings(),
        'tm1cm_yaml': tm1cm_yaml(),
        'command_line': command_line(),
        'exit_codes': codes,
        'files': project_files(),
    }
    return reference, problems(reference, named)


if __name__ == '__main__':
    reference, found = build()
    if found:
        sys.exit("The reference can't be written from the code:\n  " + '\n  '.join(found))
    if sys.argv[1:] and sys.argv[1] != '--check':
        os.makedirs(os.path.dirname(os.path.abspath(sys.argv[1])), exist_ok=True)
        with open(sys.argv[1], 'w', encoding='utf-8') as fp:
            json.dump(reference, fp, indent=1, default=str)
            fp.write('\n')
