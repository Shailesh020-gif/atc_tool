"""
Module for test
"""
 
import json
import logging
import os
import random
import re
import subprocess
import sys
 
import petl as etl
import yaml
 
from tabulate import tabulate

from config import LABELS_DEV_STATUS_ALL
 
from act.common import get_act_dir
from act.db import add_test_db
from act.cfg import get_hw_cfg
from jinja2 import Template
 
MAX_SEED = 4294967295
SQL_ALL_TESTS = 'SELECT * FROM test'
 
def drop_table(args):
 
    """ Remove the test table """
 
    cursor = args.connection.cursor()
    cursor.execute('''DROP TABLE IF EXISTS test''')
    cursor.execute('''DROP TABLE IF EXISTS var''')
    args.connection.commit()
 
def create_table(args):
 
    """ Create the test table """
 
    cursor = args.connection.cursor()

    cursor.execute('''CREATE TABLE test (TEST_NAME text,

                                         UVM_TESTNAME text,

                                         COUNT int DEFAULT 1,

                                         SEED text DEFAULT '1',

                                         DEV_STATUS text,

                                         LABEL text,

                                         PROJECT_PHASE text,

                                         HW_CFG text,

                                         DUE_DATE text,

                                         PASS_DATE text,

                                         TARGET text

                                         )''')

    cursor.execute('''CREATE TABLE var  (NAME text, VALUE text)''')

    if hasattr(args, 'seed'):

        seed = args.seed

    else:

        seed = 1

    cursor.execute(f'''INSERT INTO var (NAME,VALUE) VALUES ('test_seed','{seed}') ''')

    args.connection.commit()
 
def sync_db(args, tfiles):
 
    """ Synchronize tests from source """
 
    drop_table(args)

    create_table(args)

    read_tests(args, tfiles)

    filter_by_target(args)

    resolve_duplicates(args)

    check_fields(args)

    update_label(args)
 
def check_duplicate(name, fields):
 
    """ check if a field is duplicate in other case """
 
    if name in fields:

        return False
 
    for field in fields:

        if name.upper() == field.upper():

            return True
 
    return False
 
def add_fields(args, fields):
 
    """ add fields in the test database """
 
    cursor = args.connection.cursor()

    ids = get_fields_full(args)

    for field in [x for x in fields if x not in set(ids)]:

        if field[-3:] == '_LC':

            logging.warning('Problem with %s , the usage of _LC is deprecated. Replace %s by %s', field, field, field[0:-3].lower())

        cursor.execute('''ALTER TABLE test ADD COLUMN {} TEXT'''.format(field))

    args.connection.commit()
 
def filter_by_target(args):

    """ Resolve duplicate tests """
 
    if not args.sync_target:

        return
 
    connection = args.connection

    #cursor = args.connection.cursor()

    remove = connection.execute(f"SELECT COUNT(TEST_NAME) FROM test WHERE TARGET LIKE '%{args.sync_target}%'").fetchone()[0]

    # remove = 0

    # for row in cursor.execute('SELECT TEST_NAME, TARGET FROM test').fetchall():

    #     if row[1] is not None:

    #         if re.search(r'\b' + args.sync_target + r'\b', row[1]):

    #             continue

    #     cursor.execute(f''' DELETE FROM test WHERE TEST_NAME = '{row[0]}' ''')

    #     remove += 1

    connection.execute(f"DELETE FROM test WHERE TARGET NOT LIKE '%{args.sync_target}%' OR TARGET IS NULL")

    connection.commit()

    logging.info('%d tests were deleted with the %s target filter.', remove, args.sync_target)
 
def resolve_duplicates(args):
 
    """ Resolve duplicate tests """
 
    cursor = args.connection.cursor()

    sql = 'SELECT TEST_NAME,COUNT(*) c FROM test GROUP BY TEST_NAME HAVING c > 1'

    tests = cursor.execute(sql).fetchall()

    if len(tests) == 0:

        logging.info('0 test have duplicate name')

        return

    logging.warning('%d test(s) have duplicate name', len(tests))

    for test in tests:

        cursor.execute(f'''DELETE FROM test WHERE TEST_NAME = '{test[0]}' ''')

        logging.warning('remove %s', test[0])

    args.connection.commit()
 
