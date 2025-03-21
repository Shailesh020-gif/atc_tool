"""
ACT common module
"""
 
import logging
import os
import os.path
import shlex
import shutil
import subprocess
import sys
import json
import gzip
from datetime import datetime
 
from termcolor import colored
 
BCOLORS = {
    "HEADER"    : '\033[95m',
    "BLUE"      : '\033[94m',
    "GREEN"     : '\033[92m',
    "WARNING"   : '\033[93m',
    "FAIL"      : '\033[91m',
    "ENDC"      : '\033[0m',
    "BOLD"      : '\033[1m',
    "UNDERLINE" : '\033[4m'
}
 
DISABLE_COLOR = False
 
def get_act_dir():
 
    """  get act directory """
 
    act_dir = __file__
    for _ in range(2):
        act_dir = os.path.dirname(act_dir)
    return act_dir
 
def status_color(status):
 
    """ colorize status string """
 
    if DISABLE_COLOR:
        return status
 
    if status == 'not_run':
        return colored(status, 'cyan')
    if status == 'running':
        return colored(status, 'yellow')
    if status == 'passed':
        return colored(status, 'green')
    if status == 'failed':
        return colored(status, 'red')
    if status == 'fatal':
        return colored(status, 'magenta')
    if status == 'timeout':
        return colored(status, 'magenta')
    if status == 'stopped':
        return colored(status, 'grey')
    if status == 'delayed':
        return colored(status, 'blue')
    if status == 'done':
        return colored(status, 'green')
    if status == 'rerun':
        return colored(status, 'blue')
    return status
 
def print_color(line, name_color):
 
    """ print a line with a color """
 
    if DISABLE_COLOR:
        print(line, flush=True)
    else:
        print(BCOLORS[name_color] + line + BCOLORS["ENDC"], flush=True)
 
def color(line, name_color):
 
    """ add color at a line """
 
    if DISABLE_COLOR:
        return line
    return BCOLORS[name_color] + line + BCOLORS["ENDC"]
 
def remove_if_exists(filename):
 
    """remove a file if exist """
 
    if os.path.exists(filename):
        os.remove(filename)
 
def str_to_file(file, string, append=False):
 
    """" string to a file """
 
    if append:
        fstring = open(file, 'a')
    else:
        fstring = open(file, 'w')
    fstring.write(string)
    fstring.close()
 
def file_to_str(file):
 
    """ file content to a string (only first line) """
 
    if not os.path.exists(file):
        return ''
    for line in open(file):
        return line
 
def get_datetime_file(file):
 
    """ get modified datetime of a file """
 
    if os.path.exists(file):
        return datetime.fromtimestamp(os.path.getmtime(file)).strftime('%Y-%m-%d %H:%M:%S')
    return None
 
def print_progress_bar(iteration, total, length=100):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        length      - Optional  : character length of bar (Int)
    """
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar_value = '█' * filled_length + '-' * (length - filled_length)
    print('\rProgress: |%s| %s%% Complete' % (bar_value, percent), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()
 
def check_setup():
 
    """
    Check the setup before run act
    """
 
    if not "DV_TOP_DIR" in os.environ:
        return
 
    if not os.path.isfile(os.path.join(os.environ['DV_TOP_DIR'], '.setup.md5')):
        return
 
    cmd = subprocess.Popen('/bin/find ./setup -type f -print0 |xargs  -0 md5sum | diff -q .setup.md5 - >& /dev/null', cwd=os.environ['DV_TOP_DIR'], shell=True)
 
    if cmd.wait():
        print("The setup was changed. Please source the setup :\ncd " + os.environ['DV_TOP_DIR'] + ";source setup/common/SourceMe.csh;cd -")
        sys.exit(1)
 
def get_size(start_path='.'):
 
    """ get size of directory """
 
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        total_size += os.lstat(dirpath).st_size
        for file in filenames:
            filep = os.path.join(dirpath, file)
            total_size += os.lstat(filep).st_size
    return total_size
 
def get_duration(seconds):
 
    seconds = abs(seconds)
 
    # convert seconds to day, hour, minutes and seconds
    day = seconds // (24 * 3600)
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
 
    duration = ''
 
    if day > 0:
        duration += f' {int(day)}d'
 
    if hour > 0:
        duration += f' {int(hour)}h'
 
    if minutes > 0:
        duration += f' {int(minutes)}m'
 
    if seconds > 0:
        duration += f' {int(seconds)}s'
 
    return duration
 
def get_lines_run(run_dir):
 
    with open(os.path.join(run_dir, 'test.json')) as infile:
        test = json.load(infile)
 
    logfile = os.path.join(run_dir, f'{test["TEST_NAME"]}.log')
    logfilez = os.path.join(run_dir, f'{test["TEST_NAME"]}.log.gz')
    if os.path.isfile(logfile):
        with open(logfile, 'rt') as flog:
            lines = flog.read().splitlines()
    elif os.path.isfile(logfilez):
        with gzip.open(logfilez, 'rt') as flog:
            lines = flog.read().splitlines()
 
    return lines
 
def getmtime(path):
 
    """ wrapper of os.path.getmtime - return 0 if the file not found  """
 
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return 0
