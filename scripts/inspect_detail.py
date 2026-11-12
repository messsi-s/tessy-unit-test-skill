"""Export an object's details XML and print failed cases' expected vs actual.

Usage:
    python inspect_detail.py                       # all objects
    python inspect_detail.py appl_get_gearshift_position
    python inspect_detail.py --all                 # include not-executed cases

Reading the result:
    notok        -> executed but assertion mismatch: fix expected values / data
    notexecuted  -> not run / result invalid: stale analysis, invalid stub data (not executable),
                    or execution environment problem
"""
from __future__ import annotations

import re
import sys

from tessy_common import connect_sel, export, list_objects, select_object, workdir


def show(obj: str) -> None:
    select_object(obj)
    text = export("xml", obj + "_detail", workdir("detail")).read_text(encoding="utf-8", errors="replace")
    stat = re.search(r'<statistic ([^/]*)/>', text)
    m = re.search(r'<testobject[^>]*success="([^"]*)"', text)
    print("=" * 78)
    print("OBJECT %s  %s" % (obj, stat.group(1) if stat else ""))
    print("  testobject success=%s" % (m.group(1) if m else "?"))
    for cm in re.finditer(r'<testcase ([^>]*)>(.*?)</testcase>', text, re.S):
        attrs, body = cm.group(1), cm.group(2)
        name = re.search(r'name="([^"]*)"', attrs)
        succ = re.search(r'success="([^"]*)"', attrs)
        name = name.group(1) if name else "?"
        succ = succ.group(1) if succ else "?"
        if succ == "ok":
            continue
        print("  %s -> %s" % (name, succ))
        for rm in re.finditer(r'<result ([^/]*)/>', body):
            r = rm.group(1)
            s = re.search(r'success="([^"]*)"', r)
            if not s or s.group(1) == "ok":
                continue
            nm = re.search(r'name="([^"]*)"', r)
            ex = re.search(r'expected_value="([^"]*)"', r)
            ac = re.search(r'actual_value="([^"]*)"', r)
            print("      %s: expected=%s actual=%s" % (
                nm.group(1) if nm else "?", ex.group(1) if ex else "?", ac.group(1) if ac else "?"))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    objects = args or list_objects()
    connect_sel()
    for obj in objects:
        show(obj)


if __name__ == "__main__":
    main()