def check_project_phase(args):
 
    """ check PROJECT_PHASE """
 
    error = False

    cursor = args.connection.cursor()

    sql = 'SELECT COUNT(*) FROM test WHERE PROJECT_PHASE is NOT NULL'

    data = cursor.execute(sql).fetchall()

    if data[0][0] == 0:

        logging.warning('PROJECT_PHASE is not filled in !!!')

    sql = 'SELECT DISTINCT(PROJECT_PHASE) FROM test WHERE PROJECT_PHASE is NOT NULL'

    for data in cursor.execute(sql):

        if not re.match(r'^PHASE_\d\.\d$', data[0]):

            logging.error('The value %s is not good for PROJECT_PHASE (PHASE_<#>.<#>)', data[0])

            error = True
 
    return error
 
def check_dev_status(args):
 
    """ check DEV_STATUS """
 
    error = False

    cursor = args.connection.cursor()

    sql = 'SELECT DISTINCT(DEV_STATUS) FROM test WHERE DEV_STATUS is NOT NULL'

    dev_status = list()

    for data in cursor.execute(sql):

        if data[0] in LABELS_DEV_STATUS_ALL:

            dev_status.append(data[0])

        else:

            logging.error('%s not a good value for DEV_STATUS (%s)', data[0], ','.join(LABELS_DEV_STATUS_ALL))

            error = True

    if not dev_status:

        logging.warning('DEV_STATUS is not filled in !!!')

    sql = 'SELECT TEST_NAME FROM test WHERE DEV_STATUS is NULL'

    for data in cursor.execute(sql):

        logging.warning('%s test has no DEV_STATUS => fixed at TODO', data[0])

    cursor.execute('''UPDATE test SET DEV_STATUS='TODO' WHERE DEV_STATUS is NULL''')
 
    return error
 
def update_label(args):
 
    """ set LABEL if not defined """
 
    cursor = args.connection.cursor()

    cursor.execute('''UPDATE test SET LABEL=TEST_VIEW WHERE LABEL is NULL''')

    cursor.execute('''UPDATE test SET COUNT=1 WHERE COUNT is NULL''')

    args.connection.commit()
 
def check_due_pass_date(args):
 
    """ check DUE_DATE and PASS_DATE """
 
    error = False

    cursor = args.connection.cursor()

    re_date = re.compile(r'^(19|20)\d\d[- /.](0[1-9]|1[012])[- /.](0[1-9]|[12][0-9]|3[01])')

    if 'due_date' in args.cfg['test']:

        sql = 'SELECT TEST_NAME, DUE_DATE FROM test WHERE DUE_DATE is NOT NULL'

        for data in cursor.execute(sql):

            if not re_date.search(data[1]):

                logging.error('The DUE_DATE %s for %s is not good, should be YYYY-MM-DD', data[1], data[0])

                error = True

        cursor.execute(f'''UPDATE test SET DUE_DATE='{args.cfg["test"]["due_date"]}' WHERE DUE_DATE is NULL''')

        cursor.execute(f'''UPDATE test SET DUE_DATE=DATE(DUE_DATE)''')

    if 'pass_date' in args.cfg['test']:

        sql = 'SELECT TEST_NAME, PASS_DATE FROM test WHERE PASS_DATE is NOT NULL'

        for data in cursor.execute(sql):

            if not re_date.search(data[1]):

                logging.error('The PASS_DATE %s for %s is not good, should be YYYY-MM-DD', data[1], data[0])

                error = True

        cursor.execute(f'''UPDATE test SET PASS_DATE='{args.cfg["test"]["pass_date"]}' WHERE PASS_DATE is NULL''')

        cursor.execute(f'''UPDATE test SET PASS_DATE=DATE(PASS_DATE)''')

    args.connection.commit()
 
    return error
 
 


def check_fields(args):
 
    """ check field : PROJECT_PHASE, DEV_STATUS, LABEL, DUE_DATE, PASS_DATE """
 
    error = False

    error |= check_project_phase(args)

    error |= check_dev_status(args)

    error |= check_due_pass_date(args)

    if error:

        sys.exit(1)
 
