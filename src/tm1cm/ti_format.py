import random
import re
import string

INDENT = ' ' * 3

RE_TOKENIZE_STRING = r'(\')(.*?)(\')'
RE_TOKENIZE_COMMENT = r'^([ \t]*?)(#)(.*?)(?=\n|$)'
RE_FUNC = r'(?<=[^\w\d])({})(?=[^\w\d])'
RE_FUNC_PAREN = r'(?<=[^\w\d])({})(\s*)([^\w\d\(])'
RE_OPERATOR = r'(\s*)(\@\<\=|\@\>\=|\@\<\>|\@\=|\@\<|\@\>|\<\=|\>\=|\<\>|\+|\-|\/|\\|\*|\<|\>|\~|\||=|\&|\%)(\s*)'
RE_PARAM_PAREN = r'(\s*)(\(|\))(\s*)'
RE_PARAM_COMMA = r'(\s*)(,)(\s*)'
RE_END = r'(\s*)(;)(\s*?)(\n)'
RE_DIGITS = r'(=|\*|\+|\\|\/|-)(\s*)(\+|\-)(\s*)(\d+)'
RE_INDENT = r'(^)(\s*)(ELSEIF|ENDIF|WHILE|IF|END|ELSE)(.*;$)'
RE_EXECUTEPROCESS = r'(\s*)(EXECUTEPROCESS\(|RUNPROCESS\()(.*)(\);)'

TI_CONTROL_PARAM = (
    'if', 'elseif', 'while', 'end', 'endif', 'break', 'next', 'else', 'end'
)

