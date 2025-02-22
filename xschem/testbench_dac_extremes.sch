v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
B 2 110 70 1320 680 {flags=graph
y1=-0.018030021
y2=0.93748486
ypos1=0
ypos2=2

subdivy=4
unity=1
x1=5.4845694e-09
x2=1.0313816e-07
divx=5
subdivx=4
xlabmag=1.0
ylabmag=1.0
node=pin_out
color=4
dataset=-1
unitx=1
logx=0
logy=0
divy=20}
B 2 1340 150 2140 550 {flags=graph
y1=0
y2=.002
ypos1=0
ypos2=2
divy=5
subdivy=1
unity=1
x1=5.4845694e-09
x2=1.0313816e-07
divx=5
subdivx=1
xlabmag=1.0
ylabmag=1.0
node=i(vvss)
color=4
dataset=-1
unitx=1
logx=0
logy=0
}
N 1260 -140 1300 -140 {
lab=pin_out}
N 1300 -140 1300 -90 {
lab=pin_out}
N 1300 -30 1300 -10 {
lab=vss}
N 1300 -140 1330 -140 {
lab=pin_out}
N 920 -140 1200 -140 {
lab=#net1}
N 560 -180 620 -180 {
lab=#net2}
C {devices/lab_pin.sym} 560 -200 2 0 {name=p3 sig_type=std_logic lab=vss}
C {devices/launcher.sym} -160 30 0 0 {name=h17
descr="Load waves"
tclcommand="
xschem raw_read $netlist_dir/[file tail [file rootname [xschem get current_name]]].raw tran

"
}
C {devices/ipin.sym} 260 -220 0 0 {name=p4 lab=a0}
C {devices/ipin.sym} 260 -200 0 0 {name=p5 lab=a1}
C {devices/ipin.sym} 260 -180 0 0 {name=p6 lab=a2}
C {devices/ipin.sym} 260 -160 0 0 {name=p7 lab=a3}
C {devices/ipin.sym} 260 -140 0 0 {name=p8 lab=a4}
C {devices/simulator_commands_shown.sym} -760 140 0 0 {name=COMMANDS
simulator=ngspice
only_toplevel=false
value="
.param VCC=1.8
.param HIGH=\{VCC\}
.param LOW=0

Vvdd vdd 0 \{VCC\}
Vvss vss 0 0

Va0 a0 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va1 a1 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va2 a2 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va3 a3 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va4 a4 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va5 a5 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va6 a6 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}
Va7 a7 0 pwl 0 \{LOW\} 40n \{LOW\} 41n \{HIGH\} 80n \{HIGH\} 81n \{LOW\} 120n \{LOW\}

.control
  repeat 100
    tran 100p 160n
    write testbench_dac_extremes.raw
    set appendwrite
    reset
  end
  quit 0
.endc
"}
C {devices/res.sym} 1230 -140 3 1 {name=R1
value=500
footprint=1206
device=resistor
m=1}
C {devices/capa.sym} 1300 -60 0 1 {name=C1
m=1
value=5p
footprint=1206
device="ceramic capacitor"}
C {devices/lab_pin.sym} 1300 -10 0 1 {name=p11 sig_type=std_logic lab=vss}
C {devices/lab_pin.sym} 1330 -140 0 1 {name=p17 sig_type=std_logic lab=pin_out}
C {sky130_fd_pr/corner.sym} -150 -120 0 0 {name=CORNER only_toplevel=true corner=tt_mm}
C {devices/ipin.sym} 260 -120 0 0 {name=p12 lab=a5}
C {devices/ipin.sym} 260 -100 0 0 {name=p13 lab=a6}
C {devices/ipin.sym} 260 -80 0 0 {name=p14 lab=a7}
C {dac.sym} 410 -150 0 0 {name=x1}
C {devices/lab_pin.sym} 560 -220 2 0 {name=p1 sig_type=std_logic lab=vdd}
C {buffer.sym} 770 -160 0 0 {name=x2}
C {devices/lab_pin.sym} 920 -160 2 0 {name=p2 sig_type=std_logic lab=vss}
C {devices/lab_pin.sym} 920 -180 2 0 {name=p9 sig_type=std_logic lab=vdd}