def read_xls(args, xls, sheet):
 
    """ Save Excel file into test database """
 
    sheet_name = None

    if sheet != 'None':

        sheet_name = sheet

    table = etl.xlsx.fromxlsx(xls, sheet=sheet_name, data_only=True)

    table = etl.addfield(table, 'TEST_VIEW', sheet)

    table = etl.addfield(table, 'TEST_FILE', os.path.basename(xls))

    fields = list(set(etl.header(table)))
 
    # remove empty columns

    if None in fields:

        fields.remove(None)

        table = etl.cut(table, fields)
 
    add_fields(args, fields)

    etl.appenddb(table, args.connection, 'test')

    cursor = args.connection.cursor()

    cursor.execute('DELETE FROM test  WHERE TEST_NAME is NULL')

    args.connection.commit()
 
def get_header_tests(tests):
 
    """ get header to avoid missing field """
 
    header = set()

    for test in tests:

        header.update(test.keys())
 
    return header
 
def read_json(args, json_file, view):
 
    """ Save JSON file into test database """
 
    with open(json_file) as fjson:

        tests = json.load(fjson)
 
    table = etl.fromjson(json_file, header=get_header_tests(tests))

    table = etl.addfield(table, 'TEST_VIEW', view)

    table = etl.addfield(table, 'TEST_FILE', os.path.basename(json_file))

    fields = list(etl.header(table))
 
    add_fields(args, fields)

    etl.appenddb(table, args.connection, 'test')
 
def read_yaml(args, yaml_file, view):
 
    """ Save YAML file into test database """
 
    with open(yaml_file, 'r') as file:

        tests = yaml.safe_load(file)
 
    table = etl.fromdicts(tests, header=get_header_tests(tests))

    table = etl.addfield(table, 'TEST_VIEW', view)

    table = etl.addfield(table, 'TEST_FILE', os.path.basename(yaml_file))

    fields = list(etl.header(table))
 
    add_fields(args, fields)

    etl.appenddb(table, args.connection, 'test')
 
def read_csv(args, csv_file, view):
 
    """ Save CSV file into test database """
 
    table = etl.fromcsv(csv_file)

    table = etl.addfield(table, 'TEST_VIEW', view)

    table = etl.addfield(table, 'TEST_FILE', os.path.basename(csv_file))

    fields = list(etl.header(table))

    add_fields(args, fields)

    etl.appenddb(table, args.connection, 'test')
 
def read_py(args, py_file, view):
 
    """ Save ouput script (JSON format) into test database """
 
    result = ''

    cmd = subprocess.Popen(py_file, shell=True, stdout=subprocess.PIPE)

    for line in cmd.stdout:

        result += line.decode("utf-8")

    if cmd.wait():

        logging.error("Python error with %s", py_file)

        sys.exit(1)

    tests = json.loads(result)

    table = etl.fromdicts(tests, header=get_header_tests(tests))

    table = etl.addfield(table, 'TEST_VIEW', view)

    table = etl.addfield(table, 'TEST_FILE', os.path.basename(py_file))

    fields = list(etl.header(table))

    add_fields(args, fields)

    etl.appenddb(table, args.connection, 'test')
 
def read_tests(args, tfiles):
 
    """ read all test files """
 
    for tfile in tfiles:

        if isinstance(tfile, dict):

            file = list(tfile.keys())[0]

            view = list(tfile.values())[0]

        else:

            file = tfile

            view = 'default'

        logging.info('load %s with view %s', file, view)

        ext = os.path.splitext(file)[1]

        ext_list = ['.xlsx', '.json', '.py', '.csv', '.yaml', '.source']

        if ext == ext_list[0]:

            read_xls(args, file, view)

        elif ext == ext_list[1]:

            read_json(args, file, view)

        elif ext == ext_list[2]:

            read_py(args, file, view)

        elif ext == ext_list[3]:

            read_csv(args, file, view)

        elif ext == ext_list[4]:

            read_yaml(args, file, view)

        elif ext == ext_list[5]:

            dir_file = os.path.dirname(file)

            files = list()

            for line in open(file):

                path_file = os.path.join(dir_file, line.rstrip())

                files.append({path_file : view})

            read_tests(args, files)

        else:

            logging.error("Test file source not supported : %s", file)

            logging.info("Format supported : %s", ', '.join(ext_list))

            sys.exit(1)
 
