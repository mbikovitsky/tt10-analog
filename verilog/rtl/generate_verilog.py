#!/usr/bin/env python3

import argparse
import importlib
import importlib.util
import inspect
import re
import subprocess
import sys
import types
from types import SimpleNamespace
from typing import Any, TypeVar

import amaranth.lib.wiring as wiring
from amaranth import ClockDomain, Elaboratable, Module
from amaranth.back import rtlil
from amaranth.lib.wiring import Component, In, Signature

_T = TypeVar("_T")


class Wrapper(Component):  # type: ignore[misc]
    def __init__(
        self,
        wrapped: Any,
        *,
        async_reset: bool,
        active_low_reset: bool,
    ) -> None:
        if not hasattr(wrapped, "signature") or not isinstance(
            wrapped.signature, Signature
        ):
            raise TypeError(f"Type {type(wrapped)} is missing a signature")

        rst_name = "rst_n" if active_low_reset else "rst"

        if not wrapped.signature.members.keys().isdisjoint({"clk", rst_name}):
            raise TypeError(f"Type {type(wrapped)} defines `clk` and `{rst_name}`")

        super().__init__(
            {
                "clk": In(1),
                rst_name: In(1),
                **wrapped.signature.members,
            }
        )

        self._wrapped = wrapped
        self._async_reset = async_reset
        self._active_low_reset = active_low_reset

    def elaborate(self, platform: Any) -> Module:
        m = Module()

        m.domains.sync = cd_sync = ClockDomain(
            local=True,
            async_reset=self._async_reset,
        )
        assert cd_sync.rst is not None
        m.d.comb += [
            cd_sync.clk.eq(self.clk),
            cd_sync.rst.eq((~self.rst_n) if self._active_low_reset else self.rst),
        ]

        wrapped_signals = SimpleNamespace(
            signature=self._wrapped.signature,
            **{
                member: getattr(self, member)
                for member in self._wrapped.signature.members
            },
        )
        m.submodules.wrapped = self._wrapped
        wiring.connect(m, wiring.flipped(wrapped_signals), self._wrapped)

        return m


def _main() -> None:
    args = _parse_command_line()

    module = importlib.import_module(args.python_module)
    if args.python_class:
        klass = getattr(module, args.python_class)
        assert issubclass(klass, Elaboratable)
        elaboratable = klass
    else:
        elaboratable = _get_cls_from_module(module, Elaboratable)

    verilog_module_name = args.verilog_module_name
    if not verilog_module_name:
        verilog_module_name = re.sub(
            # https://stackoverflow.com/a/1176023/851560
            r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])",
            "_",
            elaboratable.__name__,
        ).lower()

    instance = elaboratable()
    if args.async_reset or args.active_low_reset:
        instance = Wrapper(
            instance,
            async_reset=args.async_reset,
            active_low_reset=args.active_low_reset,
        )

    yosys_il = rtlil.convert(instance, verilog_module_name)

    if args.no_init:
        # Remove the \init attribute from the IL.
        # This way we can correctly simulate X values in 4-state simulators.
        yosys_il = re.sub(
            r"^\s*attribute\s+\\init.+$",
            "",
            yosys_il,
            flags=re.MULTILINE,
        )

    # Script adapted from the code in amaranth.back.verilog
    # -sv is used to avoid this workaround: https://github.com/YosysHQ/yosys/pull/2273
    # Synthesis should get rid of it, but I don't think it's "nice" to rely on that.
    yosys_script = f"""
read_rtlil <<rtlil
{yosys_il}
rtlil

proc -nomux -norom
memory_collect

write_verilog -norename -sv
"""

    result = subprocess.run(
        [sys.executable, "-m", "amaranth_yosys", "-q", "-"],
        input=yosys_script,
        encoding="utf=8",
        capture_output=True,
        check=True,
    )
    print(result.stdout)


def _parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "python_module", help="Python module containing the Amaranth class to convert."
    )
    parser.add_argument(
        "--python-class",
        help=(
            "Amaranth class to convert. Must derive from Elaboratable. "
            "Must be constructible without arguments. If unspecified, "
            "the imported module must have exactly one Elaboratable-derived class, "
            "which will be used."
        ),
    )
    parser.add_argument(
        "--verilog-module-name",
        help=(
            "Name of the output Verilog module. "
            "If unspecified, the name of the Amaranth class will be used, "
            "after conversion to snake case."
        ),
    )
    parser.add_argument(
        "--no-init", action="store_true", help="Do not power-on-reset signals"
    )
    parser.add_argument(
        "--async-reset",
        action="store_true",
        help="Use an async reset for the module's `sync` domain",
    )
    parser.add_argument(
        "--active-low-reset",
        action="store_true",
        help="Use an active-low reset for the module's `sync` domain",
    )

    return parser.parse_args()


def _get_cls_from_module(module: types.ModuleType, cls: type[_T]) -> type[_T]:
    candidates = tuple(
        item
        for item in module.__dict__.values()
        if (
            inspect.isclass(item)
            and issubclass(item, cls)
            and item is not cls
            and item.__module__ == module.__name__  # Ignore imported classes
        )
    )
    if not candidates:
        raise RuntimeError(
            f"No {cls.__name__}-derived class found in {module.__name__}"
        )
    if len(candidates) > 1:
        raise RuntimeError(
            f"More than one {cls.__name__}-derived class found in {module.__name__}"
        )
    return candidates[0]


if __name__ == "__main__":
    _main()
