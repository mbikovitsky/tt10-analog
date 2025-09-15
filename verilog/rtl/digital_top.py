from enum import Enum
from typing import Any

from amaranth import Assert, Module, Signal, unsigned
from amaranth.lib.wiring import Component, In, Out
from player import Player
from spi_flash import FlashParams, SPIFlash


class Mode(Enum):
    DEBUG_DAC_R_PT = 0
    DEBUG_DAC_L_PT = 1
    PRODUCTION_R = 2
    # We're using uio[7:6] for the mode-select. When using the QSPI Pmod,
    # these pins are connected to the CS# of the SRAM chips through a pull-up.
    # To be compatible with the Pmod, we make it so the production mode
    # works when both of these lines are pulled up.
    # To use the debug mode, either cut the traces on the Pmod, or don't use
    # it at all :)
    PRODUCTION_L = 3


class DigitalTop(Component):  # type: ignore[misc]
    def __init__(
        self,
        *,
        flash_params: FlashParams = FlashParams(),
    ) -> None:
        super().__init__(
            {
                "ui_in": In(8),
                "uo_out": Out(8, init=0),
                "uio_in": In(8),
                "uio_out": Out(8, init=0),
                "uio_oe": Out(8, init=0),  # Everything Hi-Z by default
                "o_digital": Out(unsigned(16), init=0),  # 2 8-bit channels
            }
        )
        self._flash_params = flash_params

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        m.submodules.spi_flash = spi_flash = SPIFlash(self._flash_params)

        m.submodules.player = player = Player(
            spi_address_width_bits=self._flash_params.address_width_bits,
            channels=2,
        )

        # SPI bus
        # Pinout compatible with https://tinytapeout.com/specs/pinouts/#qspi-flash-and-psram
        m.d.comb += [
            # Chip-select
            self.uio_out[0].eq(spi_flash.o_cs_n),
            self.uio_oe[0].eq(1),
            # COPI
            self.uio_out[1].eq(spi_flash.o_copi),
            self.uio_oe[1].eq(1),
            # CIPO
            spi_flash.i_cipo.eq(self.uio_in[2]),
            self.uio_oe[2].eq(0),
            # Clock
            self.uio_out[3].eq(spi_flash.o_sclk),
            self.uio_oe[3].eq(1),
        ]

        #
        # Mode selection
        #

        mode = Signal(Mode)
        assert mode.width == 2
        m.d.comb += [
            mode.eq(self.uio_in[6:8]),
            self.uio_oe[6:8].eq(0),
        ]

        with m.Switch(mode):
            with m.Case(Mode.PRODUCTION_L, Mode.PRODUCTION_R):
                # Pull up IO3 on the QSPI Pmod, which is the HOLD# / RESET# pin
                m.d.comb += [
                    self.uio_out[5].eq(1),
                    self.uio_oe[5].eq(1)
                ]

                # Player <-> SPI controller connection
                m.d.comb += [
                    spi_flash.i_read.eq(player.o_spi_read),
                    spi_flash.i_address.eq(player.o_spi_address),
                    player.i_spi_data_valid.eq(spi_flash.o_data_valid),
                    player.i_spi_data.eq(spi_flash.o_data),
                ]

                # Player digital output; will be wired to the analog module outside
                assert self.o_digital.width == player.o_digital.shape().size
                m.d.comb += self.o_digital.eq(player.o_digital)

                # Play-pause
                m.d.comb += player.i_play.eq(self.ui_in[0])

                # Busy signal
                m.d.comb += [
                    self.uio_out[4].eq(player.o_busy),
                    self.uio_oe[4].eq(1),
                ]

                # Passthrough of a selected audio channel
                assert self.uo_out.width == player.o_digital.shape().elem_shape.width
                with m.If(mode == Mode.PRODUCTION_L):
                    m.d.comb += self.uo_out.eq(player.o_digital[0])
                with m.Else():
                    m.d.comb += Assert(mode == Mode.PRODUCTION_R)
                    m.d.comb += self.uo_out.eq(player.o_digital[1])

            with m.Case(Mode.DEBUG_DAC_L_PT, Mode.DEBUG_DAC_R_PT):
                with m.If(mode == Mode.DEBUG_DAC_L_PT):
                    m.d.comb += self.o_digital[0:8].eq(self.ui_in)
                with m.Else():
                    m.d.comb += Assert(mode == Mode.DEBUG_DAC_R_PT)
                    m.d.comb += self.o_digital[8:16].eq(self.ui_in)

                # Passthrough of SPI controller signals
                m.d.comb += [
                    spi_flash.i_read.eq(self.uio_in[5]),
                    self.uio_oe[5].eq(0),
                    spi_flash.i_address.eq(self.ui_in),
                    self.uo_out.eq(spi_flash.o_data),
                    self.uio_out[4].eq(spi_flash.o_data_valid),
                    self.uio_oe[4].eq(1),
                ]

            # Commented-out because this results in an empty always_comb
            # block being generated, which iverilog can't deal with.
            # with m.Default():
            #     m.d.comb += Assert(False)

        return m
