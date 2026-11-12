"""按 JSON 规格生成 TESSY 测试用例 XLSX，可选导入并回读校验。

用法：
    python gen_cases.py --spec cases\\appl_calc_gear_lever.json [--import] [--verify]

JSON 规格（支持高级桩变量 / 普通桩桩体 / 多测试步）：

{
  "object": "appl_calc_gear_lever",
  "default_out": "*none*",          // 未显式断言的 OUT 变量默认值（*none* = 不校验）
  "cases": [
    {
      "name": "TC01_Center",
      "desc": "alpha=86 落在中心窗口：AppGearPose.x=ZERO(0)",
      "spec": "SW-REQ-017",
      "steps": [
        {
          "values": { "DAL_Get_Gear_HallData().alpha_angle": 86, "...": 0 },
          "expect": { "AppGearPose.x": 0 },
          "stubs":  { "DAL_Get_Gear_HallData": "GEAR_HALL_DATA_TYPE d; d.alpha_angle=86U; return d;" }
        }
      ]
    }
  ]
}

要点：
- 高级桩：写 "values"（变量名即导出 CSV 里的列名，如 `xxx()`、`xxx().member`）；
- 普通桩：写 "stubs"（函数名 -> 桩体 C 代码）；**不要同时写**，先确认桩类型；
- 多测试步：steps 内多元素，行号 tcN.1、tcN.2…，每步显式给跨步状态输入；
- IN 变量未写则填 0；OUT 变量未写则用 default_out（默认 *none*，即不校验）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import openpyxl

from tessy_common import (cfg, connect_sel, do_import, export, read_csv,
                          select_object, workdir)


def build(spec: dict, template: Path | None = None) -> Path:
    obj = spec["object"]
    select_object(obj)
    tpl = template or export("xlsx", obj, workdir("tpl"))
    wb = openpyxl.load_workbook(tpl)
    ws = wb["Values"]
    hdr = [c if c is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    dirs = [str(c if c is not None else "").lower() for c in next(ws.iter_rows(min_row=2, max_row=2, values_only=True))]
    pairs = [(h, d) for h, d in zip(hdr, dirs) if h]
    existing_in = [h for h, d in pairs if d == "i"]
    existing_out = [h for h, d in pairs if d == "o"]

    need_in, need_out = [], []
    for case in spec["cases"]:
        for step in case["steps"]:
            for k in step.get("values", {}):
                if k not in existing_in and k not in need_in:
                    need_in.append(k)
            for k in step.get("expect", {}):
                if k not in existing_out and k not in need_out:
                    need_out.append(k)
    cols = existing_in + need_in + existing_out + need_out
    dirmap = ["i"] * (len(existing_in) + len(need_in)) + ["o"] * (len(existing_out) + len(need_out))
    default_out = str(spec.get("default_out", "*none*"))

    ws.delete_rows(1, ws.max_row)
    ws.append([""] + cols)
    ws.append([""] + dirmap)

    stub_rows: list[list[str]] = []
    for ci, case in enumerate(spec["cases"], 1):
        for si, step in enumerate(case["steps"], 1):
            values = step.get("values", {})
            expect = step.get("expect", {})
            row = [f"tc{ci}.{si}"]
            for d, col in zip(dirmap, cols):
                if d == "i":
                    row.append(str(values.get(col, 0)))
                else:
                    row.append(str(expect.get(col, default_out)))
            ws.append(row)
            for fn, body in step.get("stubs", {}).items():
                stub_rows.append([str(ci), str(si - 1), fn, body])

    # Properties：每个测试用例一行（Test Step=0）
    ws2 = wb["Properties"]
    ws2.delete_rows(5, ws2.max_row)
    for ci, case in enumerate(spec["cases"], 1):
        ws2.append([str(ci), "0", "", case.get("name", f"TC{ci:02d}"),
                    case.get("desc", ""), case.get("spec", ""), case.get("comment", ""), ""])

    # Stubs：普通桩桩体
    ws3 = wb["Stubs"]
    ws3.delete_rows(5, ws3.max_row)
    for row in stub_rows:
        ws3.append(row)

    out = workdir("cases") / f"{obj}.xlsx"
    wb.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="JSON 用例规格文件")
    ap.add_argument("--template", help="可选：已导出的 xlsx 模板（默认自动导出）")
    ap.add_argument("--import", dest="do_import_flag", action="store_true", help="生成后导入 TESSY")
    ap.add_argument("--verify", action="store_true", help="导入后回读 CSV 校验")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = build(spec, Path(args.template) if args.template else None)
    print("generated: %s  cases=%d  steps=%d" % (out, len(spec["cases"]), sum(len(c["steps"]) for c in spec["cases"])))

    connect_sel()
    if args.do_import_flag:
        select_object(spec["object"])
        proc = do_import(out)
        print(f"import rc={proc.returncode} {((proc.stdout or '') + (proc.stderr or '')).strip()[:300]}")
        if proc.returncode != 0:
            raise SystemExit(1)
    if args.verify:
        select_object(spec["object"])
        csv_path = export("csv", spec["object"] + "_verify", workdir("verify"))
        names, dirs, rows = read_csv(csv_path)
        print("verify: columns=%d rows=%d" % (len(names), len(rows)))
        expect_rows = sum(len(c["steps"]) for c in spec["cases"])
        if len(rows) != expect_rows:
            print("WARN row count mismatch: expected %d, got %d" % (expect_rows, len(rows)))
        # 校验高级桩变量列是否都在
        for case in spec["cases"]:
            for step in case["steps"]:
                for k in step.get("values", {}):
                    if k not in names:
                        print("WARN missing IN column: %s" % k)
        print("first columns:", names[:8])


if __name__ == "__main__":
    main()

