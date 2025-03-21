"""

Module for run

"""
 
import json

import logging

import os

import re

import shlex

import shutil

import stat

import subprocess

import sys

import time

from datetime import datetime
 
import psutil

from jinja2 import Environment, FileSystemLoader
 
from config import MAX_ERROR, MAX_LOG_SIZE, MAX_WARNING
 
from act.cfg import get_default_build, get_default_run

from act.common import color, get_size, print_color, remove_if_exists, str_to_file

from act.test import get_test, get_test_seed
 
MEBI = 1024*1024
 
 
def flatten_list(input_list):

    """Flatten a list
 
    :param input_list List to flatten

    :param list

    :return List flatten

    """

    flat_list = []

    for item in input_list:

        if type(item) == list:

            item = flatten_list(item)

            flat_list.extend(item)

        else:

            flat_list.append(item)

    return flat_list
 
 
def log_parser(logfile):
 
    """ Parse the log file """
 
    ferror = open('.error', 'a+')

    fwarning = open('.warning', 'a+')

    fseed = open('seed.info', 'w+')
 
    cerror = 0

    cwarning = 0
 
    duration = ""

    sim_time = ""
 
    if not os.path.exists(logfile):

        open(logfile, 'w').close()
 
    logging.debug('parse %s', logfile)
 
    re_seed = re.compile(r'SVSEED.+:\s*(-?\d+)\s*$')

    re_xrun_warn = re.compile(r'\S+: \*W,\S+')

    re_xrun_error = re.compile(r'\S+: \*E,\S+')

    re_xrun_fatal = re.compile(r'\S+: \*F,\S+')

    re_uvm_error = re.compile(r'^UVM_ERROR .*@')

    re_uvm_warning = re.compile(r'^UVM_WARNING .*@')

    re_uvm_fatal = re.compile(r'^UVM_FATAL .*@')

    re_test_end = re.compile(r'^--- UVM Report catcher Summary ---')

    re_xrun_duration = re.compile(r'xmsim: CPU Usage.+=\s*(\d+.?\d*)s\s*total')

    re_sim_time = re.compile(r'UVM_INFO.+@ (\d+)\.\d+ns: reporter \[UVM\/REPORT\/SERVER\]')

    re_max_quit_count = re.compile(r'Quit count :\s*(\d+)\s*of\s*(\d+)')
 
    logging.info('start to parse %s', logfile)
 
    log_size = int(os.stat(logfile).st_size / MEBI)

    if log_size > MAX_LOG_SIZE:

        logging.error("parsing stopped. Log file is too big (max=%dMiB)", MAX_LOG_SIZE)

        ferror.write(f"UVM_FATAL @ 0: [LOG_TOO_BIG] log size is {log_size}MiB (max={MAX_LOG_SIZE}MiB) => not parsed\n")

        ferror.close()

        return
 
    for buffer in open(logfile, 'rb'):

        line = buffer.decode("utf-8", "replace")

        m_seed = re_seed.search(line)

        if m_seed:

            fseed.write(m_seed.group(1))

            continue

        if cwarning < MAX_WARNING and re_xrun_warn.search(line):

            fwarning.write(line)

            cwarning += 1

            continue

        if cerror < MAX_ERROR and re_xrun_error.search(line):

            ferror.write(line)

            cerror += 1

            continue

        if cerror < MAX_ERROR and re_xrun_fatal.search(line):

            ferror.write(line)

            cerror += 1

            continue

        if cerror < MAX_ERROR and re_uvm_error.search(line):

            ferror.write(line)

            cerror += 1

            continue

        if cerror < MAX_ERROR and re_uvm_fatal.search(line):

            ferror.write(line)

            cerror += 1

            continue

        if cwarning < MAX_WARNING and re_uvm_warning.search(line):

            fwarning.write(line)

            cwarning += 1

            continue

        if re_test_end.search(line):

            open('.complete', 'w').close()

            continue

        m_max_quit_count = re_max_quit_count.search(line)

        if m_max_quit_count:

            quit_error_count = int(m_max_quit_count.group(1))

            max_error_count = int(m_max_quit_count.group(2))

            if quit_error_count >= max_error_count:

                ferror.write(f'UVM_ERROR @ 0: [MAX_QUIT_COUNT] {quit_error_count}\n')

                cerror += 1

            continue
 
        m_duration = re_xrun_duration.search(line)

        if m_duration:

            duration = m_duration.group(1)

            continue
 
        m_sim_time = re_sim_time.search(line)

        if m_sim_time:

            sim_time = m_sim_time.group(1)

            continue
 
        if cerror == MAX_ERROR:

            logging.warning("stop to capture errors (max=%d)", MAX_ERROR)

            cerror += 1
 
        if cwarning == MAX_WARNING:

            logging.warning("stop to capture warnings (max=%d)", MAX_WARNING)

            cwarning += 1
 
    logging.info('end to parse %s', logfile)
 
    str_to_file('.duration', duration)

    str_to_file('.sim_time', sim_time)
 
    ferror.close()

    fwarning.close()

    fseed.close()
 
