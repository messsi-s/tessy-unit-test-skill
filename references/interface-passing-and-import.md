# 接口方向、可执行性与导入语义（TESSY 5.1 实测）

> 本文件记录 2026-11 一轮真实工程（T1V_test / AUTOSAR 应用层）中反复踩到的四类问题：
> ① 指针参数导致接口"不完整"、对象不可执行；② 导入是整体替换；③ 模块挂了手写桩源文件导致用例桩体失效；
> ④ 数据模型到底该写成什么样（以 yaml 导出为准）。
> 全部结论都在 TESSY 5.1.10 + Keil ARMCC 上实测过。

---

## 1. 判定"对象是否可执行"（不用跑测试）

`tessycmd` 没有"查可执行状态"的命令，但可以直接读持久化文件：

```text
<TESSY_PROJECT_ROOT>\tessy\persist\tessy\project\<HI>\<LO>\.tdb\<n>\testobject.xml
```

关键属性：

| 属性 | 可执行 | 不可执行 | 含义 |
|---|---|---|---|
| `state_mask` | `0x…1188`（常见 `0x80001188`） | `0x…1180` | bit 0x8 = 测试数据有效 |
| `testitem_state_mask` | `0x80` | `0x00` | 用例级数据有效 |
| `<testcase>` 数量 | 与你导入一致 | 可能被清空 | 数据是否还在 |

快速脚本（PowerShell）：

```powershell
& $PY -c "import glob,xml.etree.ElementTree as ET; P=r'D:\T1V_Tessytest\tessy\persist\tessy\project'; [print(r.get('name'), r.get('state_mask'), r.get('testitem_state_mask'), len(list(r.iter('testcase')))) for r in (ET.parse(f).getroot() for f in glob.glob(P+r'\*\*\.tdb\*\testobject.xml', recursive=True))]"
```

> 经验值：**能正常跑的对象 = `state 0x…1188` + `item 0x80`**；判成 `0x1180 / 0x00` 的对象，
> 在 GUI 里 Execute 会弹 **"No executable test object selected for execution."**，
> 在 TDE 打开会弹 **"The test object's interface is incomplete."**。

---

## 2. 指针参数 → 接口"不完整"（最高频坑）

### 症状链

1. TDE 弹 `The test object's interface is incomplete.`，下方 Inputs/Outputs 两个列表**都是空的**；
2. Execute 弹 `No executable test object selected for execution.`，Execute 按钮灰；
3. 对象 `state_mask=0x…1180`、`testitem_state_mask=0x00`。

### 根因

被测函数的参数是**结构体指针**，TESSY 把参数本身判成 `IN`，但它内部成员既有 `IN`（输入数组）
又有 `OUT`（函数写回的字段）：

```c
void appl_steerwheel_update_sig_tx_mfsl(CanMFSLMsgBuf *msg);   // msg 内部的 status.* 是被写回的
```

而 TESSY 5.1 的 **参数（Parameter）只有三种 Passing：`IN` / `EXTERN` / `IRRELEVANT`，没有 INOUT**。
"IN 的指针 + 成员混 OUT"这种组合 TESSY 建不出数据模型 → 接口被判不完整 → 对象不可执行。
存量的测试数据还是旧形态（`$inputs { msg = ? }`），与成员级接口对不上，雪上加霜。

### 修法（CLI 可做，不用点 GUI）

把该指针参数整体设为 **IRRELEVANT**，让它的成员全部失效，接口只保留能断言的静态全局：

```python
# 1) 导出当前数据（xlsx）
export -format xlsx -file cur <dir>
# 2) 把 msg 列的方向行从 'i' 改成 'x'（x = IRRELEVANT，见 §3）
# 3) 带 -set-passing 导入
import -set-passing cur_modified.xlsx
```

修复前后状态位（实测）：

| 对象 | 修复前 | 修复后 |
|---|---|---|
| …update_sig_tx_mfsl | `0x1180 / 0x00` | `0x80001188 / 0x80` ✅ |
| …update_sig_tx_mfsr | `0x1188 / 0x00` | `0x80001188 / 0x80` ✅ |

### 代价（要跟用户讲清楚）

设为 IRRELEVANT 后，函数写进 `msg->status.*` 的内容**无法断言**（写入语句照常执行、覆盖率照算，
但期望值没有意义）。因此必须保证对象里还有**静态全局输出**可校验，例如

```c
static ApplSteerwheelRollerSendStateType g_leftRollerSendState;   // 算法结果落在这里
```

用它做 expected，RS（结果显著性）才成立。若被测函数只通过指针出参返回、没有任何静态状态，
则只能测覆盖度，RS 无法变绿 —— 这是 TESSY 的能力边界，不是数据写错。

---

## 3. `import -set-passing` 的方向标记（隐藏取值）

xlsx / yaml 的 `Values`/`Values:` 第 2 行是方向行，`import -set-passing` 会用文件里的方向
覆盖对象接口。实测标记：

| 标记 | 含义 | 典型用途 |
|---|---|---|
| `i` | IN | 让被标成 IRRELEVANT 的静态全局变成可输入（例：`AppGearPose.x`） |
| `o` | OUT | 让变量变成输出 |
| **`x`** | **IRRELEVANT** | **让指针参数 / 不想断言的成员失效（本文件 §2 的核心）** |

> 只有 `i` / `o` / `x` 有效；写 `io`、`inout`、`r`、`-`、`0` 等会让**整个导入失败**，
> 而且 TESSY 会**部分应用**（实测副作用：其它元素被改成 IRRELEVANT）→ 出事就用 TMB 恢复（见 ops 文件）。

常见两种用法：

- **IRRELEVANT → IN**（让静态变量可输入）：
  `AppGearPose` 原本全是 IRRELEVANT，加一列 `AppGearPose.x` 方向 `i` + 值，`import -set-passing`
  后 interface 变成 `IN`，`appl_calc_gear_lever_pos` 的 C0/C1 从 25%/14% 直接到 100%。
- **IN → IRRELEVANT**（指针参数解套）：见 §2。

改完必须回读验证：

```powershell
& $TESSY_CMD export -format xml -file if_after $WORK    # 看元素 passing
```

---

## 4. 导入是"整表替换"，不是合并

`import`（xlsx / script / yaml）会**整体替换**该对象的测试数据：Values + Stubs + Properties 全覆盖。

实测事故：先导入"补每用例桩体"的文件 A（成功），再用**旧导出**做底表补对象级桩体生成文件 B 导入 →
A 里每用例的桩体全被清掉，只剩对象级桩体（`{0,0}`），执行时所有用例alpha 恒为 0，
覆盖度原地不动、用例大面积 notok。

规则：

1. **一次导入必须包含完整数据**（所有用例 × 所有变量 × 所有桩体）；
2. 想改一部分，也应当 **基于刚导出的最新文件改**，而不是基于历史导出；
3. 导入后立刻回读（`export -format yaml` 看 `Values:` 段 + `Stubs:` 段）确认没丢。

---

## 5. 用 yaml 导出看"真实数据模型"（诊断神器）

```powershell
& $TESSY_CMD export -format yaml -file <object> $WORK
```

`<object>.yml` 里：

- `Properties:` 用例名/描述；
- `Stubs:` 每行 `[testcase, teststep, stub名, 桩体]`；
- **`Values:` 才是 TESSY 真正暴露的数据列**（列名 + 方向 + 每用例值）。

诊断口径：

| Values 段 | 说明 |
|---|---|
| 只有 `[tc1.1]` 这种行、表头 `[]` 空 | 数据模型是**空的** → 接口不完整/数据无效（就是 §2 的症状） |
| 有 `msg` 一列 + 少量输出列 | 指针被当整体处理（只能写 `*none*`） |
| 有完整 `xxx.yyy` 列 | 正常，可直接填值 |

script / xlsx 导出会"只列有值的列"，容易误判；**要判断接口模型一律看 yaml**。

---

## 6. script 数据格式里指针参数的写法

xlsx 做不到的部分用 script（GBK 编码！）补：

```text
$testobject {
	$testcase 1 {
		$name "TC01_Fault_LeftRoller"
		$uuid "…"
		$teststep 1.1 {
			$name ""
			$uuid "…"
			$inputs {
				msg = *none*          ← 指针参数只能这样（写成员路径会导入失败）
			}
			$outputs {
				g_leftRollerSendState {
					activeDirection = 0
					stepCount = 0
					remainingFrames = 0
				}
			}
			$stubfunctions {
				uint8_t DAL_GPIO_PopLeftRollerAction() '''
					return 1u;
				'''
				GEAR_HALL_DATA_TYPE DAL_Get_Gear_HallData() '''
					{ GEAR_HALL_DATA_TYPE s = { 86u, 58u }; return s; }
				'''
			}
			$calltrace { *** Ignore Call Trace *** }
		}
	}
}
```

要点：

