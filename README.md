# tessy-unit-test — a DSH skill for TESSY 5.x unit testing

[English](#english) | [中文](#中文)

---

<a id="english"></a>
## English

### Overview

A [DeepSeek Harness](https://github.com/deepseek-ai) skill that drives the complete TESSY 5.x embedded-C
unit-test workflow from the agent: build module/interface, choose and configure normal or advanced stubs,
generate test cases per source branch, import with `tessycmd` and read back the result, run batches and
triage failures, measure and explain C0/C1 coverage, and independently review completeness.

Target setup: TESSY 5.x with armcc/uVision, `tessycmd` available locally.

### What it covers

- **Module and interface setup** — creating a TESSY module/interface for a `.c` file, data types, port
  interface, expected/actual value handling.
- **Stubbing** — when to use a normal stub vs an advanced stub, request/response templates, passing data
  through stubs, and the common stub-configuration pitfalls.
- **Case generation** — deriving test cases from source branches (`gen_cases.py`), data-model checks,
  pointer/IDA handling.
- **Import and read-back** — importing generated cases through `tessycmd`, verifying what TESSY actually
  stored, and repairing mismatches.
- **Batch execution and triage** — `run_batch.py`, failure classes (UVSC / "Target not defined" /
  "not executable"), coverage collection, and coverage-gap explanations.
- **Independent review** — completeness and coverage checklists for delivered test sets.

### Install

Copy or clone this directory into a DSH skill directory, named `tessy-unit-test`:

| Scope | Path |
|---|---|
| user | `~/.dsh/skills/tessy-unit-test/` |
| project | `<project>/.dsh/skills/tessy-unit-test/` |

```bash
git clone https://github.com/messsi-s/tessy-unit-test-skill.git ~/.dsh/skills/tessy-unit-test
```

Configuration: copy `tessy_config.example.json`, point `tessy_bin` at your `tessycmd` directory and set the
TESSY project/collection/module and a work directory (or export `TESSY_BIN` etc.). No credentials are stored
in this repository.

### Contents

```
SKILL.md                            skill instructions (frontmatter + full workflow)
references/tessy-cmd-reference.md   tessycmd command reference
references/interface-passing-and-import.md  interface, passing and import details
references/ida-data-validity-playbook.md    IDA data-validity test construction
references/stub-request-template.md stubs and request templates
references/pitfalls.md              recurring TESSY pitfalls and fixes
references/ops-backup-recovery.md   backup/recovery and TESSY instance operations
references/coverage-review-checklist.md     coverage review checklist
references/completeness-review-checklist.md completeness review checklist
scripts/*.py                        helper scripts (inspect, generate, fill, run batch, check)
examples/*.json                     example case/config data
tessy_config.example.json           configuration template
```

### Notes

- The skill is written in Chinese, matching the TESSY project context it was developed in.
- Paths in the example configuration are placeholders; adjust them to your installation.

---

<a id="中文"></a>
## 中文

### 简介

这是一个 [DeepSeek Harness](https://github.com/deepseek-ai) skill：让模型完整跑通 TESSY 5.x 嵌入式 C 单元
测试流程——建模块/接口、选择与配置普通桩或高级桩、按源码分支生成测试用例、用 `tessycmd` 导入并回读校验、
批处理执行与失败分诊、测量并解释 C0/C1 覆盖率、以及对交付用例做独立复核（覆盖度/完整度）。

目标环境：TESSY 5.x + armcc/uVision，本机可用 `tessycmd`。

### 覆盖内容

- **模块与接口搭建** —— 为 `.c` 文件创建 TESSY 模块/接口、数据类型、端口接口、期望值与实际值处理。
- **打桩** —— 普通桩与高级桩的选择、请求/响应模板、通过桩传递数据，以及常见的桩配置坑位。
- **用例生成** —— 按源码分支推导用例（`gen_cases.py`）、数据模型检查、指针/IDA 处理。
- **导入与回读** —— 用 `tessycmd` 导入生成的用例，回读 TESSY 实际存了什么，并修正不一致。
- **批量执行与分诊** —— `run_batch.py`、失败分类（UVSC / “Target not defined” / “not executable”）、
  覆盖率收集与覆盖缺口解释。
- **独立复核** —— 针对交付用例的完整性与覆盖率检查清单。

### 安装

把本目录复制或克隆到 DSH 的 skill 目录，目录名用 `tessy-unit-test`：

| 作用域 | 路径 |
|---|---|
| 用户级 | `~/.dsh/skills/tessy-unit-test/` |
| 项目级 | `<项目>/.dsh/skills/tessy-unit-test/` |

```bash
git clone https://github.com/messsi-s/tessy-unit-test-skill.git ~/.dsh/skills/tessy-unit-test
```

配置：复制 `tessy_config.example.json`，把 `tessy_bin` 指到你的 `tessycmd` 目录，设置 TESSY 的
project/collection/module 和工作目录（也可用 `TESSY_BIN` 等环境变量）。本仓库不保存任何凭据。

### 目录结构

```
SKILL.md                            skill 指令（frontmatter + 完整工作流）
references/tessy-cmd-reference.md   tessycmd 命令参考
references/interface-passing-and-import.md  接口、数据传入与导入细节
references/ida-data-validity-playbook.md    IDA 数据有效性用例构造
references/stub-request-template.md 桩与请求模板
references/pitfalls.md              常见 TESSY 坑位与修复
references/ops-backup-recovery.md   备份/恢复与 TESSY 实例操作
references/coverage-review-checklist.md     覆盖率复核清单
references/completeness-review-checklist.md 完整性复核清单
scripts/*.py                        辅助脚本（检查、生成、填充、批处理、校验）
examples/*.json                     用例/配置示例数据
tessy_config.example.json           配置模板
```

### 说明

- 技能正文为中文，与它诞生时的 TESSY 项目语境一致。
- 示例配置里的路径都是占位符，请按你的实际安装调整。
