import itertools
import operator
import random
from enum import Enum, auto
from functools import reduce
from typing import assert_never

from amaranth.sim import SimulatorContext
from glasgow.applet import (
    GlasgowAppletV2TestCase,
    SimulationAssembly,
    applet_v2_simulation_test,
    synthesis_test,
)

from . import FlashDTRApplet, FlashDTRComponent


class State(Enum):
    IDLE = auto()
    READ_COMMAND = auto()
    READ_ADDRESS = auto()
    READ_MODE = auto()
    DUMMY = auto()
    SEND_DATA = auto()
    UNREACHABLE = auto()


class FlashDTRAppletTestCase(GlasgowAppletV2TestCase, applet=FlashDTRApplet):  # type: ignore[misc, call-arg]
    @synthesis_test  # type: ignore[misc]
    def test_build(self) -> None:
        self.assertBuilds()

    def setUp(self) -> None:
        self._payload = random.randbytes(1024)

    def _prepare_read(self, assembly: SimulationAssembly) -> None:
        # HACK based on the order of arguments in FlashDTRApplet.add_build_arguments
        sclk = assembly.get_pin("A0")
        cs = assembly.get_pin("A1")
        io = reduce(operator.add, (assembly.get_pin(f"A{i}") for i in range(2, 6)))

        # Find the single module that is our QSPI applet
        (component,) = (
            module
            for module, _ in assembly._modules
            if isinstance(module, FlashDTRComponent)
        )

        async def testbench(ctx: SimulatorContext) -> None:
            state = State.IDLE

            prev_sclk = False

            command = 0
            command_bits = 0
            address = 0
            address_bits = 0
            dummy_cycles = 0
            rst_start = False

            async for _, _, sclk_value, cs_value, data_o, data_oe in ctx.tick().sample(
                sclk.o, cs.o, io.o, io.oe
            ):
                sclk_value = bool(sclk_value)
                rising = sclk_value and not prev_sclk
                falling = not sclk_value and prev_sclk
                prev_sclk = sclk_value

                # Chip-select is active-low
                if cs_value:
                    state = State.IDLE
                    continue

                match state:
                    case State.IDLE:
                        command = 0
                        command_bits = 0
                        address = 0
                        address_bits = 0
                        dummy_cycles = 0

                        if rising:
                            self.assertEqual(data_oe & 1, 1)
                            command <<= 1
                            command |= int(data_o & 1)
                            command_bits += 1
                            state = State.READ_COMMAND

                    case State.READ_COMMAND:
                        if rising:
                            self.assertEqual(data_oe & 1, 1)
                            command <<= 1
                            command |= int(data_o & 1)
                            command_bits += 1

                        if falling:
                            if (
                                command_bits
                                == component.flash_params.command_width_bits
                            ):
                                match command:
                                    case component.flash_params.rsten_command:
                                        self.assertFalse(rst_start)
                                        rst_start = True
                                        # Immediately after this the chip-select
                                        # must be deasserted.
                                        state = State.UNREACHABLE
                                    case component.flash_params.rst_command:
                                        self.assertTrue(rst_start)
                                        rst_start = False
                                        state = State.UNREACHABLE
                                    case component.flash_params.read_command:
                                        self.assertFalse(rst_start)
                                        # The next trigger will be on the rising edge,
                                        # when the first bits of the address will be
                                        # sent.
                                        state = State.READ_ADDRESS
                                    case _:
                                        self.fail(f"Unexpected command 0x{command:X}")

                    case State.READ_ADDRESS:
                        if rising or falling:
                            self.assertEqual(data_oe & 0xF, 0xF)
                            address <<= 4
                            address |= int(data_o & 0xF)
                            address_bits += 4

                            if (
                                address_bits
                                == component.flash_params.address_width_bits
                            ):
                                address %= len(self._payload)
                                state = State.READ_MODE

                    case State.READ_MODE:
                        if rising or falling:
                            self.assertEqual(data_oe & 0xF, 0xF)
                            self.assertEqual(data_o & 0xF, 0)

                        # The are 8 mode bits. We entered this state on
                        # the rising edge, so we're leaving on the next
                        # falling edge.
                        if falling:
                            state = State.DUMMY

                    case State.DUMMY:
                        if rising:
                            self.assertEqual(data_oe & 0xF, 0)
                            dummy_cycles += 1

                        if falling:
                            if (
                                dummy_cycles
                                # The first dummy cycle is for the mode bits
                                == component.flash_params.read_dummy_cycles - 1
                            ):
                                self.assertEqual(data_oe & 0xF, 0)
                                ctx.set(io.i, self._payload[address] >> 4)
                                state = State.SEND_DATA

                    case State.SEND_DATA:
                        self.assertEqual(data_oe & 0xF, 0)
                        if rising:
                            ctx.set(io.i, self._payload[address] & 0xF)
                            address = (address + 1) % len(self._payload)
                        if falling:
                            ctx.set(io.i, self._payload[address] >> 4)

                    case State.UNREACHABLE:
                        self.fail("Unreachable state reached")

                    case _:
                        assert_never(state)

        assembly.add_testbench(testbench, background=True)

    @applet_v2_simulation_test(prepare=_prepare_read)  # type: ignore[misc]
    async def test_read(self, applet: FlashDTRApplet, ctx: SimulatorContext) -> None:
        component = applet.flash_dtr_iface._component
        assert isinstance(component, FlashDTRComponent)

        address = random.randrange(1 << component.flash_params.address_width_bits)

        expected = bytes(
            itertools.islice(
                itertools.cycle(self._payload), address, address + component.buffer_size
            )
        )

        result = await applet.flash_dtr_iface.read(address)

        self.assertEqual(result, expected)
