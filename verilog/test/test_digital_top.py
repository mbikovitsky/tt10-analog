import itertools
import random
from enum import Enum
from typing import Iterable

import cocotb
import cocotb.utils
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject, ModifiableObject
from cocotb.triggers import ClockCycles, Edge, FallingEdge, First, ReadOnly, RisingEdge
from pytest import approx

AUDIO_SAMPLE_RATE_HZ = 48e3  # https://en.wikipedia.org/wiki/48,000_Hz
SYSTEM_CLOCK_HZ = AUDIO_SAMPLE_RATE_HZ * 16 * 2


# NOTE: Keep in sync with the RTL
class Mode(Enum):
    PRODUCTION_L = 0
    PRODUCTION_R = 1
    DEBUG_DAC_L_PT = 2
    DEBUG_DAC_R_PT = 3


class Bus:
    def __init__(self, wires: Iterable[ModifiableObject]):
        self._wires = list(wires)
        self._total_bits = sum(wire.value.n_bits for wire in self._wires)

    @property
    def value(self) -> int:
        for wire in self._wires:
            if not wire.value.is_resolvable:
                raise ValueError(f"Wire {wire._path} is not resolvable ({wire.value})")

        return int("".join(wire.value.binstr for wire in reversed(self._wires)), 2)

    @value.setter
    def value(self, value: int) -> None:
        if value < 0:
            raise NotImplementedError("Negative values are not supported")
        if value >= (1 << self._total_bits):
            raise ValueError(f"{value} is out of range for this bus")

        bit_offset = 0
        for wire in self._wires:
            wire.value = (value >> bit_offset) & ((1 << wire.value.n_bits) - 1)
            bit_offset += wire.value.n_bits


@cocotb.test()  # type: ignore
async def test_player_left(dut: HierarchyObject) -> None:
    await _test_player(dut, True)


@cocotb.test()  # type: ignore
async def test_player_right(dut: HierarchyObject) -> None:
    await _test_player(dut, False)


async def _test_player(dut: HierarchyObject, left_pt: bool) -> None:
    clock = Clock(dut.clk, round(1e12 / SYSTEM_CLOCK_HZ), units="ps")
    cocotb.start_soon(clock.start())

    mode = Bus(dut.uio_in[i] for i in range(4, 6))

    # Relevant signals for this test
    play = dut.ui_in[0]
    busy = dut.uio_out[6]
    digital_out = dut.o_digital
    digital_pt = dut.uo_out

    # SPI signals
    cs_n = dut.uio_out[0]
    copi = dut.uio_out[1]
    cipo = dut.uio_in[2]
    sclk = dut.uio_out[3]

    mode.value = Mode.PRODUCTION_L.value if left_pt else Mode.PRODUCTION_R.value
    play.value = 0
    cipo.value = 1  # Pull-up :)

    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 1)

    assert dut.uio_oe.value == 0b01001011

    # Everything should be idle before we start
    assert not busy.value
    assert digital_out.value == 0
    assert digital_pt.value == 0

    samples = _generate_samples(100)

    cocotb.start_soon(
        _spi_peripheral(
            memory=bytes(itertools.chain.from_iterable(samples)),
            cs_n=cs_n,
            copi=copi,
            cipo=cipo,
            sclk=sclk,
        )
    )

    play.value = 1

    async def verify_playback(expected_samples: Iterable[tuple[int, int]]) -> None:
        last_sample_time = None

        for expected_l, expected_r in expected_samples:
            await Edge(digital_out)
            await ReadOnly()

            assert busy.value

            actual_l = digital_out.value & 0xFF
            actual_r = digital_out.value >> 8
            assert actual_l == expected_l
            assert actual_r == expected_r
            if left_pt:
                assert digital_pt == expected_l
            else:
                assert digital_pt == expected_r

            current_sample_time = cocotb.utils.get_sim_time("ps") * 1e-12
            if last_sample_time is not None:
                delta = current_sample_time - last_sample_time
                assert delta == approx(1 / AUDIO_SAMPLE_RATE_HZ)
            last_sample_time = current_sample_time

    played_samples = random.randrange(len(samples) - 2)
    await verify_playback(samples[:played_samples])

    await RisingEdge(dut.clk)
    play.value = 0
    await FallingEdge(busy)

    played_samples += 1  # One extra was played after we deasserted "play"

    for _ in range(100):
        await ClockCycles(dut.clk, 1)
        await ReadOnly()

        # We're not playing anymore, everything should be quiet
        assert not busy.value
        assert digital_out.value == 0
        assert digital_pt.value == 0

    # Make sure we can resume playback
    await ClockCycles(dut.clk, 1)
    play.value = 1
    await verify_playback(samples[played_samples:])


