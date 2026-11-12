# TESSY 5.1 数据有效性（state_mask）与 IDA 指针参数实战手册

> 本文件是 2026-11 在 `BSP_Can_UT`（`BSP_can.c`，13 个测试对象）上把 13/13 做到
> C0/C1 = 100% 时踩出来的完整结论。**任何"对象明明有数据却 not executable"的问题，
> 先读本文件。** 相关：`interface-passing-and-import.md`（方向/导入语义）、
> `pitfalls.md`（速查条目）。

---

## 1. 可执行性的唯一判据：三个 state_mask

直接读 `<persist>\tessy\project\<xx>\<yy>\.tdb\<对象目录>\testobject.xml`：

```xml
<testobject name="CAN0_IRQCallback" state_mask="0x0102CF0080003788"
            testitem_state_mask="0x80" ...>
  <testcase ... state_mask="0x80003700" ...>
```

| 字段 | 可执行 | 不可执行 |
|---|---|---|
| 对象 `state_mask` | `0x…3788` 或 `0x…1188`（含 `0x1000`） | `0x…1088`、`0x…0002C000…1088`（缺 `0x1000`） |
| `testitem_state_mask` | `0x80` / `0x0180` | `0x00` |
| 每条 `testcase` `state_mask` | `0x…3700` 或 `0x…1100`（含 `0x100`） | `0x…1000` |

经验值：
- **`0x1000`（对象）/ `0x100`（用例）= "测试数据与当前接口一致、数据有效"**，由 TESSY **自己**在
  写数据时计算，**外部写不进去**（见 §2）。
- 有效对象常见两种形态：`0x0102CF0080003788`（GUI 全量重写后）和 `0x80001188`（xlsx 导入后仍有效）。
- **不要直接改 XML 里的位**：TESSY 下次启动会按内部规则重算，改动被覆盖（实测改了 17 个位，
  重开 TESSY 后全部打回 `0x1088`）。

---

## 2. 谁能产生"有效数据"，谁不能

| 写入方式 | 是否会破坏有效性 | 说明 |
|---|---|---|
| GUI `Initialize Test Data`（Ctrl+I） | **产生有效** | TESSY 用当前接口（含 IDA 变量）重建数据模型 → 这是**唯一可靠**的产生有效数据的入口 |
| GUI 手工改单元格 + Ctrl+S | 保持有效 | 最稳但慢 |
| `tessycmd import <file.xlsx>` | **不破坏**（对象原本有效时） | 只替换数据，不动接口；实测 4 个对象反复导入仍 `0x…1188` |
| `tessycmd import <file.script>`（含 `$usercode`） | **会破坏** | 实测导入后 `item=0x00`、`state_mask` 缺 `0x1000` → not executable，且事后补位无效 |
| 直接改 `testobject.xml` 的 `state_mask` | 无效 | 重开 TESSY 被重算覆盖 |
| `restore-module`（TMB） | 取决于 TMB 里存的状态 | 见 §6：**会连 TIE 配置一起回退** |
| `analyze` | **会重算有效性位；不清数据，但会清普通桩桩体** | 见 §2.1：**Ctrl+I 之后必须紧跟一次 Analyze**，否则 mask 停在 `0x80000088` |

**结论（最重要的一条）**：
> 想要"有值且可执行"，正确顺序是
> **① TIE/IDA 配置 → ② Analyze → ③ GUI `Initialize Test Data`(Ctrl+I) → ④ Ctrl+S → ⑤ Analyze → ⑥ 再用 xlsx 导入值**
> 任何"先有数据、后加接口"的顺序都会得到不可执行对象。
>
> **③ 和 ⑤ 缺一不可**：Ctrl+I 只重建数据模型（让 `Values` 有表头/列），
> 但对象 mask 仍是 `0x80000088`；再跑一次 `analyze` 才会把 `0x1000`/`0x100` 写回去，
> 变成可执行的 `0x…1188`/`0x…1198`。2026-11 在 `BSP_Dflash_UT`、`BSP_eeprom_UT` 上各验证一次。

