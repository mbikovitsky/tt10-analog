v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
B 2 110 70 1320 680 {flags=graph
y1=0.04
y2=.65
ypos1=0
ypos2=2

subdivy=4
unity=1
x1=-1.88712e-08
x2=7.7301e-08
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
node=pin_out
color=5
dataset=-1
unitx=1
logx=0
logy=0
divy=20}
B 2 1370 130 2380 720 {flags=graph
y1=0
y2=0.002
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=-1.88712e-08
x2=7.7301e-08
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
node=i(vvss)
color=5
dataset=-1
unitx=1
logx=0
logy=0
}
N 900 -180 940 -180 {
lab=pin_out}
N 940 -180 940 -130 {
lab=pin_out}
N 940 -70 940 -50 {
lab=vss}
N 940 -180 970 -180 {
lab=pin_out}
N 560 -180 840 -180 {
lab=#net1}
N 460 -180 560 -180 {
lab=#net1}
C {devices/launcher.sym} -160 30 0 0 {name=h17 
descr="Load waves" 
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw tran

"
}
C {devices/simulator_commands_shown.sym} -380 150 0 0 {name=COMMANDS
simulator=ngspice
only_toplevel=false 
value="
Vvdd vdd 0 1.8
Vvss vss 0 0

*25.175MEG
*50.35MEG
*Vin vin 0 sin(0.9 0.9 50.35MEG)
Vin vin 0 
+ pwl 
+	0	0.9
+	1n	1.8
+	40n	1.8
+	41n	0.9
+	80n	0.9
+	81n	1.35
+	120n	1.35
+	121n	0.9

.control
  tran 100p 200n
  write testbench_buffer.raw
  quit 0
.endc
"}
C {devices/res.sym} 870 -180 3 1 {name=R1
value=500
footprint=1206
device=resistor
m=1}
C {devices/capa.sym} 940 -100 0 1 {name=C1
m=1
value=5p
footprint=1206
device="ceramic capacitor"}
C {devices/lab_pin.sym} 940 -50 0 1 {name=p11 sig_type=std_logic lab=vss}
C {devices/lab_pin.sym} 970 -180 0 1 {name=p17 sig_type=std_logic lab=pin_out}
C {sky130_fd_pr/corner.sym} -150 -120 0 0 {name=CORNER only_toplevel=true corner=ss}
C {buffer.sym} 310 -200 0 0 {name=x1}
C {devices/lab_pin.sym} 460 -220 2 0 {name=p1 sig_type=std_logic lab=vdd}
C {devices/lab_pin.sym} 460 -200 2 0 {name=p3 sig_type=std_logic lab=vss}
C {devices/lab_pin.sym} 160 -220 0 0 {name=p2 sig_type=std_logic lab=vin}
C {devices/ipin.sym} 70 -260 0 0 {name=p4 lab=vdd}
C {devices/ipin.sym} 70 -240 0 0 {name=p5 lab=vss}
C {devices/ipin.sym} 70 -220 0 0 {name=p6 lab=vin}
