import itertools
import random

import cocotb
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject
from cocotb.triggers import ClockCycles, FallingEdge, First, ReadOnly, RisingEdge

AUDIO_SAMPLE_RATE_HZ = 48e3  # https://en.wikipedia.org/wiki/48,000_Hz
SYSTEM_CLOCK_HZ = AUDIO_SAMPLE_RATE_HZ * 16 * 2


async def read_byte(dut: HierarchyObject) -> int | None:
    """
    Reads a single byte from the SPI output of the DUT. If chip-select
    is deasserted before a full byte is read, None is returned.
    """

    byte = 0

    for _ in range(8):
        await First(RisingEdge(dut.o_sclk), RisingEdge(dut.o_cs_n))
        # Wait for signals to settle after this clock edge
        # https://github.com/cocotb/cocotb/issues/204
        await ReadOnly()

        if dut.o_cs_n.value:
            return None

        # Data is sent MSB-first
        byte <<= 1
        byte |= dut.o_copi.value

    return byte


async def send_bytes(dut: HierarchyObject, data: bytes) -> None:
    """
    Sends bytes to the DUT's input, indefinitely repeating the given
    payload. Stops when the chip-select signal is deasserted.
    """

    for byte in itertools.cycle(data):
        for i in reversed(range(8)):
            await RisingEdge(dut.o_sclk)

            if dut.o_cs_n.value:
                return

            # Data is sent MSB-first
            dut.i_cipo.value = (byte >> i) & 1


@cocotb.test()  # type: ignore
async def test_read(dut: HierarchyObject) -> None:
    clock = Clock(dut.clk, round(1e12 / SYSTEM_CLOCK_HZ), units="ps")
    cocotb.start_soon(clock.start())

    dut.i_read.value = 0
    dut.i_address.value = 0
    dut.i_cipo.value = 0

    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 1)

    address = random.randrange(1 << 24)

    dut.i_address.value = address
    dut.i_read.value = 1

    await FallingEdge(dut.o_cs_n)

    cmd = await read_byte(dut)
    assert cmd == 0x03

    received_address = [(await read_byte(dut)) for _ in range(3)]
    assert received_address == list(
        reversed([(address >> i) & 0xFF for i in range(0, 24, 8)])
    )

    payload = random.randbytes(100)

    cocotb.start_soon(send_bytes(dut, payload))

    for _ in range(10):
        for byte in payload:
            await RisingEdge(dut.o_data_valid)
            await ReadOnly()
            assert dut.o_data.value == byte

    await RisingEdge(dut.clk)
    dut.i_read.value = 0

    for _ in range(100):
        await ClockCycles(dut.clk, 1)
        await ReadOnly()
        assert dut.o_cs_n.value
        assert not dut.o_data_valid.value
