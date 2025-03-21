#!/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
ACT Verification Automation
"""

import argparse
import logging
import os
import sqlite3
import sys
 
import argcomplete
import coloredlogs

import act.common

from act.run import main_run
from act.test import create_table, main_test

from act.cfg import (get_build_names, get_default_hw_cfg, get_hw_cfg, get_reg_names, get_run_names, get_test_queries, load_cfg)

from act.completion import (arg_field_complete, arg_test_complete, arg_value_complete)
def main(cfg):

    # creat the top-level parser
    parser = argparse.ArgumentParser(prog='ACT Verification Automation')
    parser.add_argument("-nolog", help="disable logging", action="store_true")
    parser.add_argument("-log", help="change level of logging", default='DEBUG', choices=['DEBUG','INFO'])
    
    # Fix: Do NOT overwrite `parser`, just call `add_argument`
    parser.add_argument(
        "-database",
        help="sqlite file for tests database",
        default=os.path.join(os.path.dirname(os.getenv('ACT_CFG', '')), 'test.sqlite')
    )
    # Create subparsers properly
    subparsers = parser.add_subparsers(dest="command")  # Set a dest for better parsing
    
    parser_test = subparsers.add_parser('test', help='create and explore the test database')
    parser_test.add_argument("-sync", "-s", help="synchronize test database", action="store_true")
    parser_test.add_argument("-sync_target", help="synchronize test database with a target", metavar='<string>')
    parser_test.add_argument("-source", "-so", help="select the source of tests and synchronize test database", action='append', metavar='<file>')
    parser_test.add_argument("-seed", help="specify a seed to randomize perl variable in a TL file", metavar='<seed>')
    parser_test.add_argument("-tests", help="get tests list", action="store_true")
    parser_test.add_argument("-field", help="filter by field", metavar='<string>').completer = arg_field_complete
    parser_test.add_argument("-value", help="filter by a value", metavar='<value>').completer = arg_value_complete
    parser_test.add_argument("-fields", help="get fields list", action="store_true")
    parser_test.add_argument("-values", help="get all values of a field", action="store_true")
    parser_test.add_argument("-print", help="print table", action="store_true")
    parser_test.add_argument("-write", help="write tests in csv,xlsx,json,list", metavar='<file>')
    parser_test.add_argument("-query", help="choose a query to execute", choices=get_test_queries(), metavar='<string>')
    parser_test.add_argument("-sql", help="write a SQL request to execute", metavar='<sql>')
    parser_test.add_argument("-sql_file", help="file containts a SQL request to execute", metavar='<file.sql>')
    parser_test.add_argument("-test", help="choose a test", action='append', metavar='<string>').completer = arg_test_complete
    parser_test.add_argument("-test_filter", help="filter test by a string", metavar='<string>')
    parser_test.add_argument("-summary", help="Print summary of test by label", action='store_true')
    parser_test.add_argument("-by_label", help="filter summary by label, to be use with -summary option", nargs='+', metavar='<label>')
    parser_test.add_argument("-by_status", help="filter summary by status, to be use with -summary option", nargs='+', 
        choices=['TODO', 'ONGOING', 'NOTPLANNED', 'DONE'])

    parser_run = subparsers.add_parser('run', help='compile and simulate')
    parser_run.add_argument("-test", "-t", help="choose a test", metavar='<string>').completer = arg_test_complete
    parser_run.add_argument("-run_name", help="choose a run profile", choices=get_run_names(cfg), metavar='<string>')
    parser_run.add_argument("-run_dir", help="choose run directory", metavar='<path>')
    parser_run.add_argument("-build", help="force build before to run (compile and elaborate)", action="store_true")
    parser_run.add_argument("-build_dir", help="choose a build directory", metavar='<path>')
    parser_run.add_argument("-build_name", help="choose a build profile", choices=get_build_names(cfg))
    parser_run.add_argument("-pre_build", help="force pre build before to build", action="store_true")
    parser_run.add_argument("-no_pre_build", help="bypass prebuild", action="store_true")
    parser_run.add_argument("-pre_build_args", help="add arguments to pre_build script", action='append', metavar='<args>', default=list())
    parser_run.add_argument("-seed", help="choose a seed (default: 1)", metavar='<seed>', default='1')
    parser_run.add_argument("-fast", help="build with fast options", action="store_true")
    parser_run.add_argument("-gui", help="launch in gui mode", action="store_true")
    parser_run.add_argument("-clean", help="clean all, build and run directories", action="store_true")
    parser_run.add_argument("-clean_run", help="clean run directory before to run", action="store_true")
    parser_run.add_argument("-clean_build", help="clean build directory before to compile", action="store_true")
    parser_run.add_argument("-timeout_sim", help="simulation timeout in ns (default: disable)", default=0, metavar='<time_ns>')
    parser_run.add_argument("-timeout", help="add run timeout in seconds", type=int, metavar='<time_s>')
    parser_run.add_argument("-top", help="choose the top to elaborate", metavar='<string>')
    parser_run.add_argument("-timing", help="enable timing simulation", choices=['min', 'max'])
    parser_run.add_argument("-waves", help="generate waves", action="store_true")
    parser_run.add_argument("-dry_run", help="not execute", action="store_true")
    parser_run.add_argument("-field_value", "-fv", help="overwrite a field", action='append', metavar='<field=value>')
    parser_run.add_argument("-run_args", help="arguments to run script (overwrite run_args)", action='append', metavar='<args>')
    parser_run.add_argument("-add_run_args", help="add arguments to run script (append run_args)", action='append', metavar='<args>')
    parser_run.add_argument("-build_args", help="arguments to build script (overwrite build_args)", action='append', metavar='<args>')
    parser_run.add_argument("-add_build_args", help="add arguments to build script (append build_args)", action='append', metavar='<args>')
    parser_run.add_argument("-nostdout", help="disable stdout", action="store_true")
    parser_run.add_argument("-verbosity", help="choose the UVM verbosity", choices=['UVM_DEBUG', 'UVM_FULL', 'UVM_HIGH', 'UVM_MEDIUM', 'UVM_LOW', 'UVM_NONE'])
    parser_run.add_argument("-max_quit_count", help="choose the UVM_MAX_QUIT_COUNT", type=int, metavar='<integer>')


    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    
    logger = logging.getLogger()
 
    if args.nolog:
        logger.disabled = True
 
    #if args.log_file:
    #    logger.addHandler(logging.FileHandler(args.log_file))
 
    #if args.no_color:
    #    act.common.DISABLE_COLOR = True
 
    #coloredlogs.install(level=args.log, fmt='-- %(levelname)s -- ACT -- %(message)s')
 
    logging.debug("test database : %s", args.database)
 
    enable_create = not os.path.isfile(args.database)
    args.connection = sqlite3.connect(args.database)
    if enable_create:
        create_table(args)
 
    args.cfg = cfg
 
    if args.command == 'test':
        main_test(args)
 
    elif args.command == 'run':
        main_run(args)
 
    #elif args.command == 'reg':
 
    #    if args.run_local:
    #        args.run = True
    #        args.run_mode = 'local'
 
    #    if args.jobs is None:
    #        args.jobs = DEFAULT_LSF_JOBS
    #        if args.run_mode == 'local':
    #            args.jobs = 1
 
    #    main_reg(args)
 
    args.connection.close()

if __name__ == '__main__':
    main(load_cfg())
