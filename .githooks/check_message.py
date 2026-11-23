#!/usr/bin/env python3
"""Check a commit message or PR title/description against our conventions.

Usage:
    check_message.py commit <file>   # commit message file, as given to the commit-msg hook
    check_message.py pr <file>       # PR title on line 1, a blank line, then the description

Expected commit message:

    Add cube listing to CubeService          <- title: <=72 chars, capitalized, no period, no #issue

    Why, what, and the decisions behind it.  <- description: required

    Refs: #12                                <- trailer: links the issue

PRs: same title rules; description must contain "Closes #N" or "Part of #N".
"""

import re
import sys

MAX_TITLE = 72
EXEMPT_PREFIXES = ("Merge ", 'Revert "', "fixup! ", "squash! ", "amend! ")
TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: .+")
REFS = re.compile(r"^Refs: #\d+(, #\d+)*$")
ISSUE_IN_TITLE = re.compile(r"#\d+")
PR_LINK = re.compile(r"^\s*(closes|fixes|resolves|part of) #\d+\b", re.IGNORECASE | re.MULTILINE)
SCISSORS = "# ------------------------ >8 ------------------------"


def read_lines(path, strip_comments):
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    lines = []
    for line in text.split("\n"):
        if strip_comments:
            if line.startswith(SCISSORS):
                break  # everything below is the diff from `git commit -v`
            if line.startswith("#"):
                continue  # git strips these comment lines itself
        lines.append(line.rstrip())
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return lines


def paragraphs(lines):
    paras, current = [], []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paras.append(current)
            current = []
    if current:
        paras.append(current)
    return paras


def check_title(title, errors):
    if not title:
        errors.append("Title is empty.")
        return
    if len(title) > MAX_TITLE:
        errors.append(f"Title is {len(title)} characters; keep it to {MAX_TITLE} or fewer.")
    if title.startswith("#"):
        errors.append("Title must not start with '#' (git treats it as a comment).")
    elif not re.match(r"[A-Z0-9]", title):
        errors.append("Title should start with a capital letter (imperative mood, e.g. 'Add ...').")
    if title.endswith("."):
        errors.append("Title should not end with a period.")
    if ISSUE_IN_TITLE.search(title):
        errors.append("Keep issue numbers out of the title; use a 'Refs: #N' trailer (commits) "
                      "or 'Closes #N' in the description (PRs).")


def check_commit(lines):
    errors = []
    title = lines[0] if lines else ""
    if title.startswith(EXEMPT_PREFIXES):
        return errors
    check_title(title, errors)
    if len(lines) > 1 and lines[1]:
        errors.append("Leave a blank line between the title and the description.")

    paras = paragraphs(lines[1:])
    trailers = paras[-1] if paras and all(TRAILER.match(l) for l in paras[-1]) else []
    prose = paras[:-1] if trailers else paras
    if not prose:
        errors.append("Add a description: what changed, why, and the decisions behind it.")
    if not any(REFS.match(l) for l in trailers):
        errors.append("End the message with a trailer linking the issue, e.g. 'Refs: #12'.")
    return errors


def check_pr(lines):
    errors = []
    title = lines[0] if lines else ""
    check_title(title, errors)
    body = "\n".join(lines[1:])
    if not PR_LINK.search(body):
        errors.append("Link the issue in the description: 'Closes #N' (completes it) or 'Part of #N'.")
    content = PR_LINK.sub("", body).strip()
    if not content:
        errors.append("Add a description: what changed, why, and the decisions behind it.")
    return errors


def main(argv):
    args = argv[1:]
    if len(args) != 2 or args[0] not in ("commit", "pr"):
        print(__doc__, file=sys.stderr)
        return 2
    mode, path = args
    lines = read_lines(path, strip_comments=(mode == "commit"))
    errors = check_commit(lines) if mode == "commit" else check_pr(lines)
    if errors:
        what = "Commit message" if mode == "commit" else "PR title/description"
        print(f"{what} doesn't follow the conventions:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        if mode == "commit":
            print("\nExpected:\n\n  Short imperative title\n\n  Why, what, and the decisions behind it.\n\n"
                  "  Refs: #12\n\n(Bypass in an emergency with --no-verify; CI still checks the PR.)",
                  file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
