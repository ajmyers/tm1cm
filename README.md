# TM1 Code Migrate

tm1cm is a utility for moving TM1 Planning Analytics objects between TM1 applications, or your local file system. It can be used to manage the software development lifecycle of a TM1 application.

## Installation

tm1cm needs Python 3.11 or newer. Use the package manager [pip](https://pip.pypa.io/en/stable/) to install it.

```bash
pip install tm1cm
```

## Setup

First things first, you must 'scaffold' a new TM1 application on your local system, and then update settings.

```bash
tm1cm --mode scaffold --path ./mytm1application
```

This command will create the folder structure expected by the tm1cm utility

```text
mytestapplication/
    config/ 
        default/
            connect.yaml
            credentials.yaml
            tm1cm.yaml
        test/
        staging/
        prod/
    data/
    files/
    scripts/
```

Under the 'config' directory, modify the folders (ignoring 'default' folder) for any environments (i.e test/staging/prod). Remove any that you won't use.

### Update connect.yaml

Copy connect.yaml from the default/ folder into each of the environment subfolders.

Update each connect.yaml file to contain the connection parameters for your TM1 application. You must be able to access the REST API endpoint of your TM1 application. For on-prem TM1 applications, this may look like:

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

`integrated_login` (Windows integrated security) and `proxies` aren't supported in 1.0; for a proxy, set `HTTPS_PROXY` in the environment.

**NOTE:** If you are using IBM Cloud, You must use an automation user that was included in the IBM Cloud Welcome Back. It is not possible to connect to use tm1cm with your IBM ID

### Logging in

tm1cm logs in the way your TM1 server wants:

- **With a password in credentials.yaml,** or a `cam_passport`, it logs in with them, exactly as it always has.
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

tm1cm.yaml is the primary configuration file that determines what objects SHOULD and SHOULD NOT be included in migrations.

Because some parts of TM1 applications are generally dynamic, you may not want to include every single TM1 hierarchy, subset, dimension, etc in your tm1cm configuration.

At runtime, the model is passed through a series of filters that are defined below. You can define one or many filters for each type of object. The yaml config is fairly flexible. You can be fairly selective about what you migrate.

```yaml
# Turbo Integrator Processes:
#   Define a list of TI processes to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere within the cube name
#     Filters can be defined as a single item, or as a list of items.
#
#   Format: <ProcessName>
#   Examples:
#      - Actual.Call.* -- include all processes that start with Actual.Call
#      - * -- include all processes

include_process: '*'
exclude_process:
  - '}tp*'

# This will apply standard case/indentation/formatting for TI Processes
autoformat_ti_process: true

# Cubes:
#   Define a list of cubes to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere within the cube name
#     Filters can be defined as a single item, or as a list of items.
#
#   Format: <CubeName>
#   Example: }ClientGroups

include_cube: '*'
exclude_cube:
  - '}ClientCAMAssociatedGroups'
  - '}ClientProperties'
  - '}ClientSettings'
  - '}ElementProperties*'
  - '}HierarchyProperties'
  - '}Stats*'
  - '}Hold*'
  - '}CubeProperties'
  - '}DimensionProperties'
  - '}ElementAttributes_}*'
  - '}ElementAttributes_}Clients'
  - '}Capabilities'
  - '}CubeSecurityProperties'
  - '}PickList*'
  - '*}tp*'
  - '}CellAnnotations*'

# Rules:
#   Define a list of cube rules to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere within the cube name
#     Filters can be defined as a single item, or as a list of items.
#
#   Format: <CubeName>
#   Example: }ClientGroups

include_rule: '*'
exclude_rule: ''

# Cube Views:
#   Define a list of cubes views to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere within the cube name
#     Filters can be defined as a single item, or as a list of items.
#
#   Note: This only includes the view definition, it does not include any data. It is recommended that any subsets included
#     in the view definition also be included using 'include_dimension_hierarchy_subset' otherwise the migration will fail
#
#   Note: Only public views are supported
#
#   Format: <CubeName>/<ViewName>
#   Examples:
#      - afReporting/Default -- include the 'Default' view for 'afReporting' cube
#      - */Default -- Match the 'Default' view for all cubes
#      - afReporting/* -- Match all views for afReporting cube

include_cube_view: '*/*'
exclude_cube_view: ''

# Cube View Data:
#   Define a list of cube view data to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere within the cube name
#     Filters can be defined as a single item, or as a list of items.
#
#   Note: This is generally intended for moving smaller sets of data, like control cube values. It is not intended for moving large
#     data sets.
#
#   Note: Only public views are supported. It's recommended to disable zero suppression on the view otherwise stale data may
#     be left behind on the target
#
#   Format: <CubeName>/<ViewName>
#   Examples:
#      - afReporting/Default -- include the 'Default' view data for 'afReporting' cube
#      - */Default -- Match the 'Default' view data for all cubes
#      - afReporting/* -- Match all view data for afReporting cube

include_cube_view_data: ''
exclude_cube_view_data: ''

# Dimensions:
#   Define a list of dimensionss to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item, 
#     or as a list of items.
#     
#   Note: A 'dimension' is only a container of hierarchies. You must also configure 'include_dimension_hierarchy' 
#
#   Note: Only public views are supported. It's recommended to disable zero suppression on the view otherwise stale data may
#     be left behind on the target
#
#   Format: <DimensionName>
#   Examples:
#      - af* -- include all dimensions starting with af
#      - *_Measure -- include all dimensions that end with _Measure

include_dimension: '*'
exclude_dimension:
  - '}Stats*'
  - '}Hierarchies*'
  - '}ApplicationEntries'
  - '}CAMAssociatedGroups'
  - '}Chores'
  - '}Client*'
  - '}Connection*'
  - '}Cube Functions'
  - '}CubeProperties'
  - '}CubeSecurityProperties'
  - '}Cubes'
  - '}Cultures'
  - '}DimensionFormatAttributes'
  - '}DimensionFormatItems'
  - '}DimensionProperties'
  - '}ElementAttributes_}*'
  - '}ElementProperties'
  - '}Features'
  - '}Groups'
  - '}PickList'
  - '}Processes'
  - '}RuleStats'
  - '}Subsets*'
  - '}Views*'
  - '}*'
  - 'Sandboxes'

# Dimension Hierarchy:
#   Define a list of dimension hierarchies to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: This will manage the migration of hierarchies, but will not explicitly include the elements of a hierarchy. In order to configure
#     including/excluding a hierarchies elements, see 'include_dimension_hierarchy_element'
#
#   Format: <DimensionName>/<HierarchyName>
#   Examples:
#      - afLocation/afLocation -- Include only the primary hierarchy for dimension afLocation
#      - afLocation/* -- include all hierarchies for dimension afLocation

include_dimension_hierarchy: '*/*'
exclude_dimension_hierarchy:
  - '}*/*'
  - '*/Leaves'

# Dimension Hierarchy Elements:
#   Define a list of dimension hierarchy elements to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: It is not recommended to include elements for hierarchies that are managed from other data sources (like upstream ERP)
#
#   Format: <DimensionName>/<HierarchyName>
#   Examples:
#      - afLocation/afLocation -- Include only the primary hierarchy elements for dimension afLocation
#      - afLocation/* -- include all hierarchy elements for dimension afLocation

include_dimension_hierarchy_element: '*/*'
exclude_dimension_hierarchy_element: ''

# Dimension Hierarchy Edges:
#   Define a list of dimension hierarchy edges to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: Edges are the parent/child relationships of a hierarchy
#
#   Format: <DimensionName>/<HierarchyName>
#   Examples:
#      - afLocation/afLocation -- Include only the primary hierarchy edges for dimension afLocation
#      - afLocation/* -- include all hierarchy edges for dimension afLocation

include_dimension_hierarchy_edge: '*/*'
exclude_dimension_hierarchy_edge: ''

# Dimension Hierarchy Attributes:
#   Define a list of dimension hierarchy attributes to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: This will only manage attributes themselves, it will not populate attribute values. In order to do that, see the
#     include_dimension_hierarchy_attribute_value
#
#   Format: <DimensionName>/<HierarchyName>/<AttributeName>
#   Examples:
#      - afLocation/afLocation/* -- include all attributes for afLocation dimension/hierarchy
#      - afLocation/*/Name -- include 'Name' attribute for all hierarchies of afLocation
#      - */*/Name -- include 'Name' attribute for all hierarchies of all dimensions

include_dimension_hierarchy_attribute: '*/*/*'
exclude_dimension_hierarchy_attribute: '*/*/}SYS*'

# Dimension Hierarchy Attribute Values:
#   Define a list of dimension hierarchy attributes values to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: This will, for any included elements, manage the attribute values for each element.
#
#   Format: <DimensionName>/<HierarchyName>/<AttributeName>
#   Examples:
#      - afLocation/afLocation/* -- include all attribute values for afLocation dimension/hierarchy
#      - afLocation/*/Name -- include 'Name' attribute values for all hierarchies of afLocation
#      - */*/Name -- include 'Name' attribute values for all hierarchies of all dimensions

include_dimension_hierarchy_attribute_value: '*/*/*'
exclude_dimension_hierarchy_attribute_value: ''

# Dimension Hierarchy Subset:
#   Define a list of subsets to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: This supports only public subsets. It will work for both Dynamic and Static subsets.
#
#   Format: <DimensionName>/<HierarchyName>/<SubsetName>
#   Examples:
#      - afLocation/afLocation/* -- include all subsets for afLocation dimension/hierarchy
#      - */*/Level 0 -- include all subsets with name 'Level 0' for all dimensions/hierarchies

include_dimension_hierarchy_subset: ''
exclude_dimension_hierarchy_subset: ''

# Application:
#   Define a list of applications to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Format: Folder1/Folder2/Folder3/Name
#   Examples:
#      - Test/* -- include all applications in the Test folder
#      - */tm1cm* -- include all applications in any folder that start with tm1cm

include_application: '*'
exclude_application: ''

# Chore:
#   Define a list of chores to include, and then exclude from tm1cm. Build a list using the 'include' filter, then filter
#     it further using the 'exclude' filter. Use * as a wildcard character anywhere. Filters can be defined as a single item,
#     or as a list of items.
#
#   Note: This supports only public subsets. It will work for both Dynamic and Static subsets.
#
#   Format: ChoreName
#   Examples:
#      - * -- include all chores
#      - Managed* -- include any chores that start with Managed

include_chore: '*'
exclude_chore: ''

# Backup on migrate
#   Configure these settings to set up running a TI process to perform a backup prior to doing migration
#
#   Note: These parameters are only relevant in Interactive Mode and have no effect in Command Line mode
#
#   backup_on_migrate: true/false -- default value to perform backup on migration
#   backup_allow_override: true/false -- allow backup setting to be overridden
#   backup_process: The name of the TI process that will be executed to perform the system backup

backup_on_migrate: false
backup_allow_override: false
backup_process: ''

# JSON or YAML -- recommended to use YAML as its human-readable
text_output_format: YAML

# File operations -- do not touch, currently unsupported
do_file_operations: false
file_to_blob_update_process: ''
include_file: ''
exclude_file: ''

# Additional settings -- do not touch
cube_path: data/cube
cube_ext: .cube
rule_path: data/rule
rule_ext: .rule
view_path: data/view
view_ext: .view
view_data_path: data/view_data
view_data_ext: .view_data
subset_path: data/subset
subset_ext: .subset
dimension_path: data/dimension
dimension_ext: .dimension
hierarchy_path: data/hierarchy
hierarchy_ext: .hierarchy
process_path: data/process
process_ext: .process
chore_path: data/chore
chore_ext: .chore
application_path: data/application
application_ext: .application
```

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
mytestapplication.local
mytestapplication.test
mytestapplication.prod
```

Begin a migration between two environments using 'migrate appfrom appto'

```
(tm1cm) $ migrate mytestapplication.test mytestapplication.prod
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

You can stage and unstage changes by using the 'add' and 'remove' commands. These commands support the use of wildcards in order to stage multiple changes with one command.

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
(tm1cm) $ remove UPDATE_PROCESS: Actual.Data.Load Actual Cash Data 
```

Use the 'ls stage' command to view the list of staged changes.

Use the 'ls' command to view all operations.

Use the 'do' command to perform the staged operations.

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

You can also use this functionality along with git version control systems and tools like Stash to do code reviews.

#### GET

This will connect to the test environment for mytestapplication, and take all of the TM1 model objects and write them to your local disk.

From your terminal, run the command:

```
tm1cm --mode get --environment test
```

#### PUT

This will connect to the test environment for mytestapplication, and update all of the model objects with the definition stored on the local computer

From your terminal, run the command:

```
tm1cm --mode put --environment prod
```

### Errors and exit codes

When something goes wrong, tm1cm says what happened and what to try, and writes a full report to the log file: the traceback, the command, the versions of tm1cm, skipcheck-tm1, Python and the OS, and the TM1 servers it connected to. Passwords and passports are masked in messages and logs. The log is `<project>.log` in the current folder, or the file given with `--log`. Attach it when you [report an issue](https://github.com/ajmyers/tm1cm/issues). `--debug` also shows the full traceback.

In `get` and `put`, an object TM1 refuses doesn't stop the run: the other operations are done, and the failed ones are listed at the end.

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

### Commit and PR conventions

Enable the commit message hook once per clone:

```bash
git config core.hooksPath .githooks
```

## License

[GNU General Public License v3.0](https://choosealicense.com/licenses/gpl-3.0/)