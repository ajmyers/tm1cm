# TM1 Code Migrate

tm1cm is a utility for moving TM1 Planning Analytics objects between TM1 applications, or your local file system. It can be used to manage the software development lifecycle of a TM1 application.

**The docs are at [skipcheck.io/tm1cm](https://skipcheck.io/tm1cm/):** a quick start, walkthroughs with what tm1cm printed when they ran against TM1, and a reference of every setting, filter and option.

## Installation

tm1cm needs Python 3.11 or newer, and git. The easiest way to install it is [uv](https://docs.astral.sh/uv/), which gets a Python for it and keeps it apart from your system's Python:

```bash
uv tool install --python 3.14 tm1cm
```

Or with pip, in a virtual environment. [Installing it](https://skipcheck.io/tm1cm/walkthroughs/first-project/#install) has every way, for macOS, Linux and Windows.

## Setup

First things first, you must 'scaffold' a new TM1 application on your local system, and then update settings.

```bash
tm1cm --mode scaffold --path ./mytm1application
```

This command will create the folder structure expected by the tm1cm utility

```text
mytm1application/
    .gitignore
    config/
        default/
            connect.yaml
            credentials.yaml
            tm1cm.yaml
        test/
            connect.yaml
        prod/
            connect.yaml
    data/
```

`default` holds the settings every environment shares, and each other folder under `config` is an environment: rename `test` and `prod`, or add others, one per server. The `.gitignore` keeps the log and `credentials.yaml` out of git.

### Update connect.yaml

Update each environment's connect.yaml to contain the connection parameters for your TM1 application. You must be able to access the REST API endpoint of your TM1 application. For on-prem TM1 applications, this may look like:

```yaml
base_url: https://myonpremapplication:10000
```

If you are using the IBM Cloud, your connect.yaml may look like

```yaml
base_url: https://mycompany.planning-analytics.ibmcloud.com:443/tm1/api/tm1
```

### Update credentials.yaml

If your credentials are the same in all environments, you can update credentials.yaml within the default/ directory

If your credentials are different across each environment, copy credentials.yaml into each environment subfolder (as with connect.yaml) and update your credentials for each environment

```yaml
namespace: LDAP
user: mysecureusername
password: mysecurepassword
```

You can leave the password out: tm1cm then asks for it when it connects (see [Logging in](#logging-in)), so it isn't kept in a file.

connect.yaml and credentials.yaml take the same settings as in tm1cm 0.9:

- `base_url`, the server's root, or else `address`, `port` and `ssl` (`true` unless set)
- `user` and `password`, with `namespace` for CAM, or `cam_passport`; `gateway` for CAM single sign-on on Windows; `decode_b64: true` if the password is base64
- `verify`: certificates are only checked when it's `true`, or the path of a CA bundle
- `async_requests_mode`, `session_context`, `impersonate` and `timeout` (seconds)

And three for logging in, all optional:

- `auth`: `basic` (TM1's own security), `cam` (a user and password in a CAM namespace) or `browser` (signing in through a browser window), when tm1cm shouldn't work it out
- `dispatcher`: Cognos's address, when the one TM1 gives (its `ClientCAMURI`) isn't reachable from where tm1cm runs
- `browser`: the path of a Chromium-based browser, when tm1cm doesn't find Chrome, Edge, Brave or Chromium itself

Any of these can be given on the command line instead, with `--connect KEY=VALUE` (or `-c`), once for each setting. They win over connect.yaml and credentials.yaml, in every environment. Text settings (`user`, `password`, `namespace`, `cam_passport`, `base_url`...) are kept as typed; the others are read as they would be in the file (`verify=true`, `port=8010`):

```bash
tm1cm --mode get --environment test -c base_url=https://tm1test:12354 -c user=admin -c verify=true
```

A password given this way can end up in your shell's history: leave it out, and tm1cm asks for it.

`integrated_login` (Windows integrated security) and `proxies` aren't supported in 1.0; for a proxy, set `HTTPS_PROXY` in the environment.

**NOTE:** On IBM Cloud, log in as an automation user (non-interactive account) that IBM set up for you: tm1cm can't log in with your IBMid.

### Logging in

tm1cm logs in the way your TM1 server wants:

- **With a password in credentials.yaml,** or a `cam_passport`, it logs in with them, exactly as it always has. A `cam_passport` and `base_url` are all it needs.
- **With a user and an empty password** (`password: ''`, as the scaffold writes it), the empty password is tried first, so a user whose password is empty logs in without being asked.
- **Without a password,** it asks TM1 how it wants to be logged in to. For TM1's own security, it asks for your user and password. For CAM security, it asks Cognos whether your namespace takes a password, and asks for it, or whether it signs in through a browser (OpenID Connect through Entra ID, Okta, Keycloak and the like, or SAML).
- **Without a namespace,** on a CAM server, it lists Cognos's namespaces for you to pick from.
- **A password you type** is asked for again when TM1 refuses it, up to three times. It's never written anywhere.

**Signing in through the browser:** tm1cm opens your namespace's own Cognos login, the same as for Planning Analytics Workspace, in a Chromium-based browser (Chrome, Edge, Brave or Chromium) with a profile of its own, never your own profile. Once you've signed in, it reads the passport Cognos gives the browser and logs in to TM1 with it. Nothing is needed on the server.

- A hidden window is tried first. It's enough while your provider still remembers you, so later runs often need no window at all.
- If the browser can't sign you in, tm1cm says why and offers a user and password instead, pasting a CAM passport (the `cam_passport` cookie of a browser signed in to Cognos), trying again, or cancelling.
- The browser's profile is kept in your user cache folder (`~/.cache/tm1cm`, `~/Library/Caches/tm1cm`, or `%LOCALAPPDATA%\tm1cm\Cache`).

**`gateway`** gets a passport from a CAM gateway with Windows single sign-on. With the `requests_negotiate_sspi` package installed, it does so as tm1cm 0.9 did; without it, through the browser, which signs you on to Windows itself.

**Without a terminal** (CI, a scheduled task), tm1cm asks nothing and opens no window. A password that isn't set is sent empty, as before, and the browser sign-in only tries its hidden window. Anything else it needs ends the run with a message naming the setting to add.

### Update tm1cm.yaml

tm1cm.yaml decides which objects tm1cm moves: for each type (processes, cubes, rules, views, dimensions, hierarchies and their elements, edges and attributes, subsets, applications, chores), an `include` filter and an `exclude` filter, by name, with `*` as a wildcard. The scaffold writes `config/default/tm1cm.yaml` with every setting, each section commented, and an environment's own `tm1cm.yaml` overrides any of them.

Because some parts of TM1 applications are generally dynamic, you may not want to include every TM1 hierarchy, subset or dimension: leave out what another system maintains, or what changes on its own. [Every setting, with its default](https://skipcheck.io/tm1cm/docs/tm1cm-yaml/).

## Usage

tm1cm has two different modes, Interactive and Command Line.

### Interactive Mode

Interactive mode allows you to pick and choose exactly what objects you would like to move between environments

To launch interactive mode, navigate in your terminal (or command prompt) to your application folder and run:

```
tm1cm
```

You will be presented with the tm1cm splash screen and a special (tm1cm) command prompt:

```
----------------------------------
TM1 Code Migrate
----------------------------------                                                      
 Created By: Andrew Myers (me@ajmyers.net) -- https://www.linkedin.com/in/andrew-myers-3112248/
 Homepage: https://github.com/ajmyers/tm1cm
 Issues & Bugs: https://github.com/ajmyers/tm1cm/issues
-----------------------------------

Welcome to TM1 Code Migrate interactive!

(tm1cm) $ 
```

Use the 'help' command to see all possible commands

```
(tm1cm) $ help
```

use the 'ls apps' command to see all of the configurations you can migrate between

```
(tm1cm) $ ls apps
mytm1application.local
mytm1application.test
mytm1application.prod
```

Begin a migration between two environments using 'migrate appfrom appto'

```
(tm1cm) $ migrate mytm1application.test mytm1application.prod
```

Once the migrate command completes, use the 'ls' command to see what operations are available.

NOTE: Operations that are NOT staged are in <span style="color:red">red</span>, whereas staged operations are in <span style="color:green">green</span>. By default, there are no staged operations

```
(tm1cm) $ ls
DELETE_PROCESS: ztemp ai check date
DELETE_SUBSET: afReclass_Index, afReclass_Index, Complete Reclasses
UPDATE_PROCESS: Actual.Call.Load Currency Rates
UPDATE_PROCESS: Actual.Data.Build Drill Table Query
UPDATE_PROCESS: Actual.Data.Load Actual Cash Data
UPDATE_PROCESS: Actual.Data.Load Actual Data
UPDATE_PROCESS: Actual.Data.Load from Ingestion
UPDATE_PROCESS: Actual.Data.Populate Drill Table
UPDATE_PROCESS: Actual.Data.Update Budget Rate Data
UPDATE_DIMENSION: afActualCash_Measure
UPDATE_HIERARCHY: afActualCash_Measure, afActualCash_Measure
UPDATE_CUBE: afActualCash
UPDATE_RULE: afActualCash
```

You can stage and unstage changes by using the 'add' and 'rm' commands. These commands support the use of wildcards in order to stage multiple changes with one command.

```
(tm1cm) $ add UPDATE_PROCESS: *
UPDATE_PROCESS: Actual.Call.Load Currency Rates
UPDATE_PROCESS: Actual.Data.Build Drill Table Query
UPDATE_PROCESS: Actual.Data.Load Actual Cash Data
UPDATE_PROCESS: Actual.Data.Load Actual Data
UPDATE_PROCESS: Actual.Data.Load from Ingestion
UPDATE_PROCESS: Actual.Data.Populate Drill Table
UPDATE_PROCESS: Actual.Data.Update Budget Rate Data
```

```
(tm1cm) $ rm UPDATE_PROCESS: Actual.Data.Load Actual Cash Data
```

Use the 'ls stage' command to view the list of staged changes.

Use the 'ls' command to view all operations.

Use the 'do' command to perform the staged operations, and 'exit' (or Ctrl-D) to leave the shell.

```
(tm1cm) $ do
Perform STAGED operations? (7/104)
[y/n]? y
Doing: UPDATE_PROCESS: Actual.Call.Load Currency Rates
Doing: UPDATE_PROCESS: Actual.Data.Build Drill Table Query
Doing: UPDATE_PROCESS: Actual.Data.Load Actual Data
Doing: UPDATE_PROCESS: Actual.Data.Load from Ingestion
Doing: UPDATE_PROCESS: Actual.Data.Populate Drill Table
Doing: UPDATE_PROCESS: Actual.Data.Update Budget Rate Data
```

### Command Line

Command line mode is useful for automating migrations. There are two modes. 'get' and 'put'

Generally, you would run the 'get' command against your test environment, and then run the 'put' command against your prod environment.

You can also use this with git, and review changes in pull requests (GitHub, GitLab, Bitbucket) before they're put: [Promote a change with git](https://skipcheck.io/tm1cm/walkthroughs/promote/).

#### GET

This will connect to the test environment, and write its TM1 model objects to the project's `data` folder.

From your terminal, run the command:

```
tm1cm --mode get --environment test
```

#### PUT

This will connect to the prod environment, and update its model objects with the definitions stored in the project

From your terminal, run the command:

```
tm1cm --mode put --environment prod
```

#### Only some objects

Give `get` or `put` the files of the objects to move, and only those are moved, whatever tm1cm.yaml's filters select:

```
tm1cm --mode put --environment prod "data/process/Actual.Data.Load Actual Data.process" data/cube/afActualCash.cube
```

- Paths are relative to the project, or to the current folder, or absolute. Each must be an object's file under `data/`.
- The objects are moved in dependency order (dimensions before the cubes made of them, and so on).
- A file that isn't there names an object to delete. `put` deletes it from TM1. `get` deletes the file when TM1 hasn't got the object.
- `get` writes only those files, and leaves the rest of `data/` as it is.
- The filters that shape what's in a hierarchy's file (`include_dimension_hierarchy_element`, `_edge`, `_attribute` and `_attribute_value`) still apply, as they did when the file was written. A put of a hierarchy whose elements tm1cm.yaml leaves out leaves its elements on TM1 alone.

So the files a commit changed, deleted ones included, put exactly that commit:

```bash
git diff -z --name-only HEAD~1 -- data | xargs -0 tm1cm --mode put --environment prod
```

### Errors and exit codes

When something goes wrong, tm1cm says what happened and what to try, and writes a full report to the log file: the traceback, the command, the versions of tm1cm, skipcheck-tm1, Python and the OS, and the TM1 servers it connected to. Passwords and passports are masked in messages and logs. The log is `<project>.log` in the current folder, or the file given with `--log`. Attach it when you [report an issue](https://github.com/ajmyers/tm1cm/issues). `--debug` also shows the full traceback.

In `get` and `put`, an object TM1 refuses doesn't stop the run: the other operations are done, and the failed ones are listed at the end. A server that can't be reached, or a login refused partway through, does stop it, with exit code 3 or 4.

| Exit code | Meaning |
|---|---|
| 0 | Done |
| 2 | A setting, file or argument is missing or invalid |
| 3 | TM1 or Cognos couldn't be reached |
| 4 | The login was refused, or couldn't be made |
| 5 | TM1 refused one or more objects |
| 70 | An unexpected error: likely a bug |
| 130 | Cancelled |

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

### Running the tests

Install tm1cm with its test dependencies, then run pytest:

```bash
pip install -e ".[test]"
pytest
```

The integration tests run against a real TM1 server, which [skipcheck-tm1-testcontainers](https://github.com/ajmyers/skipcheck-tm1/tree/master/python/tm1-testcontainers) starts in Docker for the test run. No IBM software is included: point it at your own licensed TM1 Server for Linux with one of these environment variables.

| Variable | Where TM1 comes from |
|---|---|
| `TM1_INSTALL_VOLUME` | A Docker volume holding an installed `tm1_64` folder |
| `TM1_HOME_DIR` | An installed `tm1_64` folder on this machine |
| `TM1_BUNDLE_DIR` | A folder holding IBM's TM1 Server bundle |
| `TM1_PRIVATE_IMAGE` | A Docker image with TM1 built in |

```bash
TM1_INSTALL_VOLUME=my-tm1-install pytest
```

Without Docker or any of these settings, the integration tests are skipped and the rest still run, as they do in CI. `tox` runs lint and the tests on every supported Python version.

### Releasing
Releases go to [PyPI](https://pypi.org/project/tm1cm/) from `.github/workflows/release.yml`, through PyPI's trusted publishing, so no token is stored anywhere. The version comes from the git tag ([setuptools-scm](https://setuptools-scm.readthedocs.io)), so nothing in the source changes to release:

- **Release:** tag a commit of master with `v` and the version, and push the tag (`git tag v1.0.1 && git push origin v1.0.1`). Creating a GitHub release with a new tag like that does the same.
- **Pre-release:** the same, with a pre-release tag (`v1.1.0rc1`).

Nothing is published until all of these pass on that commit:
- the tag is a version, and a commit of master;
- the whole of CI;
- the wheel and sdist are built with the tag's version and pass `twine check --strict`;
- each package is installed into an empty environment on Python 3.11–3.14, and the command, the scaffold and the test suite run against it.

PyPI then gets exactly those files. A version can never be uploaded twice, even after it's deleted.

- **Untagged builds** (a checkout, CI) get a dev version after the last tag, like `1.0.2.dev3+g1a2b3c4`.
- **Dry run:** run the workflow by hand (`gh workflow run release.yml`). It builds and tests the package with that dev version, and uploads nothing. Pull requests that change the packaging get a dry run too.

PyPI trusts the workflow by its file name: renaming `release.yml` breaks publishing.

### Commit and PR conventions

Enable the commit message hook once per clone:

```bash
git config core.hooksPath .githooks
```

## License

[GNU General Public License v3.0](https://choosealicense.com/licenses/gpl-3.0/)