"""生成批处理 tbs、执行模块、解析报告并打印每个对象的通过/失败/未执行统计。

用法：
    python run_batch.py                                    # 默认执行整个测试集合
    python run_batch.py --collection "New Test Collection"
    python run_batch.py --instrumentation TESTOBJECT_ONLY --report-name Gear_UT
    python run_batch.py --tbs my.tbs --out reports        # 直接跑已有 tbs

注意：
- <elements> 只用 <testcollection>；<testobject>/<module> 会被 TESSY 静默忽略（报告 total=0）。
- 执行前确认没有 GUI 并发执行，且无残留 UV4/exp/tthd 进程。
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from tessy_common import cfg, connect_sel, run, workdir

TBS = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<batchtest>
  <operations>
    <operation key="executeTest">
      <options>
        <option key="checkInterface" value="true"/>
        <option key="generateDriver" value="true"/>
        <option key="run" value="true"/>
        <option key="createNewTestRun" value="true"/>
        <option key="instrumentationType" value="{instrumentation}"/>
        <option key="defaultCoverage" value="true"/>
        <option key="defaultCoveragePerTestObject" value="false"/>
        <option key="abortOnMissingStubCode" value="false"/>
      </options>
    </operation>
    <operation key="generateBatchReport">
      <options>
        <option key="reportOutputDirectory" value="{report_dir}"/>
        <option key="reportFileNamePattern" value="{report_name}"/>
        <option key="reportOutputFormat" value="xml"/>
      </options>
      <arguments>
        <argument name="OPT_TESTDATA_ONLY_MODE" value="false"/>
        <argument name="OPT_SHOW_SUMMARY" value="true"/>
        <argument name="OPT_SHOW_PROJECT_ITEMS" value="true"/>
        <argument name="OPT_SHOW_TEST_OBJECT_LIST" value="true"/>
      </arguments>
    </operation>
  </operations>
  <elements>
    <testcollection name="{collection}"/>
  </elements>
  <settings>
    <setting key="reportLogoImage" value=""/>
    <setting key="reportTemplatePath" value=""/>
  </settings>
</batchtest>
"""


def parse_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<report[^>]*success=\"([^\"]*)\"", text)
    print("report: %s\noverall: %s" % (path, m.group(1) if m else "?"))
    stat = re.search(r"<statistic ([^/]*)/>", text)
    print("summary:", stat.group(1) if stat else "?")
    for tm in re.finditer(r"<tessyobject[^>]*type=\"testobject\"[^>]*name=\"([^\"]+)\"(.*?)</tessyobject>", text, re.S):
        name, body = tm.group(1), tm.group(2)
        st = re.search(r"<testcase_statistics ([^/]*)/>", body)
        if st:
            print(f"  {name:<44} {st.group(1)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tbs", help="已有 tbs 路径")
    ap.add_argument("--out", help="报告输出目录")
    ap.add_argument("--collection", default=cfg["collection"])
    ap.add_argument("--instrumentation", default="NONE",
                    choices=["NONE", "TESTOBJECT_ONLY", "CALLED_FUNCTIONS"])
    ap.add_argument("--report-name", default="Tessy_UT_Report")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else workdir("reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    connect_sel()
    if args.tbs:
        tbs = Path(args.tbs)
    else:
        tbs = workdir("run") / "run.tbs"
        tbs.write_text(TBS.format(instrumentation=args.instrumentation, report_dir=out_dir,
                                  report_name=args.report_name, collection=args.collection),
                       encoding="utf-8")
    print("executing: %s" % tbs)
    proc = run("exec-test", "-o", str(out_dir), str(tbs))
    print(f"exec rc={proc.returncode}")
    report = out_dir / f"{args.report_name}.xml"
    if report.exists():
        parse_report(report)
    else:
        print("no report generated; check execution logs under %USERPROFILE%\\.tessy_51_workspace\\.metadata\\execution\\")


if __name__ == "__main__":
    main()