def get_tests_full(args):
 
    """ get tests full list """
 
    cursor = args.connection.cursor()

    data = cursor.execute("SELECT TEST_NAME FROM test ORDER BY TEST_NAME").fetchall()

    return [table[0] for table in data]
 
def get_tests_number(args):
 
    """ get the number of tests """
 
    cursor = args.connection.cursor()

    data = cursor.execute("SELECT COUNT(TEST_NAME) as COUNT, SUM(COALESCE(COUNT,1)) as FULL_COUNT  FROM test").fetchall()

    return data[0]
 
def get_tests_number_planned(args):
 
    """ get the number of tests """
 
    cursor = args.connection.cursor()

    data = cursor.execute("SELECT COUNT(TEST_NAME) as COUNT, SUM(COALESCE(COUNT,1)) as FULL_COUNT  FROM test WHERE DEV_STATUS <> 'NOTPLANNED'").fetchall()

    return data[0]
 
def print_summary(data, head=None):
 
    

    template_head = "{:>60s}|{:^13s}|{:^13s}|{:^13s}|{:^13s}|{:^13s}"

    print(template_head.format(*head))

    template_row = "{:>60s}|{:=13d}|{:=13d}|{:=13d}|{:=13d}|{:=13d}"

    separator = '-'*60 + '|' + '-'*13 + '|' + '-'*13 + '|' + '-'*13 + '|' + '-'*13 + '|' + '-'*13

    print(separator)
 
    planned=0

    todo=0

    on_going=0

    not_planned=0

    done=0
 
    for row in data:

        print(template_row.format(*row))

        planned += row[1]

        todo += row[2]

        on_going += row[3]

        not_planned += row[4]

        done += row[5]
 
    print(separator)

    print(template_row.format('Sum', planned, todo, on_going, not_planned, done))
 
def summary(args):
 
    cursor = args.connection.cursor()
 
    summary_sql_template = Template('''

SELECT LABEL as label,

    DEV_STATUS as status,

    TEST_FILE as file,

    TEST_NAME as test

FROM test

{%- if by_label or by_status %}

WHERE

{%- endif%}

{%- if by_label %}

    LABEL IN (

    {%- for label in by_label -%}

        '{{ label }}'{%- if not loop.last -%},{%- endif -%}

    {%- endfor -%}

    )

{%- endif %}

{%- if by_label and by_status %}

AND

{%- endif%}

{%- if by_status %}

    DEV_STATUS IN (

    {%- for status in by_status -%}

        '{{ status }}'{%- if not loop.last -%},{%- endif -%}

    {%- endfor -%}

    )

{%- endif %}

ORDER BY label, file, status

        ''')
 
    summarry_sql = summary_sql_template.render(by_label=args.by_label, by_status=args.by_status)
 
    if args.by_label or args.by_status:

        summarry_sql = summary_sql_template.render(by_label=args.by_label, by_status=args.by_status)

        data =  cursor.execute(summarry_sql).fetchall()

        header = [ r[0] for r in cursor.description ]

        template = "{:>15}|{:^15s}|{:^40}|{:<50s}"

        separator = '-'*15 + '|' + '-'*15 + '|' + '-'*40 + '|' + '-'*50

        print(template.format(*header))

        print(separator)

        for row in data:

            print(template.format(*row))
 
    else:
 
        print("With test COUNT taked in account")

        data_with_count =  cursor.execute('''

    SELECT label as label, 

	sum(test.COUNT) AS planned,

        sum(CASE WHEN DEV_STATUS='TODO' THEN test.COUNT ELSE 0 END) AS todo,

        sum(CASE WHEN DEV_STATUS='ONGOING' THEN test.COUNT ELSE 0 END) AS on_going,

        sum(CASE WHEN DEV_STATUS='NOTPLANNED' THEN test.COUNT ELSE 0 END) AS not_planned,

        sum(CASE WHEN DEV_STATUS='DONE' THEN test.COUNT ELSE 0 END) AS done

    FROM test

    GROUP BY label

        ''').fetchall()

        columns = [ r[0] for r in cursor.description ]

        print_summary(data_with_count, columns)

 
        print("Without test COUNT taked in account")

        data_without_count =  cursor.execute('''

    SELECT label as label, 

	count(DEV_STATUS) AS planned,

        sum(CASE WHEN DEV_STATUS='TODO' THEN 1 ELSE 0 END) AS todo,

        sum(CASE WHEN DEV_STATUS='ONGOING' THEN 1 ELSE 0 END) AS on_going,

        sum(CASE WHEN DEV_STATUS='NOTPLANNED' THEN 1 ELSE 0 END) AS not_planned,

        sum(CASE WHEN DEV_STATUS='DONE' THEN 1 ELSE 0 END) AS done

    FROM test

    GROUP BY label

        ''').fetchall()

        columns = [ r[0] for r in cursor.description ]

        print_summary(data_without_count, columns)
 
 