- 文件必须 **GBK/cp936** 写盘，UTF-8 会静默导入失败；
- **桩签名必须与接口报告里的 `decl` 逐字一致**（不同模块的 IDB 拼写不同！）：
  有的模块认 `unsigned short DAL_Tim_GetCurrentTime()`，有的只认 `uint16_t DAL_Tim_GetCurrentTime()`；
  写错 → `[IMPEX] Failed to import`（实测：同一工程里 `appl_gear` 认 `unsigned short`，
  `DAL_SteerWheel_UT` 只认 `uint16_t`）。
  **最稳做法**：`export -format xml` 拿 `<func decl="...">`，原样抄进 `$stubfunctions`；
- 枚举/结构体返回值桩体用 TESSY 模板写法 `{ T s = { 0 }; return s; }`；
- 指针参数在 `$inputs` 里只能 `= *none*`；
- 只写 `$outputs`（不写 stubs）一定可以先导入成功 → 用这个做"最小可用导入"排查；
- xlsx 导入时**枚举值必须写符号名**（`ADC_RESOLUTION_8BIT`），写数字会整表失败。

---

## 6.1 三种"不可执行"的根因与对策（含 TIE 的限制）

| 根因 | 判定 | CLI 能否修 |
|---|---|---|
| 某元素 passing=`UNKNOWN` | `export -format xml` 看 `passing` | 部分能：`import -set-passing` + 方向 `x`；结构体/带指针参数的会被拒 |
| 接口里**没有任何 IN/OUT 元素**（全 IRRELEVANT） | 元素统计 IN=0 OUT=0 | 不能：必须先 TIE 里把某个元素设为 IN 或 OUT，否则 TESSY 不建数据模型 |
| 需要 **INOUT** 才能驱动分支（静态计数器/状态机） | 目标变量既读又写 | 不能：`i/o/x` 之外没有 INOUT 标记，必须 TIE 手工改 |

> 实测：`-set-passing` 用非法方向标记（`io`/`inout`/`b`）会让**整个导入失败**，
> 而且 TESSY 会**部分应用**——目标元素被改成 `IRRELEVANT`（把已有方向也弄丢）。
> 所以试之前一定先 `save-db`，出事 `restore-module`。

TIE 里能选的方向：局部变量/全局变量一般是 `IN` / `OUT` / `INOUT` / `IRRELEVANT`；
**函数指针参数**只有 `IN` / `EXTERN` / `IRRELEVANT`（没有 INOUT，见 §2）。

---

## 7. 模块挂"手写桩源文件"（harness stub）的坑
### 症状

- 每个用例都写了 `$stubfunctions` 桩体，但**执行结果全部一样**（覆盖度卡住不动，C1 只有第一条分支）；
- 生成出来的 `ts_src01.c` 里搜不到你的桩体；
- 执行日志出现 `[UCE] Missing stub code for function 'xxx' using pointer parameter`；
- 生成驱动目录里能看到 `ts_p_ts_harness_stubs_<module>.c`（从 `# 1 "…/ts_harness_stubs_xxx.c"` 展开）。

### 根因

模块的**源文件列表**里除了被测 `.c`，还额外挂了一个手写的桩源文件，例如：

```c
// D:\...\baseline_startup\ts_harness_stubs_gear.c
uint16_t DAL_Tim_GetCurrentTime(void) { return 0u; }
uint8_t  DAL_Tim_CheckTimeOut(uint16_t a, uint16_t b, uint16_t c) { return 0u; }
GEAR_HALL_DATA_TYPE DAL_Get_Gear_HallData(void) { GEAR_HALL_DATA_TYPE d={0,0}; return d; }
void DAL_eeprom_Read(...) { ... }
uint8_t E2E_CalcCrc(...) { return 0u; }
```

这些函数**已经被这个文件定义**了 → TESSY 链接的是它 → 用例级/对象级桩体全部被忽略，
被测代码永远只看得到 0/空结构体 → 所有用例走同一条分支。

### 修法

```powershell
& $TESSY_CMD list-source-files                       # 确认是否多了一个 ts_harness_stubs_*.c
# 备份后从模块移除
& $TESSY_CMD remove-source-file "D:\...\baseline_startup\ts_harness_stubs_gear.c"
& $TESSY_CMD analyze                                 # 重建 IDB（不 analyze 会残留引用）
```

移除后**必须**给"每条用例 × 每个桩"都写桩体，否则：

- 报 `com.razorcat.tessy.services.testdata.MissingStubCodeException: [UCE] Missing stub code for test object 'xxx'`
  （工程选项 `Abort on missing stub code` 默认是开的）。

补桩体时注意：

- **每用例行必须非空**；对象级（Test Case = 0）行留空即可（它只是默认值）；
- 若只剩对象级桩体（例如 `{...,0u}`），所有用例仍会拿到相同值 → 覆盖度不动；
- 补完后回读 yaml：`Stubs:` 段应出现 `[1,0,函数名,桩体] … [N,0,函数名,桩体]`。

