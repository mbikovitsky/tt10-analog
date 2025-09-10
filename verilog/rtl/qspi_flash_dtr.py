from dataclasses import dataclass
from typing import Any

from amaranth import Assert, Cat, Module, Signal, unsigned
from amaranth.lib.wiring import Component, In, Out


@dataclass(kw_only=True, frozen=True, slots=True)
class FlashParams:
    command_width_bits: int = 8
    address_width_bits: int = 24
    rsten_command: int = 0x66
    rst_command: int = 0x99
    read_command: int = 0xED
    read_dummy_cycles: int = 15

    def __post_init__(self) -> None:
        assert self.command_width_bits > 0

        assert self.address_width_bits > 0
        # This assertion makes the mode bits implementation easier.
        # See the FSM implementation for more info.
        assert self.address_width_bits % 8 == 0

        assert self.rsten_command.bit_length() <= self.command_width_bits
        assert self.rst_command.bit_length() <= self.command_width_bits

        # This makes the implementation easier, since we don't need to
        # special-case when there's only 1 dummy cycle, which overlaps
        # with the mode bits.
        assert self.read_dummy_cycles > 1


class QSPIFlashDTR(Component):  # type: ignore[misc]
    def __init__(self, params: FlashParams = FlashParams()) -> None:
        super().__init__(
            {
                "i_configure": In(1),
                "o_configure_done": Out(1, init=0),
                "i_read": In(1),
                "i_address": In(unsigned(params.address_width_bits)),
                "o_data": Out(unsigned(8), init=0),
                "o_cs_n": Out(1, init=1),
                "o_sclk": Out(1, init=1),
                "i_io": In(4),
                "o_io": Out(4, init=0),
                "o_oe": Out(4, init=0),  # Set all lines to input (high-Z)
            }
        )
        self._params = params

    @property
    def params(self) -> FlashParams:
        return self._params

    @property
    def cycles_until_first_read_byte(self) -> int:
        command_clocks = (
            # The command is send in 1S mode (1 line, 1 bit per clock)
            self.params.command_width_bits
            # The address is sent in 4D mode (4 lines DTR), so 8 bits per clock
            + self.params.address_width_bits // 8
            + self.params.read_dummy_cycles
        )
        return (
            # Two cycles to transition from "Idle" to start sending the command
            2
            # The command is at the SPI clock, so 2 cycles of the main clock
            + 2 * command_clocks
            # The "Read" state is entered on the falling edge of the SPI clock,
            # but the first data arrives only on the next rising edge. Skip it.
            + 1
            # It takes 2 clocks (1 SPI clock) for the first byte to be assembled.
            # After this, a new byte arrives every 2 clocks.
            + 2
        )

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        #
        # SPI clock. Half the frequency of the module clock.
        #

        with m.If(~self.o_cs_n):
            m.d.sync += self.o_sclk.eq(~self.o_sclk)
        with m.Else():
            m.d.sync += self.o_sclk.eq(1)

        stb_r = Signal()
        m.d.comb += stb_r.eq(self.o_sclk)

        stb_f = Signal()
        m.d.comb += stb_f.eq(~self.o_sclk)

        command_cycle = Signal(range(self._params.command_width_bits), init=0)
        command = Signal(unsigned(self._params.command_width_bits))
        address_cycle = Signal(range(self._params.address_width_bits // 4))
        address = Signal(self.i_address.shape())
        dummy_cycle = Signal(range(self._params.read_dummy_cycles))
        read_buffer = Signal(unsigned(4))

        # For asserting that the delay is what we expect
        read_cycles = Signal(unsigned(16), init=0)
        m.d.sync += read_cycles.eq(read_cycles + 1)

        def prepare_send_command(opcode: int, next_state: str) -> None:
            m.d.sync += command_cycle.eq(0)
            m.d.sync += command.eq(opcode)
            m.d.sync += self.o_cs_n.eq(0)
            m.next = next_state

        def send_command(next_state: str) -> None:
            with m.If(stb_r):
                m.d.sync += self.o_oe[0].eq(1)
                # Commands are sent MSB-first
                m.d.sync += self.o_io[0].eq(command[-1])
                m.d.sync += command.eq(command << 1)
                with m.If(command_cycle == self._params.command_width_bits - 1):
                    m.d.sync += command_cycle.eq(0)
                    m.next = next_state
                with m.Else():
                    m.d.sync += command_cycle.eq(command_cycle + 1)

        with m.FSM():
            with m.State("Idle"):
                m.d.sync += Assert(self.o_cs_n)

                m.d.sync += read_cycles.eq(0)

                with m.If(self.i_configure):
                    m.d.sync += self.o_configure_done.eq(0)
                    prepare_send_command(self._params.rsten_command, "RSTEN send")
                with m.Elif(self.i_read):
                    m.d.sync += address.eq(self.i_address)
                    m.d.sync += address_cycle.eq(0)
                    prepare_send_command(self._params.read_command, "FRQDTR send")

                    m.d.sync += read_cycles.eq(1)

            with m.State("RSTEN send"):
                send_command("RSTEN send done")

            with m.State("RSTEN send done"):
                with m.If(stb_r):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_sclk.eq(1)
                    m.d.sync += self.o_oe[0].eq(0)
                    m.next = "RST send start"

            with m.State("RST send start"):
                prepare_send_command(self._params.rst_command, "RST send")

            with m.State("RST send"):
                send_command("RST send done")

            with m.State("RST send done"):
                with m.If(stb_r):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_sclk.eq(1)
                    m.d.sync += self.o_oe[0].eq(0)
                    m.d.sync += self.o_configure_done.eq(1)
                    m.next = "Config done"

            with m.State("Config done"):
                m.d.sync += self.o_configure_done.eq(0)
                m.next = "Idle"

            with m.State("FRQDTR send"):
                send_command("FRQDTR send done")

            with m.State("FRQDTR send done"):
                with m.If(stb_r):
                    m.next = "Address send"

            with m.State("Address send"):
                # The address is sent on both edges of the clock.
                m.d.sync += self.o_oe.eq(0xF)
                # Send the next 4 MSBits
                m.d.sync += self.o_io.eq(address[-4:])
                m.d.sync += address.eq(address << 4)
                with m.If(address_cycle == self._params.address_width_bits // 4 - 1):
                    m.d.sync += address_cycle.eq(0)
                    # The next state assumes it's starting on a falling edge.
                    m.d.sync += Assert(stb_r)
                    m.next = "Mode bits"
                with m.Else():
                    m.d.sync += address_cycle.eq(address_cycle + 1)

            with m.State("Mode bits"):
                # Explicitly drive 0 for the mode bits, since we don't
                # want continuous reading without a command.
                # It's easier this way.
                m.d.sync += self.o_io.eq(0)

                # We checked that the address is a multiple of 8 bits,
                # which means that we entered this state on the falling
                # edge of the SPI clock. On the rising edge we drive
                # the low 4 mode bits, and move on to the next state.
                with m.If(stb_r):
                    m.d.sync += dummy_cycle.eq(1)
                    m.next = "Dummy cycles"

            with m.State("Dummy cycles"):
                m.d.sync += self.o_oe.eq(0)
                with m.If(stb_r):
                    with m.If(dummy_cycle == self._params.read_dummy_cycles - 1):
                        m.d.sync += Assert(
                            # We're on the rising edge of the last dummy cycle.
                            # The next byte will *begin* transmitting on the next
                            # rising edge, so after 2 main clock ticks.
                            # After 2 more ticks (1 SPI clock), the full byte
                            # will have been read.
                            read_cycles == self.cycles_until_first_read_byte - 4
                        )

                        m.d.sync += dummy_cycle.eq(0)
                        m.next = "Read"
                    with m.Else():
                        m.d.sync += dummy_cycle.eq(dummy_cycle + 1)

            with m.State("Read"):
                with m.If(~self.i_read):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_sclk.eq(1)
                    m.next = "Idle"
                with m.Else():
                    with m.If(stb_r):
                        m.d.sync += read_buffer.eq(self.i_io)
                    with m.Else():
                        # We enter this branch also upon first transitioning
                        # to the "Read" state, since we move immediately
                        # after counting the last dummy cycle on the previous
                        # rising edge. This means we sample the input lines
                        # before there's anything meaningful on them.
                        # This should be fine, since the user shouldn't
                        # be sampling *us* at this point anyway.
                        m.d.sync += Assert(stb_f)
                        m.d.sync += self.o_data.eq(Cat(self.i_io, read_buffer))

        return m
