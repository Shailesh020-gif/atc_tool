#!/bin/csh

#module load dv_eng/python/3.7.7

setenv DV_SIM_ROOT $PWD/sim

setenv DV_TOP_DIR $PWD

setenv DV_DUT_NAME demo

setenv DV_TB_NAME 'act_tb_top'

setenv ACT ${PWD}/../main.py

alias act ${ACT}

complete "act" 'p@*@`python-argcomplete-tcsh "$ACT"`@'
