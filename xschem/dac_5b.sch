v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
N 100 -10 160 -10 {
lab=#net1}
N 160 -40 160 -10 {
lab=#net1}
N 340 -10 400 -10 {
lab=#net2}
N 400 -40 400 -10 {
lab=#net2}
N 160 -10 280 -10 {
lab=#net1}
N 310 -70 380 -70 {
lab=VSS}
N 310 -70 310 -30 {
lab=VSS}
N 70 -70 140 -70 {
lab=VSS}
N 70 -70 70 -30 {
lab=VSS}
N 580 -10 640 -10 {
lab=#net3}
N 640 -40 640 -10 {
lab=#net3}
N 400 -10 520 -10 {
lab=#net2}
N 550 -70 620 -70 {
lab=VSS}
N 550 -70 550 -30 {
lab=VSS}
N 820 -10 880 -10 {
lab=#net4}
N 880 -40 880 -10 {
lab=#net4}
N 640 -10 760 -10 {
lab=#net3}
N 790 -70 860 -70 {
lab=VSS}
N 790 -70 790 -30 {
lab=VSS}
N 1060 -10 1120 -10 {
lab=out}
N 1120 -40 1120 -10 {
lab=out}
N 880 -10 1000 -10 {
lab=#net4}
N 1030 -70 1100 -70 {
lab=VSS}
N 1030 -70 1030 -30 {
lab=VSS}
N 1120 -10 1250 -10 {
lab=out}
C {devices/iopin.sym} -80 -190 0 0 {name=p2 lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 160 -70 0 0 {name=R1
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 70 -10 1 0 {name=R3
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 40 -10 0 0 {name=p3 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 400 -70 0 0 {name=R2
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 310 -10 1 0 {name=R4
L=20
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 310 -70 1 0 {name=p1 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 70 -70 1 0 {name=p4 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 640 -70 0 0 {name=R5
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 550 -10 1 0 {name=R6
L=20
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 550 -70 1 0 {name=p5 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 880 -70 0 0 {name=R7
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 790 -10 1 0 {name=R8
L=20
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 790 -70 1 0 {name=p6 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 1120 -70 0 0 {name=R9
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 1030 -10 1 0 {name=R10
L=20
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 1030 -70 1 0 {name=p7 sig_type=std_logic lab=VSS}
C {devices/ipin.sym} 160 -100 1 0 {name=p8 lab=a0}
C {devices/ipin.sym} 400 -100 1 0 {name=p9 lab=a1}
C {devices/ipin.sym} 640 -100 1 0 {name=p10 lab=a2}
C {devices/ipin.sym} 880 -100 1 0 {name=p11 lab=a3}
C {devices/ipin.sym} 1120 -100 1 0 {name=p12 lab=a4}
C {devices/opin.sym} 1250 -10 0 0 {name=p13 lab=out}
