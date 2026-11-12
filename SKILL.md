---
name: tessy-unit-test
description: >
  TESSY 5.x 嵌入式 C 单元测试全流程技能：建模块/接口、普通桩与高级桩的选择与配置、
  按源码分支生成测试用例、用 tessycmd 导入并回读校验、批处理执行与失败分诊、
  覆盖率(C0/C1)测量与缺口解释、独立复核（覆盖度/完整度）。适用于 armcc/uVision
  目标，也适用于需要用 TESSY 做单元测试用例交付的场景。
whenToUse: >
  当用户要求"用 TESSY 做单元测试""给 xx.c 写单元测试用例并导入 TESSY""补全/审查 TESSY 用例"
  "分析 TESSY 覆盖率为什么低""解决 TESSY 执行报错(UVSC/Target not defined/not executable)"
  时加载本技能。不用于纯手工测试用例编写（用 test-case-writing）、接口/UI 自动化。
---

# TESSY 单元测试技能包

面向 **TESSY 5.1.x + armcc/uVision** 的可复用操作手册。核心原则只有一句：

> **先用 `tessycmd` 看清"真实接口 + 桩类型"，再生成数据；生成后必须回读校验、执行验证。**

本技能把踩过的坑固化成流程，避免重复：**桩类型判错、期望值算错、Analyze 顺序错、导入静默丢列、独立执行状态语义错**。

---

## 0. 前置：定位工具与项目（不要硬编码）

| 变量 | 含义 | 示例 |
|---|---|---|
| `TESSY_BIN` | tessycmd 所在目录 | `D:\tessy\TESSY_5.1\bin` |
| `TESSY_CMD` | tessycmd 全路径 | `%TESSY_BIN%\tessycmd.exe` |
| `TESSY_PROJECT` | 工程名 | `Demo_test` |
| `TESSY_COLLECTION` | 测试集合名 | `New Test Collection` |
| `TESSY_MODULE` | 模块名 | `demo_gear` |
| `PY` | 带 openpyxl 的 python | `D:\PythonProject\.venv\Scripts\python.exe` |
| `WORK` | 临时工作目录 | `%TEMP%\tessy_ut` |

环境体检（每次开工先跑）：

```powershell
# 1) TESSY 是否在跑（GUI 在跑才能用 tessycmd）
Get-Process TESSY -ErrorAction SilentlyContinue | Select-Object Id,MainWindowTitle
# 2) 是否有残留执行进程（会抢 uVision/调试口）
Get-Process UV4,exp,tthd -ErrorAction SilentlyContinue
# 3) 连接 + 选择上下文
& $TESSY_CMD connect
& $TESSY_CMD select-test-collection $TESSY_COLLECTION
& $TESSY_CMD select-module -test-collection $TESSY_MODULE
& $TESSY_CMD which          # 确认当前选中链
& $TESSY_CMD list-test-objects
```

> ⚠️ TESSY GUI 必须通过 `explorer.exe "…\TESSY.exe"` 启动；用脚本/任务计划启动会出现 `CreateProcess failed with error 5`。

---

## 1. 流程总览（严格按顺序）

```
P0 环境体检
P1 模块准备（源文件/include/define/排除列表/analyze）
P2 接口与桩（判断普通桩 or 高级桩；必要时请用户建桩）
P3 从源码生成用例（分支驱动、期望值现算）
P4 导入 + 回读校验
P5 批处理执行 + 失败分诊
P6 覆盖度/完整度独立复核
P7 覆盖率(C0/C1)统计与缺口解释
P8 交付物与文档
```

**顺序铁律**：任何"改 TIE / 改源码 / 改 uVision 工程 / 改环境属性"之后，都要
`analyze` → 再导入用例 → 再执行。**先导入后 Analyze 会把普通桩桩体清空**，用例随即变 `not executable`。

---

## 2. P1 模块准备

0. **新建模块（CLI 语法与已知限制）**：
   ```powershell
   & $TESSY_CMD connect
   & $TESSY_CMD select-project <项目名>
   & $TESSY_CMD select-test-collection <集合名>
   # 正确语法：-env 给环境名，-test-collection 是"标志"（不是集合名！），最后一个位置参数才是模块名
   & $TESSY_CMD new-module -env "<环境名>" -test-collection <模块名>
   & $TESSY_CMD list-modules -test-collection
   ```
   实测注意：如果工程库上下文异常，`new-module` 可能返回 0 但模块落到错误的 project id 下，
   随后 `analyze` 报 `idbmake: failed to load module`（模块在 project 7、Analyze 用 project 1024）。
   遇到这种情况**不要继续猜 CLI**：请用户在 TESSY GUI 里新建空模块（最快），再用 CLI
   `add-source-file / add-include-dir / analyze` 继续，或重启 TESSY 后重试。
   命令速查用 UTF-16 字符串可查：`tessycmd.exe` 内含 usage（`strings -el` 即可看到 `new-module -env ... [-test-collection] <module name>`）。

1. 新建/选中模块，添加源文件：`add-source-file`；头文件目录 `add-include-dir`；宏 `add-define`（如 `CPU_IM94`）。
2. **外部依赖**（DAL/E2E/UDS 等）二选一处理：
   - 真实源码不链接时，添加"harness 桩源文件"（默认返回 0/空）让从机可链接；
   - 需要按用例控制返回值时 → 见 P2。
3. 内联库函数（CMSIS `__*`、`ARM_MPU_*`、`NVIC_*`、`SCB_*`、`SysTick_*` 等）与 harness 函数
   加入 **Test Object Exclude List**：
   - **分隔符必须是英文逗号 `,`**（分号无效）；
   - 环境 ini 与 `module.xml` **两处都要改**（模块属性会被环境值覆盖）；
   - 改后重启 TESSY 再 `analyze`。
4. `analyze` 后 `list-test-objects`，确认对象数 = 预期（例如只剩业务函数）。

常用属性速查 → `references/tessy-cmd-reference.md`

---

## 3. P2 接口与桩（本技能最关键的一节）

### 3.1 先判定"桩类型"，不要凭想像写数据

```powershell
# 导出对象的 details XML（里面有 interfaceReport：stub="advanced"/"normal"/"none" 与 passing 方向）
& $TESSY_CMD select-test-object <object>
& $TESSY_CMD export -format xml -file <object> $WORK\detail
```

看 `<interfaceReport>`：

| 看到什么 | 含义 | 数据怎么写 |
|---|---|---|
| `name="void DAL_eeprom_Read(...)" stub="none"` | 未打桩，链接真实实现（或 harness 默认实现） | 不用管 |
| `stub="normal"` | 普通桩（代码桩） | 在 **Stubs 表**写桩体 `return 1u;`、`DEMO_DATA_TYPE d; d.alpha_angle=86U; return d;` |
| `stub="advanced"` 且出现 `name="xxx()" passing="IN"` | **高级桩** | 在 **Values 表**给变量：`函数名()`、`函数名().成员`、`函数名(参数名)`；**Stubs 表桩体会被静默忽略** |

**最容易犯的错**：函数是高级桩，却写了普通桩桩体 → 导入成功、执行全挂在默认值（一轮用例几乎全废）。
生成数据前，必须用上面的 XML 确认每个外部函数的桩类型。

### 3.2 高级桩变量命名与方向（照抄即可）

| 变量 | 方向 | 说明 |
|---|---|---|
| `DAL_Get_Data()` | IN | 结构体返回值容器 |
| `DAL_Get_Data().alpha_angle` | IN | 返回值成员（被测代码用到的成员才出现） |
| `DAL_Get_Data().beta_angle` | IN / IRRELEVANT | 未用到的成员可能是 IRRELEVANT，不用给 |
| `DAL_Tim_CheckTimeout()` | IN | 标量返回值 |
| `DAL_Tim_CheckTimeout(lastTime)` / `(currentTime)` / `(timeout)` | OUT | **函数参数会被校验**，要给期望值（即使它被标成 OUT） |
| `E2E_CalcCrc()` | IN | 返回值 |
| `E2E_CalcCrc(nBytes)` | OUT（常见） | 参数期望值（长度 2 就要给 2） |
| `E2E_CalcCrc(message)` | IN(targetPassing=OUT) | 指针参数，需要给列（值可 0） |
| `demo_get_position_local().x` | IN | **本地函数**高级桩的结构体返回成员 |

规则总结：

- **返回值 → IN**（测试数据给"桩的返回值"）；
- **参数 → IN/OUT 都要给值**（TESSY 用它校验实际调用参数；缺了会 notok 或 object not executable）；
- **未使用成员 → IRRELEVANT**（可忽略）；
- 指针/数组参数：高级桩对"指向数组的指针"支持有限，优先用被测对象的全局变量（如 `Demo_Cal_Data.caldata.data[]`）间接控制。

### 3.3 需要用户手工建桩时：发出"建桩请求"（固定模板）

TIE 配置存在工程数据库里、**没有 CLI**，所以这一步必须请用户在 GUI 里做。
用下面模板发请求，明确到"对象 + 函数 + 类型 + 建完后的验证方法"：

```text
请在 TESSY 的 TIE（Test Interface Editor）里为下列测试对象建桩，建完告诉我，我来生成用例：

测试对象：demo_gear_task
  1) DAL_Tim_CheckTimeout        → 建 Advanced Stub（返回值用于控制超时分支）
  2) DAL_Tim_GetTime      → 建 Advanced Stub（返回值 uint16）
  3) DAL_Get_Data       → 建 Advanced Stub（结构体返回，alpha/beta 用于分支）
测试对象：demo_calc_lever_pos
  4) demo_get_position_local（Local Functions 里的本地函数）→ 建 Advanced Stub
测试对象：demo_calibration_init
  5) E2E_CalcCrc                 → 建 Advanced Stub
测试对象：demo_shift_fault_check
  6) DAL_Get_Hall_Gear_Diag_Err  → 建 Advanced Stub

类型说明：
- 选 "Create Advanced Stub"（不是 "Create Stub"）；作用域选当前测试对象（或全局高级桩）。
- 高级桩建好后，接口里会出现 `函数名()` / `函数名().成员` / `函数名(参数名)` 这些变量，
  这些变量的方向（IN/OUT）由 TESSY 自动决定，不需要你改。
- 建完请点一次 Analyze（或告诉我，我来 Analyze）。
```

如果用户只想"能跑通"，也可以只建**普通桩**：此时数据用 Stubs 表桩体，不需要 IN 变量；
但**同一函数不要既普通桩又按高级桩写数据**。

### 3.4 验证桩是否真的生效（必做）

```powershell
& $TESSY_CMD export -format csv -file <object> $WORK   # 看接口列
# 高级桩：CSV 里应出现 "xxx()" 或 "xxx().member" 列
# 若没有：可能没 Analyze / 建成了普通桩 / 建在别的对象上
```

> 注意：CSV 导出有时只列"测试数据里已有值"的列；验证高级桩更可靠的是 details XML 的 interfaceReport。

### 3.5 接口方向（Passing）与"对象可执行性"（高频坑，务必先看）

详细版：`references/interface-passing-and-import.md`

**先判断对象当前能不能跑**（不用执行测试）：

```text
<persist>\…\.tdb\<n>\testobject.xml
  state_mask            0x…1188  => 可执行    0x…1180 => 不可执行
  testitem_state_mask   0x80     => 有效      0x00    => 无效
```

不可执行时 GUI 会报 **"No executable test object selected for execution."**，
TDE 打开会报 **"The test object's interface is incomplete."**（Inputs/Outputs 两个列表全空）。

**`tessycmd` 的导入方向标记（实测唯一有效三个）**：

| 标记 | 含义 | 用途 |
|---|---|---|
| `i` | IN | 把 IRRELEVANT 的静态变量变成可输入（例：`DemoPose.x` → 覆盖率从 25% 到 100%） |
| `o` | OUT | 设成输出 |
| **`x`** | **IRRELEVANT** | **让指针参数/无法断言的成员失效（见下）** |

用法：`import -set-passing <file.xlsx>`，`Values` 第 2 行写标记；`io`/`inout`/`r` 等非法标记会导致
**导入失败且部分应用**（把别的元素改坏）→ 出事立刻用 TMB 恢复（见 §10 第 22 条）。

**指针参数规则（TESSY 5.1 硬限制）**：函数的指针参数在 TIE 里只有 `IN` / `EXTERN` / `IRRELEVANT`，
**没有 INOUT**。若函数通过指针写回、同时内部又有输入成员（`*_c[]` IN + `status.*` OUT），
接口会被判"不完整"、对象不可执行。修法：

```powershell
& $TESSY_CMD export -format xlsx -file cur $WORK          # 导出
# 把该指针列方向行 'i' 改成 'x'（IRRELEVANT）
& $TESSY_CMD import -set-passing <改好的.xlsx>
& $TESSY_CMD export -format xml  -file if_after $WORK     # 回读：元素应为 IRRELEVANT
```

代价：函数写进指针目标的内容**无法断言**（写入照执行、覆盖率照算），所以对象里必须另有
**静态全局输出**（如 `g_xxxRollerSendState`）用于 expected，RS 才成立。
若函数只通过指针出参返回、没有静态状态 → 只能测覆盖度，RS 无法变绿（TESSY 能力边界）。

**script 格式里的指针参数只能写 `msg = *none*`**（写成员路径会导入失败）。

**诊断神器：yaml 导出看真实数据模型**

```powershell
& $TESSY_CMD export -format yaml -file <object> $WORK
# <object>.yml 里 "Values:" 段才是 TESSY 真正暴露的列
#   Values 只有 [tc1.1] 行、表头为 []  => 数据模型是空的（接口不完整/数据无效）
```

---

### 3.6 模块挂了"手写桩源文件"会让用例桩体全部失效（极易误判）

详细版：`references/interface-passing-and-import.md` §7

症状：每个用例都写了 `$stubfunctions` 桩体，但**执行结果全都一样、覆盖度纹丝不动**，
生成目录里出现 `ts_p_ts_harness_stubs_<module>.c`，日志有
`[UCE] Missing stub code for function 'xxx' using pointer parameter`。

根因：模块源文件列表里额外挂了一个手写桩源文件（如 `baseline_startup\ts_harness_stubs_demo.c`），
里面**已经定义**了 `DAL_Tim_GetTime/DAL_eeprom_Read/E2E_CalcCrc/...` →
TESSY 链接的是它，用例级桩体被完全忽略。

修法：

```powershell
& $TESSY_CMD list-source-files                     # 确认多出来的 .c
& $TESSY_CMD remove-source-file "<路径>\ts_harness_stubs_xxx.c"
& $TESSY_CMD analyze                               # 必须，否则会残留 flow 引用
```

移除后**必须给"每条用例 × 每个桩"都补桩体**（对象级 case 0 行可留空），
否则 `MissingStubCodeException: [UCE] Missing stub code for test object 'xxx'`
（工程选项 `Abort on missing stub code` 默认开）。若报告阶段报
`Failed to create flow file … Failed to lookup 'ts_harness_stubs_xxx' in module source files`，
**再 analyze 一次**即可（不影响执行结果）。

---

## 4. P3 从源码生成用例

### 4.1 先读源码，列出"分支清单"

对每个被测函数列出：判定表达式、每条分支对应的输入区间、分支里的赋值、空分支（`;`）、
`switch` 的每个 case/default、`||`/`&&` 的每个子条件（MC/DC 用）。
**期望值必须按源码宏和表达式现算**，不要凭记忆（典型坑：`left_frist_step_L = (alpha-HORIZO)-BUFFER` 曾算错成 `-10`）。

### 4.2 数据格式（XLSX 导入导出）

| 工作表 | 用途 |
|---|---|
| `Values` | 第 1 行变量名、第 2 行方向 `i/o`、之后每行 `tcN.M`（M 为测试步号） |
| `Properties` | 第 4 行表头：Test Case / Test Step / Repeat Count / Name / Description / Specification / Comment / Is Fault Injection |
| `Stubs` | 仅普通桩用：Test Case / Test Step / Stub / Stub Body |
| `User Code` / `Call Trace` / `Fault Injections` | 需要时再用 |

### 4.3 用例设计硬规则

1. **每条分支 ≥1 条用例**；边界值（含/不含）、越界、`default`、空分支单独覆盖。
2. **空分支（无赋值）**：
   - 开 `Execute testcases separately` → 期望 = 静态初值（如 0）；
   - 不开 → 用 `*none*`（不校验）。
3. **不要留空单元格**：输入为空非法；需要"不校验"就写 `*none*`。
4. **函数 static 变量**（如 `lastValidPos`、`startupInvalidMaskCnt`）在独立执行时每个用例重置；
   需要状态演进 → 用**多测试步**（`tc1.1`、`tc1.2`…），并在每一步**显式给上一步的状态**作为输入。
5. 一个对象用例数 ≥ 分支数；先跑通再谈覆盖率。
6. 描述里写清"分支 + 期望依据"，方便评审追溯。

### 4.4 生成脚本

用 `scripts/gen_cases.py`（读 JSON 用例规格 → 基于导出模板生成 XLSX → 导入 → 回读校验）：

```powershell
& $PY scripts\gen_cases.py --spec cases\demo_calc_lever.json
```

JSON 规格格式见 `scripts/gen_cases.py` 文件头注释：支持
`values`（普通变量）、`stub_vars`（高级桩变量）、`stubs`（普通桩桩体）、`steps`（多测试步）。

---

## 5. P4 导入与回读校验

```powershell
& $TESSY_CMD select-test-object <object>
& $TESSY_CMD import <file.xlsx>
# 必须回读
& $TESSY_CMD export -format yaml -file <object> $WORK   # 看 Values/Stubs 段是否完整
& $TESSY_CMD export -format xml  -file <object> $WORK   # 看接口方向是否符合预期
```

> ⚠️ **import 是"整表替换"，不是合并**：Values + Stubs + Properties 全被覆盖。
> 因此每次导入都必须带**完整数据**（所有用例 × 所有变量 × 所有桩体），并且
> **基于刚导出的最新文件**改，绝不能用历史导出当底表。
> 实测事故：先导入"每用例桩体"，再拿旧导出补"对象级桩体"导入 → 每用例桩体全被清掉，
> 所有用例实际行为相同、覆盖度不动。

| 现象 | 原因 | 处理 |
|---|---|---|
| `[IMPEX] Failed to import` | 列名不匹配（多了类型名/少了 `()`/拼写错） | 从最新导出模板核对列名 |
| 导入成功但数据丢列 | 未知列被**静默忽略** | 回读对比列数/值 |
| 行数变少、出现 `*none*` | 文件里有空单元格 | 输入全填；不校验用 `*none*` |
| object 变 `not executable` | 桩体被 Analyze 清掉 / 高级桩变量缺 / 参数期望缺 / 接口方向不自洽 | 补数据后重导；方向问题见 §3.5 |
| 导入后所有用例结果一样 | 桩体没生效（模块挂了手写桩源文件 / 只有对象级桩体） | 见 §3.6 |

---

## 6. P5 执行与失败分诊

批处理 `.tbs` 模板见 `references/tessy-cmd-reference.md`，要点：

- `<elements>` 用 **`<testcollection name="...">`** 最可靠（`<testobject>`/`<module>` 元素会被静默忽略、报告 total=0）；
- 覆盖率测量：`instrumentationType` 取 `TESTOBJECT_ONLY`（或 `CALLED_FUNCTIONS`）；`NONE` 时覆盖率为空；
- 执行前后清理残留 `UV4/exp/tthd`；**不要与 GUI 并发执行**。

```powershell
& $TESSY_CMD exec-test -o $WORK\reports $WORK\run.tbs
& $PY scripts\run_batch.py --tbs $WORK\run.tbs --out $WORK\reports --report Demo_UT
```

失败分诊顺序：

1. 报告 `notexecuted` → 看 `.metadata\.log` / 执行 log：target/flash/UVSC 问题，或 `not executable`（测试数据无效）；
2. `notok` → 导出 details XML，逐条比 `expected_value` vs `actual_value`；
3. 常见修正：期望值公式错、输入未生效（static 变量/独立执行）、高级桩参数缺、桩类型判错。

