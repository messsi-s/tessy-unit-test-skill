"""Export and print each test object's interface (IN/OUT) and stub types.

Usage:
    python inspect_interface.py                 # all objects
    python inspect_interface.py appl_a appl_b   # given objects

Data sources:
    CSV export   -> interface variable names + direction (i/o)
    details XML  -> interfaceReport with stub="advanced|normal|none" and passing

Note: CSV may only list advanced-stub variables that already have values in test data;
trust the details XML for stub type.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from tessy_common import connect_sel, export, list_objects, read_csv, select_object, workdir


def stub_info(detail_xml: Path) -> list[tuple[str, str]]:
    text = detail_xml.read_text(encoding="utf-8", errors="replace")
    found = re.findall(r'name="([^"]+)"\s+stub="(advanced|normal)"', text)
    seen, result = set(), []
    for name, kind in found:
        if name not in seen:
            seen.add(name)
            result.append((name, kind))
    return result


def main() -> None:
    objects = sys.argv[1:] or list_objects()
    connect_sel()
    dump = workdir("inspect")
    for obj in objects:
        select_object(obj)
        csv_path = export("csv", obj, dump)
        names, dirs, rows = read_csv(csv_path)
        try:
            stubs = stub_info(export("xml", obj + "_detail", dump))
        except Exception:
            stubs = []
        print("=" * 78)
        print("OBJECT %s  cases=%d" % (obj, len(rows)))
        print("  stub config:")
        if not stubs:
            print("    (no stub)")
        for name, kind in stubs:
            print("    [%s] %s" % (kind, name))
        ins = [n for n, d in zip(names, dirs) if d == "i"]
        outs = [n for n, d in zip(names, dirs) if d == "o"]
        print("  IN (%d):" % len(ins))
        for n in ins:
            print("    %s" % n)
        print("  OUT (%d):" % len(outs))
        for n in outs:
            print("    %s" % n)
        adv = [(n, d) for n, d in zip(names, dirs) if "()" in n]
        print("  advanced stub vars: %s" % (adv or "-"))


if __name__ == "__main__":
    main()