def get_tests(args):
 
    """ get tests list """
 
    if args.sql is None:

        args.sql = SQL_ALL_TESTS
 
    if args.sql == SQL_ALL_TESTS:

        return get_tests_full(args)
 
    cursor = args.connection.cursor()
 
    logging.debug("SQL executed : %s", args.sql)
 
    tests = list()

    for row in cursor.execute(args.sql).fetchall():

        for i, field in enumerate(cursor.description, 0):

            if field[0] == 'TEST_NAME':

                tests.append(row[i])

    return tests
 
def get_fields_full(args):
 
 


    """ get fields full list """
 
    cursor = args.connection.cursor()

    data = cursor.execute("pragma table_info('test')").fetchall()
 
    return [fields[1] for fields in data]
 
def get_fields(args):
 
    """ get fields list """
 
    fields = list()

    if args.sql == SQL_ALL_TESTS:

        fields = get_fields_full(args)

    else:

        cursor = args.connection.cursor()

        fields_set = set()

        for row in cursor.execute(args.sql).fetchall():

            for i, field in enumerate(cursor.description, 0):

                if row[i] is not None:

                    fields_set.add(field[0])

        fields = list(set(fields_set))
 
    if 'UVM_TESTNAME' in fields:

        fields.remove('UVM_TESTNAME')

        fields.insert(0, 'UVM_TESTNAME')
 
    if 'TEST_NAME' in fields:

        fields.remove('TEST_NAME')

        fields.insert(0, 'TEST_NAME')

    return fields
 
def get_values(args):
 
    """" get list of values of a field """
 
    cursor = args.connection.cursor()

    values = set()

    for row in cursor.execute(args.sql).fetchall():

        for i, field in enumerate(cursor.description, 0):

            if field[0] == args.field and row[i] is not None:

                values.add(row[i])

    return sorted(list(values))
 
def print_tests(args):
 
    """" print tests with fields in the terminal """
 
    tests = etl.fromdb(args.connection, args.sql)

    fields = get_fields(args)

    tests = etl.cut(tests, fields)

    print(tabulate(tests, tablefmt='psql'), flush=True)
 
def print_tests_by_hw_cfg(args):
 
    """ print tests summary by cfg """
 
    list_hw_cfg = get_hw_cfg(args.cfg)

    if not list_hw_cfg:

        return

    cursor = args.connection.cursor()

    for hw_cfg in list_hw_cfg:

        sql = f'''SELECT COUNT(*) as COUNT, SUM(COALESCE(COUNT,1)) as FULL_COUNT FROM test where HW_CFG like '%{hw_cfg}%' or HW_CFG is NULL'''

        data = cursor.execute(sql).fetchall()

        if data[0][0] == 0:

            logging.warning("No test for %s", hw_cfg)

            continue

        logging.info("%s: %d tests (%d with the count) loaded", hw_cfg, data[0][0], data[0][1])

        sql += ''' AND DEV_STATUS <> 'NOTPLANNED' '''

        data = cursor.execute(sql).fetchall()

        if data[0][0] == 0:

            logging.warning("No planned tests for %s", hw_cfg)

            continue

        logging.info("%s: %d tests (%d with the count) planned", hw_cfg, data[0][0], data[0][1])
 
