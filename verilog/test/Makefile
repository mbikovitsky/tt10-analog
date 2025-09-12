SIM ?= icarus
TOPLEVEL_LANG = verilog

MODULE_TO_TEST ?= qspi_flash_dtr

VERILOG_SOURCES = $(CURDIR)/generated/$(MODULE_TO_TEST).v

# VERILOG_SOURCES may be updated by the included makefiles,
# so make sure to expand it now while we still know what it contains.
TOPLEVEL := $(basename $(notdir $(VERILOG_SOURCES)))

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

RTL_DIR=$(CURDIR)/../rtl
$(CURDIR)/generated/%.v: FORCE
	mkdir -p $(@D)
	PYTHONPATH=$(RTL_DIR) $(RTL_DIR)/generate_verilog.py \
		--no-init \
		--active-low-reset \
		--verilog-module-name $(TOPLEVEL) \
		$(basename $(@F)) > $@

ifeq ($(SIM),verilator)
# This will be passed to Verilator
COMPILE_ARGS += -j 0
# This will be passed to the make that builds the Verilated sources
BUILD_ARGS += -j
endif

# Disable warnings from Amaranth-generated Verilog
ifeq ($(SIM),verilator)
COMPILE_ARGS += -Wno-CASEINCOMPLETE -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

FORCE:
