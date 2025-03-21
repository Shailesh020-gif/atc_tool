"""

Module for database

"""
 
import json

import logging

import os

import sys

import sqlite3

from datetime import datetime
 
import mysql.connector

from config import (LABELS_DEV_STATUS, LABELS_DEV_STATUS_ALL,

                    LABELS_DEV_STATUS_IGNORE)
 
from act.cfg import get_hw_cfg
 
from act.common import file_to_str, get_datetime_file, get_act_dir
 
DUT_NAME = os.getenv('ACT_DV_DUT_NAME', os.getenv('DV_DUT_NAME', ''))

PROJECT_NAME = os.getenv('ACT_PROJECT_NAME', os.getenv('PROJECT_NAME', ''))
 
TEST_TABLE = f'''test_{PROJECT_NAME}'''

REG_TABLE = f'''reg_{PROJECT_NAME}'''

RUN_TABLE = f'''run_{PROJECT_NAME}'''

ERROR_TABLE = f'''error_{PROJECT_NAME}'''

METRIC_TABLE = f'''metric_{PROJECT_NAME}'''
 
def connect():
 
    """ connect to mysql database """
 
    profile = os.getenv('ACT_DB_PROFILE', '.dv_regression.cnf')

    return mysql.connector.connect(option_files=os.path.join(get_act_dir(), profile))
 
def insert_row(connection, table, row):
 
    """ insert a row in the table from a dict """
 
    cursor = connection.cursor()

    values = (str(list(row.values()))[1:-1])

    sql = f'INSERT INTO {table}'

    sql += ' (' + ','.join([x.lower() for x in row.keys()]) + ')'

    sql += ' VALUES (' + values + ')'

    try:

        cursor.execute(sql)

        row_id = cursor.lastrowid

        connection.commit()

        logging.debug("insert row into %s with id %d", table, row_id)

        return row_id

    except mysql.connector.Error as err:

        logging.info("SQL: %s", sql)

        logging.error("SQL error: %s", err)

        sys.exit(1)
 
def update_row(connection, table, row, run_id):
 
    """ update a row in the table from a dict and an id """
 
    cursor = connection.cursor()

    sql = f'UPDATE {table} SET '

    sql_list = list()

    for field in row:

        sql_list.append(f'''{field} = %s ''')

    sql += ','.join(sql_list)

    sql += f' WHERE id = {run_id}'

    try:

        cursor.execute(sql, tuple(row.values()))

        logging.debug("update %d into %s", run_id, table)

    except mysql.connector.Error as err:

        logging.info("SQL: %s", sql)

        logging.error("SQL error: %s", err)

        sys.exit(1)
 
def get_project_phases(cursor):
 
    """ get all phases in the test  """
 
    project_phases = set()

    for data in cursor.execute('SELECT DISTINCT(PROJECT_PHASE) FROM test WHERE PROJECT_PHASE is NOT NULL'):

        project_phases.add(data[0])
 
    return list(project_phases)
 
def get_labels(cursor, where=None):
 
    """ get all phases in the test  """
 
    labels = set()

    sql = '''SELECT DISTINCT(LABEL) FROM test WHERE '''

    sql_where = [f"( DEV_STATUS <> '{x}' )" for x in LABELS_DEV_STATUS_IGNORE]

    sql_where += ["( LABEL <> '' )"]
 
    if where is not None:

        sql_where += where
 
    sql += ' AND '.join(sql_where)
 
    for data in cursor.execute(sql):

        labels.add(data[0])
 
    return list(labels)
 
def add_tests_by_dev_status(cursor, row, where=None):
 
    """ add tests in the db by DEV_STATUS """
 
    sql = '''SELECT DEV_STATUS, COUNT(TEST_NAME), SUM(COALESCE(COUNT,1)) FROM test WHERE '''
 
    sql_where = [f"( DEV_STATUS <> '{x}' )" for x in LABELS_DEV_STATUS_IGNORE]
 
    if where is not None:

        sql_where += where
 
    sql += ' AND '.join(sql_where)
 
    sql += ' GROUP BY DEV_STATUS '
 
    row['tests'] = 0

    row['tests_full'] = 0

    for label in LABELS_DEV_STATUS:

        row[f'tests_{label}'] = 0

        row[f'tests_{label}_full'] = 0

    for data in cursor.execute(sql):

        label = data[0]

        if label in LABELS_DEV_STATUS:

            row[f'tests_{label}'] = data[1]

            row['tests'] += data[1]

            row[f'tests_{label}_full'] = data[2]

            row['tests_full'] += data[2]

        else:

            logging.error('%s not a good value for DEV_STATUS (%s)', data[0], ','.join(LABELS_DEV_STATUS_ALL))

            sys.exit(1)

    return row
 
 


