`default_nettype none

module tb (input    wire        clk,
           input    wire        rst_n,
           input    wire [7:0]  ui_in,
           output   wire [7:0]  uo_out,
           input    wire [7:0]  uio_in,
           output   wire [7:0]  uio_out,
           output   wire [7:0]  uio_oe,
           output   wire [15:0] o_digital);
   digital_top top (.VGND('0),
                    .VPWR('1),
                    .clk(clk),
                    .rst_n(rst_n),
                    .ui_in(ui_in),
                    .uo_out(uo_out),
                    .uio_in(uio_in),
                    .uio_out(uio_out),
                    .uio_oe(uio_oe),
                    .o_digital(o_digital)
                    );
endmodule // tb
