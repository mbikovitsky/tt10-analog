import logging
import sys
from argparse import ArgumentParser, Namespace
from contextlib import nullcontext
from typing import Any

from amaranth import (
    ClockDomain,
    ClockSignal,
    DomainRenamer,
    Module,
    ResetSignal,
    Signal,
    unsigned,
)
from amaranth.lib import stream, wiring
from amaranth.lib.io import Buffer, Direction, PortLike
from amaranth.lib.memory import Memory, WritePort
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
from glasgow.gateware.pll import PLL
from glasgow.gateware.stream import AsyncQueue

from .qspi_flash_dtr import FlashParams, QSPIFlashDTR


class FlashDTRInner(Component):  # type: ignore[misc]
    def __init__(
        self,
        *,
        sclk: PortLike,
        cs: PortLike,
        io: PortLike,
        memory_addr_width: int,
        flash_params: FlashParams,
    ) -> None:
        super().__init__(
            {
                "i_address": In(
                    stream.Signature(unsigned(flash_params.address_width_bits))
                ),
                "o_done": Out(stream.Signature(0)),
                "o_memory": Out(
                    WritePort.Signature(
                        addr_width=memory_addr_width, shape=unsigned(8)
                    ).flip()
                ),
            }
        )
        self._sclk = sclk
        self._cs = cs
        self._io = io
        self._flash_params = flash_params

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        m.submodules.controller = controller = QSPIFlashDTR(self._flash_params)
        m.d.comb += controller.i_configure.eq(0)

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

        read_wait_cycles = Signal(range(controller.cycles_until_first_read_byte))

        assert controller.i_read.init == 0
        assert self.i_address.ready.init == 0
        assert self.o_done.valid.init == 0
        assert self.o_memory.en.init == 0

        m.d.comb += self.o_memory.data.eq(controller.o_data)

        new_byte_available = Signal()

        with m.FSM():
            with m.State("Idle"):
                # When outside this state, the "ready" bit will be 0.
                # Combinational signals assume their reset value if no
                # assignments are active, and we asserted the reset value is 0
                # above.
                m.d.comb += self.i_address.ready.eq(1)

                with m.If(self.i_address.valid):
                    m.d.sync += controller.i_read.eq(1)
                    m.d.sync += controller.i_address.eq(self.i_address.payload)
                    m.d.sync += read_wait_cycles.eq(0)
                    m.next = "Wait for transfer start"

            with m.State("Wait for transfer start"):
                with m.If(
                    read_wait_cycles == controller.cycles_until_first_read_byte - 1
                ):
                    m.d.sync += self.o_memory.addr.eq(0)
                    m.d.sync += new_byte_available.eq(1)
                    m.next = "Transfer"
                with m.Else():
                    m.d.sync += read_wait_cycles.eq(read_wait_cycles + 1)

            with m.State("Transfer"):
                # When outside this state, the "en" bit will be 0.
                # It's fine to always assert "en" here, since our QSPI
                # controller guarantees the data changes only on every SPI
                # clock.
                m.d.comb += self.o_memory.en.eq(1)

                # A new byte is read every 2 clocks
                m.d.sync += new_byte_available.eq(~new_byte_available)

                # If there's going to be a new byte on the next clock,
                # increment the memory address.
                with m.If(~new_byte_available):
                    m.d.sync += self.o_memory.addr.eq(self.o_memory.addr + 1)

                with m.If(self.o_memory.addr == (1 << self.o_memory.addr.width) - 1):
                    m.d.sync += controller.i_read.eq(0)
                    m.d.sync += self.o_done.valid.eq(1)
                    m.next = "Transfer done"

            with m.State("Transfer done"):
                with m.If(self.o_done.ready):
                    m.d.sync += self.o_done.valid.eq(0)
                    m.next = "Idle"

        return m