def _generate_samples(count: int) -> list[tuple[int, int]]:
    return [(random.randrange(1 << 8), random.randrange(1 << 8)) for _ in range(count)]


async def _spi_peripheral(
    *,
    memory: bytes,
    cs_n: ModifiableObject,
    copi: ModifiableObject,
    cipo: ModifiableObject,
    sclk: ModifiableObject,
) -> None:
    """
    Emulates a SPI flash peripheral. Responds to plain read commands.
    """

    async def read_byte() -> int | None:
        """
        Reads a single byte from the SPI output. If chip-select
        is deasserted before a full byte is read, None is returned.
        """

        byte = 0

        for _ in range(8):
            await First(RisingEdge(sclk), RisingEdge(cs_n))
            await ReadOnly()

            if cs_n.value:
                return None

            # Data is sent MSB-first
            byte <<= 1
            byte |= copi.value

        return byte

    async def read_bytes(count: int) -> bytes | None:
        result = bytearray(count)
        for i in range(count):
            byte = await read_byte()
            if byte is None:
                return None
            result[i] = byte
        return bytes(result)

    async def send_bytes(data: Iterable[int]) -> None:
        for byte in itertools.cycle(data):
            for i in reversed(range(8)):
                await RisingEdge(sclk)

                if cs_n.value:
                    return

                # Data is sent MSB-first
                cipo.value = (byte >> i) & 1

    while True:
        await FallingEdge(cs_n)

        cmd = await read_byte()
        if cmd != 0x03:
            continue

        address = await read_bytes(3)
        if address is None:
            continue

        offset = int.from_bytes(address, "big") % len(memory)
        await send_bytes(memory[offset:] + memory[:offset])


@cocotb.test()  # type: ignore
async def test_debug_pt_left(dut: HierarchyObject) -> None:
    await _test_debug(dut, True)


@cocotb.test()  # type: ignore
async def test_debug_pt_right(dut: HierarchyObject) -> None:
    await _test_debug(dut, False)


async def _test_debug(dut: HierarchyObject, left_pt: bool) -> None:
    clock = Clock(dut.clk, round(1e12 / SYSTEM_CLOCK_HZ), units="ps")
    cocotb.start_soon(clock.start())

    mode = Bus(dut.uio_in[i] for i in range(4, 6))

    # Relevant signals for this test
    pt_in = dut.ui_in
    digital_out = dut.o_digital
    spi_ctl_read = dut.uio_in[6]
    spi_ctl_data_out = dut.uo_out
    spi_ctl_data_valid = dut.uio_out[7]

    # SPI signals
    cs_n = dut.uio_out[0]
    copi = dut.uio_out[1]
    cipo = dut.uio_in[2]
    sclk = dut.uio_out[3]

    mode.value = Mode.DEBUG_DAC_L_PT.value if left_pt else Mode.DEBUG_DAC_R_PT.value
    cipo.value = 1  # Pull-up :)
    spi_ctl_read.value = 0

    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 1)

    assert dut.uio_oe.value == 0b10001011

    #
    # Test passthrough to the DACs.
    # The disabled DAC should be fed 0.
    #

    pt_value = random.randrange(1 << 8)
    pt_in.value = pt_value
    await ClockCycles(dut.clk, 1)
    if left_pt:
        assert digital_out.value == pt_value
    else:
        assert digital_out.value == pt_value << 8

    #
    # Test SPI controller passthrough
    #

    memory = random.randbytes(16 * 1024 * 1024)  # Size of IS25WP128 flash chip

    cocotb.start_soon(
        _spi_peripheral(
            memory=memory,
            cs_n=cs_n,
            copi=copi,
            cipo=cipo,
            sclk=sclk,
        )
    )

    # The input is limited to 8 bits 🤷
    address = random.randrange(1 << 8)

    await ClockCycles(dut.clk, 1)
    pt_in.value = address
    spi_ctl_read.value = 1
    for i in range(1024):
        await RisingEdge(spi_ctl_data_valid)
        await ReadOnly()
        assert spi_ctl_data_out.value == memory[(address + i) % len(memory)]