TI_FUNCTIONS = (
    'attrn', 'attrs', 'cubeattrn', 'cubeattrs', 'dimensionattrn', 'dimensionattrs', 'elementattrn', 'elementattrs',
    'consolidatedavg', 'consolidatedcount', 'consolidatedcountunique', 'consolidatedmax', 'consolidatedmin',
    'isundefinedcellvalue', 'undef', 'undefinedcellvalue', 'date', 'dates', 'day', 'dayno', 'month', 'now', 'time',
    'timst', 'timvl', 'today', 'year', 'dimix', 'dimnm', 'dimsiz', 'dnext', 'dnlev', 'dtype', 'tabdim', 'elcomp',
    'elcompn', 'elementcomponent', 'elementcomponentcount', 'elementcount', 'elementfirst', 'elementindex',
    'elementisancestor', 'elementiscomponent', 'elementisparent', 'elementlevel', 'elementname', 'elementnext',
    'elementparent', 'elementparentcount', 'elementtype', 'elementweight', 'elisanc', 'eliscomp', 'elispar', 'ellev',
    'elpar', 'elparn', 'elweight', 'levelcount', 'fv', 'paymt', 'pv', 'continue', 'abs', 'acos', 'asin', 'atan', 'cos',
    'exp', 'int', 'isund', 'ln', 'log', 'max', 'min', 'mod', 'rand', 'round', 'roundp', 'sign', 'sin', 'sqrt', 'tan',
    'capit', 'char', 'code', 'codew', 'delet', 'fill', 'insrt', 'long', 'lower', 'numbr', 'scan', 'str', 'subst',
    'trim', 'upper', 'asciidelete', 'asciioutput', 'numbertostring', 'numbertostringex', 'setinputcharacterset',
    'setoutputcharacterset', 'setoutputescapedoublequote', 'stringtonumber', 'stringtonumberex', 'textoutput', 'attrnl',
    'attrsl', 'attrdelete', 'attrinsert', 'attrputn', 'attrputs', 'choreattrdelete', 'choreattrinsert', 'choreattrn',
    'choreattrnl', 'choreattrputn', 'choreattrputs', 'choreattrs', 'choreattrsl', 'cubeattrdelete', 'cubeattrinsert',
    'cubeattrputn', 'cubeattrputs', 'cubeattrnl', 'cubeattrsl', 'dimensionattrdelete', 'dimensionattrinsert',
    'dimensionattrputn', 'dimensionattrputs', 'dimensionattrnl', 'dimensionattrsl', 'elementattrnl', 'elementattrsl',
    'elementattrputn', 'elementattrputs', 'elementattrinsert', 'elementattrdelete', 'hierarchyattrputn',
    'hierarchyattrputs', 'hierarchyattrn', 'hierarchyattrs', 'hierarchyattrnl', 'hierarchyattrsl',
    'hierarchysubsetattrs', 'hierarchysubsetattrn', 'hierarchysubsetattrsl', 'hierarchysubsetattrnl',
    'hierarchysubsetattrputs', 'hierarchysubsetattrputn', 'hierarchysubsetattrinsert', 'hierarchysubsetattrdelete',
    'processattrdelete', 'processattrinsert', 'processattrn', 'processattrnl', 'processattrputn', 'processattrputs',
    'processattrs', 'processattrsl', 'subsetattrs', 'subsetattrn', 'subsetattrsl', 'subsetattrnl', 'subsetattrputs',
    'subsetattrputn', 'subsetattrinsert', 'subsetattrdelete', 'viewattrdelete', 'viewattrinsert', 'viewattrn',
    'viewattrnl', 'viewattrputn', 'viewattrputs', 'viewattrs', 'viewattrsl', 'choreerror', 'chorequit', 'chorerollback',
    'setchoreverbosemessages', 'addcubedependency', 'cellgetn', 'cellgets', 'cellincrementn', 'cellisupdateable',
    'cellputn', 'cellputproportionalspread', 'cellputs', 'cubecleardata', 'cubecreate', 'cubedestroy',
    'cubedimensioncountget', 'cubeexists', 'cubegetlogchanges', 'cubesavedata', 'cubesetconnparams',
    'cubesetlogchanges', 'cubetimelastupdated', 'cubeunload', 'cubedatareservationacquire',
    'cubedatareservationrelease', 'cubedatareservationreleaseall', 'cubedatareservationget',
    'cubedatareservationgetconflicts', 'cubedracquire', 'cubedrrelease', 'cubedrreleaseall', 'cubedrget',
    'cubedrgetconflicts', 'formatdate', 'newdateformatter', 'parsedate', 'dimensioncreate',
    'dimensiondeleteallelements', 'dimensiondeleteelements', 'dimensiondestroy', 'dimensionelementcomponentadd',
    'dimensionelementcomponentadddirect', 'dimensionelementcomponentdelete', 'dimensionelementcomponentdeletedirect',
    'dimensionelementdelete', 'dimensionelementdeletedirect', 'dimensionelementexists', 'dimensionelementinsert',
    'dimensionelementinsertdirect', 'dimensionelementprincipalname', 'dimensionexists', 'dimensionhierarchycreate',
    'dimensionsortorder', 'dimensiontimelastupdated', 'dimensiontopelementinsert', 'dimensiontopelementinsertdirect',
    'dimensionupdatedirect', 'createhierarchybyattribute', 'hierarchycontainsallleaves', 'hierarchycreate',
    'hierarchydeleteallelements', 'hierarchydeleteelements', 'hierarchydestroy', 'hierarchyelementcomponentadd',
    'hierarchyelementcomponentadddirect', 'hierarchyelementcomponentdelete', 'hierarchyelementcomponentdeletedirect',
    'hierarchyelementdelete', 'hierarchyelementdeletedirect', 'hierarchyelementexists', 'hierarchyelementinsert',
    'hierarchyelementinsertdirect', 'hierarchyelementprincipalname', 'hierarchyexists', 'hierarchyhasorphanedleaves',
    'hierarchysortorder', 'hierarchytimelastupdated', 'hierarchytopelementinsert', 'hierarchytopelementinsertdirect',
    'hierarchyupdatedirect', 'odbcclose', 'odbcopen', 'odbcopenex', 'odbcoutput', 'setodbcunicodeinterface',
    'executecommand', 'executeprocess', 'getprocesserrorfiledirectory', 'getprocesserrorfilename', 'getprocessname',
    'itemreject', 'itemskip', 'processbreak', 'processerror', 'processexists', 'processexitbychorerollback',
    'processexitbyprocessrollback', 'processquit', 'processrollback', 'runprocess', 'synchronized',
    'cubeprocessfeeders', 'cuberuleappend', 'cuberuledestroy', 'deleteallpersistentfeeders', 'forceskipcheck',
    'ruleloadfromfile', 'getuseactivesandboxproperty', 'serveractivesandboxget', 'serveractivesandboxset',
    'serversandboxclone', 'serversandboxcreate', 'serversandboxesdelete', 'serversandboxdiscardallchanges',
    'serversandboxmerge', 'serversandboxexists', 'serversandboxget', 'serversandboxlistcountget',
    'setuseactivesandboxproperty', 'addclient', 'addgroup', 'assignclienttogroup', 'assignclientpassword',
    'associatecamidtogroup', 'cellsecuritycubecreate', 'cellsecuritycubedestroy', 'deleteclient', 'deletegroup',
    'elementsecurityget', 'elementsecurityput', 'hierarchyelementsecurityget', 'hierarchyelementsecurityput',
    'removecamidassociation', 'removecamidassociationfromgroup', 'removeclientfromgroup', 'sethierarchygroupssecurity',
    'sethierarchyelementgroupssecurity', 'setdimensiongroupssecurity', 'setelementgroupssecurity',
    'securityoverlaygloballockcell', 'securityoverlaycreateglobaldefault', 'securityoverlaydestroyglobaldefault',
    'securityoverlaygloballocknode', 'securityrefresh', 'batchupdatefinish', 'batchupdatefinishwait',
    'batchupdatestart', 'disablebulkloadmode', 'enablebulkloadmode', 'refreshmdxhierarchy', 'savedataall',
    'servershutdown', 'hierarchysubsetaliasget', 'hierarchysubsetaliasset', 'hierarchysubsetcreate',
    'hierarchysubsetdeleteallelements', 'hierarchysubsetdestroy', 'hierarchysubsetelementexists',
    'hierarchysubsetelementdelete', 'hierarchysubsetelementgetindex', 'hierarchysubsetelementinsert',
    'hierarchysubsetexists', 'hierarchysubsetgetsize', 'hierarchysubsetgetelementname', 'hierarchysubsetisallset',
    'hierarchysubsetmdxget', 'hierarchysubsetmdxset', 'publishsubset', 'subsetaliasget', 'subsetaliasset',
    'subsetcreate', 'subsetcreatebymdx', 'subsetdeleteallelements', 'subsetdestroy', 'subsetelementdelete',
    'subsetelementexists', 'subsetelementgetindex', 'subsetelementinsert', 'subsetexists', 'subsetexpandaboveset',
    'subsetformatstyleset', 'subsetgetelementname', 'subsetgetsize', 'subsetisallset', 'subsetmdxget', 'subsetmdxset',
    'publishview', 'disablemtqviewconstruct', 'enablemtqviewconstruct', 'viewcolumndimensionset',
    'viewcolumnsuppresszeroesset', 'viewconstruct', 'viewcreate', 'viewcreatebymdx', 'viewdestroy', 'viewexists',
    'viewextractfilterbytitlesset', 'viewextractskipcalcsset', 'viewextractskipconsolidatedstringsset',
    'viewextractskiprulevaluesset', 'viewextractskipzeroesset', 'viewmdxset', 'viewmdxget', 'viewrowdimensionset',
    'viewrowsuppresszeroesset', 'viewsubsetassign', 'viewsuppresszeroesset', 'viewtitledimensionset',
    'viewtitleelementset', 'viewzeroout', 'addinfocuberestriction', 'executejavan', 'executejavas', 'expand',
    'fileexists', 'logoutput', 'tm1user', 'wildcardfilesearch', 'stringglobalvariable', 'numericglobalvariable'
)

