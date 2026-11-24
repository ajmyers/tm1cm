# docs-site

Builds and serves tm1cm's pages at [skipcheck.io/tm1cm](https://skipcheck.io/tm1cm/), the way
skipcheck-tm1's `api-site` builds its projects' pages, and in the same look: the site's masthead,
footer and styles, loaded at view time.

| Address | What | Built by |
|---|---|---|
| `/tm1cm/` | The landing page: what tm1cm does, a quick start, the walkthroughs, a prompt for a coding agent. | `scripts/pages.mjs`, from `content/tm1cm.md` |
| `/tm1cm/walkthroughs/<slug>/` | A task step by step, each command with what it printed against TM1, for macOS and Linux, and Windows. | `scripts/pages.mjs`, from `content/walkthroughs/<slug>.md` |
| `/tm1cm/docs/` | The reference: connection settings, tm1cm.yaml, the command line, exit codes, project files. | `scripts/reference.mjs`, from the code |
| `/tm1cm/search.json` | The reference's search index. | `scripts/reference.mjs` |
| `/tm1cm/llms.txt`, `llms-full.txt` | The docs for coding agents ([llms.txt](https://llmstxt.org)). | `scripts/llms.mjs` |
| `/tm1cm/release.json` | The version the pages describe, for the site's badge. | `scripts/build.mjs` |
| (the project store) | tm1cm's entry, which skipcheck.io and ajmyers.net draw its card from: summary, links, release and a terminal visual. Not served here: `docs.yml` publishes it when it deploys (see ajmyers/skipcheck.io's README, "The project store"). | `scripts/project.mjs`, from `content/tm1cm.md`'s `card` and `description` |

## Nothing is typed by hand

| On a page | Where it comes from |
|---|---|
| A command, a file, what a command printed | A step of a session in `sessions/`. `tests/tm1cm/docs_recordings_test.py` runs every session against TM1 in Docker with IBM's SData sample and writes `example-output/<session>.json`: what each step printed, its exit code, and a hash of the step. The build fails when a step changed since it was recorded, or isn't recorded. What changes from run to run is replaced: the server's address by `http://localhost:8011`, the temporary folder by `~/projects`, the time in log lines by 09:00. |
| A command on Windows | The step's `windows:`, in PowerShell. Its output is the one recorded on macOS. `scripts/install-check.mjs` runs the Windows variants that need no TM1 on a Windows runner, in Windows PowerShell and in PowerShell 7, and the Unix ones on Linux. |
| How to install | `setup.py`: the newest Python of its classifiers (what uv installs with), its `python_requires`. Before a release, from GitHub; after, from PyPI. The same script runs every install route on Linux and Windows. |
| The reference | `extract/reference.py`, from the code: `tm1.SETTING_DOCS`, the commented `include/tm1cm.yaml`, `__main__.parser()`, `errors.EXIT_CODES` and `files.PARTS`. It fails, naming it, on anything without a description, and so does `tests/tm1cm/docs_reference_test.py`. |
| The words | `content/`, in the small Markdown of `scripts/markdown.mjs`. A fenced code block fails the build: commands come from a session (`::step <session> <step>`), the install from `::install` and `::install-venv`. |

`scripts/check-links.mjs` checks every link of every page, and every address in the docs for agents.

## After changing a session

Run the live tests with a TM1 source (`TM1_INSTALL_VOLUME` or the others in the main README), and
commit what they write:

```sh
TM1_INSTALL_VOLUME=… pytest tests/tm1cm/docs_recordings_test.py
```

## Preview locally

```sh
pip install -e .            # the reference is read from tm1cm itself
cd docs-site
npm ci
PYTHON=python npm run build
npm run dev                 # http://localhost:8787/tm1cm/
```

`wrangler dev` passes everything outside `/tm1cm` (the site's styles, masthead and footer) through
to skipcheck.io.

## Deploying

`.github/workflows/docs.yml` builds and checks on every change. It deploys when the release
workflow calls it for a tag, after its gate, or when run by hand. The Worker (`src/worker.js`,
`wrangler.jsonc`) serves `/tm1cm*` on skipcheck.io; the site and skipcheck-tm1's pages are Workers of
their own. skipcheck.dev and www.skipcheck.io are redirected to skipcheck.io by Cloudflare before any
Worker. Deploying needs the repository secrets `CLOUDFLARE_API_TOKEN` (Workers Scripts: Edit on the
account, and Workers Routes: Edit on the skipcheck.io zone) and `CLOUDFLARE_ACCOUNT_ID`.
