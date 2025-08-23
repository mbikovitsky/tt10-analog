from dataclasses import dataclass
from typing import Any

from amaranth import Module, Signal, unsigned
from amaranth.lib.wiring import Component, In, Out


@dataclass(kw_only=True, frozen=True, slots=True)
class FlashParams:
    command_width_bits: int = 8
    address_width_bits: int = 24
    rsten_command: int = 0x66
    rst_command: int = 0x99

    def __post_init__(self) -> None:
        assert self.command_width_bits > 0
        assert self.address_width_bits > 0
        assert self.rsten_command.bit_length() <= self.command_width_bits
        assert self.rst_command.bit_length() <= self.command_width_bits


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
                "o_sclk": Out(1, init=0),
                "i_io": In(4),
                "o_io": Out(4, init=0),
                "o_oe": Out(4, init=0),  # Set all lines to input (high-Z)
            }
        )
        self._params = params

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        #
        # SPI clock. Half the frequency of the module clock.
        #

        with m.If(~self.o_cs_n):
            m.d.sync += self.o_sclk.eq(~self.o_sclk)
        with m.Else():
            m.d.sync += self.o_sclk.eq(0)

        stb_r = Signal()
        m.d.comb += stb_r.eq(self.o_sclk)

        stb_f = Signal()
        m.d.comb += stb_f.eq(~self.o_sclk)

        command_cycle = Signal(range(self._params.command_width_bits), init=0)
        command = Signal(unsigned(self._params.command_width_bits))

        def prepare_send_command(opcode: int, next_state: str) -> None:
            m.d.sync += command_cycle.eq(0)
            m.d.sync += command.eq(opcode)
            m.d.sync += self.o_cs_n.eq(0)
            m.next = next_state

        def send_command(next_state: str) -> None:
            with m.If(stb_f):
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
                with m.If(self.i_configure):
                    m.d.sync += self.o_configure_done.eq(0)
                    prepare_send_command(self._params.rsten_command, "RSTEN send")

            with m.State("RSTEN send"):
                send_command("RSTEN send done")

            with m.State("RSTEN send done"):
                with m.If(stb_f):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_oe[0].eq(0)
                    m.next = "RST send start"

            with m.State("RST send start"):
                prepare_send_command(self._params.rst_command, "RST send")

            with m.State("RST send"):
                send_command("RST send done")

            with m.State("RST send done"):
                with m.If(stb_f):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_oe[0].eq(0)
                    m.d.sync += self.o_configure_done.eq(1)
                    m.next = "Idle"

        return m