### 2.1 数据模型被写成空表后的修复三步（`Values` 只有 `[] []`）

**识别**：`export -format yaml` 后 `Values:` 段形如

```yaml
Values:
- []
- []
- [tc1.1]      # 只有用例标签，没有表头行/变量行
```

= 数据模型是空的（外部导入把接口列写丢了），此时 xlsx/script 怎么导都没用，对象 mask 通常
`0x80000088`（连 `0x1000` 都没有）。

**修复（3 步，前两步在 GUI）**：

```text
1) 每个对象：TDE → Test Data → Initialize Test Data (Ctrl+I)
   → 勾 Overwrite existing test data / 全部用例 → Ctrl+S
2) 关 TESSY（保存提示 No）→ 由 CLI 侧执行：
   tessycmd analyze          # 模块级；这一步把有效性位算回去
3) 再 export xlsx → 填参数值 + 普通桩桩体 → import → 回读 mask 应为 0x…1188/0x…1198
```

实测（`BSP_Dflash_UT` 3 对象 / `BSP_eeprom_UT` 5 对象）：
只做 Ctrl+I 时 mask 仍 `0x80000088`；补一次 `analyze` 立刻变
`0x80001188`（用例 `0x80001100`）→ 填数据导入 → 执行 → **C0/C1 全 100%**。

### 2.2 情况区分：`0x80000088` 有两种成因，别一律叫用户做 Ctrl+I

| 现象 | 缺什么 | 修法（**不一定需要 GUI**） |
|---|---|---|
| yaml `Values:` 只有 `- []` `- []` `- [tc1.1]`（**没有表头行**） | 数据模型本身是空的 | 只能 GUI `Ctrl+I` → `analyze` → xlsx 填值（§2.1） |
| yaml `Values:` **有表头/变量行**，但所有**普通桩桩体为空** | 桩体不全 → 数据被判不完整 | **不需要 GUI**：`export xlsx` → 给每条用例×每个普通桩填桩体（`(void)0;` / `return 0u;`）→ `import` → mask 立刻变 `0x…1188` |

实测（`DAL_Dflash_UT` 3 对象）：`Values` 本来就有 `Erase_Address` / `Write_Address` / `Read_Address` 等列，
但桩体全空、mask `0x80000088`；仅用 xlsx 补齐桩体 + 参数值后导入，mask 直接变 `0x80001188`，
**没有做任何 Ctrl+I**，随后执行 3/3 全 100%。

> 结论：`0x1000` 位 = "测试数据完整（值 + 桩体）"。数据模型已有列时，xlsx 导入就能把它写出来；
> 只有"模型本身空"才必须走 GUI Ctrl+I。

### 2.3 第三种：mask 只有 `0x88` 的"半损坏"对象 —— `import -append -set-passing` 复活

**症状**（`DAL_GearControl_UT / DAL_Get_Gear_HallData` 实测）：

- `mask=0x88`（连 `0x1000`、`0x80000000`、`0x20000000000` 都没有），同模块其他对象是 `0x0002000000001188`；
- 用例是占位 `name="Dummy" state_mask="0x00"`；
- TDE 里能看到接口树（`Globals → s_gearHallDataType`、`Return → GEAR_HALL_DATA_TYPE`）但**没有任何可编辑列**；
- `Ctrl+I` 无反应/被禁用；`export xlsx` 只有 1 列（行号列）；
- 普通 `import` 报 `[IMPEX] Failed to import test object '...'`；
- `import -set-passing`（不带 `-append`）不报错但 mask 不变。

**成因**：对象在 PDB 里**没有数据模型记录**（早期 TMB/restore 留下的孤儿对象，id 与同模块其他对象差很远）。

**修法（3 步，全部 CLI，不需要删对象、不需要 Ctrl+I）**：

