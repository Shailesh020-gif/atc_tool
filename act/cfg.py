
import glob
import logging
import os
import re
import sys

import yaml
from collections.abc import Sequence

from act.common import get_act_dir

PATH_MATCHER = re.compile(r'.*\$\{([^}^{]+)\}.*')


def path_constructor(loader, node):
    return os.path.expandvars(node.value)
 
 
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ' '.join([str(i) for i in seq])
 
 
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
 
 
def concat(loader, node):
 
    concat_list = []
    if isinstance(node.value, list):
        for node_element in node.value:
            if isinstance(node_element, yaml.SequenceNode):
                concat_list.extend(loader.construct_sequence(node_element, deep=True))
            elif isinstance(node_element, yaml.ScalarNode):
                concat_list.append(loader.construct_scalar(node_element))
 
    compute_node = flatten_list(concat_list)
    return compute_node
 
 
yaml.Loader.add_implicit_resolver('!path', PATH_MATCHER, None)
yaml.Loader.add_constructor('!path', path_constructor)
yaml.Loader.add_constructor('!join', join)
yaml.Loader.add_constructor('!concat', concat)
 
 
def load_cfg():
    """Load configuration from yaml file
 
    Function will load yaml file given in environment variable ACT_CFG
    or by default act.yaml file in current directory
 
    :return: dict which contain configuration
    """
 
    yfile = os.getenv('ACT_CFG', 'act.yaml')
    if not os.path.isfile(yfile):
        logging.error("ACT configuration file does not exist")
        sys.exit(1)
    cfg = dict()
    logging.debug('load Configuration from %s', os.path.abspath(yfile))
    with open(yfile) as fyaml:
        cfg = yaml.load(fyaml, Loader=yaml.Loader)
    return cfg
 
 
def get_build_names(cfg):
    """Get list of build names.
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return list of build names
    """
 
    names = list()
    for build in cfg['build']:
        names.append(build['name'])
    return names
 
 
def get_default_build(cfg):
    """Get default build
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return default build name
    """
 
    return cfg['build'][0]['name']
 
 
def get_default_pre_build(cfg):
    """Get default pre build
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return default pre_build name or None
    """
 
    if 'pre_build' in cfg:
        return cfg['pre_build'][0]['name']
    return None
 
 
def get_run_names(cfg):
    """Get list of run names
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return list of run names
    """
    names = list()
    for run in cfg['run']:
        names.append(run['name'])
    return names
 
 
def get_default_run(cfg):
    """Get default run
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return default run name or None
    """
 
    return cfg['run'][0]['name']

def get_reg_names(cfg):
    """Get list of reg names
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return list of reg conf names
    """
    names = list()
    for reg in cfg['reg']:
        names.append(reg['name'])
    return names
 
 
def get_default_reg(cfg):
    """Get default reg
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return default reg conf name or None
    """
    return cfg['reg'][0]['name']
 
 
def get_test_queries():
 
    """ get list of queries for tests """
 
    sql_dir = os.path.join(get_act_dir(), 'sql')
    return [os.path.splitext(os.path.basename(x))[0] for x in glob.glob('{}/*.sql'.format(sql_dir))]
 
 
def get_hw_cfg(cfg):
    """Get list of hw_cfg
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return list of hw cfg names
    """
    if 'hw_cfg' not in cfg:
        return list()
    return cfg['hw_cfg']
 
 
def get_default_hw_cfg(cfg):
    """Get default hw_cfg
 
    :param cfg: act configuration
    :type cfg: dict
    :returns: Return default hw cfg name or None
    """
    if 'hw_cfg' not in cfg:
        return ''
    return cfg['hw_cfg'][0]
