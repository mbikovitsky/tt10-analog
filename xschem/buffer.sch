v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
N 60 -220 280 -220 {
lab=in}
N 320 -220 420 -220 {
lab=VSS}
N 320 -320 320 -250 {
lab=VDD}
N 320 -130 420 -130 {
lab=VSS}
N 320 -190 650 -190 {
lab=out}
N 320 -100 320 -30 {
lab=VSS}
N 320 -190 320 -160 {
lab=out}
N 80 -120 80 -90 {
lab=#net1}
N 80 -30 80 -10 {
lab=VSS}
N 80 -100 280 -130 {
lab=#net1}
C {devices/iopin.sym} 40 -380 0 0 {name=p2 lab=VSS}
C {devices/iopin.sym} 40 -400 0 0 {name=p20 lab=VDD}
C {devices/ipin.sym} 60 -220 0 0 {name=p1 lab=in}
C {devices/lab_pin.sym} 320 -320 0 0 {name=p3 sig_type=std_logic lab=VDD}
C {devices/opin.sym} 650 -190 0 0 {name=p7 lab=out}
C {sky130_fd_pr/nfet_01v8_lvt.sym} 300 -220 0 0 {name=M3
L=0.15
W=7
nf=7
mult=1
ad="'int((nf+1)/2) * W/nf * 0.29'" 
pd="'2*int((nf+1)/2) * (W/nf + 0.29)'"
as="'int((nf+2)/2) * W/nf * 0.29'" 
ps="'2*int((nf+2)/2) * (W/nf + 0.29)'"
nrd="'0.29 / W'" nrs="'0.29 / W'"
sa=0 sb=0 sd=0
model=nfet_01v8_lvt
spiceprefix=X
}
C {devices/lab_pin.sym} 420 -220 2 0 {name=p10 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/nfet_01v8_lvt.sym} 300 -130 0 0 {name=M1
L=0.15
W=7
nf=7
mult=1
ad="'int((nf+1)/2) * W/nf * 0.29'" 
pd="'2*int((nf+1)/2) * (W/nf + 0.29)'"
as="'int((nf+2)/2) * W/nf * 0.29'" 
ps="'2*int((nf+2)/2) * (W/nf + 0.29)'"
nrd="'0.29 / W'" nrs="'0.29 / W'"
sa=0 sb=0 sd=0
model=nfet_01v8_lvt
spiceprefix=X
}
C {devices/lab_pin.sym} 420 -130 2 0 {name=p4 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 320 -30 2 0 {name=p5 sig_type=std_logic lab=VSS}
C {sky130_fd_pr/res_high_po_0p35.sym} 80 -60 0 0 {name=R5
L=40
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {sky130_fd_pr/res_high_po_0p35.sym} 80 -150 0 0 {name=R6
L=20
model=res_high_po_0p35
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 60 -150 0 0 {name=p6 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 60 -60 0 0 {name=p8 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 80 -10 2 0 {name=p9 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 80 -180 0 0 {name=p11 sig_type=std_logic lab=VDD}