TI_VARIABLES = (
    'DatasourceNameForServer', 'DatasourceNameForClient', 'DatasourceType', 'DatasourceUsername', 'DatasourcePassword',
    'DatasourceQuery', 'DatasourceCubeView', 'DatasourceDimensionSubset', 'DatasourceASCIIDelimiter',
    'DatasourceASCIIDecimalSeparator', 'DatasourceASCIIThousandSeparator', 'DatasourceASCIIQuoteCharacter',
    'DatasourceASCIIHeaderRecords', 'Value_Is_String', 'NValue', 'SValue', 'OnMinorErrorDoItemSkip',
    'MinorErrorLogMax', 'DataSourceODBOCatalog', 'DataSourceODBOConnectionString', 'DataSourceODBOCubeName',
    'DataSourceODBOHierarchyName', 'DataSourceODBOLocation', 'DataSourceODBOProvider', 'DataSourceODBOSAPClientID',
    'DataSourceODBOSAPClientLanguage', 'DataMinorErrorCount', 'MetadataMinorErrorCount', 'ProcessReturnCode',
    'PrologMinorErrorCount'
)


def format_procedure(text):
    token_dict = {}

    text = _tokenize(text, token_dict)

    text = text.replace('\t', '   ')
    text = text.replace(' ', '')
    text = text.replace('\r\n', '\n')

    text = _update_functions(text)
    text = _update_control(text)
    text = _update_operator(text)
    text = _update_variables(text)
    text = _update_indent(text)
    text = _update_executeprocess(text)

    text = _detokenize(text, token_dict)

    return text


