#!/bin/csh -f

xrun \
    -xmlibdirname /home/shailesh/ATT/demo/sim/snapshots/rtl_debug/INCA64_rtl \
    -c \
    -zlib 6 \
    -uvm \
    -uvmhome CDNS-1.2 \
    -disable_sem2009 \
    -access +rwc \
    -timescale 1ns/1ps \
    -top act_tb_top \
    -f ${DV_TOP_DIR}/xrun.fof \
    -define IP_LEV \
    -l build.log

# end of script