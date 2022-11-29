# TM1 Code Migrate

tm1cm is a utility for moving TM1 Planning Analytics objects between TM1 applications, or your local file system. It can be used to manage the software development lifecycle of a TM1 application.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install tm1cm.

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

**NOTE:** If you are using IBM Cloud, You must use an automation user that was included in the IBM Cloud Welcome Back. It is not possible to connect to use tm1cm with your IBM ID

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

include_cube_view: ''
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

This will connect to the test environment for mytestapplication, and update all of the model objets with the definition stored on the local computer

From your terminal, run the command:

```
tm1cm --mode put --environment prod
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[GNU General Public License v3.0](https://choosealicense.com/licenses/gpl-3.0/)