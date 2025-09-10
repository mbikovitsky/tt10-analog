import argparse
import logging
from argparse import ArgumentParser, Namespace
from typing import Any

from amaranth import Module, Signal, unsigned
from amaranth.lib.io import Buffer, Direction, PortLike
from amaranth.lib.memory import Memory
from amaranth.lib.wiring import Component, In, Out
from amaranth.utils import exact_log2
from glasgow.abstract import PullState
from glasgow.applet import (
    AbstractAssembly,
    GlasgowAppletArguments,
    GlasgowAppletV2,
    GlasgowAppletV2TestCase,
    GlasgowPin,
    SimulationAssembly,
)

from .qspi_flash_dtr import FlashParams, QSPIFlashDTR


class FlashDTRComponent(Component):  # type: ignore[misc]
    def __init__(
        self,
        *,
        sclk: PortLike,
        cs: PortLike,
        io: PortLike,
        buffer_size: int = 256,
        flash_params: FlashParams = FlashParams(),
    ) -> None:
        super().__init__(
            {
                "i_read": In(1),
                "i_address": In(unsigned(flash_params.address_width_bits)),
                "o_read_done": Out(1, init=0),
                "i_mem_addr": In(unsigned(exact_log2(buffer_size))),
                "o_mem": Out(unsigned(8)),
            }
        )
        self._sclk = sclk
        self._cs = cs
        self._io = io
        self._buffer_size = buffer_size
        self._flash_params = flash_params

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    @property
    def flash_params(self) -> FlashParams:
        return self._flash_params

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        m.submodules.memory = memory = Memory(
            shape=unsigned(8),
            depth=self._buffer_size,
            init=b"",
        )

        # Expose the memory read port over I2C
        rd_port = memory.read_port(domain="comb")
        m.d.comb += [
            rd_port.addr.eq(self.i_mem_addr),
            self.o_mem.eq(rd_port.data),
        ]

        m.submodules.controller = controller = QSPIFlashDTR(self._flash_params)

        m.submodules.sclk_buffer = sclk_buffer = Buffer(Direction.Output, self._sclk)
        m.d.comb += sclk_buffer.o.eq(controller.o_sclk)

        m.submodules.cs_buffer = cs_buffer = Buffer(Direction.Output, self._cs)
        m.d.comb += cs_buffer.o.eq(controller.o_cs_n)

        m.submodules.io_buffer = io_buffer = Buffer(Direction.Bidir, self._io)
        m.d.comb += controller.i_io.eq(io_buffer.i)
        m.d.comb += io_buffer.o.eq(controller.o_io)
        # Treat all lines as a single "bus". Technically QSPI requires
        # some lines' directionality to be controlled individually
        # (e.g. IO1-3 should be Hi-Z when sending a command on IO0),
        # but we want to check that this works anyway.
        m.d.comb += io_buffer.oe.eq(controller.o_oe.any())

        wr_port = memory.write_port(domain="sync")
        m.d.comb += wr_port.data.eq(controller.o_data)

        read_wait_cycles = Signal(range(controller.cycles_until_first_read_byte))

        assert controller.i_configure.init == 0
        assert controller.i_read.init == 0
        assert wr_port.en.init == 0

        new_byte_available = Signal()

        with m.FSM():
            with m.State("Idle"):
                with m.If(self.i_read):
                    m.d.sync += controller.i_configure.eq(1)
                    # Store the address now, to avoid TOCTTOU.
                    # We'll start the transfer later by setting "i_read".
                    m.d.sync += controller.i_address.eq(self.i_address)
                    m.next = "Wait for configure done"

            with m.State("Wait for configure done"):
                m.d.sync += controller.i_configure.eq(0)
                with m.If(controller.o_configure_done):
                    m.d.sync += controller.i_read.eq(1)
                    m.d.sync += read_wait_cycles.eq(0)
                    m.next = "Wait for transfer start"

            with m.State("Wait for transfer start"):
                with m.If(
                    read_wait_cycles == controller.cycles_until_first_read_byte - 1
                ):
                    m.d.sync += wr_port.addr.eq(0)
                    m.d.sync += new_byte_available.eq(1)
                    m.next = "Transfer"
                with m.Else():
                    m.d.sync += read_wait_cycles.eq(read_wait_cycles + 1)

            with m.State("Transfer"):
                # When outside this state, the "en" bit will be 0.
                # It's fine to always assert "en" here, since our QSPI
                # controller guarantees the data changes only on every SPI
                # clock.
                m.d.comb += wr_port.en.eq(1)

                # A new byte is read every 2 clocks
                m.d.sync += new_byte_available.eq(~new_byte_available)

                # If there's going to be a new byte on the next clock,
                # increment the memory address.
                with m.If(~new_byte_available):
                    m.d.sync += wr_port.addr.eq(wr_port.addr + 1)

                with m.If(wr_port.addr == (1 << wr_port.addr.width) - 1):
                    m.d.sync += controller.i_read.eq(0)
                    m.d.sync += self.o_read_done.eq(1)
                    m.next = "Transfer done"

            with m.State("Transfer done"):
                with m.If(~self.i_read):
                    m.d.sync += self.o_read_done.eq(0)
                    m.next = "Idle"

        return m


class FlashDTRInterface:
    def __init__(
        self,
        logger: logging.Logger,
        assembly: AbstractAssembly,
        *,
        sclk: GlasgowPin,
        cs: GlasgowPin,
        io: tuple[GlasgowPin, ...],
    ) -> None:
        self._logger = logger

        assembly.use_pulls(
            {
                sclk: PullState.High,
                cs: PullState.High,
                # IO pins should be pulled high so that WP# and HOLD#/RESET#
                # are not active.
                io: PullState.High,
            }
        )

        sclk_port = assembly.add_port(sclk, "sclk")
        cs_port = assembly.add_port(cs, "cs")
        io_port = assembly.add_port(io, "io")

        self._component = assembly.add_submodule(
            FlashDTRComponent(sclk=sclk_port, cs=cs_port, io=io_port)
        )
        self._read_reg = assembly.add_rw_register(self._component.i_read)
        self._addr_reg = assembly.add_rw_register(self._component.i_address)
        self._read_done_reg = assembly.add_ro_register(self._component.o_read_done)
        self._mem_addr_reg = assembly.add_rw_register(self._component.i_mem_addr)
        self._mem_reg = assembly.add_ro_register(self._component.o_mem)

        self._assembly = assembly

    async def read(self, address: int) -> bytes:
        assert not (await self._read_reg.get())
        assert not (await self._read_done_reg.get())

        await self._addr_reg.set(address)
        await self._read_reg.set(True)

        while not (await self._read_done_reg.get()):
            if isinstance(self._assembly, SimulationAssembly):
                await self._assembly._context.tick()
        await self._read_reg.set(False)
        for _ in range(5):
            if not (await self._read_done_reg.get()):
                break
            if isinstance(self._assembly, SimulationAssembly):
                await self._assembly._context.tick()
        else:  # We didn't break out of the loop
            raise TimeoutError("Timeout while waiting for read-done deassertion")

        result = bytearray(self._component.buffer_size)
        for i in range(self._component.buffer_size):
            await self._mem_addr_reg.set(i)
            result[i] = await self._mem_reg.get()
        return bytes(result)


class FlashDTRApplet(GlasgowAppletV2):  # type: ignore[misc]
    logger = logging.getLogger(__name__)
    help = "read a QSPI flash chip in DTR mode"
    required_revision = "C3"

    @classmethod
    def add_build_arguments(
        cls, parser: ArgumentParser, access: GlasgowAppletArguments
    ) -> None:
        access.add_voltage_argument(parser)
        access.add_pins_argument(parser, "sclk", default=True, required=True)
        access.add_pins_argument(parser, "cs", default=True, required=True)
        access.add_pins_argument(parser, "io", 4, default=True, required=True)

    def build(self, args: Namespace) -> None:
        with self.assembly.add_applet(self):
            self.assembly.use_voltage(args.voltage)
            self.flash_dtr_iface = FlashDTRInterface(
                self.logger,
                self.assembly,
                sclk=args.sclk,
                cs=args.cs,
                io=args.io,
            )

    @classmethod
    def add_run_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            help="output file",
            default="-",
            type=argparse.FileType("wb"),
        )
        parser.add_argument("--address", type=lambda s: int(s, 0), default=0)
        parser.add_argument("--size", type=lambda s: int(s, 0), default=1024)

    async def run(self, args: Namespace) -> None:
        remaining = args.size
        addr = args.address
        while remaining:
            data = await self.flash_dtr_iface.read(addr)
            data = data[:remaining]
            args.output.write(data)
            remaining -= len(data)
            addr += len(data)

    @classmethod
    def tests(cls) -> type[GlasgowAppletV2TestCase]:
        from . import test

        return test.FlashDTRAppletTestCase
