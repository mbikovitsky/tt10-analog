from dataclasses import dataclass
from typing import Any

from amaranth import Assert, Module, Signal, unsigned
from amaranth.lib.wiring import Component, In, Out


@dataclass(kw_only=True, frozen=True, slots=True)
class FlashParams:
    command_width_bits: int = 8
    address_width_bits: int = 24
    read_command: int = 0x03

    def __post_init__(self) -> None:
        assert self.command_width_bits > 0
        assert self.address_width_bits > 0
        assert self.read_command.bit_length() <= self.command_width_bits


class SPIFlash(Component):  # type: ignore[misc]
    def __init__(self, params: FlashParams = FlashParams()) -> None:
        super().__init__(
            {
                "i_read": In(1),
                "i_address": In(unsigned(params.address_width_bits)),
                "o_data": Out(unsigned(8), init=0),
                "o_data_valid": Out(1, init=0),
                "o_cs_n": Out(1, init=1),
                "o_sclk": Out(1, init=1),  # CPOL=1
                "o_copi": Out(1, init=0),  # Controller out, Peripheral In
                "i_cipo": In(1),  # Controller In, Peripheral Out
            }
        )
        self._params = params

    @property
    def params(self) -> FlashParams:
        return self._params

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        #
        # SPI clock, CPOL=1.
        # Half the frequency of the module clock, for better timing control.
        # We implement CPHA=1, so data is sent on the falling edge,
        # and sampled on the rising edge. By halving the clock, we can do:
        #   with m.If(sclk): o_copi.eq(something)
        # which will output the data in time for the next falling edge,
        # and there will be plently of time to honor the setup conditions
        # for the rising edge.
        #
        # I hope.
        #

        with m.If(~self.o_cs_n):
            m.d.sync += self.o_sclk.eq(~self.o_sclk)
        with m.Else():
            m.d.sync += self.o_sclk.eq(1)

        #
        # Shift register to send or receive data
        #

        # The maximum width of anything we'll ever need to send or receive
        max_width = max(
            self.params.command_width_bits,
            self.params.address_width_bits,
            8,  # A single data byte
        )

        shift_reg = Signal(max_width)

        # Timer for counting how many more clocks we need for transmission.
        # Since we're in plain SPI mode, we transmit a single bit per clock.
        timer = Signal(range(max_width), init=0)

        #
        # Main FSM
        #

        address = Signal.like(self.i_address, init=0)

        # When a whole byte is shifted in we'll set o_data_valid so that
        # the enclosing module can sample it. See below.
        m.d.comb += self.o_data.eq(shift_reg[0:8])

        with m.FSM():
            with m.State("Idle"):
                m.d.sync += Assert(self.o_cs_n)
                m.d.sync += Assert(~self.o_data_valid)

                with m.If(self.i_read):
                    m.d.sync += [
                        address.eq(self.i_address),
                        shift_reg.eq(self.params.read_command),
                        timer.eq(self.params.command_width_bits - 1),
                        self.o_cs_n.eq(0),
                    ]
                    m.next = "Send read command"

            with m.State("Send read command"):
                with m.If(self.o_sclk):
                    # Data is sent MSB-first
                    m.d.sync += [
                        self.o_copi.eq(shift_reg[self.params.command_width_bits - 1]),
                        shift_reg.eq(shift_reg.shift_left(1)),
                    ]
                    with m.If(timer == 0):
                        m.d.sync += [
                            shift_reg.eq(address),
                            timer.eq(self.params.address_width_bits - 1),
                        ]
                        m.next = "Send address"
                    with m.Else():
                        m.d.sync += timer.eq(timer - 1)

            with m.State("Send address"):
                with m.If(self.o_sclk):
                    # Data is sent MSB-first
                    m.d.sync += [
                        self.o_copi.eq(shift_reg[self.params.address_width_bits - 1]),
                        shift_reg.eq(shift_reg.shift_left(1)),
                    ]
                    with m.If(timer == 0):
                        m.next = "Delay"
                    with m.Else():
                        m.d.sync += timer.eq(timer - 1)

            with m.State("Delay"):
                with m.If(self.o_sclk):
                    m.d.sync += timer.eq(8 - 1)
                    m.next = "Transfer"

            with m.State("Transfer"):
                # Ensure the valid signal is asserted only for a single
                # clock.
                m.d.sync += self.o_data_valid.eq(0)

                with m.If(~self.i_read):
                    m.d.sync += [
                        self.o_cs_n.eq(1),
                        self.o_sclk.eq(1),
                    ]
                    m.next = "Idle"
                with m.Else():
                    with m.If(self.o_sclk):
                        m.d.sync += [
                            shift_reg.eq(shift_reg.shift_left(1) | self.i_cipo)
                        ]
                        with m.If(timer == 0):
                            m.d.sync += [
                                self.o_data_valid.eq(1),
                                timer.eq(8 - 1),
                            ]
                        with m.Else():
                            m.d.sync += timer.eq(timer - 1)

        return m