```python
# 1) 手工造最小 xlsx：列名 = 接口元素路径（用 details XML 里的 member 名）
#    Values 表：第 1 行元素名，第 2 行方向 i/o/x，第 3 行起用例值
cols = [('s_gearHallDataType.alpha_angle', 'i', '100'),
        ('s_gearHallDataType.beta_angle',  'i', '200')]
# 2) 关键：-append + -set-passing 一起用
#    tessycmd import -append -set-passing hall.xlsx      -> mask 0x88 变 0x1188，数据列出现
# 3) 再普通 import 一次（覆盖成干净用例，避免 append 出的重复用例）
#    tessycmd import hall_clean.xlsx
```

实测结果：`mask 0x88 → 0x1188`，3 条用例均 `0x1100`，对象可执行。




---

## 3. IDA（指针参数目标变量）完整流程

### 3.1 为什么要 IDA
被测函数形如：

```c
static void CAN_Controller_Rx_handler(can_msgbuff_t *canMsg)
{
    if ((canMsg->msgId == NPD_UID_PHYS) || (canMsg->msgId == NPD_UID_FUNC)) { ... }
    else { for (...) { ... } if (msgId 是网络管理帧) {...} else {...} }
}
```

`canMsg` 是**指针**：不给它一个"可赋值的测试变量"，`canMsg->msgId` 就永远是裸内存里的垃圾值，
诊断帧 / 网络管理帧 / 应用帧 / 拷贝循环 4 个分支全部不可达（实测 C0 只有 41.66%）。

### 3.2 GUI 操作（没有 CLI，必须手工）
1. 双击对象 → **TIE** → **IDA** 页
2. 选中指针参数（如 `canMsg`）→ Pointer Target = **Global Variable** → New
3. 类型选结构体（如 `can_msgbuff_t`）、名字自定义（如 `target_canMsg`）
4. 保存 → **Analyze**
5. **关键一步**：打开 **TDE** → `Test Data → Initialize Test Data (Ctrl+I)`
   - 勾 **Overwrite existing test data**
   - 范围选**全部测试用例**
   - 确定 → **Ctrl+S**

> 第 5 步就是把 IDA 变量的成员（`target_canMsg.msgId` / `.dataLen` / `.data[0..63]`）
> 真正写进数据模型。**跳过它 = 数据模型里没有这些列 = 后续怎么填都不可执行。**

#### 3.2.1 ⚠️ IDA 的"Type"列表里**没有 `uint16_t`/`uint32_t` 这类 typedef**

New Variable 对话框的 Type 列表只有 **C 基本类型 + Enums + Structs and Unions**。
若指针参数是 `uint16_t *`，在列表里找 `uint16_t` 会找不到（会有红色提示
`Please specify a type for the variable.`）——**按位宽/符号选对应的基本类型**：

| C 参数类型 | IDA 里选（Basic Types） |
|---|---|
| `uint8_t *` | `unsigned char` |
| `uint16_t *` | **`unsigned short`** |
| `uint32_t *` | `unsigned long` |
| `int8_t / int16_t / int32_t *` | `signed char` / `short` / `long` |
| `_Bool *` | `_Bool` |
| 结构体/枚举指针（`can_msgbuff_t *`、`gpio_pin_level_t *`） | 列表里直接有该结构体/枚举，选它 |

实测：`BSP_TJA1145_Send(uint16_t *data)` 的 `data` 用 `unsigned short` 建 IDA（名 `target_data`）后，
数据模型出现 `target_data`（输入）与 `target_data`（输出期望）两列，执行 100%。

#### 3.2.2 ⚠️ 指针参数被"解引用读写"时，传 `NULL` 必崩

- 只**读**指针（如 `PduInfo->length`、`sdu[i]`）：给 `NULL` 或裸地址有时能跑（桩不访问就没事）。
- **读写**指针（如 `BSP_TJA1145_Send` 里 `tmpData=*data; ... *data=...;`）：
  `data = NULL` → 目标机直接异常退出（`terminated with exit code 6`），
  **必须**用 IDA 变量或有效地址，不能图省事写 `NULL`。