class FlashDTRComponent(Component):  # type: ignore[misc]
    def __init__(
        self,
        *,
        spi_freq: float,
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
        self._spi_freq = spi_freq
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

        m.domains.spi = cd_spi = ClockDomain()

        if platform is None:
            # We must be in simulation mode...
            m.d.comb += [
                cd_spi.clk.eq(ClockSignal()),
                cd_spi.rst.eq(ResetSignal()),
            ]
        else:
            m.submodules.spi_pll = PLL(
                f_in=platform.default_clk_frequency,
                f_out=self._spi_freq * 2,
                odomain="spi",
            )
            # The PLL block already provides a reset signal to the driven
            # domain -- the PLL lock status.
            # https://github.com/GlasgowEmbedded/glasgow/blob/d7db593e8025406432dd963766c31c5660047be7/software/glasgow/hardware/platform/ice40.py#L95
            # So no need to provide our own.
            # m.submodules.spi_rst = ResetSynchronizer(ResetSignal(), domain="spi")

        m.submodules.memory = memory = Memory(
            shape=unsigned(8),
            depth=self._buffer_size,
            init=b"",
        )

        # Expose the memory read port over I2C
        rd_port = memory.read_port(domain="comb")
        m.d.comb += [rd_port.addr.eq(self.i_mem_addr), self.o_mem.eq(rd_port.data)]

        m.submodules.addr_fifo = addr_fifo = AsyncQueue(
            shape=self.i_address.shape(),
            depth=2,
            i_domain="sync",
            o_domain="spi",
        )

        m.submodules.done_fifo = done_fifo = AsyncQueue(
            # There's no payload, we only care about synchornizing the "done"
            # indication.
            shape=unsigned(0),
            depth=2,
            i_domain="spi",
            o_domain="sync",
        )

        m.submodules.inner = inner = DomainRenamer("spi")(
            FlashDTRInner(
                sclk=self._sclk,
                cs=self._cs,
                io=self._io,
                memory_addr_width=exact_log2(memory.depth),
                flash_params=self._flash_params,
            )
        )

        wiring.connect(m, addr_fifo.o, inner.i_address)
        wiring.connect(m, inner.o_done, done_fifo.i)

        wr_port = memory.write_port(domain="spi")
        wiring.connect(m, inner.o_memory, wr_port)

        assert addr_fifo.i.valid.init == 0
        assert done_fifo.o.ready.init == 0
        with m.FSM():
            with m.State("Idle"):
                with m.If(self.i_read):
                    m.d.sync += addr_fifo.i.valid.eq(1)
                    m.d.sync += addr_fifo.i.payload.eq(self.i_address)
                    m.next = "Push address"

            with m.State("Push address"):
                with m.If(addr_fifo.i.ready):
                    m.d.sync += addr_fifo.i.valid.eq(0)
                    m.d.sync += done_fifo.o.ready.eq(1)
                    m.next = "Wait done"

            with m.State("Wait done"):
                with m.If(done_fifo.o.valid):
                    m.d.sync += done_fifo.o.ready.eq(0)
                    m.d.sync += self.o_read_done.eq(1)
                    m.next = "Wait read done ACK"

            with m.State("Wait read done ACK"):
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
        spi_freq: float,
    ) -> None:
        self._logger = logger

        assembly.use_pulls({sclk: PullState.Low, cs: PullState.High, io: PullState.Low})

        sclk_port = assembly.add_port(sclk, "sclk")
        cs_port = assembly.add_port(cs, "cs")
        io_port = assembly.add_port(io, "io")

        self._component = assembly.add_submodule(
            FlashDTRComponent(
                spi_freq=spi_freq,
                sclk=sclk_port,
                cs=cs_port,
                io=io_port,
            )
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
        parser.add_argument(
            "--spi-freq",
            type=float,
            help="base SPI clock frequency",
            default=25.175e6,
        )

    def build(self, args: Namespace) -> None:
        with self.assembly.add_applet(self):
            self.assembly.use_voltage(args.voltage)
            self.flash_dtr_iface = FlashDTRInterface(
                self.logger,
                self.assembly,
                sclk=args.sclk,
                cs=args.cs,
                io=args.io,
                spi_freq=args.spi_freq,
            )

    @classmethod
    def add_run_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-o", "--output", help="save output to file instead of stdout"
        )
        parser.add_argument("--size", type=lambda s: int(s, 0), default=1024)

    async def run(self, args: Namespace) -> None:
        output = (
            nullcontext(sys.stdout.buffer)
            if args.output is None
            else open(args.output, "wb")
        )
        with output as f:
            remaining = args.size
            addr = 0  # TODO: Parameter
            while remaining:
                data = await self.flash_dtr_iface.read(addr)
                data = data[:remaining]
                f.write(data)
                remaining -= len(data)
                addr += len(data)

    @classmethod
    def tests(cls) -> type[GlasgowAppletV2TestCase]:
        from . import test

        return test.FlashDTRAppletTestCase
