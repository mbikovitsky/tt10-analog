from typing import Any

from amaranth import Assert, Module, Signal, unsigned
from amaranth.lib.data import ArrayLayout
from amaranth.lib.wiring import Component, In, Out


class Player(Component):  # type: ignore[misc]
    def __init__(
        self,
        *,
        spi_address_width_bits: int = 24,
        channels: int = 2,
    ) -> None:
        assert spi_address_width_bits > 0
        assert channels > 0
        super().__init__(
            {
                "i_play": In(1),
                "o_busy": Out(1),
                # Interface to the SPI controller
                "o_spi_read": Out(1, init=0),
                "o_spi_address": Out(unsigned(spi_address_width_bits), init=0),
                "i_spi_data_valid": In(1),
                "i_spi_data": In(unsigned(8)),
                # Interface to the DACs,
                "o_digital": Out(ArrayLayout(unsigned(8), channels), init=[0, 0]),
            }
        )

    @property
    def channels(self) -> int:
        return len(self.o_digital)

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        received_samples = Signal(range(self.channels))
        buffer = Signal(ArrayLayout(unsigned(8), self.channels - 1))

        with m.FSM() as fsm:
            with m.State("Paused"):
                m.d.sync += Assert(received_samples == 0)
                m.d.sync += self.o_digital.eq(0)  # Quiet down
                with m.If(self.i_play):
                    m.next = "Playing"

            with m.State("Playing"):
                m.d.comb += self.o_spi_read.eq(1)

                with m.If(self.i_spi_data_valid):
                    with m.If(received_samples == self.channels - 1):
                        m.d.sync += [
                            self.o_digital[:-1].eq(buffer),
                            self.o_digital[-1].eq(self.i_spi_data),
                            self.o_spi_address.eq(self.o_spi_address + self.channels),
                            received_samples.eq(0),
                        ]
                        with m.If(~self.i_play):
                            m.next = "Paused"
                    with m.Else():
                        m.d.sync += [
                            buffer[received_samples].eq(self.i_spi_data),
                            received_samples.eq(received_samples + 1),
                        ]

        m.d.comb += self.o_busy.eq(~fsm.ongoing("Paused"))

        return m