### 3.3 导入后确认数据模型真的有成员列
```powershell
& $TESSY_CMD select-test-object <object>
& $TESSY_CMD export -format xlsx -file <object> $WORK
```
导出的 `Values` 表头必须出现：`canMsg`、`target_canMsg.msgId`、`target_canMsg.dataLen`、
`target_canMsg.data[0]`…`data[63]`（还会重复出现一组，属 input/output 两段，都要填）。
**没有这些列 → 回到 §3.2 第 5 步重做 Ctrl+I。**

### 3.4 指针参数值必须写"IDA 变量名"，且**名字要一丝不差**
```text
canMsg = target_canMsg      ← 正确（不是地址 0x20010000）
```
> 实测坑：同一模块里 CAN0 的变量叫 `target_canMsg`、CAN1 的叫 **`target_canMsg1`**。
> 两者都填成 `target_canMsg` 时，CAN1 的驱动生成代码是
> `TESSY_address_vector_defaultdefault[1] = (void *)&target_canMsg;`
> → 编译报 **`identifier "target_canMsg" is undefined`**。
> **务必用 `export -format xml` 查 `<var nam="...">` 的实际名字。**

### 3.5 按分支分配 msgId 的取值方案（结构化参数）
`can_msgbuff_t` 成员：`msgId`(4B)、`cs`(4B)、`data[64]`、`dataLen`(1B)。
指针不会按地址解引用到真实硬件，所以 `data` 只填 `data[0]`（或全 0）即可。

| 用例 | msgId | dataLen | 命中分支 |
|---|---|---|---|
| 1 | `0x758` | 8 | 诊断帧分支（PHYS）+ 内部 `if (judge_diag_frame_flag==1)` → 调 UDS |
| 2 | `0x7DF` | 8 | 诊断帧分支（FUNC） |
| 3 | `0x758` | 8 | 诊断帧 + judge_flag=0 → 空 else |
| 4 | `0x67E` | **0** | 非诊断帧 + 拷贝循环**跳过**（`dataLen=0` 直接不进入 for） |
| 5 | `0x626` | 8 | 非诊断帧 + 循环执行 + **网络管理帧**（判据 `msgId!=NMID && (msgId>>8)==(NMID>>8)`） |
| 6 | `0x123` | 8 | 非诊断帧 + 循环执行 + **应用帧**（`CanIf_RxIndication`） |
| 7 | `0x7DF` | 8 | 备用组合（judge_flag=1） |

CAN1 版本（`CAN1NMID=0x67E`）：`0x758/8`、`0x7DF/8`、`0x626/8`、`0x123/8`、`0x67E/8`、`0x7EF/**0**`。

### 3.6 批量填写脚本骨架（XLSX，安全）

> 已封装成可直接运行的脚本：`scripts/fill_ida_pointer.py`，
> 配套示例 `examples/can_controller_rx_handler_ida.json`、
> `examples/can1_controller_rx_handler_ida.json`：
>
> ```powershell
> python scripts\fill_ida_pointer.py examples\can_controller_rx_handler_ida.json
> # 输出：[auto] IDA 变量名 / [import] ok / [mask] object=0x80001188 testcase=0x80001100 -> OK 可执行
> ```
>
> 下面是其核心逻辑，便于按需改写：

