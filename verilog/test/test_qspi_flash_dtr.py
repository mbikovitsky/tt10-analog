import itertools
import random

import cocotb
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject
from cocotb.triggers import ClockCycles, FallingEdge, ReadOnly, RisingEdge

PIXEL_CLOCK_HZ = 25.175e6  # http://www.tinyvga.com/vga-timing/640x480@60Hz
SYSTEM_CLOCK_HZ = PIXEL_CLOCK_HZ * 2


async def read_byte(dut: HierarchyObject, n_bits: int, dtr: bool = False) -> int | None:
    """
    Reads a single byte from the SPI output of the DUT. If chip-select
    is deasserted before a full byte is read, None is returned.
    """

    assert 8 % n_bits == 0

    edge = True

    byte = 0

    for _ in range(8 // n_bits):
        await (RisingEdge(dut.o_sclk) if edge else FallingEdge(dut.o_sclk))
        # Wait for signals to settle after this clock edge
        # https://github.com/cocotb/cocotb/issues/204
        await ReadOnly()

        if dtr:
            edge = not edge

        if dut.o_cs_n.value:
            return None

        mask = (1 << n_bits) - 1
        assert dut.o_oe.value & mask == mask

        # Data is sent MSB-first
        byte <<= n_bits
        byte |= dut.o_io.value & mask

    return byte


async def read_bytes(dut: HierarchyObject, n_bits: int) -> bytes:
    """
    Reads bytes from the SPI output of the DUT, until the chip-select signal
    is deasserted.
    """
    collected: list[int] = []
    while (byte := await read_byte(dut, n_bits)) is not None:
        collected.append(byte)
    return bytes(collected)


async def send_bytes(
    dut: HierarchyObject,
    n_bits: int,
    data: bytes,
    dtr: bool = False,
) -> None:
    """
    Sends bytes to the DUT's input, indefinitely repeating the given
    payload. Stops when the chip-select signal is deasserted.
    """

    assert 8 % n_bits == 0

    edge = True

    for byte in itertools.cycle(data):
        for i in reversed(range(8 // n_bits)):
            await (RisingEdge(dut.o_sclk) if edge else FallingEdge(dut.o_sclk))

            if dtr:
                edge = not edge

            if dut.o_cs_n.value:
                return

            mask = (1 << n_bits) - 1
            assert dut.o_oe.value & mask == 0  # The data lines must be inputs

            # Data is sent MSB-first
            dut.i_io.value = (byte >> (i * n_bits)) & mask


@cocotb.test()  # type: ignore[misc]
async def test_configure(dut: HierarchyObject) -> None:
    clock = Clock(dut.clk, round(1e12 / SYSTEM_CLOCK_HZ) + 1, units="ps")
    cocotb.start_soon(clock.start())

    dut.i_configure.value = 0
    dut.i_read.value = 0
    dut.i_address.value = 0
    dut.i_io.value = 0

    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 1)

    dut.i_configure.value = 1
    await ClockCycles(dut.clk, 1)
    dut.i_configure.value = 0

    commands: list[bytes] = []
    while not dut.o_configure_done.value:
        commands.append(await read_bytes(dut, 1))
    assert commands == [b"\x66", b"\x99"]

    # Sanity: the chip-select signal should not be asserted after
    # the configuration is finished.
    for _ in range(100):
        assert dut.o_cs_n.value
        await ClockCycles(dut.clk, 1)


@cocotb.test()  # type: ignore
async def test_read(dut: HierarchyObject) -> None:
    clock = Clock(dut.clk, round(1e12 / SYSTEM_CLOCK_HZ) + 1, units="ps")
    cocotb.start_soon(clock.start())

    dut.i_configure.value = 0
    dut.i_read.value = 0
    dut.i_address.value = 0
    dut.i_io.value = 0

    dut.rst.value = 1
    await ClockCycles(dut.clk, 2)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 1)

    address = random.randrange(1 << 24)

    dut.i_address.value = address
    dut.i_read.value = 1

    await FallingEdge(dut.o_cs_n)

    cmd = await read_byte(dut, 1)
    assert cmd == 0xED

    received_address = [(await read_byte(dut, 4, True)) for _ in range(3)]
    assert received_address == list(
        reversed([(address >> i) & 0xFF for i in range(0, 24, 8)])
    )

    # Mode bits
    assert 0 == await read_byte(dut, 4, True)

    # Dummy cycles
    for _ in range(14):
        await RisingEdge(dut.o_sclk)
        await ReadOnly()
        assert dut.o_oe.value == 0

    payload = random.randbytes(100)

    cocotb.start_soon(send_bytes(dut, 4, payload, True))

    await RisingEdge(dut.o_sclk)

    for _ in range(10):
        for byte in payload:
            await ClockCycles(dut.clk, 2)
            await ReadOnly()
            assert dut.o_data.value == byte

    await RisingEdge(dut.clk)
    dut.i_read.value = 0

    for _ in range(100):
        await ClockCycles(dut.clk, 1)
        await ReadOnly()
        assert dut.o_cs_n.value
