PROJECT_NAME ?= tt_um_mbikovitsky_audio_player
MAGIC_RC := $(PDK_ROOT)/sky130A/libs.tech/magic/sky130A.magicrc
TEMPLATE_FILE := tt_analog_1x2.def
#TEMPLATE_FILE := tt_analog_1x2_3v3.def
BUILD_DIR := $(CURDIR)/build
SCHEM_DIR := $(CURDIR)/../xschem

.PHONY: lvs magic start

magic:
	magic -rcfile $(MAGIC_RC) $(PROJECT_NAME).mag

tt_analog_1x2.def:
	wget https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/tt10/def/analog/tt_analog_1x2.def

tt_analog_1x2_3v3.def:
	wget https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/tt10/def/analog/tt_analog_1x2_3v3.def

start: $(TEMPLATE_FILE)
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/tt-analog-draw.tcl $(TEMPLATE_FILE) $(PROJECT_NAME)

$(PROJECT_NAME).lvs.spice: $(PROJECT_NAME).mag
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/extract_for_lvs.tcl $(PROJECT_NAME)
	rm -f *.ext

antenna:
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/antenna.tcl $(PROJECT_NAME)
	rm -f *.ext

drc:
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/drc.tcl $(PROJECT_NAME)

$(PROJECT_NAME).sim.spice: $(PROJECT_NAME).mag
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/extract_for_sim.tcl $(PROJECT_NAME)
	rm -f *.ext

LVS_DEPENDS = \
	$(PROJECT_NAME).lvs.spice \
	$(BUILD_DIR)/dac.spice \
	$(BUILD_DIR)/buffer.spice \
	../src/project.v \
	../verilog/gl/digital_top.v

$(BUILD_DIR)/%.spice: $(SCHEM_DIR)/%.sch
	cd $(SCHEM_DIR) && xschem $(<F) --no_x --command 'set local_netlist_dir 0; set netlist_dir $(abspath $(BUILD_DIR)); set netlist_type spice; xschem netlist; exit'

lvs.report: $(LVS_DEPENDS)
	netgen -batch eval "set project $(PROJECT_NAME) ; source tcl/lvs_netgen.tcl"

lvs: lvs.report
	@propOk=1; match=0; port=1; \
    if grep -q "match uniquely" lvs.report; then \
        match=1; \
    fi; \
    if grep -q "Property errors were found" lvs.report; then \
        propOk=0; \
    fi; \
    if grep -q "failed pin matching" lvs.report; then \
        match=0; \
    fi; \
    if grep -q "Final result: Netlists do not match" lvs.report; then \
        match=0; \
    fi; \
    if grep -q "port errors" lvs.report; then \
        port=0; \
    fi; \
    if grep -q "Final result: Circuits match uniquely\." lvs.report; then \
        match=1; \
    fi; \
	if [ $$match -eq 1 ] && [ $$propOk -eq 1 ] && [ $$port -eq 1 ]; then \
        echo "LVS OK"; \
	    exit 0; \
    else \
        echo "LVS FAIL: match=$$match properties=$$propOk port=$$port"; \
	    exit 1; \
    fi

update_gds:
	mkdir -p ../gds ../lef
	magic -rcfile $(MAGIC_RC) -noconsole -dnull tcl/update_gds_lef.tcl $(PROJECT_NAME)

clean:
	rm -f lvs.report *.lvs.spice *.nodes *.sim.spice *.sim
	rm -rf $(BUILD_DIR)