```python
import openpyxl, subprocess, os
TESSY = r'D:\tessy\Razorcat\TESSY_5.1\bin\tessycmd.exe'
VAR = 'target_canMsg'          # ← 用 export xml 里 <var nam=...> 的真实名字
obj = 'CAN_Controller_Rx_handler'
plan = [('0x758', 8, '1'), ('0x7DF', 8, '0'), ('0x758', 8, '0'),
        ('0x67E', 0, '0'), ('0x626', 8, '0'), ('0x123', 8, '0'), ('0x7DF', 8, '1')]

sh = lambda *a: subprocess.run([TESSY]+list(a), capture_output=True, text=True).stdout
for c in (('connect',), ('select-project','T1V_test'), ('select-test-collection','New Test Collection'),
          ('select-module','-test-collection','BSP_Can_UT'), ('select-test-object', obj)):
    sh(*c)
sh('export','-format','xlsx','-file',obj,WORK)
p = os.path.join(WORK, obj + '.xlsx'); wb = openpyxl.load_workbook(p); ws = wb['Values']
cols = {}
for c in range(1, ws.max_column+1):
    v = ws.cell(1, c).value
    if v: cols.setdefault(v, []).append(c)     # 同名列可能出现两次（in/out 两段），全要填
for i, (msgid, dlen, flag) in enumerate(plan):
    r = 3 + i
    for c in cols['canMsg']:                 ws.cell(r, c).value = VAR
    for c in cols[VAR+'.msgId']:             ws.cell(r, c).value = msgid
    for c in cols[VAR+'.dataLen']:           ws.cell(r, c).value = str(dlen)
    for c in cols.get(VAR+'.cs', []):        ws.cell(r, c).value = '0'
    for k in range(64):
        for c in cols.get('%s.data[%d]' % (VAR, k), []): ws.cell(r, c).value = '0'
    for c in cols.get('judge_diag_frame_flag', []):      ws.cell(r, c).value = flag
wb.save(p)
sh('import', p)      # xlsx 导入不破坏有效性
```
导入后再读一次 `testobject.xml`，确认 `state_mask` 仍含 `0x1000`。

---

## 4. 分支覆盖：高级桩没有 Call Count 怎么办

场景：

```c
case CAN_EVENT_RX_COMPLETE:
    while (CAN_REG_IsRxFifoEmpty(CAN0_REGBASE) == false)   /* 需要先 0 后 1 */
    { (void)CAN_Receive(instance, &CAN0_Receivebuff);
      CAN_Controller_Rx_handler(&CAN0_Receivebuff); }
```

TESSY 5.1 的高级桩只能给**一个**固定返回值：
- 返回 `0` → 进循环体，但恒为 0 → 死循环；
- 返回 `1` → 循环体 0 覆盖。

**解法：把该函数改成"普通桩"，桩体用静态计数器**

```c
/* 普通桩桩体（Stubs 页） */
static int ts_cnt = 0;
ts_cnt++;
return (ts_cnt > 1) ? 1 : 0;     /* 第 1 次 0 → 进入循环体；第 2 次 1 → 退出 */
```

如果**同一对象里还有别的用例会调用同一个桩**（或需要按用例变化），桩体要能用"模块全局变量"门控：

```c
static int ts_cnt = 0;
if (PduTxId == 2u) { ts_cnt++; return (ts_cnt > 1) ? 1 : 0; }
return 1;
```
配合数据里把 `PduTxId` 按用例设为 `2`/`1`/`0`。

> ⚠️ **桩体里不能引用被测函数的形参**。桩函数是独立函数，看不到调用者的 `instance`/`event`。
> 实测：桩体写 `if (instance == 2u)` → 编译报 `identifier "instance" is undefined`。
> 只能用**模块全局变量**（如 `PduTxId`、`judge_diag_frame_flag`）或自己 `static` 的计数器。

> ⚠️ TESSY 会把"每个用例都相同"的桩体合并成**对象级（Test Case=0）一行**。所以
> 「按用例不同返回值」不要指望逐行不同桩体，要靠上面的全局变量门控。

---

## 5. 执行入口：只在模块上 Execute

- 在 **TDE 里**点 Execute → 只对"当前对象"，对象无效时报
  **`No executable test object selected for execution.`**（常被误读成"整个模块坏了"）。
- 正确姿势：左侧工程树 **右键模块 → Execute Test**，勾 `Run` + `Force generate driver`。
- 执行前必须重启 TESSY 让 DB 里的新数据生效；**关闭时若提示保存，选 `No`**
  （否则界面里的旧数据会覆盖刚导入的数据）。

---

## 6. `restore-module` 的副作用（务必记住）

`restore-module` 用 TMB **整体替换模块**，会一并回退：
- **TIE 配置（IDA 变量、桩类型普通/高级）**
- 测试数据、执行结果、覆盖率

