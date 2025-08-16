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

        def send_command(
            command_name: str,
            command_value: int,
            next_state: str,
        ) -> str:
            state_name = f"Send command {command_name} -> {next_state}"

            with m.State(state_name):
                with m.If(stb_f):
                    m.d.sync += self.o_oe[0].eq(1)
                    for i in range(self._params.command_width_bits):
                        with m.If(command_cycle == i):
                            m.d.sync += self.o_io[0].eq((command_value >> i) & 1)
                    with m.If(command_cycle == self._params.command_width_bits - 1):
                        m.d.sync += command_cycle.eq(0)
                        m.next = next_state
                    with m.Else():
                        m.d.sync += command_cycle.eq(command_cycle + 1)

            return state_name

        with m.FSM(init="Idle"):
            with m.State("RST done"):
                with m.If(stb_f):
                    m.d.sync += self.o_cs_n.eq(1)
                    m.d.sync += self.o_configure_done.eq(1)
                    m.next = "Idle"

            rst_start = send_command("RST", self._params.rst_command, "RST done")

            with m.State("RSTEN done"):
                with m.If(stb_f):
                    m.d.sync += self.o_cs_n.eq(1)
                # This is going to trigger on the next cycle after deasserting
                # chip-select.
                with m.If(stb_r & self.o_cs_n):
                    m.d.sync += self.o_cs_n.eq(0)
                    m.next = rst_start

            rsten_start = send_command(
                "RSTEN", self._params.rsten_command, "RSTEN done"
            )

            with m.State("Idle"):
                with m.If(self.i_configure):
                    m.d.sync += self.o_cs_n.eq(0)
                    m.d.sync += self.o_configure_done.eq(0)
                    m.next = rsten_start

        return m
