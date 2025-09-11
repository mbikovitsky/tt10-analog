import argparse
import logging
import os
import random
import subprocess
import sys

# From the IS25WP128 datasheet
# https://www.mouser.com/datasheet/2/198/IS25WP032_064_128-737458.pdf
PAGE_SIZE = 256
VOLTAGE = "1.8"
FLASH_SIZE_BITS = 128 * 1024 * 1024
FLASH_SIZE_BYTES = FLASH_SIZE_BITS // 8


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    args = _parse_command_line()
    if args.size > FLASH_SIZE_BYTES:
        raise ValueError(
            f"Payload size 0x{args.size:X} is larger than flash "
            f"size 0x{FLASH_SIZE_BYTES:X}"
        )

    payload = random.randbytes(args.size)
    address = random.randrange(0, FLASH_SIZE_BYTES - len(payload) + 1)

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

    logging.info("Reading data using *our* code")
    readback = subprocess.run(
        [
            sys.executable,
            "-m",
            "glasgow.cli",
            "run",
            "flash",
            f"--voltage={VOLTAGE}",
            "--output=-",
            f"--address=0x{address:X}",
            f"--size=0x{len(payload):X}",
        ],
        check=True,
        stdout=subprocess.PIPE,
        env={
            **os.environ,
            "GLASGOW_OUT_OF_TREE_APPLETS": "I-am-okay-with-breaking-changes",
        },
    ).stdout

    if readback != payload:
        raise RuntimeError("Verification failed")

    logging.info("Verification succeeded")


def _parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--size", type=lambda s: int(s, 0), default=0x1000)

    return parser.parse_args()


if __name__ == "__main__":
    main()