def write_tests(args):
 
    """" writes tests with fields in a file """
 
    ext = os.path.splitext(args.write)[1]

    tests = etl.fromdb(args.connection, args.sql)

    fields = get_fields(args)

    tests = etl.cut(tests, fields)

    ext_list = ['.csv', '.xlsx', '.json', '.list']

    if ext == ext_list[0]:

        logging.info("start to write csv")

        etl.tocsv(tests, args.write)

        logging.info("end to write csv")

    elif ext == ext_list[1]:

        logging.info("start to write Excel")

        etl.toxlsx(tests, args.write)

        logging.info("end to write Excel")

    elif ext == ext_list[2]:

        logging.info("start to write JSON")

        etl.tojson(tests, args.write, indent=4)

        logging.info("end to write JSON")

    elif ext == ext_list[3]:

        logging.info("start to write list")

        flist = open(args.write, 'w')

        flist.write('\n'.join(list(etl.values(tests, 'TEST_NAME'))))

        flist.close()

        logging.info("end to write list")

    else:

        logging.error("the extension %s is not reconized", ext)

        logging.info("Format supported : %s", ', '.join(ext_list))

        sys.exit(1)
 
def get_test_seed(args):
 
 
    """ get the seed which is used at database creation """
 
    cursor = args.connection.cursor()

    data = cursor.execute('''SELECT VALUE FROM var WHERE NAME="test_seed"''').fetchall()

    return data[0][0]
 
def get_test(args, name):
 
    """ get a test with field  test['field]='value'"""
 
    test = dict()

    cursor = args.connection.cursor()

    for row in cursor.execute("SELECT * FROM test WHERE TEST_NAME ='" + name + "'").fetchall():

        for i, field in enumerate(cursor.description, 0):

            if row[i] is not None:

                test[field[0]] = row[i]

    return test
 
def main_test(args):
 
    """ main of test module """
 
    tests = None

    if args.query:

        args.sql_file = os.path.join(get_act_dir(), 'sql', '{}.sql'.format(args.query))

    if args.sql_file:

        with open(args.sql_file, 'r') as file:

            args.sql = file.read()

    if args.sql:

        if not args.write:

            args.print = True

    if not args.sql:

        args.sql = SQL_ALL_TESTS

    if args.source:

        source = list()

        for source_file in args.source:

            file, view = (source_file.split(':') + [None])[:2]

            source.append({file : view})

        args.source = source

        args.sync = True

    else:

        args.source = args.cfg['test']['source']

    if args.sync_target:

        args.sync = True

    if args.sync:

        if args.seed:

            if args.seed == 'random':

                args.seed = random.randint(0, MAX_SEED)

        else:

            args.seed = 1

        sync_db(args, args.source)

        add_test_db(args)

        tests, tests_full = get_tests_number(args)

        logging.info("%d tests (%d with the count) loaded with seed %d", tests, tests_full, args.seed)

        tests, tests_full = get_tests_number_planned(args)

        logging.info("%d tests (%d with the count) planned", tests, tests_full)

        print_tests_by_hw_cfg(args)

    if args.summary:

        summary(args)
 
    if args.test:

        where_test = list()

        for test in args.test:

            where_test.append(" TEST_NAME = '{}'".format(test))

        args.sql += ' WHERE ( ' + ' OR '.join(where_test) + ' )'

    elif args.test_filter:

        args.sql += ''' WHERE TEST_NAME like '%{}%' '''.format(args.test_filter)

        tests = get_tests(args)

        logging.info("%d test(s) for %s", len(tests), args.test_filter)

    if args.field:

        if args.sql == SQL_ALL_TESTS:

            args.sql += ' WHERE '

        else:

            args.sql += ' AND '

        args.sql += '{} is NOT NULL'.format(args.field)

        tests = get_tests(args)

        logging.info("%d test(s) for %s", len(tests), args.field)

        if args.values:

            values = get_values(args)

            for value in values:

                print(value, flush=True)

            logging.info("%d possible value(s) for %s", len(values), args.field)

        if args.value:

            args.sql += " AND {} = '{}'".format(args.field, args.value)

            tests = get_tests(args)

            logging.info("%d test(s) for %s=%s", len(tests), args.field, args.value)

    if args.tests:

        tests = get_tests(args)

        print('\n'.join(sorted(tests)), flush=True)

        logging.info("%d test(s)", len(tests))

    if args.fields:

        fields = get_fields(args)

        print('\n'.join(sorted(fields)), flush=True)

        logging.info("%d fields(s)", len(fields))

    if args.print:

        print_tests(args)

    if args.write:

        write_tests(args)
 
