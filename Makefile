PROJECT_NAME := digital_top
# needs PDK_ROOT and OPENLANE_ROOT, OPENLANE_IMAGE_NAME set from your environment
harden: $(CURDIR)/openlane/$(PROJECT_NAME)/generated/$(PROJECT_NAME).v
	docker run --rm \
	-v $(OPENLANE_ROOT):/openlane \
	-v $(PDK_ROOT):$(PDK_ROOT) \
	-v $(CURDIR):/work \
	-e PDK_ROOT=$(PDK_ROOT) \
	-e PDK=$(PDK) \
	-u $(shell id -u $(USER)):$(shell id -g $(USER)) \
	$(OPENLANE_IMAGE_NAME) \
	/bin/sh -c "./flow.tcl -overwrite -design /work/openlane/$(PROJECT_NAME) -run_path /work/openlane/$(PROJECT_NAME)/runs -tag $(PROJECT_NAME)"

update_files:
	mkdir -p gds/
	cp openlane/$(PROJECT_NAME)/runs/$(PROJECT_NAME)/results/final/gds/$(PROJECT_NAME).gds gds/
	mkdir -p verilog/gl/
	cp openlane/$(PROJECT_NAME)/runs/$(PROJECT_NAME)/results/final/verilog/gl/$(PROJECT_NAME).v verilog/gl/

RTL_DIR := $(CURDIR)/verilog/rtl
%.v: FORCE
	mkdir -p $(@D)
	PYTHONPATH=$(RTL_DIR) $(RTL_DIR)/generate_verilog.py \
		--no-init \
		--active-low-reset \
		--no-asserts \
		$(basename $(@F)) > $@

FORCE:
