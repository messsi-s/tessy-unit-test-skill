# TESSY 单元测试踩坑全量清单（按类别）

> 每条格式：**现象** → 根因 → 规避规则。附"排错入口"。

---

## 一、环境与工程配置

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| E1 | `unsupported character ' '` | TESSY 不支持路径含空格 | 建无空格目录联接/junction（如 `CodeTest`），所有 TESSY 侧路径用它 |
| E2 | `idbmake: No rule to make target 'D:/.../Code'` | make 按空格拆分路径 | 环境 `Project File` 写无空格路径 |
| E3 | `CreateProcess ... failed with error 5` | 从脚本/任务计划/快捷方式启动 TESSY | **只用 `explorer.exe "…\TESSY.exe"` 启动** |
| E4 | `"TessySimu" — Target not defined in Project` | TESSY `Project Target` 与 uVision 工程 target 不同名 | 两边名字必须一致；改完 Analyze |
| E5 | `Failed to flash programm with errno 1/9` | uVision target 是 J-Link 硬件配置但板子未连/未上电；或 `Use UVSC Flash` 与仿真模式冲突 | 硬件：J-Link + `Use UVSC Flash=true`；仿真：`uSim=1` + `Use UVSC Flash=false`；或改 RAM 调试 |
| E6 | `Failed to create breakpoint at 'tslows_sync' errno 4` | 在 Flash 地址下断点，硬件断点不足 / FlashBP 未启 | uVision 中启 J-Link **Flash Breakpoints / Connect under reset**；或改 RAM 运行 |
| E7 | 改了 TESSY 配置不生效/被还原 | 属性在 ini 与 module.xml 两处；模块值被环境值同步覆盖 | 停 TESSY → 两处都改 → 重启 → 验证 |
| E8 | 改 uVision 工程后用例变灰/不可执行 | `uvprojx` 是 TESSY 跟踪的环境文件，改动使分析过期 | 改工程后 Analyze |
| E9 | uVision 界面"变了"（目标/断点/调试设置丢失） | TESSY 跑测试会启动 uVision 并写 `uvoptx`；外部回滚 `uvoptx` 会连用户 UI 状态一起回滚 | 改工程文件前**关闭 uVision 并告知**；优先只改 TESSY 配置；备份 `.bak` 用完清理 |
| E10 | 分析报头文件/宏找不到 | 包含路径、宏未配全 | 一次性配全 `Compiler Includes` + `add-define`；改 `Target Install Path` 后检查 `$(CMSIS Path)` 引用 |
| E11 | `-lUVSC` 找不到 | UV4 目录缺 `libUVSC.a` | 用 `dlltool` 从 `UVSC.dll` 导出生成后放 `C:\uVision\UV4` |

---

## 二、模块分析 / 测试对象

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| A1 | 60+ 测试对象、大量 `not executable` | CMSIS 内联函数/外部桩函数被当成测试对象 | 配 `Test Object Exclude List`；**分隔符必须是英文逗号**；ini + module.xml 都改；改后重启 + Analyze |
| A2 | 排除列表改了不生效 | 模块属性被环境值覆盖 / 对象已存在 | 两处同步改 + 重启；必要时 touch 源文件强制重分析 |
| A3 | Analyze 后用例全灰、桩体丢失 | Analyze 清空执行结果与普通桩桩体 | 顺序：**改配置/TIE/源码 → Analyze → 导入用例 → 执行** |
| A4 | `Test object 'xxx' is not executable` | 桩体被 Analyze 清掉 / 高级桩变量缺 / 参数期望缺 | 先看 details XML interfaceReport，再补数据 |
| A5 | `idbmake: failed to load module (1024/xxxx)` | 模块被 CLI 建到了错误的 project id 下（persist 目录出现新的 project 号） | 让用户在 GUI 建空模块；或重启 TESSY 后重试；不要反复调用 new-module |
| A6 | `new-module` 返回 0 但模块不存在 | 未正确选 project/collection，或 CLI 参数顺序错 | 正确顺序：connect → select-project → select-test-collection → `new-module -env "<env>" -test-collection <模块名>`（`-test-collection` 是标志位，不接收集合名） |
| A7 | 驱动编译 `Internal fault: [0xee9849] in __nop` | TESSY 为 armcc/CMSIS 内建函数（`__memory_changed`/`__dmb`/`__nop`/`__isb`/`__dsb`）自动生成桩，`int __dmb(void)` 等与编译器内建签名冲突，armcc 5 崩溃 | 把模块属性 **`Compiler Dialect` 改为 `--gnu`**（实测编译通过 0 errors）。`Enable Create Function Stubs=false`、`Function Stub Exclude List`、`Header File Exclude List` 都**不能**阻止这些函数进入 IDB，不要反复试 |
| A8 | 执行卡在 `Copying target binary for uVision` 长时间无响应 | 目标 Flash 下载/断点问题（UVSC/J-Link），与用例无关 | 确认目标板/调试器状态，或改 RAM 调试（scatter 到 RAM + `Use UVSC Flash=false`）；同批次能跑通的对象可作为环境正常与否的对照 |

---

## 三、桩（最高风险区）

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| S1 | 桩体写了但无效，整组用例挂在默认值 | 函数是**高级桩**，Stubs 表桩体被**静默忽略** | 先判断桩类型：接口出现 `函数名()` 变量 = 高级桩；高级桩用 Values 变量，普通桩用 Stubs 桩体 |
| S2 | 导入不报错但列丢了 | TESSY 对无法识别的列**静默忽略** | 每次导入后回读导出，核对列名/行数/桩体 |
| S3 | `[IMPEX] Failed to import` | 列名不匹配（多类型名/少 `()`/拼写） | 从最新导出模板核对：`DAL_Get_Data().alpha_angle`、`demo_get_position_local().x`、`DAL_Tim_CheckTimeout()`、`E2E_CalcCrc(nBytes)` |
| S4 | 高级桩用例 notok，只报参数不对 | 高级桩参数参与校验：返回值 IN、参数 IN（个别 OUT）都要给期望值；指针参数（`E2E_CalcCrc(message)`）也要给列 | 建桩后先导出看每个变量的 passing 方向 |
| S5 | 驱动生成报"桩函数返回值未定义" | 普通桩返回非 void 却没写桩体 | 桩体必须 `return 确定值;` |
| S6 | 桩体编译不过 | 类型名在桩上下文不可用 | 桩体使用头文件里的类型：`DEMO_DATA_TYPE d; d.alpha_angle=86U; return d;` |
| S7 | 本地函数（static）也要可控 | 只能测试对象内部调用，无法从接口注入 | 在 TIE 的 **Local Functions** 里对本地函数建 Advanced Stub（结构体返回的成员变量名为 `本地函数名().成员`） |

---

## 四、用例设计 / 数据

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| D1 | 导入后整行变 `*none*` / 导入失败 | 文件里有空单元格；输入为空非法 | 输入全填；不校验用**显式 `*none*`** |
| D2 | "无赋值"空分支期望值争议 | 空分支不赋值，值取决于执行语义 | 独立执行 → 期望=静态初值；否则 `*none*` |
| D3 | 跨用例状态假设失效 | `Execute testcases separately` 每个用例从初值开始 | 独立执行时显式给 static 变量初值；状态演进用**多测试步**，每步显式给上一步状态 |
| D4 | 期望值系统性错误 | 凭记忆算公式 | 期望值必须按源码宏/表达式现算（例：`left_frist_step_L=(alpha-HORIZO)-BUFFER`，HORIZO=15、BUFFER=5） |
| D5 | 用例少、分支覆盖不全 | 只写了冒烟用例 | 每条分支 ≥1 条；边界/越界/default/空分支单独用例 |
| D6 | 覆盖率空/0 | `instrumentationType=NONE` | 覆盖率测量必须 `TESTOBJECT_ONLY` 或 `CALLED_FUNCTIONS` |
| D7 | 导入后被"还原" | `import` 是整体替换 | 保留导出副本；批量改后整文件导入 |
| D8 | 依赖桩的用例数据缺失 | 桩变量/桩体与用例分开写 | 导入前核对：每条用例的桩数据都有值 |

---

## 五、执行 / 排错

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| R1 | 执行卡住（如 33%） | 目标配置与实际硬件不符 / uVision 会话卡死 | 清残留 `UV4/tthd/exp`；看 `work\<x>\<y>\<NN>\out_*.dat` 是否 0 字节定位卡在哪个对象 |
| R2 | GUI 与 CLI 并发执行冲突 | 同一 work 目录 / 同一 uVision 实例 | 不要并发；CLI 前确认 GUI 没在跑 |
| R3 | 报告 total=0 | 批处理 `<elements>` 用了 `testobject`/`module` 元素（被忽略） | 用 `<testcollection name="..."/>` |
| R4 | `notexecuted` 与 `notok` 混淆 | 前者=未执行/结果失效/数据无效；后者=执行失败 | notexecuted 查桩/接口/分析状态；notok 看 actual vs expected |
| R5 | 排错靠猜 | 不看 XML | 首选 details XML：interfaceReport（桩类型/方向）+ actual/expected |
| R6 | 覆盖率/结果异常 | 执行成功但结果未保存 | `createNewTestRun=true`；执行后核对报告对象数/用例数 |

---

## 六、流程 / 协作

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| P1 | 用户的代码/数据改动被覆盖 | 外部直接改工程文件、回滚 uvoptx、导入替换数据 | 改前备份、改后告知；导入前确认用户是否在改同一对象 |
| P2 | TIE 配置做不了自动化 | TIE 配置存工程数据库、无 CLI | 用固定"建桩请求模板"请用户在 GUI 建桩（见 SKILL.md §3.3） |
| P3 | 反复返工 | 没有"先验证接口/桩类型再写用例" | 固定顺序：接口 → 桩类型 → 用例 → 导入回读 → 执行验证 |

---

## 七、接口方向 / 可执行性 / 导入语义（2026-11 新增，详见 `interface-passing-and-import.md`）

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| I1 | GUI 报 `No executable test object selected for execution.`；TDE 报 `The test object's interface is incomplete.`（Inputs/Outputs 全空） | 对象不可执行：`testobject.xml` 的 `state_mask=0x…1180`、`testitem_state_mask=0x00` | 判定标准：`0x…1188` + `0x80` 才可执行；不可执行先查接口方向与数据有效性 |
| I2 | 结构体指针参数导致接口不完整 | TESSY 5.1 **指针参数没有 INOUT**（只有 IN/EXTERN/IRRELEVANT），而成员里混着 IN/OUT | `import -set-passing` 把该指针方向标成 `x`(IRRELEVANT)；用静态全局输出做 expected；指针写回内容无法断言 |
| I3 | 想把 IRRELEVANT 的静态变量变成可输入 | 默认方向由分析决定 | `import -set-passing` 加列方向 `i`（实测 `DemoPose.x` 这样修后覆盖率 25%→100%） |
| I4 | `-set-passing` 用了 `io/inout/-` 后其它元素被改坏 | 只支持 `i`/`o`/`x`；非法标记导致导入失败但**部分应用** | 试之前先 `save-db`；坏了 `restore-module` 恢复 |
| I5 | 改了一部分数据，另一部分被清空 | `import` 是**整表替换**（Values/Stubs/Properties 全被覆盖） | 一次导入必须含"所有用例 × 所有变量 × 所有桩体"，且基于最新导出改 |
| I6 | 判断接口模型靠 xlsx/csv 结果误判 | 这两种导出只列"有值"的列 | 用 `export -format yaml` 看 `Values:` 段：为空 = 数据模型空/接口不完整 |
| I7 | 桩体写了但执行结果全一样、覆盖度不动 | 模块源文件里挂了手写桩文件（`ts_harness_stubs_*.c`），函数已被定义 → 用例桩体被忽略 | `list-source-files` 确认 → `remove-source-file` → `analyze` → 每用例×每桩补桩体 |
| I8 | 移除手写桩文件后报 `MissingStubCodeException` | 工程选项 `Abort on missing stub code` 默认开，且没有每用例桩体 | 给每条用例的每个桩都写桩体（对象级 case 0 行可空） |
| I9 | 报 `Failed to create flow file … Failed to lookup 'ts_harness_stubs_xxx'` | 移除源文件后 IDB/flow 仍引用旧文件 | 再 `analyze` 一次（不影响执行结果） |
| I10 | script 里写指针成员路径导入失败 | 指针参数只能整体赋值 | `$inputs { msg = *none* }`；成员级只能靠 IRRELEVANT 后放弃断言 |

---

## 八、运维 / 数据安全（2026-11 新增，详见 `ops-backup-recovery.md`）

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| O1 | TESSY **正常退出**后某模块对象变 0（用例一起丢） | 最近改动过的模块退出时未落盘 | 关 TESSY 前逐模块 `save-db`；丢了用 `restore-module` 恢复并补回快照后的改动 |
| O2 | 对象前红色感叹号，提示 `REMOVED: This test object has been removed (or renamed)…` | 对象挂着孤儿 CTE 分类树数据（`CTEX File` 属性） | `unset-attribute 'CTEX File'`（返回 `Attribute.getDeclaration()…null` 即成功）→ 正常退出落盘 → 把 `testSpecification.ctex` 等移走 |
| O3 | 批处理卡在某个对象、整体"卡在 33%" | `CAN_REG_*`（static inline 寄存器轮询）、`DAL_System_Delay`（同文件 static inline 打不了桩）死等 | 提前排除/单独最后跑；看门狗杀超龄 `ts_*_m`/`exp`；`Execution Timeout` 对此无效；收尾清残留进程 |
| O4 | 想只跑一个模块 | `.tbs` 的 `<module>` 元素被忽略 | 让用户在 GUI 右键模块 Execute，或建临时集合（收尾需手工删） |
| O5 | 覆盖度结果找不到 | 不知道覆盖率文件位置 | `work\<mod>\<obj>\ts_<id>.coverage.xml` 的 `c0_data`/`c1_data`；对象名在同目录 `ts_*_m.cpp` 的 `#define TS_TESTOBJECT` |
| O6 | 导入/执行失败不明原因 | 没看日志 | `%USERPROFILE%\.tessy_51_workspace\.metadata\problems.log`（导入异常）、`.metadata\execution\<hi>\<lo>\<id>.log`（执行）、`ti.error.log`（目标/调试口） |

---

## 九、数据有效性 state_mask 与 IDA 指针参数（2026-11 实测，详见 `ida-data-validity-playbook.md`）

| # | 现象 | 根因 | 规避规则 |
|---|---|---|---|
| V1 | 对象明明有用例却 `not executable`；`state_mask` 缺 `0x1000`（如 `0x…1088`）、`testitem=0x00`、testcase 缺 `0x100` | 外部写入（script 导入 / 直接改库）不产生"数据有效"位 | 用 GUI `Initialize Test Data`(Ctrl+I) 生成数据模型，之后只用 **xlsx** 导入值 |
| V2 | 用 `.script` 导入后对象全变 not executable，事后补状态位也无效 | script 导入路径不写界面级有效性标记 | 一律 `export -format xlsx` 取模板 → 改值 → `import`；实测 xlsx 反复导入不破坏有效性 |
| V3 | 手工改 `testobject.xml` 的 `state_mask`，重启后被打回原值 | TESSY 启动时按内部一致性重算 | 不要改位，去修数据模型本身（V1 流程） |
| V4 | 指针参数 `canMsg` 是裸地址，`msgId` 分支全不覆盖（C0 仅 41%） | 没有可赋值的指针目标 | TIE → IDA → Pointer Target=Global Variable（类型选结构体）→ Analyze |
| V5 | 建好 IDA 后仍不可执行、数据表里没有 `变量.成员` 列 | 数据模型是"加 IDA 之前"生成的 | IDA 建好后必须再 `Ctrl+I`（Overwrite、全部用例）重建模型 → 成员列才出现 |
| V6 | 生成驱动编译报 `identifier "target_canMsg" is undefined` | 数据里写的 IDA 变量名与该对象实际的 `<var nam=…>` 不一致（同模块 CAN0=`target_canMsg`、CAN1=`target_canMsg1`） | 先 `export -format xml` 查真实变量名，按对象分别填 |
| V7 | 桩体里写 `if (instance == 2u)` 编译报 `identifier "instance" is undefined` | 桩函数是独立函数，看不到被测函数形参 | 桩体只能用**模块全局变量**（如 `PduTxId`）门控，或自身 static 计数器 |
| V8 | 想"循环体覆盖一次再退出"，高级桩只能给固定值（0 死循环 / 1 不进入） | TESSY 5.1 高级桩无 Call Count | 该函数改**普通桩**，桩体 `static int c=0; c++; return (c>1)?1:0;` |
| V9 | 逐用例写了不同桩体，行为仍一样 | 所有用例相同的桩体会被合并成对象级（Test Case=0）一行 | 全局变量门控 + 每用例不同全局值实现差异化 |
| V10 | 改好 IDA/桩类型后 `restore-module`，配置全没了 | restore 用 TMB 整体替换模块（含 TIE 配置） | 改 TIE 前先 `save-db` 备份；出问题优先补数据/re-Analyze，别随手 restore |
| V11 | 点执行报 `No executable test object selected for execution`，误以为模块坏了 | 在 TDE 里点 Execute（只作用于当前单对象） | 左侧工程树右键**模块** → Execute；跑前重开 TESSY，关闭时保存提示选 `No` |
| V12 | ARMCC 报 `#3092 anonymous unions are only supported in --gnu mode` | 源码用了匿名联合 | 在**安装目录** `sys\templates\make\ts_make_uvision_uvsc_arm_v5.tpl` 编译行加 `--preinclude=<dir>\ts_anon_unions.h`（内容 `#pragma anon_unions`）；项目目录同名模板不生效 |
| V13 | 做完 Ctrl+I 并保存，mask 仍是 `0x80000088`、用例 `0x80000000`，依旧不可执行 | Ctrl+I 只重建**数据模型**，不重算有效性位 | 紧接着跑一次模块级 `tessycmd analyze` → mask 变 `0x…1188`/`0x…1198`、用例 `0x…1100`（`BSP_Flash_UT`、`BSP_Eeprom_UT` 实测） |
| V14 | yaml 的 `Values:` 只有 `- []` `- []` `- [tc1.1]`，没有任何表头/变量行 | 数据模型被外部导入写成空表（接口列丢了） | 这是"空模型"signature：按 V13 的三步修（Ctrl+I → analyze → xlsx 填值）；此时 xlsx/script 直接导入都没用 |
| V15 | 普通桩 body 空着，执行报 `MissingStubCodeException` | `Abort on missing stub code` 默认开，且每条用例 × 每个桩都要桩体 | 按返回类型补：非 void `return 0u;`、void `(void)0;`；对象级（Test Case=0）行也填一份更省事 |
| V16 | 建 IDA 时在 Type 列表里找不到 `uint16_t`/`uint32_t`，确定性提示 `Please specify a type for the variable.` | TESSY Type 列表只含 C 基本类型 + 枚举 + 结构体，**typedef 不在里面** | 按位宽/符号选基本类型：`uint8_t*`→`unsigned char`、`uint16_t*`→**`unsigned short`**、`uint32_t*`→`unsigned long`、`intN_t*`→`signed char/short/long`；结构体/枚举指针直接选对应类型 |
| V17 | 对象可执行、编译通过，执行时目标机 `terminated with exit code 6` | 指针参数被被测代码**解引用读写**，而测试数据里给了 `NULL`（如 `BSP_Ext_Send` 的 `tmpData=*data; *data=...;`） | 只读指针可给 NULL；**读写指针必须给 IDA 变量或有效地址** |
| V18 | 某个队列/数组相关对象执行必崩（exit code 6），单独跑也崩 | 遗留自动生成用例把大整数当**数组下标**（如 `g_rightRollerQueueHead=90`，数组只有 64）→ `queue[90]=x` 越界写 | 修正测试数据：下标/head/tail 必须 `< 数组长度`；顺手核对该对象所有数组/指针入参 |
| V19 | Ctrl+I 后 `Values` 里**没有返回值/输出列**（只有入参列），执行结果 RS 显示 notok | 该对象返回值没有被 TESSY 建模为可断言输出（Ctrl+I 只生成了入参） | 覆盖度统计**不受影响**；要 RS 绿需在 TIE 里把 Return 设为可断言，或让函数写某个全局变量再断言该全局 |
| V20 | 以为"指针参数就必须 IDA"，多做了 GUI 操作 | 指针只被**透传**给普通桩、被测函数自身不解引用（如 `DAL_Can_Write`：`return BSP_Can_Write(Hth, PduInfo);`） | 先看源码：**函数体内没有 `*ptr` / `ptr->x`** → 指针可传 `NULL`，不需要 IDA；有解引用才需要（见 V17） |
| V21 | mask `0x80000088`，但 yaml `Values` **有表头/变量行**（不是空表） | 普通桩**桩体不全**（每个用例×每个桩都要有），数据被判不完整 | **不需要 GUI Ctrl+I**：export xlsx → 给所有用例行填桩体（`(void)0;`/`return 0u;`）+ 参数值 → import → mask 直接变 `0x…1188`（`DAL_Flash_UT` 3 对象实测） |
| V22 | mask 只有 `0x88`（连 `0x1000`/`0x80000000` 都没有），TDE 里接口树能显示但**没有可编辑列**，`Ctrl+I` 无反应/被禁用，普通 `import` 报 `[IMPEX] Failed to import` | 该对象**没有数据模型记录**（PDB 里缺失），属"半损坏"对象（常见于早期 restore/TMB 导入留下的孤儿对象；用例名是占位 `Dummy`、`state_mask=0x00`） | **不用删对象、不用 Ctrl+I**：手工造一个最小 xlsx（列名用接口元素路径如 `s_demoDataType.alpha_angle`，第 2 行写方向 `i/o`，第 3 行起写用例值）→ `tessycmd import -append -set-passing <file.xlsx>` → mask 变 `0x1188` 且数据列出现；随后再普通 `import` 一次把多余用例覆盖成干净用例（`DAL_Demo_UT/DAL_Get_Data` 实测：0x88 → 0x1188，3 条用例全 `0x1100`） |
| V23 | 先批量"按返回类型补桩体"，之后逐个设计分支 → 覆盖率从 100% 掉到 10%/12% | 批量补桩把**逐用例桩体**（按用例变返回值）统一成了固定值，等于所有用例走同一条分支 | 顺序要反过来：**先按源码分支设计每用例的桩返回值与输入，再补"其余桩"的默认桩体**；改完必须回读 yaml 的 `Stubs:` 段确认逐用例值没被同质化（`DAL_updatePosition_Task` 实测：0.10/0.125 → 1.00/1.00） |
| V24 | `if / else if` 链只覆盖了一部分，C1 差一个分支（如 87.50%，8 分支缺 1） | `else if` 的**第二个条件为假**从没被求值：输入只取了 0 或 1，第一个条件为真时第二个短路不求值 | 加一条**非法值用例**（如 `ReadStep=99`，既不等于 `START_3D(0)` 也不等于 `GET_RESULT(1)`）→ 两个条件都求值且都假，`else if` 链的"两假"分支才被覆盖 |
| V25 | 指针参数填了 `NULL`、裸全局变量名或 `&全局名`：分别导致**执行卡死**或 `import` 报 500 且**数据模型被清空**（mask 回到 `0x80000088`） | 指针参数在测试数据里只认 **IDA 变量名**（以及地址常量）；裸全局名不是合法指针值 | **必须 TIE→IDA** 建同类型变量（`uint8_t*` → `unsigned char`），填 `cnt = target_cnt`；不要试 `NULL`/`SbcRegConfigErr`/`&SbcRegConfigErr`（`DAL_SBC_Check_Reg` 实测） |
| V26 | 被测函数的**局部值由桩通过指针参数写回**时，分支只走一条（如 C0 75%/C1 50%，`feeddog_en=true` 未覆盖） | 普通桩桩体 `{ _Bool s={0}; return s; }` 不写 `*value`，被测代码里的 `s_crvalue` 恒 0 | 桩体里按**参数名**写回：`{ if (value != 0) { *value = 0x02U; } return 1; }`，每条用例给不同写回值即可覆盖 if/else（`DAL_SBC_Read_WindowDog_Period` 实测 75/50% → 100/100%） |
| V27 | 执行"卡住"：界面无响应、目标机不返回 | 看 `<work>\<mod>\<obj#>\out_*.dat`：**0 字节 + `ts_*_m.exe` 持续占 CPU** = 目标机硬故障在原地等（典型：解引用 NULL 指针） | 杀 `ts_*_m`/`exp`/`tthd`/`UV4` 残留；`<obj#>` 取自目录名后到 `testobject.xml` 的 `id=` 属性（十进制）对照对象名；杀完 TESSY 会继续下一个对象 |
