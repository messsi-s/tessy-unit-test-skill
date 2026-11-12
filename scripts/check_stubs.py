"""Check whether given functions are configured as advanced / normal stubs.

Usage:
    python check_stubs.py appl_gear_control_task DAL_Tim_CheckTimeOut DAL_Tim_GetCurrentTime
    python check_stubs.py appl_calc_gear_lever_pos appl_get_gear_position

Reading the result:
    advanced : put values into the Values sheet variables (see SKILL.md 3.2), no stub body
    normal   : write C stub body in the Stubs sheet
    none     : no stub data needed
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from tessy_common import connect_sel, export, select_object, workdir


def interface_report(detail_xml: Path) -> str:
    text = detail_xml.read_text(encoding="utf-8", errors="replace")
    i = text.find("<interfaceReport>")
    return text[i:] if i >= 0 else text


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    obj, funcs = sys.argv[1], sys.argv[2:]
    connect_sel()
    select_object(obj)
    text = interface_report(export("xml", obj + "_stubchk", workdir("stubchk")))
    print("OBJECT %s" % obj)
    for fn in funcs:
        m = re.search(r'name="([^"]*\b%s\s*\([^"]*\))"\s+stub="(advanced|normal)"' % re.escape(fn), text)
        if m:
            kind = m.group(2)
            if kind == "advanced":
                vars_found = re.findall(
                    r'name="([^"]*\b%s\(\)[^"]*)"\s+passing="(IN|OUT|INOUT|IRRELEVANT)"' % re.escape(fn), text)
                vars_txt = ", ".join("%s(%s)" % (n, d) for n, d in vars_found) or "not expanded yet"
                print("  %-34s -> advanced  vars: %s" % (fn, vars_txt))
            else:
                print("  %-34s -> normal    write stub body in Stubs sheet" % fn)
        else:
            print("  %-34s -> none      no stub data needed" % fn)
    print("\nadvanced: return value and parameters need values in test data (parameters are checked);"
          " normal: write C stub body in the Stubs sheet.")


if __name__ == "__main__":
    main()