def _detokenize(text, token_dict):
    # Replace tokens with their original values
    for k, v in token_dict.items():
        text = text.replace(v, k)

    return text


def _tokenize(text, token_dict):
    # Replace comments with tokens
    found_string = re.search(RE_TOKENIZE_COMMENT, text, flags=re.MULTILINE)
    while found_string:

        start = found_string.start(0)
        end = found_string.end(0)

        entry = ''.join(found_string.groups()).lstrip()

        if entry not in token_dict:
            key = '^COMMENT:' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)) + '^'
            token_dict[entry] = key
        else:
            key = token_dict[entry]

        text = text[:start] + key + text[end:]

        found_string = re.search(RE_TOKENIZE_COMMENT, text, flags=re.MULTILINE)

    # Replace strings with tokens
    found_string = re.search(RE_TOKENIZE_STRING, text, flags=re.DOTALL)
    while found_string:
        start = found_string.start(0)
        end = found_string.end(0)

        entry = ''.join(found_string.groups())

        if entry not in token_dict:
            key = '^STRING:' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)) + '^'
            token_dict[entry] = key
        else:
            key = token_dict[entry]

        text = text[:start] + key + text[end:]

        found_string = re.search(RE_TOKENIZE_STRING, text, flags=re.DOTALL)

    return text


def _update_functions(text):
    text = re.sub(RE_FUNC.format('|'.join(TI_FUNCTIONS)), lambda x: x.group(1).upper(), text, flags=re.IGNORECASE)
    text = re.sub(RE_PARAM_PAREN, r'\2', text)
    text = re.sub(RE_PARAM_COMMA, r'\2 ', text)
    text = re.sub(RE_END, r'\2\4', text)

    return text


def _update_control(text):
    text = re.sub(RE_FUNC.format('|'.join(TI_CONTROL_PARAM)), lambda x: x.group(1).upper(), text, flags=re.IGNORECASE)

    return text


def _update_operator(text):
    text = re.sub(RE_OPERATOR, r' \2 ', text)

    return text


def _update_variables(text):
    for var in TI_VARIABLES:
        text = re.sub(RE_FUNC.format(var), var, text, flags=re.IGNORECASE)

    text = re.sub(RE_DIGITS, r'\1 \3\5', text)

    return text


def _update_indent(text):
    lines_new = []
    indent = 0
    for line in text.split('\n'):
        match = re.match(RE_INDENT, line, flags=re.IGNORECASE)
        if match:
            if match.group(3).upper() in ('IF', 'WHILE'):
                line = INDENT * indent + line
                indent = indent + 1
            elif match.group(3).upper() in ('ELSEIF', 'ELSE'):
                line = INDENT * (indent - 1) + line
            else:
                indent = indent - 1
                line = INDENT * indent + line
        else:
            line = INDENT * indent + line

        line = line.rstrip()

        lines_new.append(line)

    text = '\n'.join(lines_new)

    return text


def _update_executeprocess(text):
    lines_new = []
    for line in text.split('\n'):
        match = re.match(RE_EXECUTEPROCESS, line, flags=re.IGNORECASE)
        if match:
            # Tokenize parameters
            param_string = match.group(3)
            params = []
            level = 0
            start = 0
            for i, char in enumerate(param_string):
                if char == '(':
                    level += 1
                elif char == ')':
                    level -= 1
                elif char == ',' and level == 0:
                    params.append(param_string[start:i])
                    start = i + 1

                if i == len(param_string) - 1:
                    params.append(param_string[start:])

            if len(params) > 3:
                lines_new.append(match.group(1) + match.group(2) + params[0])
                for v, w in zip(params[1::2], params[2::2]):
                    lines_new.append(match.group(1) + INDENT + ',' + v + ',' + w)
                lines_new.append(match.group(1) + match.group(4))
                continue

        lines_new.append(line)

    return '\n'.join(lines_new)
