import logging
import os
import random
import subprocess
import sys

from .qspi_flash_dtr import FlashParams

# From the IS25WP128 datasheet
# https://www.mouser.com/datasheet/2/198/IS25WP032_064_128-737458.pdf
PAGE_SIZE = 256
VOLTAGE = "1.8"
FLASH_SIZE_BITS = 128 * 1024 * 1024
FLASH_SIZE_BYTES = FLASH_SIZE_BITS // 8
QE_BIT_POSITION = 6
DUMMY_CYCLES_BIT_POSITION = 3
DUMMY_CYCLES_BIT_WIDTH = 4
DUMMY_CYCLES_MASK = ((1 << DUMMY_CYCLES_BIT_WIDTH) - 1) << DUMMY_CYCLES_BIT_POSITION

TEST_PAYLOAD_SIZE = 4
assert TEST_PAYLOAD_SIZE <= FLASH_SIZE_BYTES

# NOTE: Keep this in sync with the applet code
TEST_DUMMY_CYCLES = FlashParams().read_dummy_cycles
assert TEST_DUMMY_CYCLES.bit_length() <= DUMMY_CYCLES_BIT_WIDTH


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    payload = random.randbytes(TEST_PAYLOAD_SIZE)
    address = random.randrange(0, FLASH_SIZE_BYTES - len(payload))

    logging.info("Checking for Glasgow devices")
    devices = subprocess.run(
        [sys.executable, "-m", "glasgow.cli", "list"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.splitlines()
    if len(devices) != 1:
        raise RuntimeError(f"Expected only 1 device, but got: {devices}")
    logging.info("Found device %s", devices[0])

    status_reg = _read_status_register()
    logging.info("Enabling quad mode")
    status_reg |= 1 << QE_BIT_POSITION
    _write_status_register(status_reg)
    if _read_status_register() != status_reg:
        raise RuntimeError("Failed enabling quad mode")

    read_reg = _read_read_parameters()
    logging.info("Configuring dummy cycles")
    read_reg &= ~DUMMY_CYCLES_MASK
    read_reg |= TEST_DUMMY_CYCLES << DUMMY_CYCLES_BIT_POSITION
    _write_read_parameters(read_reg)
    if _read_read_parameters() != read_reg:
        raise RuntimeError("Failed configuring dummy cycles")

    logging.info("Erasing flash")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "memory-25x",
            f"--voltage={VOLTAGE}",
            "erase-chip",
        ],
        check=True,
        capture_output=True,
    )

    logging.info("Writing 0x%X bytes to address 0x%X", len(payload), address)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "memory-25x",
            f"--voltage={VOLTAGE}",
            "program",
            f"--page-size={PAGE_SIZE}",
            "--file=-",
            hex(address),
        ],
        check=True,
        capture_output=True,
        input=payload,
    )

    logging.info("Verifying written data")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "memory-25x",
            f"--voltage={VOLTAGE}",
            "verify",
            "--file=-",
            hex(address),
        ],
        check=True,
        capture_output=True,
        input=payload,
    )

    logging.info("Reading data in QSPI DTR mode")
    readback = subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "flash-dtr",
            f"--voltage={VOLTAGE}",
            # Same pinout as the defaults for memory-25x
            "--cs=A5",
            "--sclk=A1",
            "--io=A2,A4,A3,A0",
            "--output=-",
            f"--address=0x{address:X}",
            f"--size=0x{len(payload):X}",
        ],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GLASGOW_OUT_OF_TREE_APPLETS": "I-am-okay-with-breaking-changes",
        },
    ).stdout

    assert readback == payload


def _read_status_register() -> int:
    # Expect a single line of output
    (response,) = subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            # The command-line interface of this applet only performs SPI-mode
            # transactions, which is what we need.
            # The plain spi-controller doesn't seem to work, presumably
            # because of incorrect pull-up/down settings on the other pins.
            "qspi-controller",
            f"--voltage={VOLTAGE}",
            # Same pinout as the defaults for memory-25x
            "--cs=A5",
            "--sck=A1",
            "--io=A2,A4,A3,A0",
            "0500",  # Command and dummy byte to read the response
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.splitlines()
    # The output should have 2 bytes: one byte was shifted in while we were
    # sending the command, and the second byte is the actual response.
    (_, status_reg) = bytes.fromhex(response)
    logging.info("Status register: 0x%X", status_reg)
    return status_reg


def _write_status_register(status_reg: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "qspi-controller",
            f"--voltage={VOLTAGE}",
            # Same pinout as the defaults for memory-25x
            "--cs=A5",
            "--sck=A1",
            "--io=A2,A4,A3,A0",
            "06",  # Write-enable
            bytes([0x01, status_reg]).hex(),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


def _read_read_parameters() -> int:
    # Expect a single line of output
    (response,) = subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            # The command-line interface of this applet only performs SPI-mode
            # transactions, which is what we need.
            # The plain spi-controller doesn't seem to work, presumably
            # because of incorrect pull-up/down settings on the other pins.
            "qspi-controller",
            f"--voltage={VOLTAGE}",
            # Same pinout as the defaults for memory-25x
            "--cs=A5",
            "--sck=A1",
            "--io=A2,A4,A3,A0",
            "6100",  # Command and dummy byte to read the response
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout.splitlines()
    # The output should have 2 bytes: one byte was shifted in while we were
    # sending the command, and the second byte is the actual response.
    (_, read_reg) = bytes.fromhex(response)
    logging.info("Read register: 0x%X", read_reg)
    return read_reg


def _write_read_parameters(read_reg: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "qspi-controller",
            f"--voltage={VOLTAGE}",
            # Same pinout as the defaults for memory-25x
            "--cs=A5",
            "--sck=A1",
            "--io=A2,A4,A3,A0",
            "06",  # Write-enable
            bytes([0x65, read_reg]).hex(),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