def check_error(max_warnings=-1):
 
    """ Count errors and warnings of the run """
 
    cwd = os.getcwd()
 
    result = {

        'errors'       : 0,

        'warnings'     : 0,

        'first_error'  : '',

        'max_warnings' : max_warnings,

        'status'       : 'PASSED',

        'dir'          : cwd,

    }
 
    for line in open('.error'):

        if result['errors'] == 0:

            result['first_error'] = line

        result['errors'] += 1
 
    if result['errors'] > 0:

        print("\n[FIRST_ERROR]:", flush=True)

        print_color(result['first_error'], 'FAIL')

        print(f"\n[ERROR] {result['errors']} error(s) detected", flush=True)

        print(f"Read {cwd}/.error\n", flush=True)
 
    for line in open('.warning'):

        result['warnings'] += 1
 
    if 0 <= max_warnings < result['warnings']:

        print(f"\n[ERROR] {result['warnings']} warnings detected ({max_warnings} warnings maximum are authorized)", flush=True)

        print("Read " + cwd + "/.warning\n", flush=True)

        result['errors'] += 1

    elif result['warnings'] > 0:

        print(f"[WARNING] {result['warnings']} warning(s) detected", flush=True)

        print(f"Read {cwd}/.warning\n", flush=True)
 
    if result['errors'] > 0:

        result['status'] = 'FAILED'
 
    return result['errors']
 
 


def check_run(logfile, build_enable, error_message, max_warnings=-1):
 
    """ Check the status of the run """
 
    remove_if_exists('.error')

    remove_if_exists('.warning')

    remove_if_exists('.complete')
 
    log_parser(logfile)
 
    ferror = open('.error', 'a')
 
    if error_message:

        ferror.write(f"UVM_FATAL @ 0: {error_message}\n")
 
    if not build_enable and not os.path.exists('.complete'):

        ferror.write("UVM_FATAL @ 0: [NOT_COMPLETED] execution not completed\n")
 
    ferror.close()
 
    print("\nResult:", flush=True)
 
    if check_error(max_warnings) == 0:

        print_passed()

        remove_if_exists('.error')

        open('.parsed', 'w').close()

        return True
 
    print_failed()

    open('.parsed', 'w').close()

    return False
 
def print_passed():
 
    """" Print the passed message """
 
    print('\n', flush=True)

    print_color('######     #     #####   #####  ####### ######', 'GREEN')

    print_color('#     #   # #   #     # #     # #       #     #', 'GREEN')

    print_color('#     #  #   #  #       #       #       #     #', 'GREEN')

    print_color('######  #     #  #####   #####  #####   #     #', 'GREEN')

    print_color('#       #######       #       # #       #     #', 'GREEN')

    print_color('#       #     # #     # #     # #       #     #', 'GREEN')

    print_color('#       #     #  #####   #####  ####### ######', 'GREEN')

    print('\n', flush=True)
 
