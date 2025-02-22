import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from PIL import Image
from pytest import approx

TOLERANCE = 35

matplotlib.use("agg")


@pytest.mark.parametrize("corner", ["tt", "tt_mm"])
def test(corner: str, tmp_path: Path) -> None:
    results = tmp_path / "sim.txt"
    _run_simulation(corner, results)
    df = _parse_sim_results(results)

    assert df["i(vcc)"].abs().max() < 0.002

    # Find lowest value
    assert df.iloc[0]["i_rst_n"]
    assert df.iloc[0]["in"] == 0
    low = df.iloc[0]["pin_out"]
    assert isinstance(low, float)

    # Find highest value
    high = df[(df["in"] == 0xFF) & df["i_rst_n"]]["pin_out"].max()
    assert isinstance(high, float)

    step = (high - low) / 255

    edges = _edges(df)

    # Find the first clock after the reset is released
    next(t for e, t in edges if e and not df.loc[t]["i_rst_n"])
    next(t for e, t in edges if e and df.loc[t]["i_rst_n"])

    # Now, for each falling clock edge, test that the output analog value
    # is within the expected tolerance
    digital: list[Any] = []
    analog: list[Any] = []
    expected: list[Any] = []
    for edge, time in edges:
        if edge:
            continue

        digital.append(df.loc[time]["in"])
        analog.append(df.loc[time]["pin_out"])
        expected.append(low + digital[-1] * step)
        assert analog[-1] == approx(expected[-1], abs=TOLERANCE * step), time

    # Check that the *sampled* high value is pretty close to the real high value.
    # The sampled value may be smaller because of capacitance on the output.
    assert analog[digital.index(255)] == approx(high, abs=5 * step)

    # The LFSR doesn't output 0
    assert 0 not in digital
    digital.append(0)
    analog.append(low)
    expected.append(low)

    plt.scatter(digital, analog, s=1, label="Actual")
    plt.scatter(digital, expected, s=1, label="Expected")
    plt.xlabel("Digital")
    plt.ylabel("Analog")
    plt.legend()
    plt.savefig(tmp_path / "plot.png")

    image: Image.Image = Image.open(Path(__file__).parent / "ttlogo_400.png")
    image = image.point(lambda p: round((analog[digital.index(p)] - low) / step))
    image.save(tmp_path / "image.png")


def _edges(df: pd.DataFrame) -> Iterator[tuple[bool, float]]:
    prev_clk = False
    for time, row in df.iterrows():
        clk = row["i_clk"]
        if clk != prev_clk:
            assert isinstance(clk, bool)
            assert isinstance(time, float)
            yield clk, time
        prev_clk = clk


def _run_simulation(corner: str, results: Path) -> None:
    subprocess.run(
        ["ngspice", f"mixed_{corner}.cir"],
        env={**os.environ, "SIM_OUTPUT": str(results)},
        cwd=Path(__file__).parent,
        check=True,
    )


def _parse_sim_results(results: Path) -> pd.DataFrame:
    @dataclass
    class Column:
        name: str
        start: int
        end: int

    with open(results, mode="r", encoding="utf-8") as f:
        lines = iter(f)

        columns: list[Column] = []
        for m in re.finditer(r"\s(\S+)\s+(?=\s)", next(lines)):
            columns.append(Column(m.group(1), m.start(), m.end()))

        # Parse data into a list of lists: column -> list of floats
        data: list[list[float]] = [[] for _ in range(len(columns))]
        for line in lines:
            for i, column in enumerate(columns):
                column_str = line[column.start : column.end].strip()
                if column_str:
                    data[i].append(float(column_str))

    # Make DataFrames out of all signals. Index is the time, the column is the signal value.
    dfs: list[pd.DataFrame] = []
    for i in range(0, len(columns), 2):
        times = data[i]
        values = data[i + 1]
        dfs.append(
            pd.DataFrame(index=times, data=values, columns=[columns[i + 1].name])
        )

    # Pop the clock DataFrame out of the list
    (clk_df,) = (df for df in dfs if df.columns[0] == "i_clk")
    dfs.remove(clk_df)

    # Merge all other signals into a single DF.
    # Also make sure there are no missing values, since the analog part should be updated with the same time step.
    signals_df = pd.concat(dfs, axis="columns")
    assert not signals_df.isnull().values.any()

    # The clock will have duplicate index entries, because it rises and falls
    # instantaneously.
    # Keep only the last value of each duplicate timestamp.
    clk_df = clk_df[~clk_df.index.duplicated(keep="last")]

    df = pd.concat([clk_df, signals_df], axis="columns").sort_index().ffill()

    #
    # Convert i_clk and i_rst_n to boolean values, and concat the input bits to integers
    #

    def concat_bits(values: Iterable[float]) -> int:
        result = 0
        for v in values:
            result <<= 1
            result |= bool(v)
        return result

    df = pd.concat(
        [
            df["i_clk"].map(lambda v: bool(v)),
            df["i_rst_n"].map(lambda v: v >= 0.9),
            pd.DataFrame(
                df.loc[:, df.columns.str.startswith("a")].apply(
                    concat_bits, axis="columns"
                ),
                columns=["in"],
            ),
            df["pin_out"],
            df["i(vcc)"],
        ],
        axis="columns",
    )

    # All 256 unique byte values should be present.
    # 1-255 are generated by the LFSR.
    # 0 is the X value of Verilator, present before i_rst_n is asserted.
    assert len(df["in"].unique()) == 256

    return df
