BUILD_DIR:=build
SCHEM_DIR:=../xschem
MAG_DIR:=../mag
RTL_DIR:=../verilog/rtl

.PHONY: all clean netlist cosim

all: netlist cosim
netlist: $(BUILD_DIR)/dac.spice $(BUILD_DIR)/buffer.spice $(BUILD_DIR)/dac.sim.spice $(BUILD_DIR)/buffer.sim.spice
cosim: $(BUILD_DIR)/lfsr.so

clean:
	rm -rf $(BUILD_DIR)

$(BUILD_DIR)/%.spice: $(SCHEM_DIR)/%.sch
	cd $(SCHEM_DIR) && xschem $(<F) --no_x --command 'set local_netlist_dir 0; set netlist_dir $(abspath $(BUILD_DIR)); set netlist_type spice; xschem netlist; exit'
	sed -i 's/\*\*\.subckt/\.subckt/g' $@
	sed -i 's/\*\*\.ends/\.ends/g' $@

$(BUILD_DIR)/%.sim.spice: $(MAG_DIR)/%.mag
	rm -f $(MAG_DIR)/$*.sim.spice
	PROJECT_NAME=$* $(MAKE) -C $(MAG_DIR) clean $*.sim.spice
	cp $(MAG_DIR)/$*.sim.spice $(BUILD_DIR)

$(BUILD_DIR)/lfsr.so: $(RTL_DIR)/lfsr.v
	cd $(BUILD_DIR) && ngspice vlnggen -- $(abspath $^) --x-initial 0 --x-assign 0
