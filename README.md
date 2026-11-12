# tessy-unit-test — a DSH skill for TESSY 5.x unit testing

A [DeepSeek Harness](https://github.com/deepseek-ai) skill that drives the complete TESSY 5.x embedded-C
unit-test workflow from the agent: build module/interface, choose and configure normal or advanced stubs,
generate test cases per source branch, import with `tessycmd` and read back the result, run batches and
triage failures, measure and explain C0/C1 coverage, and independently review completeness.

Target setup: TESSY 5.x with Keil (ARMCC)/uVision, `tessycmd` available locally.

## What it covers

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

## Install

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

## Contents

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

## Notes

- The skill is written in Chinese, matching the TESSY project context it was developed in.
- Paths in the example configuration are placeholders; adjust them to your installation.
