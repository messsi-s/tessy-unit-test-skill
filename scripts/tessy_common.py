"""TESSY 单元测试脚本公共层。

配置来源（优先级从高到低）：
1. 环境变量；
2. 技能目录下的 tessy_config.json（可选，便于固定本机路径）；
3. 内置默认值（贴合本机 TESSY 5.1.10 + uVision 安装）。

用法示例：
    from tessy_common import cfg, run, connect_sel, export, do_import
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

DEFAULTS = {
    "tessy_bin": r"D:\tessy\TESSY_5.1\bin",
    "project": "Demo_test",
    "collection": "New Test Collection",
    "module": "demo_gear",
    "work": os.path.join(os.environ.get("TEMP", "."), "tessy_ut"),
}


def load_config() -> dict:
    conf = dict(DEFAULTS)
    skill_conf = Path(__file__).resolve().parent.parent / "tessy_config.json"
    if skill_conf.exists():
        conf.update(json.loads(skill_conf.read_text(encoding="utf-8")))
    env_map = {
        "TESSY_BIN": "tessy_bin",
        "TESSY_PROJECT": "project",
        "TESSY_COLLECTION": "collection",
        "TESSY_MODULE": "module",
        "TESSY_WORK": "work",
    }
    for env, key in env_map.items():
        if os.environ.get(env):
            conf[key] = os.environ[env]
    return conf


cfg = load_config()


def cmd() -> str:
    return os.path.join(cfg["tessy_bin"], "tessycmd.exe")


def workdir(*parts: str) -> Path:
    p = Path(cfg["work"]).joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def run(*args: str, check: bool = False, timeout: int = 900) -> subprocess.CompletedProcess:
    """调用 tessycmd，返回 CompletedProcess；默认不抛异常，由调用方判断 returncode。"""
    proc = subprocess.run([cmd(), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"tessycmd {' '.join(args)} failed rc={proc.returncode}\n"
                           f"{(proc.stdout or '') + (proc.stderr or '')}")
    return proc


def out(proc: subprocess.CompletedProcess) -> str:
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def connect_sel(select_module: bool = True) -> None:
    run("connect")
    run("select-test-collection", cfg["collection"])
    if select_module:
        run("select-module", "-test-collection", cfg["module"])


def select_object(name: str) -> None:
    connect_sel()
    run("select-test-object", name)


def export(fmt: str, name: str, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or workdir("export"))
    run("export", "-format", fmt, "-file", name, str(out_dir))
    suffix = {"xlsx": ".xlsx", "csv": ".csv", "xml": ".xml", "txt": ".txt"}.get(fmt, "")
    p = out_dir / (name + suffix)
    if not p.exists():
        raise RuntimeError(f"export 未生成文件: {p}")
    return p


def do_import(xlsx_path: Path) -> subprocess.CompletedProcess:
    return run("import", str(xlsx_path))


def list_objects() -> list[str]:
    connect_sel()
    proc = run("list-test-objects")
    return [x.strip() for x in (proc.stdout or "").replace("\r", "").split("\n") if x.strip()]


def read_csv(path: Path) -> tuple[list[str], list[str], list[list[str]]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return [], [], []
    names = lines[0].split(";")[1:]
    dirs = lines[1].split(";")[1:] if len(lines) > 1 else []
    rows = [ln.split(";")[1:] for ln in lines[2:] if ln.strip()]
    return names, dirs, rows


def advanced_stub_vars(names: list[str], dirs: list[str]) -> list[tuple[str, str]]:
    """CSV 接口中形如 xxx() / xxx().member 的高级桩变量。"""
    return [(n, d) for n, d in zip(names, dirs) if "()" in n]