移除手写桩文件后若报告生成阶段报：

```text
[ERROR] [SUM] Failed to create flow file for module 'xxx'
        Failed to lookup 'ts_harness_stubs_xxx' in module source files
```

→ **再执行一次 `analyze`**（重建 IDB/flow 引用），报错即消失。此错误不影响用例执行结果。

---

## 8. 批处理无法按模块执行（要按模块测只能走 GUI）

实测 `exec-test` 的 `.tbs` 里：

```xml
<elements>
  <testcollection name="New Test Collection"/>
  <module name="BSP_Timer_UT"/>      <!-- 会被静默忽略 -->
</elements>
```

`<module>` 元素被忽略 → 又变成整集合执行。想要"只跑某个模块"：

1. GUI 里右键模块 → Execute（推荐，用户操作）；
2. 或建只含该模块的临时集合（要用户最后手动删集合，`tessycmd` 没有删集合的命令）。

**不要**为了验证一个对象就发整集合批处理（几百个对象 + 会卡死的对象，一跑一小时）。

---

## 9. 一次典型修复流程（可直接套用）

```text
1. 读 testobject.xml 的 state_mask/testitem_state_mask
     0x1188+0x80 → 已可执行，问题在数据/期望值
     0x...1180+0x00 → 不可执行
2. export -format yaml → 看 Values 段是否为空
     空 → 接口不完整（走 §2 指针参数处理）
     有列 → 看是否还有 '?'（导出 script grep '= ?'）
3. 修接口：import -set-passing（i / o / x）
4. 修数据：一次导入完整文件（用例 × 值 × 每用例桩体）
5. 回读：yaml Values/Stubs + testobject.xml state_mask
6. 让用户在 GUI 只跑这个模块
7. 读 work\<mod>\<obj>\ts_<id>.coverage.xml 的 c0_data/c1_data 看覆盖度，循环第 3~6 步
```

---

## 10. 补充：`state_mask` 的"有效位"是导入流程决定的（2026-11 实测）

上面第 1 步只判了"可执行/不可执行"，但还有一层更隐蔽的区别——**数据是否被 TESSY 判为有效**：

| 位 | 含义 | 由谁写入 |
|---|---|---|
| 对象 `0x1000` | 测试数据与当前接口自洽、有效 | **只有 TESSY 自己**（GUI Ctrl+I / 保存单元格） |
| testcase `0x100` | 该用例数据有效 | 同上 |

因此：

- **`.script` 导入**不会写这两个位 → 导完对象变 `0x…1088`、`testitem=0x00`，事后补状态位无效（启动重算）。
- **`.xlsx` 导入**在对象原本有效时会保留这两个位 → 实测 13 个对象反复导入仍是 `0x…1188`。
- **直接改 `testobject.xml` 的 `state_mask`** 无效，重启被打回。

正确顺序（唯一可靠）：

```text
TIE/IDA 配置 → Analyze → GUI Test Data → Initialize Test Data (Ctrl+I, Overwrite, 全部用例)
→ Ctrl+S → **再 Analyze** → 用 xlsx 导入值（指针参数写 IDA 变量名）
```

> **Ctrl+I 和 Analyze 缺一不可**：只做 Ctrl+I，mask 停在 `0x80000088`（数据模型有了但有效性位没算）；
> 补一次 `tessycmd analyze` 才变 `0x…1188`/`0x…1198`。2026-11 在 `BSP_Dflash_UT`（3 对象）
> 和 `BSP_eeprom_UT`（5 对象）上两次验证，修完执行 C0/C1 全 100%。
> "数据模型空"的 signature：yaml 的 `Values:` 只有 `- []` `- []` `- [tc1.1]`。

指针参数（`can_msgbuff_t *canMsg`）必须先用 **TIE → IDA → Pointer Target = Global Variable**
给它一个可赋值目标，**并且建好 IDA 后再做一次 Ctrl+I**，否则数据模型里没有
`变量.msgId` / `.dataLen` / `.data[i]` 这些列，填不出分支、对象一直不可执行。
同类 IDA 变量名在同一模块可能不同（实测 `target_canMsg` vs `target_canMsg1`），
填之前用 `export -format xml` 查 `<var nam="…">`，否则驱动生成
`(void *)&target_canMsg` 会编译报 `identifier … is undefined`。

完整实战手册（含 13 对象 100% 案例、桩体计数器、restore 副作用）：
`ida-data-validity-playbook.md`。
