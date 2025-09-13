SIM ?= icarus
TOPLEVEL_LANG = verilog

MODULE_TO_TEST ?= digital_top

ifeq ($(GATES),1)
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v
VERILOG_SOURCES += $(CURDIR)/$(MODULE_TO_TEST)_gl_tb.v
VERILOG_SOURCES += $(CURDIR)/../gl/$(MODULE_TO_TEST).v
COMPILE_ARGS += -DFUNCTIONAL
COMPILE_ARGS += -DUSE_POWER_PINS
COMPILE_ARGS += -DUNIT_DELAY=\#1
TOPLEVEL := tb
else
VERILOG_SOURCES = $(CURDIR)/generated/$(MODULE_TO_TEST).v
# VERILOG_SOURCES may be updated by the included makefiles,
# so make sure to expand it now while we still know what it contains.
TOPLEVEL := $(basename $(notdir $(VERILOG_SOURCES)))
endif

MODULE = test_$(MODULE_TO_TEST)

# Wave generation
ifeq ($(SIM),icarus)
WAVES = 1
else ifeq ($(SIM),verilator)
EXTRA_ARGS += --trace --trace-fst --trace-structs
# This flag is only documented in the changelog...
# https://github.com/cocotb/cocotb/blob/master/docs/source/release_notes.rst#cocotb-190-2024-07-14
SIM_ARGS += --trace-file "$(SIM_BUILD)/$(TOPLEVEL).fst"
endif

ifeq ($(SIM),verilator)
# This will be passed to Verilator
COMPILE_ARGS += -j 0
# This will be passed to the make that builds the Verilated sources
BUILD_ARGS += -j
endif

# Disable warnings from Amaranth-generated Verilog
ifeq ($(SIM),verilator)
ifneq ($(GATES),1)
COMPILE_ARGS += -Wno-CASEINCOMPLETE -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND
endif
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

RTL_DIR=$(CURDIR)/../rtl
$(CURDIR)/generated/%.v: FORCE
	mkdir -p $(@D)
	PYTHONPATH=$(RTL_DIR) $(RTL_DIR)/generate_verilog.py \
		--no-init \
		--active-low-reset \
		--verilog-module-name $(TOPLEVEL) \
		$(basename $(@F)) > $@

# The synthesis makefile can synthesize only the top digital module.
# We're not forcing a rebuild every time because this file will be committed
# to the repo.
$(CURDIR)/../gl/digital_top.v:
	$(MAKE) -C $(CURDIR)/../.. harden
	$(MAKE) -C $(CURDIR)/../.. update_files

FORCE:
