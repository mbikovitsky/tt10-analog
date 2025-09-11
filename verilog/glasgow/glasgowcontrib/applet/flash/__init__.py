import logging
from argparse import ArgumentParser, FileType, Namespace
from typing import Any

from amaranth import Module, unsigned
from amaranth.lib.io import Buffer, Direction, PortLike
from amaranth.lib.memory import Memory
from amaranth.lib.wiring import Component, In, Out
from glasgow.abstract import PullState
from glasgow.applet import (
    AbstractAssembly,
    GlasgowAppletArguments,
    GlasgowAppletV2,
    GlasgowAppletV2TestCase,
    GlasgowPin,
    SimulationAssembly,
)

from .spi_flash import FlashParams, SPIFlash


class FlashComponent(Component):  # type: ignore[misc]
    def __init__(
        self,
        sclk: PortLike,
        cs: PortLike,
        io: PortLike,
        buffer_size: int = 8,
        flash_params: FlashParams = FlashParams(),
    ) -> None:
        super().__init__(
            {
                "i_read": In(1),
                "i_address": In(unsigned(flash_params.address_width_bits)),
                "o_read_done": Out(1, init=0),
                "i_mem_addr": In(range(buffer_size)),
                "o_mem": Out(unsigned(8)),
            }
        )

        assert buffer_size > 0

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
            depth=self.buffer_size,
            init=b"",
        )

        # Expose the memory read port over I2C
        rd_port = memory.read_port(domain="comb")
        m.d.comb += [
            rd_port.addr.eq(self.i_mem_addr),
            self.o_mem.eq(rd_port.data),
        ]

        m.submodules.controller = controller = SPIFlash(self._flash_params)

        m.submodules.sclk_buffer = sclk_buffer = Buffer(Direction.Output, self._sclk)
        m.d.comb += sclk_buffer.o.eq(controller.o_sclk)

        m.submodules.cs_buffer = cs_buffer = Buffer(Direction.Output, self._cs)
        m.d.comb += cs_buffer.o.eq(controller.o_cs_n)

        m.submodules.copi_buffer = copi_buffer = Buffer(Direction.Output, self._io[0])
        m.submodules.cipo_buffer = cipo_buffer = Buffer(Direction.Input, self._io[1])
        m.d.comb += [
            copi_buffer.o.eq(controller.o_copi),
            controller.i_cipo.eq(cipo_buffer.i),
        ]

        wr_port = memory.write_port(domain="sync")
        m.d.comb += [
            wr_port.data.eq(controller.o_data),
            wr_port.en.eq(controller.o_data_valid),
            # The address will be set by the FSM below
        ]

        assert controller.i_read.init == 0

        with m.FSM():
            with m.State("Idle"):
                with m.If(self.i_read):
                    m.d.sync += [
                        controller.i_read.eq(1),
                        controller.i_address.eq(self.i_address),
                        wr_port.addr.eq(0),
                    ]
                    m.next = "Transfer"

            with m.State("Transfer"):
                with m.If(controller.o_data_valid):
                    with m.If(wr_port.addr == self.buffer_size - 1):
                        m.d.sync += [
                            controller.i_read.eq(0),
                            self.o_read_done.eq(1),
                        ]
                        m.next = "Transfer done"
                    with m.Else():
                        m.d.sync += wr_port.addr.eq(wr_port.addr + 1)

            with m.State("Transfer done"):
                with m.If(~self.i_read):
                    m.d.sync += self.o_read_done.eq(0)
                    m.next = "Idle"

        return m


class FlashInterface:
    def __init__(
        self,
        logger: logging.Logger,
        assembly: AbstractAssembly,
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
            FlashComponent(sclk=sclk_port, cs=cs_port, io=io_port)
        )

        self._read_reg = assembly.add_rw_register(self._component.i_read)
        self._addr_reg = assembly.add_rw_register(self._component.i_address)
        self._read_done_reg = assembly.add_ro_register(self._component.o_read_done)

        self._mem_addr_reg = assembly.add_rw_register(self._component.i_mem_addr)
        self._mem_reg = assembly.add_ro_register(self._component.o_mem)

        self._assembly = assembly

    async def read(self, address: int, size: int = -1) -> bytes:
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

        if size < 0 or size > self._component.buffer_size:
            size = self._component.buffer_size

        result = bytearray(size)

        for i in range(size):
            await self._mem_addr_reg.set(i)
            result[i] = await self._mem_reg.get()

        return bytes(result)


class FlashApplet(GlasgowAppletV2):  # type: ignore[misc]
    logger = logging.getLogger(__name__)
    help = "read a QSPI flash chip"
    required_revision = "C3"

    @classmethod
    def add_build_arguments(
        cls, parser: ArgumentParser, access: GlasgowAppletArguments
    ) -> None:
        access.add_voltage_argument(parser)
        # This is the same pinout as for the memory-25x applet
        access.add_pins_argument(parser, "cs", required=True, default="A5")
        access.add_pins_argument(
            parser,
            "io",
            required=True,
            width=4,
            default="A2,A4,A3,A0",
            help="bind the applet I/O lines 'copi', 'cipo', 'wp', 'hold' to PINS",
        )
        access.add_pins_argument(parser, "sclk", required=True, default="A1")

    def build(self, args: Namespace) -> None:
        with self.assembly.add_applet(self):
            self.assembly.use_voltage(args.voltage)
            self.flash_iface = FlashInterface(
                self.logger, self.assembly, sclk=args.sclk, cs=args.cs, io=args.io
            )

    @classmethod
    def add_run_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            help="output file",
            default="-",
            type=FileType("wb"),
        )
        parser.add_argument("--address", type=lambda s: int(s, 0), default=0)
        parser.add_argument("--size", type=lambda s: int(s, 0))

    async def run(self, args: Namespace) -> None:
        remaining = args.size if args.size else self.flash_iface._component.buffer_size
        addr = args.address
        while remaining:
            data = await self.flash_iface.read(addr, remaining)
            args.output.write(data)
            remaining -= len(data)
            addr += len(data)
            self.logger.info("Read %d/%d bytes", args.size - remaining, args.size)

    @classmethod
    def tests(cls) -> type[GlasgowAppletV2TestCase]:
        from . import test

        return test.FlashAppletTestCase
