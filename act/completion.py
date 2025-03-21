"""
Module for tcsh completion
"""
 
import sqlite3
 
from act.test import get_tests
 
 
def arg_test_complete(prefix, parsed_args, **kwargs):
 
    """" completion for test """
 
    parsed_args.sql = 'SELECT * FROM test'
    if prefix != '':
        parsed_args.sql += ''' WHERE TEST_NAME like '{}%' '''.format(prefix)
    parsed_args.connection = sqlite3.connect(parsed_args.database)
    return get_tests(parsed_args)
 
def arg_field_complete(prefix, parsed_args, **kwargs):
 
    """" completion for field """
 
    parsed_args.connection = sqlite3.connect(parsed_args.database)
    cursor = parsed_args.connection.cursor()
    sql = "SELECT name FROM pragma_table_info('test')"
    if prefix != '':
        sql += ''' WHERE name like '{}%' '''.format(prefix)
    return (row[0] for row in cursor.execute(sql).fetchall())
 
def arg_value_complete(prefix, parsed_args, **kwargs):
 
    """" completion for value """
 
    parsed_args.connection = sqlite3.connect(parsed_args.database)
    cursor = parsed_args.connection.cursor()
    sql = "SELECT DISTINCT {field} FROM test WHERE {field} IS NOT NULL".format(field=parsed_args.field)
    if prefix != '':
        sql += ''' AND {f} like '{p}%' '''.format(p=prefix, f=parsed_args.field)
    return (row[0] for row in cursor.execute(sql).fetchall())