> `scripts/inspect_detail.py` 可一次打印所有对象的失败字段与 actual/expected。

### 6.1 只跑一个模块（batch 做不到，别硬来）

`.tbs` 的 `<elements>` **只认 `<testcollection>`**；加 `<module name="…"/>` 会被静默忽略 →
又变回整集合执行（几百个对象 + 会卡死的对象，一轮一小时）。

正确姿势：

1. **让用户在 GUI 里右键模块 → Execute**（最快，也避免并发执行冲突）；
2. 或建一个只含该模块的临时集合（收尾要用户手动删集合，`tessycmd` 没有删集合命令）。

改完一个模块 → 只跑这个模块 → 读覆盖度 → 再改，是最高效的循环。

### 6.2 覆盖度文件在哪、怎么读

```text
<PROJECT>\tessy\work\<模块目录>\<对象目录>\ts_<id>.coverage.xml
  c0_data reached_branches / number_branches / coverage
  c1_data 同上
```

对象名对应：同目录 `ts_*_m.cpp` 里的 `#define TS_TESTOBJECT "对象名"`。
用脚本一次汇总所有对象：

```powershell
# 遍历 work\<mod>\*\*.coverage.xml，解析 c0_data/c1_data，打印 对象名 C0 C1
```

### 6.3 目标卡死（行内寄存器函数/死循环）

`CAN_REG_*` 这类 `static inline` 寄存器访问器、`DAL_System_Delay` 的 `while` 轮询会让目标**永远等**；
`Execution Timeout` 选项对这种死等无效。处理：提前排除、单独最后跑、必要时用看门狗进程
杀掉超龄 `ts_*_m` / `exp`（详见 `references/ops-backup-recovery.md` §3）。
卡死对象被杀后 TESSY 会继续下一个；**收尾必须清残留进程**，否则下一轮报 branches 文件错误。

### 6.4 备份/恢复（TESSY 退出会丢对象）

**实测事故**：TESSY 正常退出再打开，最近改过的模块对象变成 0（测试用例一起丢）。

规则：

```powershell
# 改完/关 TESSY 前，逐模块备份
& $TESSY_CMD select-module -test-collection <模块>
& $TESSY_CMD save-db -source module -to <备份目录>
# 产物：<备份目录>\New%20Test%20Collection.<模块>.tmb

# 恢复（同名模块整体替换，模块数不变）
& $TESSY_CMD restore-module -test-collection "<备份目录>\New%20Test%20Collection.<模块>.tmb"
```

详细（含 CTE REMOVED 清理、日志位置、启动/关闭姿势）：`references/ops-backup-recovery.md`。

---

## 7. P6 覆盖度与完整度复核

交付前必须做**独立复核**（可派 subagent，避免自证）：

- 覆盖度清单：`references/coverage-review-checklist.md`
  （分支清单 vs 用例、边界/错误/默认分支、MC/DC 子条件、桩可控性、覆盖率口径）；
- 完整度清单：`references/completeness-review-checklist.md`
  （Properties 名称/描述/规格、Values 无空行、桩数据齐全、交付文件与文档一致）；
- 输出：`review/coverage_review.md`、`review/completeness_review.md`，含"未覆盖项 + 原因 + 需补用例"。

---

## 8. P7 覆盖率(C0/C1)统计与缺口解释

- 只有 `instrumentationType=TESTOBJECT_ONLY/CALLED_FUNCTIONS` 才有 C0/C1；
- 覆盖率缺口解释模板（对每个对象）：`分支数 / 已覆盖 / 未覆盖分支 → 原因(桩不可控|输入缺失|用例不足|不可达) → 动作`；
- 不可达分支要能说清"为什么不可达"（硬件依赖、内部调用无法注入、结构体返回等），而不是笼统说"覆盖不了"。

---

## 9. P8 交付物

```
Tessy_UT_SWCxxx\
  README.md                      # 状态、如何执行、环境改动说明、FAQ
  cases\<object>.xlsx             # 每个对象一份可导入用例
  reports\<run>_Report.xml        # 执行报告
  review\coverage_review.md
  review\completeness_review.md
  <module>.tbs                    # 批处理模板
```

---

## 10. 踩坑速查（详细版见 `references/pitfalls.md`）

1. 路径含空格 → TESSY 拒绝；用无空格 junction。
2. TESSY 必须用 `explorer.exe` 启动，否则 `CreateProcess error 5`。
3. `"TessySimu" Target not defined` → TESSY `Project Target` 与 uVision 工程 target 不同名。
4. 执行方式三件套要一致：uVision target 调试器（J-Link/Simulator）、`Use UVSC Flash`、scatter（Flash/RAM）。
5. `Failed to flash programm errno 1/9`、`uvscSetBreak errno 4` → 目标/Flash 配置问题，不是用例问题。
6. 环境属性在 `configuration_*.ini` 与 `module.xml` 两处，模块值会被环境覆盖 → 停 TESSY、两处改、重启。
7. Analyze 清空执行结果、清空普通桩桩体 → 顺序：改配置/TIE/源码 → Analyze → 导用例 → 执行。
8. 高级桩与普通桩不能混用；高级桩时写普通桩桩体不报错但无效。
9. 高级桩参数也要给期望值（否则 notok/not executable）。
10. 导入未知列静默忽略 → 必须回读校验。
11. 空单元格会变 `*none*` → 输入必须全填，忽略用显式 `*none*`。
12. `Execute testcases separately` 改变状态语义 → 每步显式给状态/多测试步。
13. 期望值必须按源码公式现算。
14. 改 `uvprojx/uvoptx` 会动用户 uVision UI 状态（目标/断点）——先关 uVision、先备份、用完清理 `.bak`。
15. 批处理 `<testobject>`/`<module>` 无效 → 用 `<testcollection>`；只跑一个模块请用户在 GUI 里右键模块执行。
16. **对象不可执行**（GUI：`No executable test object selected`；TDE：`interface is incomplete`）→ 查
    `testobject.xml` 的 `state_mask`：`0x…1188`+`item 0x80` 才可执行，`0x…1180`/`0x00` 不可执行 → 见 §3.5。
17. **指针参数没有 INOUT**（TIE 只有 IN/EXTERN/IRRELEVANT）→ 用 `import -set-passing` 把方向标成 `x`(IRRELEVANT)，
    改完 `state_mask` 会从 `0x…1180` 变成 `0x…1188`。代价：指针写回的内容无法断言，需另有静态全局输出。
18. `import -set-passing` 的方向标记只有 **`i`/`o`/`x`**；其它写法会导致**导入失败且部分应用**（把别的元素改坏）
    → 先 `save-db` 再试，坏了 `restore-module`。
19. **import 是整表替换**：一次导入必须含"所有用例 × 所有变量 × 所有桩体"；用旧导出补数据会把新数据冲掉。
20. **yaml 导出才是数据模型真相**：`Values:` 段为空 = 接口不完整/数据无效；xlsx/script 只列有值的列，会误判。
21. **模块源文件里挂了手写桩文件**（`ts_harness_stubs_*.c`）→ 用例桩体全部被忽略、覆盖度纹丝不动；
    `remove-source-file` + `analyze`，然后每用例×每桩都补桩体，否则 `MissingStubCodeException`。
22. **TESSY 正常退出也可能丢对象**（最近改过的模块变 0）→ 关之前逐模块 `save-db`；丢了用
    `restore-module` 恢复，并补回快照后的改动。
23. **CTE 的 `REMOVED:` 提示** → 对象上挂了孤儿分类树数据；`unset-attribute 'CTEX File'`（返回
    `Attribute.getDeclaration() … null` 即视为成功），正常退出落盘，再把 `testSpecification.ctex` 等移到备份目录。
24. `CAN_REG_*`（`static inline` 寄存器访问）与 `DAL_System_Delay`（同文件 `static inline` 无法打桩）会让目标死等；
    `Execution Timeout` 无效，只能排除/最后跑/看门狗杀进程。
25. 覆盖率只在 `TESTOBJECT_ONLY`/`CALLED_FUNCTIONS` 下有意义；`work\<mod>\<obj>\ts_*.coverage.xml` 的
    `c0_data`/`c1_data` 有 reached/number/coverage。
26. testresult XML 里 `expected_value="-"` 表示**期望值无效/未设**（不是空值）；批量特征化时把 expected 改成 actual 再导入。
27. RS（结果显著性）要求至少一个**被求值的期望结果**；call trace 不算、`*none*` 也不算 → `static void` 且无输出状态的对象 RS 必为 notok。
28. 高级桩参数（如 `DAL_Tim_CheckTimeout(lastTime)`）标成 OUT 也要给期望值，否则 notok。
29. 修改共享文件（`ts_harness_stubs_*.c`、`uvprojx`、`module.xml`、工程 ini）先备份；这些文件不属于被测代码，但会改变链接行为。
30. 导入 script 必须 **GBK/cp936** 编码；UTF-8 会静默失败。桩签名要去 `const`、补参数名、`uint8_t`→`unsigned char`。

**31. `state_mask` 才是可执行性的唯一判据**（`0x…1188`/`0x…3700` + `item 0x80` + testcase `0x…1100`/`0x…3700`）。
    直接改 `testobject.xml` 的位没用——重开 TESSY 会被重算覆盖。详见 `references/ida-data-validity-playbook.md`。
32. **script 导入会破坏有效性、xlsx 导入不会**。凡是"导完就 not executable"，八成用了 `.script`；
    改用 `export -format xlsx` 的模板填值再 `import`。
33. **产生"有值且有效"数据的唯一可靠顺序**：TIE/IDA 配置 → Analyze → GUI **Initialize Test Data (Ctrl+I)**
    （Overwrite、全部用例）→ Ctrl+S → 再用 xlsx 导入值。反过来（先数据后接口）必得 `0x…1088`。
34. **IDA 指针参数**：TIE → IDA → Pointer Target = Global Variable（类型选结构体）→ Analyze → **再 Ctrl+I**，
    否则数据模型里没有 `变量.成员` 列，怎么填都不可执行。指针值写**变量名**（如 `target_canMsg`），不是地址。
35. **IDA 变量名同一模块内可能不同**（实测 CAN0=`target_canMsg`、CAN1=`target_canMsg1`）。
    写错 → 生成驱动 `(void *)&目标名` 编译报 `identifier "xxx" is undefined`。填之前先
    `export -format xml` 查 `<var nam="...">`。
36. **高级桩没有 Call Count 时**：把该函数改成**普通桩**，桩体用静态计数器
    （第 1 次 0、第 2 次 1）来覆盖 `while(条件)` 循环体；需要按用例区分时用**模块全局变量**门控。
    ⚠️ 桩体**不能引用被测函数的形参**（`identifier "instance" is undefined`），只能用模块全局或自身 static。
37. **每个用例相同的桩体会被合并成对象级（Test Case=0）一行**，逐用例不同返回值靠全局变量门控实现。
38. **`restore-module` 会回退 TIE 配置**（IDA 变量、桩类型）+ 数据 + 结果。改 TIE 前先 `save-db`；
    出问题优先补数据/重 Analyze，**不要**随手 restore。
39. **执行入口**：只在工程树右键**模块** Execute；在 TDE 里点 Execute 只对单对象，会报
    `No executable test object selected for execution`（不是模块坏了）。跑之前重开 TESSY，关闭提示选 `No`。
40. ARMCC 报 `#3092 anonymous unions` → 补丁打在**安装目录**的
    `sys\templates\make\ts_make_uvision_uvsc_arm_v5.tpl`（加 `--preinclude=ts_anon_unions.h`），
    项目目录下的同名模板不生效。
41. **Ctrl+I 之后必须再 `analyze`**：只做 Ctrl+I 时对象 mask 仍是 `0x80000088`（不可执行）；
    补一次模块级 `tessycmd analyze` 立刻变 `0x…1188`/`0x…1198`、用例 `0x…1100`。
    实测两轮：`BSP_Flash_UT`（3 对象）、`BSP_Eeprom_UT`（5 对象）修复后都 100%/100%。
    详见 `references/ida-data-validity-playbook.md` §2.1。
42. **判断"数据模型空"的 signature**：`export -format yaml` 的 `Values:` 只有 `- []` `- []` `- [tc1.1]`
    （无表头/变量行）。此时 xlsx/script 导入都无效，只能走「Ctrl+I → analyze → xlsx 填值」。
43. **普通桩桩体按返回类型补全**：非 void `return 0u;`、void `(void)0;`；每条用例 × 每个桩都要有，
    对象级（Test Case=0）行也填一份更稳（否则 `MissingStubCodeException`）。
    纯直线调用的模块（如 Dflash/Eeprom 的 `Unlock → 操作 → Lock`）修好有效性后自然 100%，不用设计分支用例。
44. **IDA 的 Type 列表里没有 `uint16_t`/`uint32_t` 这类 typedef**（只有 C 基本类型+枚举+结构体）。
    按位宽选基本类型：`uint8_t*`→`unsigned char`、`uint16_t*`→`unsigned short`、`uint32_t*`→`unsigned long`、
    `intN_t*`→`signed char/short/long`；结构体/枚举指针直接选同名类型。
45. **指针参数被"解引用读写"时不能传 NULL**：只读（`PduInfo->length`、`sdu[i]`）可以；
    读写（`tmpData=*data; *data=...;`）→ 执行必崩（`exit code 6`），必须 IDA 或有效地址。
    实测 `BSP_Ext_Send(uint16_t *data)`。
46. **遗留自动用例可能把大整数当数组下标**：如 `g_rightRollerQueueHead=90` 而数组只有 `[0..63]` →
    `queue[90]=x` 越界写 → slave `exit code 6`，且会挡住整个模块的 Execute。修数据前先看数组/指针入参范围。
    无参数函数的用例区分技巧：拿一个**纯输入全局**（只读不写）当"用例选择码"，桩体按码切换返回序列。
47. **不是所有指针参数都要 IDA**：先看函数体——只有 `*ptr` / `ptr->x` 这类**解引用**才需要可赋值目标；
    纯透传（如 `DAL_Can_Write`：`return BSP_Can_Write(Hth, PduInfo);`）传 `NULL` 即可（桩也不访问）。
48. **返回值/输出列缺失 ≠ 对象有问题**：Ctrl+I 后 `Values` 只有入参列、没有返回值列时，执行结果
    RS 可能 notok，但**C0/C1 覆盖度照常统计**。要 RS 绿需在 TIE 里把 Return 设为可断言，或
    让函数写一个全局变量再断言该全局。模块名大小写要照 `module.xml`（例：`DAL_CAN_UT` 不是 `DAL_Can_UT`）。
