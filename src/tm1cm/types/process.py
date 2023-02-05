import copy
import json
import logging
import os
import urllib.parse

import yaml
from TM1py.Objects.Process import Process as TM1PyProcess

from tm1cm.common import Dumper
from tm1cm.types.base import Base

PROCEDURES = ['PrologProcedure', 'MetadataProcedure', 'DataProcedure', 'EpilogProcedure']


class Process(Base):

    def __init__(self, config, app=None):
        self.type = 'process'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Processes?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_local(self, app, items):

        files = [os.path.join(app.path, self.path, item + self.ext) for item in items]

        for name, file in zip(items, files):
            with open(file, 'rb') as fp:
                result = fp.read().decode('utf8')

            yield name, self._transform_from_local(name, result)

    def _get_remote(self, app, items):
        filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in items]
        select = "*,UIData,VariablesUIData," \
                 "DataSource/dataSourceNameForServer," \
                 "DataSource/dataSourceNameForClient," \
                 "DataSource/asciiDecimalSeparator," \
                 "DataSource/asciiDelimiterChar," \
                 "DataSource/asciiDelimiterType," \
                 "DataSource/asciiHeaderRecords," \
                 "DataSource/asciiQuoteCharacter," \
                 "DataSource/asciiThousandSeparator," \
                 "DataSource/view," \
                 "DataSource/query," \
                 "DataSource/userName," \
                 "DataSource/password," \
                 "DataSource/usesUnicode," \
                 "DataSource/subset"
        request = '/api/v1/Processes?$select={}&$filter='.format(select)

        results = self._do_filter_request(app, request, filter)
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        for name, result in results:
            yield name, self._transform_from_remote(name, result)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        process = TM1PyProcess.from_dict(item)

        if not session.processes.exists(process.name):
            session.processes.create(process)
        else:
            session.processes.update(process)

    def _update_local(self, app, name, item):
        path = os.path.join(app.path, self.path, item['Name'] + self.ext)
        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'wb') as outfile:
            output = []
            for procedure in PROCEDURES:
                header = globals().get('{}_BEGIN'.format(procedure[:-9].upper()))

                text = item[procedure]
                text = self._fix_generated_lines(text)
                text = text.replace('\r\n', '\n')

                footer = globals().get('{}_END'.format(procedure[:-9].upper()))
                output.append((header + text + footer).encode('utf8'))

            header = globals().get('PROPERTIES_BEGIN').encode('utf8')
            text = {key: value for key, value in item.items() if key not in PROCEDURES}

            if self.file_format == 'YAML':
                text = yaml.dump(text, Dumper=Dumper, width=255)
            else:
                text = json.dumps(text, indent=4, sort_keys=True, ensure_ascii=False)

            footer = globals().get('PROPERTIES_END').encode('utf8')
            output.insert(0, header + text.encode('utf8') + footer)

            outfile.write(''.encode('utf8').join(output))

    def _delete_remote(self, app, name):
        session = app.session

        if session.processes.exists(name):
            session.processes.delete(name)

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        if 'Variables' in item:
            for pos, variable in enumerate(item['Variables'], start=1):
                variable['Position'] = pos

        return item

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)
        if 'DataSource' in item:
            if 'password' in item['DataSource']:
                del item['DataSource']['password']
        if 'Attributes' in item:
            del item['Attributes']
        if 'Variables' in item:
            for variable in item['Variables']:
                del variable['Position']

        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        process = self._get_process_text(item, 'PropertiesProcedure')

        if self.file_format == 'YAML':
            process = yaml.safe_load(process)
        else:
            process = json.safe_load(process, indent=4, sort_keys=True, ensure_ascii=False)

        process['Name'] = name

        for procedure in PROCEDURES:
            procedure_text = self._get_process_text(item, procedure)
            process[procedure] = procedure_text

        return process

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']
        return item

    def _get_process_text(self, text, procedure):
        header = globals().get('{}_BEGIN'.format(procedure[:-9].upper()))
        footer = globals().get('{}_END'.format(procedure[:-9].upper()))
        start = text.index(header) + len(header)
        end = text.index(footer)

        process_text = text[start:end]
        process_text = process_text.replace('\r\n', '\n')
        process_text = '\r\n'.join(process_text.split('\n'))

        return process_text

    def _fix_generated_lines(self, text):
        try:
            split = text.split('\r\n')
            index = split.index('#****End: Generated Statements****')

            if index + 1 == len(split) or split[index + 1] != '':
                split.insert(index + 1, '')

            return '\r\n'.join(split)
        except Exception:
            return text


logger = logging.getLogger(Process.__name__)

PROPERTIES_BEGIN = """
###############################################################################
# BEGIN: PROPERTIES ###########################################################
###############################################################################
""".lstrip()

PROPERTIES_END = """
###############################################################################
# END: PROPERTIES #############################################################
###############################################################################
""".rstrip()

PROLOG_BEGIN = """
###############################################################################
# BEGIN: PROLOG PROCEDURE #####################################################
###############################################################################

"""

PROLOG_END = """

###############################################################################
# END: PROLOG PROCEDURE #######################################################
###############################################################################
""".rstrip()

METADATA_BEGIN = """
###############################################################################
# BEGIN: METADATA PROCEDURE ###################################################
###############################################################################

"""

METADATA_END = """

###############################################################################
# END: METADATA PROCEDURE #####################################################
###############################################################################
""".rstrip()

DATA_BEGIN = """
###############################################################################
# BEGIN: DATA PROCEDURE #######################################################
###############################################################################

"""

DATA_END = """

###############################################################################
# END: DATA PROCEDURE #########################################################
###############################################################################
""".rstrip()

EPILOG_BEGIN = """
###############################################################################
# BEGIN: EPILOG PROCEDURE #####################################################
###############################################################################

"""

EPILOG_END = """

###############################################################################
# END: EPILOG PROCEDURE #######################################################
###############################################################################
""".rstrip()