def add_test_db(args):
 
    """ add a row in the test table  """
 
    if not "JENKINS_URL" in os.environ:

        return

    if not os.environ["JOB_NAME"][-4:] in ['_REG', '_reg']:

        return

    connection = connect()

    row = dict()

    row['url'] = os.getenv('GIT_URL', '')

    row['project'] = DUT_NAME

    row['commit'] = os.getenv('GIT_COMMIT', '')

    row['sync'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor = args.connection.cursor()

    list_hw_cfg = get_hw_cfg(args.cfg)

    if not list_hw_cfg:

        list_hw_cfg = [None]

    for hw_cfg in list_hw_cfg:

        where = list()

        row['hw_cfg'] = ''

        row['project_phase'] = ''

        row['label'] = ''

        if hw_cfg is not None:

            where.append(f''' ( HW_CFG like "%{hw_cfg}%" OR HW_CFG is NULL ) ''')

            row['hw_cfg'] = hw_cfg

        add_tests_by_dev_status(cursor, row, where)

        insert_row(connection, TEST_TABLE, row)

        for project_phase in get_project_phases(cursor):

            where_phase = where.copy()

            row['project_phase'] = project_phase

            where_phase.append(f''' ( PROJECT_PHASE='{project_phase}' ) ''')

            add_tests_by_dev_status(cursor, row, where_phase)

            insert_row(connection, TEST_TABLE, row)

        row['project_phase'] = ''

        for label in get_labels(cursor, where):

            where_label = where.copy()

            row['label'] = label

            where_label.append(f''' ( LABEL='{label}' ) ''')

            add_tests_by_dev_status(cursor, row, where_label)

            insert_row(connection, TEST_TABLE, row)

    connection.close()

    logging.info('insert test in the db')
 
def add_reg_db(args):
 
    """ add a row in the reg table and row(s) in the run table  """
 
    if not "JENKINS_URL" in os.environ:

        return

    if not os.environ["JOB_NAME"][-4:] in ['_REG', '_reg']:

        return

    connection = connect()

    row = dict()

    row['url'] = os.getenv('GIT_URL', '')

    row['project'] = DUT_NAME

    row['commit'] = os.getenv('GIT_COMMIT', '')

    row['build_url'] = os.getenv('BUILD_URL', '')

    row['hw_cfg'] = os.getenv('ACT_HW_CFG', '')

    row['start'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    row['dir'] = args.reg_dir

    reg_id = insert_row(connection, REG_TABLE, row)

    with open(os.path.join(args.reg_dir, '.db_reg.json'), 'w') as outfile:

        json.dump(reg_id, outfile, indent=4)

    cursor = args.connection.cursor()

    project_phase = dict()

    for data in cursor.execute('''SELECT TEST_NAME, PROJECT_PHASE FROM test WHERE PROJECT_PHASE <> '' '''):

        project_phase[data[0]] = data[1]
 
    label = dict()

    for data in cursor.execute('''SELECT TEST_NAME, LABEL FROM test WHERE LABEL <> '' '''):

        label[data[0]] = data[1]
 
    runs_id = dict()

    for run in cursor.execute('SELECT TEST_NAME, RUN_DIR FROM result'):

        row = dict()

        row['reg_id'] = reg_id

        row['test_name'] = run[0][0:150] #limit size due to DB restriction

        row['dir'] = os.path.basename(run[1])

        if run[0] in project_phase:

            row['project_phase'] = project_phase[run[0]]

        if run[0] in label:

            row['label'] = label[run[0]]

        run_id = insert_row(connection, RUN_TABLE, row)

        runs_id[run[1]] = run_id

    connection.close()

    with open(os.path.join(args.reg_dir, '.db.json'), 'w') as outfile:

        json.dump(runs_id, outfile, indent=4)

    logging.info('insert reg in the db with id=%d', reg_id)
 
def end_reg_db(args):
 
    """ update the date in the reg table  """
 
    if not "JENKINS_URL" in os.environ:

        return

    if not os.environ["JOB_NAME"][-4:] in ['_REG', '_reg']:

        return

    connection = connect()

    row = dict()

    if os.path.isfile(os.path.join(args.reg_dir, '.stop')):

        row['published'] = 'N'

    row['end'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(os.path.join(args.reg_dir, '.db_reg.json')) as infile:

        reg_id = json.load(infile)

    dir_size = file_to_str(os.path.join(args.reg_dir, 'build', '.dir_size'))

    if dir_size != '':

        row['build_size'] = dir_size

    update_row(connection, REG_TABLE, row, reg_id)

    connection.commit()
 
def sync_runs_db(args):
 
    """ force a synchronisation between local regression and the db  """
 
    cursor = args.connection.cursor()

    runs_dir = list()

    for row in cursor.execute('SELECT RUN_DIR FROM result').fetchall():

        runs_dir.append(row[0])
 
    update_runs_db(args, runs_dir)
 
def count_error_db(connection, run_id):
 
    cursor = connection.cursor()

    cursor.execute(f''' SELECT COUNT(*) FROM {ERROR_TABLE} WHERE run_id={run_id} ''')

    return cursor.fetchall()[0][0]
 
def insert_error_db(args, run_dir, connection, run_id):
 
    cursor = args.connection.cursor()

    row = dict()

    if not "ACT_DB_INSERT_ERROR" in os.environ:

        return

    if count_error_db(connection, run_id) > 0:

        return

    for error in cursor.execute(f'''SELECT MSG, MSG_TAG, FILE, INSTANCE, MSG_FULL FROM error WHERE RUN_DIR = '{run_dir}' ''').fetchall():

        row['run_id'] = run_id

        row['msg'] = error[0][0:1020] + ' ...'

        row['msg_tag'] = error[1]

        row['file'] = error[2]

        row['instance'] = error[3]

        row['msg_full'] = error[4]

        insert_row(connection, ERROR_TABLE, row)
 
def update_runs_db(args, runs_dir):
 
    """ update row in the run table  """
 
    if not "JENKINS_URL" in os.environ:

        return

    if not os.environ["JOB_NAME"][-4:] in ['_REG', '_reg']:

        return
 
    if not 'ACT_DB_UPDATE_RUN' in os.environ:

        return

    connection = connect()

    cursor = args.connection.cursor()

    with open(os.path.join(args.reg_dir, '.db.json')) as infile:

        runs_id = json.load(infile)

    for run_dir in runs_dir:

        row = dict()

        data = cursor.execute(f'''SELECT STATUS, ERROR_FIRST_MSG_FULL, DURATION, SEED, ERROR_COUNT, DONE FROM result WHERE RUN_DIR='{run_dir}' ''').fetchall()

        row['status'] = data[0][0]

        if data[0][1] is not None:

            row['first_error'] = data[0][1]

        if data[0][2] is not None and data[0][2] != '':

            row['duration'] = data[0][2]

        if data[0][3] is not None and data[0][3] != '':

            row['seed'] = data[0][3]

        row['errors'] = data[0][4]

        done = data[0][5]

        start = get_datetime_file(os.path.join(run_dir, '.start'))

        if start is not None:

            row['start'] = start

        end = get_datetime_file(os.path.join(run_dir, '.parsed'))

        if start is not None:

            row['end'] = end

        dir_size = file_to_str(os.path.join(run_dir, '.dir_size'))

        if dir_size != '':

            row['size'] = dir_size

        sim_time = file_to_str(os.path.join(run_dir, '.sim_time'))

        if sim_time != '':

            row['sim_time'] = sim_time

        if row['status'] == 'passed':

            row['status_report'] = 'passed'

        update_row(connection, RUN_TABLE, row, runs_id[run_dir])

        if done == 1:

            insert_error_db(args, run_dir, connection, runs_id[run_dir])

    connection.commit()
 
def add_metric_db(args, metric):
 
    """ add metric in the metric table  """
 
    if not "JENKINS_URL" in os.environ:

        return

    if not os.environ["JOB_NAME"][-4:] in ['_REG', '_reg']:

        return

    connection = connect()

    row = dict()

    with open(os.path.join(args.reg_dir, '.db_reg.json')) as infile:

        reg_id = json.load(infile)

    row['reg_id'] = reg_id

    for selection in metric:

        if selection == 'all':

            row['selection'] = ''

        else:

            row['selection'] = selection

        for name in metric[selection]:

            row['name'] = name

            row['value'] = metric[selection][name]

            insert_row(connection, METRIC_TABLE, row)

    connection.commit()

    logging.info('insert metric in the db')
 
def get_reg_id(args, add_dir):
 
    # Get id from current regression

    connection = connect()

    cursor = connection.cursor()

    cursor.execute(f"SELECT id FROM {REG_TABLE} WHERE dir = '{add_dir}'")

    row_id = cursor.fetchone()
 
    return row_id[0]

def update_reg_id_runs(args, add_id):

    with open(os.path.join(args.reg_dir, '.merge_runs'), 'a') as fd:

        print('add_id:', add_id)

        # Get current regression id

        reg_id = get_reg_id(args, args.reg_dir)

        fd.write(f"current regression id: {reg_id}\n")
 
        fd.write(f"regression to merge id: {add_id}\n")
 
        # Update run from other regression

        connection = connect()

        cursor = connection.cursor()

        cursor.execute(f"SELECT MIN(id), MAX(id), COUNT(id) FROM {RUN_TABLE} WHERE reg_id = {reg_id}")

        row_id = cursor.fetchone()

        print('current run stats (min/max/count): ', row_id)
 
        fd.write(f"currents regression id stats (min/max/count): {row_id}\n")
 
        cursor.execute(f"SELECT MIN(id), MAX(id), COUNT(id) FROM {RUN_TABLE} WHERE reg_id = {add_id}")

        row_id = cursor.fetchone()

        print('additional run stats (min/max/count): ', row_id)
 
        fd.write(f"regression to merge id stats (min/max/count): {row_id}\n")
 
        cursor.execute(f"UPDATE {RUN_TABLE} SET reg_id = {reg_id} WHERE reg_id = {add_id}")

        cursor.execute(f"UPDATE {REG_TABLE} SET published = 'N' WHERE id = {add_id}")
 
        cursor.execute(f"SELECT MIN(id), MAX(id), COUNT(id) FROM {RUN_TABLE} WHERE reg_id = {reg_id}")

        row_id = cursor.fetchone()

        print('merge run stats (min/max/count): ', row_id)

        fd.write(f"merged regression id stats (min/max/count): {row_id}\n")

        connection.commit()
 
 