def print_failed():
 
    """" Print the failed message """
 
    print('\n', flush=True)

    print_color('#######    #    ### #       ####### ######', 'FAIL')

    print_color('#         # #    #  #       #       #     #', 'FAIL')

    print_color('#        #   #   #  #       #       #     #', 'FAIL')

    print_color('#####   #     #  #  #       #####   #     #', 'FAIL')

    print_color('#       #######  #  #       #       #     #', 'FAIL')

    print_color('#       #     #  #  #       #       #     #', 'FAIL')

    print_color('#       #     # ### ####### ####### ######', 'FAIL')

    print('\n', flush=True)
 
def j2toscript(param, build, run, test, tfile):
 
    """ Generate script from Jinja2 template"""
 
    if not os.path.isfile(tfile):

        tfile = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', tfile)

    logging.debug("Jinja2 script : %s", tfile)

    file_loader = FileSystemLoader(os.path.dirname(tfile))

    env = Environment(loader=file_loader)

    template = env.get_template(os.path.basename(tfile))

    output = template.render(param=param, build=build, run=run, test=test)
 
    # write the script in the current directory

    script = os.path.splitext(os.path.basename(tfile))[0]

    fscript = open(script, 'w')

    fscript.write(output)

    fscript.close()

    stat_script = os.stat(script)

    os.chmod(script, stat_script.st_mode | stat.S_IEXEC)

    return script
 
def test_2_cmd(test, args):
 
    """" Generate command parameters from test fields """
 
    cmd = list()

    fields = set(test.keys())

    test_over = dict()

    if args.field_value:

        for line in [x.split('=') for x in args.field_value]:

            test_over[line[0]] = line[1]

            fields.add(line[0])

    logging.info("test fields:")

    for field in sorted(fields):

        if field in test:

            if field in test_over:

                value = test_over[field]

                print_color(f'{field} = {test[field]} -> {value}', 'WARNING')

            else:

                value = test[field]

                print(f'{field} = {value}', flush=True)

        else:

            value = test_over[field]

            print_color(f'{field} = {value}', 'GREEN')

        field_bool = False

        name = field

        if name.upper() in ['TL_FILE', 'TEST_NAME', 'N', 'SEED', 'UVM_VERBOSITY', 'COUNT']:

            continue

        m_bool = re.search(r'^(.+)_BOOL$', name)

        if m_bool:

            name = m_bool.group(1)

            field_bool = value == 'TRUE'

            if not field_bool:

                continue

        # convert field with a bracket in the name

        m_bracket = re.search(r'^(.+)_B_(\d+)_B(.*)$', name)

        if m_bracket:

            name = '{}[{}]{}'.format(m_bracket.group(1), m_bracket.group(2), m_bracket.group(3))

        m_lower = re.search(r'^(.+)_LC$', name)

        if m_lower:

            name = m_lower.group(1).lower()

        if field_bool:

            cmd.append('+{}'.format(name))

        else:

            cmd.append('+{}="{}"'.format(name, value))

    cmd_line = ' \\\n    '.join(cmd)

    logging.debug("test paramaters:\n%s", cmd_line)

    return cmd_line
 
 
def copy_files(files):
 
    """ Copy files in the buid directory """
 
    files = flatten_list(files)
 
    logging.info("copy %d file(s) in the build directory", len(files))
 
 
    for node in files:

        node = os.path.expandvars(node)

        print(node)

        shutil.copyfile(node, os.path.basename(node))
 
 
def link_files(files, source_dir=None, dest_dir='.'):

    """ link files in the run directory """
 
    files = flatten_list(files)

    logging.info("create %d symbolic link(s) in the run directory ", len(files))
 
    

    for node in files:

        node = os.path.expandvars(node)

        if not source_dir:

            source_dir = os.path.dirname(node)
 
        basename = os.path.basename(node)

        if os.path.isfile(os.path.join(dest_dir, basename)):

            os.remove(os.path.join(dest_dir, basename))

            logging.debug("remove %s", os.path.join(dest_dir, basename))

        os.symlink(os.path.join(source_dir, basename), os.path.join(dest_dir, basename))

        logging.debug("create symbolic link %s from %s", basename, dest_dir)
 
 