实测：辛苦改好的 IDA 变量 + 普通桩，被一次 `restore-module` 全部还原成旧 TMB 状态，
CID 就此丢失、对象又变不可执行。

因此：
1. **改动前**先 `save-db -source module -to <备份目录>`。
2. 改 TIE 后先 `save-db`，再考虑任何 restore。
3. 出问题优先"补数据/再 Analyze"，**不要**随手 restore。

---

## 7. 一次完整有效的循环（可直接照做）

```text
1) 读状态：python scripts/check_executable.py <project> <collection> <module>
   （或直接看 yaml 的 Values 段：只有 [tc1.1] 没有表头 → 数据模型空，走 §2.1 三步）
2) 若对象不可执行：
   a. TIE 建 IDA / 改桩类型 → Analyze
   b. TDE Ctrl+I（Overwrite，全部用例）→ Ctrl+S
   c. **再跑一次 `tessycmd analyze`**（漏这步 mask 停在 0x80000088，见 §2.1）
   d. 再跑 check_executable.py，确认 0x…1188 / 0x…1198
3) 导出 xlsx → 用脚本填值（指针=IDA变量名；msgId/dataLen/cs/data；普通桩桩体）
   `python scripts\fill_ida_pointer.py examples\can_controller_rx_handler_ida.json`
4) import xlsx → 再 check_executable（确认仍有效）   ← fill_ida_pointer.py 已自动做这步校验
5) 关闭 TESSY(选 No) → 重开 → 右键模块 Execute
6) 读覆盖率：work\<mod>\<obj#>\ts_c0_*.txt / ts_c1_*.txt 的 C0-COVERAGE / C1-COVERAGE
```

---

## 8. 案例结果（BSP_Can_UT，13 对象）

| 对象 | C0 | C1 | 关键动作 |
|---|---|---|---|
| BSP_CAN0_Init / BSP_CAN1_Init / BSP_CAN_TxByInstance | 100% | 100% | 常规用例 |
| CAN_Controller_Busoff_handler / CAN_Controller_Tx_handler | 100% | 100% | 常规用例 |
| CAN_GetTxInstanceByHth / Can_SetControllerMode / UDS_Datalink_TransmitRequest | 100% | 100% | 常规用例 |
| BSP_Can_Write | 100% | 100% | IDA `target_PduInfo` + `length=8` + `CAN_Send` 返回 0/1/2/3/5 |
| CAN0_IRQCallback / CAN1_IRQCallback | 100% | 100% | 11 条事件用例 + `CAN_REG_IsRxFifoEmpty` 改普通桩 + 计数器桩体 |
| CAN_Controller_Rx_handler | 100% | 100% | IDA `target_canMsg` + Ctrl+I + 7 条 msgId 用例 |
| CAN1_Controller_Rx_handler | 100% | 100% | IDA **`target_canMsg1`** + Ctrl+I + 6 条 msgId 用例 |

### 8.1 数据模型为空型（`0x80000088`）——Ctrl+I + Analyze 两步修复

| 模块 / 对象 | 状态 | C0 | C1 | 关键动作 |
|---|---|---|---|---|
| BSP_Dflash_UT（3 对象：Erase_Page / Write / Read） | 原 `0x80000088` 全部不可执行 | 100% | 100% | Ctrl+I（GUI，3 个对象）→ `tessycmd analyze` → mask `0x80001188` → 填 `Erase/Write/Read_Address=0x00010000`、`length=8/0`、指针 `NULL`、普通桩桩体（`FLASH_Unlock/Lock`→`(void)0;`、`FLASH_ErasePage/ProgramSection`→`return 0u;`）→ import → Execute |
| BSP_eeprom_UT（5 对象：JobErrorNotification / Init / Write / Read / MainFunction） | 原 `0x80000088`（Write/Read） | 100% | 100% | Ctrl+I → `analyze`（5 对象全变 `0x…1198`/`0x…1188`）→ 填 `blockId/offset/length/dataBuffer=NULL/buffer=NULL` + 普通桩桩体（`FLASH_Eeprom_*`→`return 0u;`，void 的 `FLASH_Eeprom_MainFunction`→`(void)0;`）→ import → Execute |

