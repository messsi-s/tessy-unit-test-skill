"""给"无分支直线调用"型对象批量填参数值 + 普通桩桩体，并回读 state_mask。

适用场景（BSP_Flash_UT / BSP_Eeprom_UT 这类）：
  函数只是 Unlock → 操作 → Lock 的顺序调用，没有分支；
  修复的难点只在**数据有效性**，不在用例设计。

前置（缺一不可，详见 references/ida-data-validity-playbook.md §2.1）：
  1. GUI 里每个对象做过 Test Data → Initialize Test Data (Ctrl+I)（Overwrite、全部用例）；
  2. 紧接着跑过一次模块级 `tessycmd analyze`（否则 mask 停在 0x80000088 不可执行）；
  3. 对象 mask 已含 0x1000。

用法：
    python fill_values_stubs.py plan.json
    python fill_values_stubs.py examples/bsp_eeprom_ut_fix.json

plan.json：
{
  "module": "BSP_Eeprom_UT",
  "objects": [
    {"object": "BSP_eeprom_Read",
     "values": [{"blockId": "0", "offset": "0", "dataBuffer": "NULL", "length": "8"},
                {"blockId": "1", "offset": "0", "dataBuffer": "NULL", "length": "0"}],
     "stubs": {"FLASH_Eeprom_Read": "return 0u;"}}
  ]
}

stubs 里的 body 按返回类型写：非 void → `return 0u;`，void → `(void)0;`。
填法说明：Value 列按表头名匹配；同名表头可能出现两次（input/output 两段），**全部**都会填。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tessy_common as tc  # noqa: E402


def find_tdb() -> Path | None:
    base = Path(os.environ.get("TESSY_PERSIST", r"D:\Demo_Tessytest\tessy\persist"))
    hits = glob.glob(str(base / "**" / "testobject.xml"), recursive=True)
    return Path(max(hits, key=os.path.getmtime)).parent.parent if hits else None


def read_masks(tdb: Path) -> dict[str, str]:
    res: dict[str, str] = {}
    for p in tdb.glob("*/testobject.xml"):
        t = p.read_text(encoding="utf-8", errors="replace")
        nm = re.search(r'<testobject[^>]*name="([^"]+)"', t)
        ob = re.search(r'<testobject[^>]*\sstate_mask="(0x[0-9A-Fa-f]+)"', t)
        if nm and ob:
            res[nm.group(1)] = ob.group(1)
    return res


def fill_object(obj: str, values: list[dict], stubs: dict[str, str]) -> None:
    tc.select_object(obj)
    xlsx = tc.export("xlsx", obj)
    wb = openpyxl.load_workbook(xlsx)

    ws = wb["Values"]
    cols: dict[str, list[int]] = {}
    for c in range(1, ws.max_column + 1):
        name = ws.cell(1, c).value
        if name:
            cols.setdefault(str(name), []).append(c)
    for i, row in enumerate(values):
        r = 3 + i
        if not ws.cell(r, 1).value:
            continue
        for key, val in row.items():
            for c in cols.get(key, []):
                ws.cell(r, c).value = val

    st = wb["Stubs"]
    if st.max_row >= 4:
        hdr = {str(st.cell(4, c).value): c for c in range(1, st.max_column + 1) if st.cell(4, c).value}
        if "Stub" in hdr and "Stub Body" in hdr:
            for r in range(5, st.max_row + 1):
                name = st.cell(r, hdr["Stub"]).value
                if not name:
                    continue
                body = stubs.get(str(name).strip())
                if body is not None:
                    st.cell(r, hdr["Stub Body"]).value = body

    wb.save(xlsx)
    print(f"[{obj}] import: {tc.out(tc.do_import(xlsx))[:120] or 'ok'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan_json")
    a = ap.parse_args()
    spec = json.loads(Path(a.plan_json).read_text(encoding="utf-8"))
    if spec.get("module"):
        tc.cfg["module"] = spec["module"]  # tessy_common 已加载，直接改运行时配置
    for item in spec["objects"]:
        fill_object(item["object"], item.get("values", []), item.get("stubs", {}))
    tdb = find_tdb()
    masks = read_masks(tdb) if tdb else {}
    for item in spec["objects"]:
        obj = item["object"]
        m = masks.get(obj, "?")
        ok = "1000" in m.lower()
        print(f"[mask] {obj}: {m} -> {'OK 可执行' if ok else '不可执行（Ctrl+I + analyze 没做全，见 playbook §2.1）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