def launch_pre_build(args, build):
 
    """" launch the pre build only """
 
    os.makedirs(args.build_dir, exist_ok=True)

    os.chdir(args.build_dir)
 
    logging.info("build directory is %s", args.build_dir)
 
    logging.info("start of pre_build")
 
    if args.dry_run:

        logging.info("[DRY_RUN] no execution of %s", build['pre_build'])

        return
 
    if args.no_pre_build:

        logging.info("[NO_PRE_BUILD] no execution of %s", build['pre_build'])

        return
 
    if isinstance(build['pre_build'], str):

        pre_builds = [build['pre_build']]

    else:

        pre_builds = build['pre_build']
 
    for pre_build in pre_builds:
 
        cmd = shlex.split(pre_build)
 
        for pre_build_args in args.pre_build_args:

            cmd += shlex.split(pre_build_args)
 
        process = subprocess.Popen(cmd)
 
        logging.info("start to execute : %s", ' '.join(cmd))
 
        if process.wait():

            logging.error("problem during execution of %s", ' '.join(cmd))

            sys.exit(1)

        else:

            logging.info("end to execute : %s", ' '.join(cmd))
 
    open('.pre_build_complete', 'w').close()

    logging.info("end of pre_build")

    logging.info("build directory is %s", args.build_dir)
 