> 这两个模块的函数都是**无分支直线调用**（`FLASH_Unlock → FLASH_ErasePage → FLASH_Lock` 这类），
> 所以修复后自然 100%；难点**只在数据有效性**，不在用例设计。
> 桩体注意：`void` 函数的普通桩桩体写 `(void)0;`，非 void 写 `return 0u;`（按返回类型）。

### 8.2 分支覆盖 + 越界数据 + IDA 基本类型（BSP_GPIO_UT / BSP_SPI_UT）

| 模块 / 对象 | 原问题 | C0 | C1 | 关键动作 |
|---|---|---|---|---|
| BSP_GPIO_UT / GPIOB_IRQHandler | `0x80000088`，`Values` 空表 | 100% | 100% | Ctrl+I → `analyze` → 5 条用例：`g_rightRollerQueueTail`(纯输入全局) 当**用例选择码** 0..4；`GPIO_GetPinIntFlag` 桩按码返回 1,0 / 0,1；`GPIO_ReadPin` 桩按码返回 低,高 / 高,高 → 左/右 × 判定真/假 四分支全覆盖 |
| BSP_GPIO_UT / 4 个 Push/Pop 对象 | 自动生成用例把 **90** 当下标 → `queue[90]` 越界写 → **slave exit code 6** | 100% | 100% | 改成合法数据：Push `head=0,tail=0/1`（写/队列满）；Pop `head/tail=0/1`、`queue[0]=7`（非空/空） |
| BSP_SPI_UT / 5 对象 | 桩体全空（`MissingStubCode`）；`TJA1145_Send` 的 `data=NULL` 被解引用读写 → 崩 | 100% | 100% | 桩体按返回类型补（`SPI_MasterInit`/`SPI_MasterTransferBlocking`→`return 0u;`、`GPIO_*`→`(void)0;`）；`TJA1145_Send` 的 `uint16_t *data` 建 IDA（类型选 **`unsigned short`**，名 `target_data`）→ Ctrl+I+Analyze → `data=target_data`、`target_data=0x1234`、期望 `ERR_SUCCESS`/`0` |

**无参数对象的用例区分技巧**：函数没有形参时，用某个**纯输入全局变量**（只被读、不被写）当
"用例选择码"，桩体按它的值切换返回序列，并用 `static int cur` 检测"码变了就重置计数器"。
`BSP_GPIO` 里选的是 `g_rightRollerQueueTail`（只被 Push 比较，不被写，最干净）。

### 8.3 DAL 包装层（DAL_CAN_UT / DAL_Dflash_UT）

这两个模块都是**一行透传**的 DAL 包装（`DAL_Xxx(...) { BSP_Xxx(...); }`），没有分支，
修的都是数据完整性：

| 模块 / 对象 | 原问题 | C0 | C1 | 关键动作 |
|---|---|---|---|---|
| DAL_CAN_UT / DAL_Can_Write | `0x80000088`，`Values` **空表** | 100% | 100% | Ctrl+I → `analyze` → `Hth=1/2`、`PduInfo=NULL`（**本函数不解引用指针，不需要 IDA**）、桩体 `return 0;`/`return 1;` → import |
| DAL_Dflash_UT / Erase_Page / Write / Read | `0x80000088`，但 `Values` **有列**、桩体全空 | 100% | 100% | **无需 GUI**：xlsx 补齐桩体（`BSP_Dflash_*` 均 void → `(void)0;`）+ 参数值（`*_Address=0x18000000`、`length=8/3/0`、指针 `NULL`）→ import → mask 变 `0x80001188` |
| DAL_eeprom_UT / MainFunction / Write / Read（5 对象） | 同上，`Values` 有列、桩体空 | 100% | 100% | 同上：`BSP_eeprom_*`/`DAL_Tim_*` 桩体按返回类型补；`MainFunction` 两条用例分别让 `DAL_Tim_CheckTimeOut` 返回 1/0 覆盖 if 两侧（`EepromMainFuncTimer` 输入 0x1000、`GetCurrentTime` 返回 0x2000） |

