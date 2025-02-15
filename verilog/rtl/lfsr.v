/*
 * Galois LFSR.
 *
 * Once the reset is released, the state is updated every clock cycle.
 *
 * Parameters:
 *  BITS:   Number of bits for the LFSR state.
 *  TAPS:   LFSR taps.
 *
 * Signals:
 *  i_clk:      Clock.
 *  i_rst_n:    Async reset.
 *  o_state:    Current LFSR state.
 */
module lfsr #(
    parameter   int unsigned    BITS    = 8,
    parameter   bit [BITS-1:0]  TAPS    = 8'hC3  // https://users.ece.cmu.edu/~koopman/lfsr/8.txt
) (
    input   logic               i_clk,
    input   logic               i_rst_n,
    output  logic [BITS-1:0]    o_state
);

    logic [BITS-1:0] state;
    assign o_state = state;

    always_ff @( posedge i_clk or negedge i_rst_n ) begin
        if (~i_rst_n) begin
            state <= TAPS;
        end else begin
            if (state[0]) begin
                state <= (state >> 1) ^ TAPS;
            end else begin
                state <= (state >> 1);
            end
        end
    end

endmodule