49. **`0x80000088` 有两种成因，先分清再决定要不要用户做 Ctrl+I**：
    - `Values` 只有 `- []` `- []`（无表头）= 数据模型空 → 必须 GUI Ctrl+I → analyze → xlsx 填值；
    - `Values` **有表头/变量行**、但普通桩桩体全空 = 只是数据不完整 → **不用 GUI**，
      直接 export xlsx 补齐"每条用例×每个桩"的桩体 + 参数值 → import → mask 立刻变 `0x…1188`
      （`DAL_Flash_UT` 3 对象实测，执行 3/3 全 100%）。
    即 `0x1000` = "值 + 桩体都齐"，数据模型已有列时 xlsx 导入就足以把该位写出来。
50. **mask 只有 `0x88`（没有数据模型的"半损坏"对象）也能救活，不用删对象、不用 Ctrl+I**：
    TDE 里接口树能显示但无编辑列、`Ctrl+I` 无反应、普通 `import` 报 `[IMPEX] Failed to import` 时：
    手工造最小 xlsx（列名 = 接口元素路径，如 `s_demoDataType.alpha_angle`；第 2 行方向 `i`/`o`；
    第 3 行起用例值）→ **`tessycmd import -append -set-passing <file.xlsx>`** → mask 变 `0x1188`；
    再普通 `import` 一次覆盖成干净用例即可（`DAL_Demo_UT/DAL_Get_Data`：0x88 → 0x1188）。
51. **补桩顺序：先分支设计、后补默认桩体**。若先按返回类型"批量补桩"，会把**逐用例桩返回值**同质化成固定值，
    覆盖率从 100% 掉到 10~12%（`DAL_updatePosition_Task` 实测）。改完必须回读 yaml `Stubs:` 确认逐用例值还在。
52. **`if / else if` 链的"两假"分支需要一条非法值用例**：只取合法值（0/1）时第二个条件被短路，永远不求值 → C1 卡在
    比如 87.50%（8 分支缺 1）。加 `ReadStep=99` 这类既不等于 A 也不等于 B 的用例即可补满。
53. **指针参数只认 IDA 变量名**：填 `NULL` → 执行卡死（硬故障）；填裸全局名 → 静默变 0；填 `&全局名` →
    `import` 报 500 且**清空数据模型**。必须 TIE→IDA 建同类型变量（`uint8_t*`→`unsigned char`）。
54. **桩要写回指针参数才算"给到被测代码"**：普通桩 `{ _Bool s={0}; return s; }` 不写 `*value`，
    被测函数里的局部变量恒 0 → 分支只走一条。桩体里 `{ if (value) { *value = 0x02U; } return 1; }`，
    每条用例给不同写回值（`DAL_SBC_Read_WindowDog_Period` 75/50% → 100/100%）。
55. **执行卡死判定与定位**：`work\<mod>\<obj#>\out_*.dat` 为 0 字节 + `ts_*_m.exe` 持续占 CPU = 目标机硬故障等待；
    典型是 NULL 指针解引用。`<obj#>` 转十进制后到 `testobject.xml` 的 `id=` 对照对象名；杀
    `ts_*_m`/`exp`/`tthd`/`UV4` 后 TESSY 会继续下一对象。指针参数一律用 IDA 就不会再遇到。

---

## 11. 常用命令与脚本

- 命令速查：`references/tessy-cmd-reference.md`
- **★ 数据有效性 / IDA 指针参数 / 桩体计数器 / restore 副作用**：`references/ida-data-validity-playbook.md`
  （state_mask 判据、script vs xlsx、Ctrl+I 顺序、IDA 变量名坑、无 Call Count 的循环体覆盖、13 对象 100% 案例）
- **接口方向 / 可执行性 / 导入语义**：`references/interface-passing-and-import.md`
  （指针参数、`-set-passing` 的 `i/o/x`、state_mask 判定、yaml 数据模型、手写桩源文件坑、script 写法）
- **备份恢复 / 卡死处理 / 诊断日志 / CTE 清理**：`references/ops-backup-recovery.md`
- 脚本：
  - `scripts/tessy_cmd.py`：连接/选择/导出/导入/执行的轻封装（读环境变量）；
  - `scripts/inspect_interface.py`：导出所有对象接口（CSV）+ 解析 details XML 的桩类型/方向；
  - `scripts/check_stubs.py`：给定对象/函数，报告 `advanced/normal/none`；
  - `scripts/gen_cases.py`：JSON 规格 → XLSX → 导入 → 回读校验；
  - `scripts/run_batch.py`：生成 tbs → 执行 → 解析报告；
  - `scripts/inspect_detail.py`：打印失败用例的 actual/expected；
  - **`scripts/fill_ida_pointer.py`**：指针参数 + IDA 变量的分支取值批量写入
    （`python fill_ida_pointer.py examples/can_rx_handler_ida.json`，导入后自动校验 `state_mask`）；
    示例规格：`examples/can_rx_handler_ida.json`、`examples/can1_rx_handler_ida.json`。
  - **`scripts/fill_values_stubs.py`**：无分支直线调用模块的"参数值 + 普通桩桩体"批量写入
    （`python fill_values_stubs.py examples/bsp_eeprom_ut_fix.json`，导入后自动打印每个对象的 `state_mask`）；
    示例规格：`examples/bsp_eeprom_ut_fix.json`、`examples/bsp_flash_ut_fix.json`。