> `DAL_Can_Write` 的返回值列 Ctrl+I 后没生成 → RS 可能 notok，但覆盖度正常（见 pitfalls V19）。

### 8.4 分支型模块补覆盖（DAL_GearControl_UT）

| 对象 | 起始覆盖 | 最终 | 关键动作 |
|---|---|---|---|
| DAL_GearControl_Init | C0 75% / C1 50% | 100% / 100% | 3 条用例：`Gear_Hall_ReadConfigSTS`(纯输入全局)=1 → 外层 if 假；=0 且 `ReadModeConfigSTS` 桩返回 `0x0F`(ALL_OK=0x1\|0x2\|0x4\|0x8) → 内层 if 真（写 EEPROM 标志，唯一未覆盖语句）；=0 且返回 0 → 内层假 |
| DAL_updateGearPositiondata_Task | C0 10% / C1 12.5% | 100% / 100%（补第 5 条后） | 5 条用例：①`CheckTimeOut`桩=0（外层假）②=1 且 `ReadStep`=0(START_3D)③=1、`ReadStep`=1、`DIAG_STATE`=0（诊断失败）④=1、1、`DIAG_STATE`=1（成功）⑤=1、`ReadStep`=**99**（`else if` 两假，补最后一个分支） |

> 注意坑：`DAL_GearControl_Init` 的 8 个普通桩、`updateGear` 的 5 个普通桩都要**每用例**有桩体；
> 先用通用脚本"按返回类型批量补"会把分支设计同质化（V23），正确顺序是**先分支设计再补默认桩**。

### 8.5 指针参数 + 桩写回（DAL_SBC_UT）

| 对象 | 起始 | 最终 | 关键动作 |
|---|---|---|---|
| DAL_SBC_Check_Reg | `mask=0x80000088`，执行**卡死** | 100% / 100% | 对象级桩体为空 → 补；`uint8_t *cnt` 被 `*cnt` 解引用 → **必须 IDA**（`cnt = target_cnt`，`target_cnt` 输入 0/0/3）；3 用例覆盖「相等提前返回 / 自增重写 / 达上限置错误位」；期望 `target_cnt` 0/1/3、`SbcRegConfigErr` 0/0/4 |
| DAL_SBC_Read_Reg_Config | `mask=0x80000088` | 100% / 100% | 补 `IM1169_Spi_Read/Write` 每用例桩体；函数无分支 |
| DAL_SBC_Read_WindowDog_Period | C0 75% / C1 50% | 100% / 100% | 局部 `s_crvalue` 由桩 `IM1169_Spi_Read(addr, value)` **通过指针写回**；桩体改为 `{ if (value) { *value = 0x02U; } return 1; }`（tc1）与 `0x00U`（tc2），期望返回 1/0 |

> 三个反复出现的坑（详见 pitfalls V25–V27）：
> 1. 指针参数填 `NULL` → 执行卡死（`out_*.dat` 0 字节、`ts_*_m.exe` 占 CPU）；
> 2. 指针参数填裸全局名/`&全局名` → 前者静默为 0、后者 import 500 并清空数据模型；
> 3. 普通桩不写 `*value` → 被测函数里的局部输入恒 0，分支覆盖卡在 50%。




编译环境补丁（不属于产品代码）：ARMCC 报 `#3092 anonymous unions` 时，在
`<TESSY安装>\sys\templates\make\ts_make_uvision_uvsc_arm_v5.tpl` 的编译行加
`--preinclude=<路径>\ts_anon_unions.h`（该头文件内容为 `#pragma anon_unions`），并备份模板。
注意：项目目录下的同名模板**不生效**，必须改安装目录里的那份。
