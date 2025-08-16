import cocotb
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject
from cocotb.triggers import ClockCycles, RisingEdge

PIXEL_CLOCK_HZ = 25.175e6  # http://www.tinyvga.com/vga-timing/640x480@60Hz
SYSTEM_CLOCK_HZ = PIXEL_CLOCK_HZ * 2


async def read_bytes(dut: HierarchyObject) -> bytes:
    """
    Reads bytes from the SPI output of the DUT, until the chip-select signal
    is deasserted.
    """
    collected: list[int] = []
    while True:
        byte = 0
        for i in range(8):
            await RisingEdge(dut.o_sclk)
            if dut.o_cs_n.value:
                return bytes(collected)
            else:
                byte |= dut.o_io[0].value << i
        else:  # Didn't break out of the loop
            collected.append(byte)


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
        commands.append(await read_bytes(dut))
    assert commands == [b"\x66", b"\x99"]

    # Sanity: the chip-select signal should not be asserted after
    # the configuration is finished.
    for _ in range(100):
        assert dut.o_cs_n.value
        await ClockCycles(dut.clk, 1)