def launch_build(args, build, run):
 
    """" launch the build only """
 
    param = vars(args)
 
    os.makedirs(args.build_dir, exist_ok=True)

    os.chdir(args.build_dir)
 
    str_to_file('.start', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
 
    param['log_file'] = "build.log"
 
    if args.build_args:

        build['args'] = ''.join(args.build_args)
 
    if args.add_build_args:

        if build['args'] is None:

            build['args'] = ''

        build['args'] += ''.join(args.add_build_args)
 
    if 'copy_files' in build:

        copy_files(build['copy_files'])

    if 'link_files' in build:

        link_files(build['link_files'], dest_dir=args.build_dir)
 
    logging.debug("generate script")

    test = dict()

    script = j2toscript(param, build, run, test, build['script'])
 
    logging.info("build directory is %s", args.build_dir)
 
    if args.dry_run:

        logging.info("[DRY_RUN] no execution of %s", script)

        return
 
    logging.info("start to execute : %s", script)
 
    error_message = ''

    proc = subprocess.Popen(f'./{script}')
 
    try:

        proc.communicate()

    except KeyboardInterrupt:

        error_message = '[STOPPED] compilation stopped by the user'
 
    proc.wait()
 
    str_to_file('.end', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
 
    if proc.returncode != 0 and not error_message:

        error_message = f'[BAD_STATUS] simulation exit with status = {proc.returncode}'

    else:

        logging.info("end to execute : %s", script)
 
    logging.info("build directory is %s", args.build_dir)
 
    if not 'max_warnings' in build:

        build['max_warnings'] = -1
 
    result = check_run(param['log_file'], True, error_message, build['max_warnings'])
 
    str_to_file('.dir_size', str(get_size()))
 
    if result:

        open('.build_complete', 'w').close()

    else:

        sys.exit(1)
 
 


def kill_tree(pid):

    for child in psutil.Process(pid).children(recursive=True):

        logging.warning('terminate %s(%d)', child.name(), child.pid)

        child.terminate()

    wait_kill = 120

    while wait_kill > 0:

        if len(psutil.Process(pid).children(recursive=True)) == 0:

            logging.warning('terminate done')

            return

        wait_kill -= 1

        time.sleep(1)

    for child in psutil.Process(pid).children(recursive=True):

        logging.warning('kill %s(%d)', child.name(), child.pid)

        child.kill()
 
def launch_run(args, build, build_base, run):
 
    """" launch the run only """
 
    test = dict()

    param = vars(args)
 
    if args.run_dir is None:

        args.run_dir = run['runs_dir']
 
        if build_base is not None:

            args.run_dir = os.path.join(args.run_dir, build_base)
 
        args.run_dir = os.path.join(args.run_dir, f'{args.run_name}_{args.test}')
 
    if args.clean_run:

        logging.info("remove run directory : %s", args.run_dir)

        os.environ["ACT_RUN_CLEAN"] = 'clean'

        shutil.rmtree(args.run_dir, ignore_errors=True)
 
    os.makedirs(args.run_dir, exist_ok=True)
 
    act_dir = os.path.join(args.run_dir, '.act')

    os.makedirs(act_dir, exist_ok=True)

    stat_dir = os.stat(act_dir)

    os.chmod(act_dir, stat_dir.st_mode | stat.S_IWGRP)
 
    test = get_test(args, args.test)
 
    if not test:

        logging.error("the test %s not exist", args.test)

        sys.exit(1)
 
    param['seed'] = args.seed
 
    if args.run_args:

        run['args'] = ''.join(args.run_args)
 
    if args.add_run_args:

        if not 'args' in run:

            run['args'] = ''

        if run['args'] is None:

            run['args'] = ''

        run['args'] += ''.join(args.add_run_args)
 
    param['test_cmd'] = test_2_cmd(test, args)
 
    #  go to run directory

    os.chdir(args.run_dir)
 
    with open('test.json', 'w') as outfile:

        json.dump(test, outfile, indent=4)
 
    files_to_link = []

    if 'copy_files' in build:

        files_to_link.extend(build['copy_files'])

    if 'link_files' in build:

        files_to_link.extend(build['link_files'])
 
    link_files(files_to_link, source_dir=args.build_dir)
 
    param['log_file'] = '{}.log'.format(args.test)
 
    if 'pre_run' in run:

        logging.info("pre_run : execute %s", run['pre_run'])

        exec_status = os.system(run['pre_run'])

        if exec_status >> 8 == 120:

            logging.warning("The test must be delayed")

            str_to_file('.delayed', '')

            sys.exit(0)

        if exec_status:

            logging.error("problem during execution of pre_run")

            ferror = open('.error', 'a+')

            ferror.write("UVM_FATAL @ 0: [PRE_RUN] problem during execution of pre_run\n")

            ferror.close()

            open('.parsed', 'w').close()

            sys.exit(1)

        if os.path.isfile('.delayed'):

            os.remove('.delayed')
 
    logging.debug("generate script from %s", run['script'])

    script = j2toscript(param, build, run, test, run['script'])
 
    logging.info("test %s will be executed in %s", args.test, args.run_dir)
 
    if args.dry_run:

        logging.info("[DRY_RUN] no execution of %s", script)

        return
 
    logging.info("start to execute %s", script)
 
    if os.path.exists(".start_sim"):

        os.remove(".start_sim")
 
    if "ACT_RUN_DISABLE_TIMEOUT" in os.environ:

        logging.warning('the variable ACT_RUN_DISABLE_TIMEOUT is defined => timeout disable')

        args.timeout = 0
 
    error_message = ''

    proc = subprocess.Popen(f'./{script}')
 
    if args.timeout == 0:

        run_timeout = None

    else:

        run_timeout = args.timeout
 
    if os.path.exists(".act/kill"):

        os.remove(".act/kill")
 
    counter = 0

    status = {

        'xmsim' : ''

    }

    while proc.poll() is None:

        try:

            if (run_timeout is not None) and (counter > run_timeout):

                kill_tree(proc.pid)

                error_message = f'[TIMEOUT] simulation killed after {run_timeout} seconds'

            if os.path.exists(".act/kill"):

                kill_tree(proc.pid)

                error_message = f'[KILLED] simulation killed by the user'

            for child in psutil.Process(proc.pid).children(recursive=True):

                if child.name() in status:

                    if child.status() != status['xmsim']:

                        logging.debug('new status for %s(%d) =>  %s', child.name(), child.pid, child.status())

                        status['xmsim'] = child.status()

            time.sleep(1)

            counter += 1

        except KeyboardInterrupt:

            logging.warning('simulation interrupt')

        except psutil.NoSuchProcess:

            pass
 
    if proc.returncode != 0 and not error_message:

        error_message = f'[BAD_STATUS] simulation exit with status = {proc.returncode}'

    else:

        logging.info("end to execute %s", script)
 
    if 'post_run' in run:

        logging.info("post_run : execute %s", run['post_run'])

        exec_status = os.system(run['post_run'])

        if exec_status:

            logging.warning("problem during execution of post_run")
 
    if 'table_script' in run:

        for table_script in run['table_script']:

            logging.info("table_script : execute %s", table_script)

            table = os.path.splitext(os.path.basename(table_script))[0]

            os.makedirs('table', exist_ok=True)

            cmd = [table_script, args.run_dir]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout

            str_to_file(os.path.join('table', f'{table}.json'), result)
 
    run_ok = check_run(param['log_file'], False, error_message)
 
    seed = ''

    for line in open('seed.info'):

        seed = line.rstrip()
 
    logging.info("build directory is %s", args.build_dir)
 
    logging.info("test %s with seed %s was executed in %s", color(args.test, 'BOLD'), color(seed, 'BOLD'), args.run_dir)
 
    if not run_ok:

        sys.exit(1)
 
def main_run(args):
 
    """ Main of run """
 
    os.environ["ACT_RUN_CLEAN"] = ''

    os.environ["ACT_BUILD_CLEAN"] = ''
 
    if args.run_name is None:

        args.run_name = get_default_run(args.cfg)
 
    run = dict()

    for i, run_cfg in enumerate(args.cfg['run']):

        if run_cfg['name'] == args.run_name:

            run = args.cfg['run'][i]
 
    if args.build_name is None:

        if 'build_name' in run:

            args.build_name = run['build_name']

        else:

            args.build_name = get_default_build(args.cfg)
 
    build = dict()

    for i, build_cfg in enumerate(args.cfg['build']):

        if build_cfg['name'] == args.build_name:

            build = args.cfg['build'][i]
 
    build_base = None
 
    # manage build dir

    if args.build_dir is None:
 
        build_base = args.build_name
 
        if args.fast:

            build_base += '_fast'

        else:

            build_base += '_debug'
 
        if args.timing:

            build_base += f'_{args.timing}'
 
        args.build_dir = os.path.join(build['builds_dir'], build_base)
 
    if args.clean:

        args.clean_build = True

        args.clean_run = True
 
    if args.clean_build:

        logging.info("remove build directory : %s", args.build_dir)

        os.environ["ACT_BUILD_CLEAN"] = 'clean'

        shutil.rmtree(args.build_dir, ignore_errors=True)
 
    build_complete = os.path.join(args.build_dir, '.build_complete')
 
    if 'pre_build' in build:

        pre_build_complete = os.path.join(args.build_dir, '.pre_build_complete')
 
        if args.pre_build:

            remove_if_exists(pre_build_complete)

            remove_if_exists(build_complete)
 
        if args.no_pre_build:

            logging.info("pre_build bypass")

        else:

            if os.path.isfile(pre_build_complete):

                logging.info("pre_build done")

            else:

                launch_pre_build(args, build)
 
    if args.build:

        remove_if_exists(build_complete)
 
    if os.path.isfile(build_complete):

        logging.info("build directory : %s", args.build_dir)

    else:

        if args.build or args.test:

            launch_build(args, build, run)
 
    if args.test and os.path.isfile(build_complete):

        launch_run(args, build, build_base, run)
 
