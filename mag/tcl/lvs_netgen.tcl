set layout [readnet spice $project.lvs.spice]
set source [readnet spice /dev/null]
readnet spice $::env(PDK_ROOT)/$::env(PDK)/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice $source

# Top level GL verilog
readnet verilog ../src/project.v $source

# GL verilog of the top digital block
readnet verilog ../verilog/gl/digital_top.v $source

# Analog blocks:
readnet spice ./build/dac.spice $source
readnet spice ./build/buffer.spice $source

lvs "$layout $project" "$source $project" $::env(PDK_ROOT)/sky130A/libs.tech/netgen/sky130A_setup.tcl lvs.report -blackbox
