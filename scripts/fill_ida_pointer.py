"""把「指针参数 + IDA 变量」的分支取值批量写进 TESSY 测试数据。

前置条件（缺一不可，详见 references/ida-data-validity-playbook.md）：
  1. TIE 中已给指针参数建好 IDA 变量（Pointer Target = Global Variable，类型=结构体）；
  2. Analyze 之后在 TDE 做过 Test Data → Initialize Test Data (Ctrl+I)（Overwrite、全部用例）；
  3. 对象此刻是可执行状态（state_mask 含 0x1000）。

本脚本只做：export xlsx → 改 Values 单元格 → import xlsx → 回读 state_mask 校验。
**xlsx 导入不会破坏数据有效性；script 导入会。**

用法：
    python fill_ida_pointer.py plan.json
    python fill_ida_pointer.py --object CAN_Controller_Rx_handler --target target_canMsg \
        --cases '[{"msgId":"0x758","dataLen":8},{"msgId":"0x67E","dataLen":0}]'

plan.json 格式：
{
  "object": "CAN_Controller_Rx_handler",
  "pointer": "canMsg",               # 可选，默认 canMsg
  "target":  "target_canMsg",        # IDA 变量名，必须与该对象 <var nam=...> 完全一致
  "plan": [                          # 按测试用例顺序，一条一个 dict
     {"msgId": "0x758", "dataLen": 8, "judge_diag_frame_flag": "1"},
     {"msgId": "0x67E", "dataLen": 0}
  ]
}
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


def find_testobject_xml() -> Path | None:
    """在 persist 目录里找最近一次写过的 testobject.xml 所在 tdb。"""
    base = Path(os.environ.get("TESSY_PERSIST", r"D:\T1V_Tessytest\tessy\persist"))
    hits = [p for p in glob.glob(str(base / "**" / "testobject.xml"), recursive=True)]
    if not hits:
        return None
    return Path(max(hits, key=os.path.getmtime))


def read_masks(xml: Path) -> dict[str, tuple[str, str]]:
    """返回 {对象名: (对象 state_mask, testcase[0] state_mask)}，仅同目录的兄弟对象。"""
    res: dict[str, tuple[str, str]] = {}
    for p in xml.parent.parent.glob("*/testobject.xml"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        nm = re.search(r'<testobject[^>]*name="([^"]+)"', t)
        ob = re.search(r'<testobject[^>]*\sstate_mask="(0x[0-9A-Fa-f]+)"', t)
        tcm = re.search(r'<testcase[^>]*\sstate_mask="(0x[0-9A-Fa-f]+)"', t)
        if nm and ob:
            res[nm.group(1)] = (ob.group(1), tcm.group(1) if tcm else "n/a")
    return res


def object_var_name(xml: Path, obj: str) -> str | None:
    """从对象导出的 details XML 里取 IDA 变量真实名字（模块内可能不同！）。"""
    p = Path(tc.cfg["work"]) / "export" / f"{obj}.xml"
    if not p.exists():
        tc.select_object(obj)
        p = tc.export("xml", obj)
    t = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<var\b[^>]*\bnam="([^"]+)"', t)
    return m.group(1) if m else None


def fill(obj: str, target: str, pointer: str, plan: list[dict]) -> Path:
    tc.select_object(obj)
    xlsx = tc.export("xlsx", obj)
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Values"]
    cols: dict[str, list[int]] = {}
    for c in range(1, ws.max_column + 1):
        name = ws.cell(1, c).value
        if name:
            cols.setdefault(str(name), []).append(c)  # 同名列可能出现两次（in/out 两段）
    if "canMsg" not in cols and pointer not in cols:
        raise SystemExit(f"数据模型里没有 {pointer} 列 → 说明没做 Ctrl+I，见脚本头注释前置条件 2")
    if f"{target}.msgId" not in cols:
        raise SystemExit(f"数据模型里没有 {target}.msgId 列 → IDA 变量名不对，或未做 Ctrl+I")

    def put(row: int, col: str, val):
        for c in cols.get(col, []):
            ws.cell(row, c).value = val

    data_keys = [k for k in cols if ".data[" in k]
    for i, spec in enumerate(plan):
        r = 3 + i
        if not ws.cell(r, 1).value:
            continue
        put(r, pointer, target)                       # 指针值 = IDA 变量名，不是地址
        for key, val in spec.items():
            put(r, f"{target}.{key}", str(val))
        for k in ("cs",):
            put(r, f"{target}.{k}", "0")
        for col in data_keys:
            put(r, col, "0")
    wb.save(xlsx)
    res = tc.out(tc.do_import(xlsx))
    print(f"[import] {obj}: {res[:160] or 'ok'}")
    return xlsx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan_json", nargs="?")
    ap.add_argument("--object")
    ap.add_argument("--pointer", default="canMsg")
    ap.add_argument("--target")
    ap.add_argument("--cases", help="JSON 数组，按测试用例顺序")
    a = ap.parse_args()

    if a.plan_json:
        spec = json.loads(Path(a.plan_json).read_text(encoding="utf-8"))
        obj = spec["object"]
        target = spec.get("target")
        pointer = spec.get("pointer", "canMsg")
        plan = spec["plan"]
    else:
        if not (a.object and a.cases):
            ap.error("需要 plan.json 或 --object + --cases")
        obj, target, pointer = a.object, a.target, a.pointer
        plan = json.loads(a.cases)

    xml = find_testobject_xml()
    if target is None:
        target = object_var_name(xml, obj) if xml else None
        if not target:
            ap.error("未能自动取到 IDA 变量名，请用 --target 指定（export -format xml 查 <var nam=...>）")
        print(f"[auto] {obj} 的 IDA 变量名 = {target}")

    fill(obj, target, pointer, plan)

    xml = find_testobject_xml()
    masks = read_masks(xml) if xml else {}
    m = masks.get(obj)
    if m:
        ok = ("1000" in m[0].lower())
        print(f"[mask] {obj}: object={m[0]} testcase={m[1]} -> "
              f"{'OK 可执行' if ok else '不可执行（回到 playbook §3.2 做 Ctrl+I）'}")
    else:
        print("[mask] 未读到 testobject.xml，请手工确认 state_mask 含 0x1000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
