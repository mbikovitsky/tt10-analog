import itertools
import random
from enum import Enum, auto
from typing import assert_never

from amaranth.sim import SimulatorContext
from glasgow.applet import (
    GlasgowAppletV2TestCase,
    SimulationAssembly,
    applet_v2_simulation_test,
    synthesis_test,
)

from . import FlashApplet, FlashComponent


class State(Enum):
    IDLE = auto()
    READ_COMMAND = auto()
    READ_ADDRESS = auto()
    SEND_DATA = auto()


class FlashAppletTestCase(GlasgowAppletV2TestCase, applet=FlashApplet):  # type: ignore[misc, call-arg]
    @synthesis_test  # type: ignore[misc]
    def test_build(self) -> None:
        self.assertBuilds()

    def setUp(self) -> None:
        self._payload = random.randbytes(1024)

    def _prepare_read(self, assembly: SimulationAssembly) -> None:
        # HACK based on the defaults in FlashApplet.add_build_arguments
        sclk_port = assembly.get_pin("A1")
        cs_port = assembly.get_pin("A5")
        copi_port = assembly.get_pin("A2")
        cipo_port = assembly.get_pin("A4")

        # Find the single module that is our QSPI applet
        (component,) = (
            module
            for module, _ in assembly._modules
            if isinstance(module, FlashComponent)
        )

        async def testbench(ctx: SimulatorContext) -> None:
            state = State.IDLE

            prev_sclk = bool(ctx.get(sclk_port.o))

            async for _, _, sclk, cs, copi in ctx.tick().sample(
                sclk_port.o, cs_port.o, copi_port.o
            ):
                sclk = bool(sclk)
                rising = sclk and not prev_sclk
                falling = not sclk and prev_sclk
                prev_sclk = sclk

                # Chip-select is active-low
                if cs:
                    state = State.IDLE
                    continue

                match state:
                    case State.IDLE:
                        command = 0
                        command_bits = 0
                        address = 0
                        address_bits = 0
                        current_bit = 7

                        if rising:
                            command <<= 1
                            command |= int(copi)
                            command_bits += 1
                            state = State.READ_COMMAND

                    case State.READ_COMMAND:
                        if rising:
                            command <<= 1
                            command |= int(copi)
                            command_bits += 1

                            if (
                                command_bits
                                == component.flash_params.command_width_bits
                            ):
                                self.assertEqual(
                                    command, component.flash_params.read_command
                                )
                                state = State.READ_ADDRESS

                    case State.READ_ADDRESS:
                        if rising:
                            address <<= 1
                            address |= int(copi)
                            address_bits += 1

                            if (
                                address_bits
                                == component.flash_params.address_width_bits
                            ):
                                address %= len(self._payload)
                                state = State.SEND_DATA

                    case State.SEND_DATA:
                        # Shift data out on the falling edge of the clock,
                        # so that it's available on the rising edge (CPHA=1)
                        if falling:
                            ctx.set(
                                cipo_port.i,
                                (self._payload[address] >> current_bit) & 1,
                            )
                            current_bit -= 1
                            if current_bit == -1:
                                address = (address + 1) % len(self._payload)
                                current_bit = 7

                    case _:
                        assert_never(state)

        assembly.add_testbench(testbench, background=True)

    @applet_v2_simulation_test(prepare=_prepare_read)  # type: ignore[misc]
    async def test_read(self, applet: FlashApplet, ctx: SimulatorContext) -> None:
        component = applet.flash_iface._component
        assert isinstance(component, FlashComponent)

        address = random.randrange(1 << component.flash_params.address_width_bits)

        expected = bytes(
            itertools.islice(
                itertools.cycle(self._payload), address, address + component.buffer_size
            )
        )

        for _ in range(random.randrange(1, 6)):
            result = await applet.flash_iface.read(address)
            self.assertEqual(result, expected)
