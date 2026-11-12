# 运维手册：备份/恢复、卡死处理、诊断日志、收尾清理

> TESSY 5.1 在真实工程里会"吃掉"数据（退出时丢模块对象）、会卡在行内寄存器函数上、
> 会遗留 CTE 孤儿数据。本文件把这些事故的处理步骤固化，避免每次现场摸索。

---

## 1. 铁律：改完就备份（save-db），关 TESSY 前必须备份

### 事故现象

TESSY **正常退出**（File → Exit，非强杀）后重新打开，**最近被修改过的模块对象数变成 0**
（例：`DAL_SBC_UT` 从 7 个对象变成 0；另一次是 7 个模块同时变空）。测试用例、桩数据一起丢。

### 规则

1. **任何"批量导入/改属性/分析"之后**，立刻给被改模块做 TMB 备份；
2. **关闭 TESSY 之前**，给所有模块做一遍备份；
3. 备份是 `.tmb` 归档，一个模块一个文件。

```powershell
& $TESSY_CMD select-test-collection $TESSY_COLLECTION
& $TESSY_CMD select-module -test-collection $TESSY_MODULE
& $TESSY_CMD save-db -source module -to <备份目录>
# 产物：<备份目录>\<集合名>.<模块名>.tmb
```

全量备份（30 个模块约 2~3 秒/模块）：

```powershell
$mods = (& $TESSY_CMD list-modules -test-collection) | Where-Object {$_ -and $_.Trim()}
foreach($m in $mods){
  $mm=$m.Trim()
  & $TESSY_CMD select-module -test-collection $mm | Out-Null
  & $TESSY_CMD save-db -source module -to $BAK | Out-Null
}
```

> `save-db` 的输出文件名里空格会编码成 `%20`（如 `New%20Test%20Collection.appl_gear.tmb`），
> `restore-module` 时要用**这个带 %20 的真实文件名**。

---

## 2. 恢复：restore-module（对象丢了/接口搞坏了）

```powershell
& $TESSY_CMD select-test-collection $TESSY_COLLECTION
& $TESSY_CMD restore-module -test-collection "<备份目录>\New%20Test%20Collection.<模块名>.tmb"
& $TESSY_CMD select-module -test-collection <模块名>
& $TESSY_CMD list-test-objects
```

语义（实测）：

- **同名模块被整体替换**（模块数量不变），对象、用例、桩数据、接口方向一起回来；
- TMB 是"当时那一刻"的快照 → 恢复后要**补回快照之后做过的改动**（例如期望值回填）；
- TESSY 必须在运行（restore 走 GUI 进程）。

> 经验：`restore-module` 是"被自己搞坏"时唯一可靠的后悔药。任何"要试新玩法"的操作前，
> 先 `save-db` 一个快照，出问题 30 秒内恢复。

---

## 3. 卡死：目标里的 while/寄存器轮询

### 现象

- 批处理执行停在某个对象很久；`exp.exe` 长时间不退出；整轮执行"卡在 33%"；
- 被杀之后 UV4/`ts_*_m` 进程残留，后续对象报 `Error opening branches file`。

### 已知会死循环/死等的代码形态

| 代码 | 原因 |
|---|---|
| `static inline` 寄存器访问器（`CAN_REG_AbortTxMsg` / `CAN_REG_ClearIntFlag` / `CAN_REG_IsBusoff`…） | 轮询硬件寄存器，无仿真就永远等 |
| `void DAL_System_Delay(x){ while(DAL_Tim_CheckTimeOut(...)==0){} }` | 同文件内的 `static inline` 无法打桩 → 死循环 |

### 处理

1. **提前排除**：这类函数不要建测试对象（Test Object Exclude List）；
   已经建出来的对象**删不掉**（Delete 置灰）、Exclude List 对存量对象也无效 →
   只能"跑的时候接受它"。
2. **看门狗**（能救整轮批处理）：后台循环杀掉超龄执行进程，让 TESSY 继续下一个对象：

```powershell
for($i=0;$i -lt 2000;$i++){
  Start-Sleep -Seconds 5
  $now=Get-Date
  foreach($p in (Get-Process -Name 'ts_*_m' -EA SilentlyContinue)){
    try { if($p.StartTime -and ($now-$p.StartTime).TotalSeconds -gt 35){ Stop-Process -Id $p.Id -Force -EA SilentlyContinue } } catch {}
  }
  foreach($p in (Get-Process -Name 'exp' -EA SilentlyContinue)){
    try { if($p.StartTime -and ($now-$p.StartTime).TotalSeconds -gt 45){ Stop-Process -Id $p.Id -Force -EA SilentlyContinue } } catch {}
  }
}
```

3. **执行超时选项没用**：`Execution Timeout` 设 30000 也不会中断这种死等；
4. 一个对象被卡死杀掉后，TESSY 会**继续下一个**（用 `[EXE] Test execution finished after …` 判断结束）；
5. 收尾必须清残留：`Get-Process ts_*_m,exp,UV4 | Stop-Process -Force`，否则下一轮报 branches 文件错误。

### 建议排期

- 含 `CAN_REG_*` 的模块（如 `BSP_Can_UT`）**单独放最后跑**，跑的时候准备随时 Stop；
- 其它模块正常 8~10 秒/对象。

---

## 4. CTE "REMOVED" 提示的清理

### 现象

GUI 里对象前出现红色感叹号，悬停提示：

```text
REMOVED: This test object has been removed (or renamed). You may assign the test data
to another existing test object and perform a reuse in the IDA perspective.
```

### 根因

该测试对象上挂了 **CTE（分类树）数据**（属性 `CTEX File` 指向
`persist\…\ .tdb\<n>\testSpecification.ctex`）。当对象被重新分析/用例 UUID 变化后，
CTE 数据里的引用失效，TESSY 的 CTE 插件（`CteEditorExtension`）就报 REMOVED。

### 清理步骤

1. 找出唯一挂了 CTE 的对象：

```powershell
& $PY -c "import os,xml.etree.ElementTree as ET; P=r'<project persist 目录>'; [print(ET.parse(os.path.join(dp,f)).getroot().get('name'), os.path.join(dp,f)) for dp,dn,fn in os.walk(P) if 'testobject.xml' in fn for f in ['testobject.xml'] if 'CTEX File' in [p.get('name') for p in ET.parse(os.path.join(dp,f)).getroot().iter('property')]]"
```

2. 清属性（TESSY **运行时**执行；退出时落盘才生效）：

```powershell
& $TESSY_CMD select-module -test-collection <模块名>
& $TESSY_CMD select-test-object <对象名>
& $TESSY_CMD unset-attribute 'CTEX File'
```

   注意：`unset-attribute` 对"property 型"属性会返回 `Cannot invoke "…Attribute.getDeclaration()" because "attrib" is null`
   —— **这条错误说明"已经不存在了"，是成功**；`get-attribute` 之后也报同样错误即为已清除。

3. 正常关闭 TESSY（File → Exit，**不要**任务管理器强杀）→ 重启后检查：

```powershell
& $PY -c "… 扫描 testobject.xml 里是否还有 CTEX File …"     # 应为 0 个
```

4. 把孤儿的 `testSpecification.ctex`、`ctenodemap.dat`、`ctepassing.dat` 移到备份目录（不要留在原处）。

5. 另有一类 REMOVED 是**历史运行记录**：删掉临时测试集合后，Test Runs / IDA 视角里那些 run
   仍指向已删对象 → 显示 REMOVED。**不影响任何测试**，需要干净就在 Test Runs 视图里删 run。

---

## 5. 诊断日志在哪

| 日志 | 路径 | 用途 |
|---|---|---|
| TESSY 问题日志 | `%USERPROFILE%\.tessy_51_workspace\.metadata\problems.log` | 导入失败、异常堆栈（`[IMPEX] Failed to import…`） |
| 执行日志 | `…\.metadata\execution\<HI>\<LO>\<id>.log` | 每个对象/模块的执行日志 |
| TI 错误 | `…\.metadata\ti.error.log` | 目标/调试口（`TE - Error (10054)`） |
| 对象生成产物 | `<PROJECT>\tessy\work\<HI>\<LO>\<n>\` | `ts_*.c`、`ts_*.coverage.xml`、`ts_c0_*_report.txt` |
| 对象数据 | `<PROJECT>\tessy\persist\tessy\project\<HI>\<LO>\.tdb\<n>\` | `testobject.xml`、`testresult_*.xml` |

### 覆盖率从哪里读

```powershell
# 每个对象的覆盖度在 work 目录的 coverage xml 里
# <PROJECT>\tessy\work\<模块目录>\<对象目录>\ts_<id>.coverage.xml
# 字段：c0_data reached_branches / number_branches / coverage
#       c1_data 同上
```

对象名与目录的对应：同目录下 `ts_*_m.cpp` 里 `#define TS_TESTOBJECT "对象名"`。

### 从 testresult 反查失败原因

```powershell
# persist 下每个对象目录的 testresult_<id>.xml
# <result name="..." expected_value="..." actual_value="..." success="notok"/>
```

- `expected_value="-"` ⇒ 期望值**无效/未设置**（不是"期望为空"）；
- `actual_value` 与 expected 不一致 ⇒ notok；
- 想批量把 notok 变绿（特征化）：对每个失败用例把 expected 改成 actual 再导入，
  但优先修真正的期望值。

---

## 6. TESSY 启动/关闭的正确姿势

```powershell
# 启动：必须经过 explorer（否则报 CreateProcess failed with error 5）
Start-Process explorer.exe -ArgumentList '"D:\tessy\Razorcat\TESSY_5.1\bin\TESSY.exe"'
# 等 30~45 秒再 connect
& $TESSY_CMD connect
& $TESSY_CMD list-projects
```

- **关闭用 GUI 的 File → Exit**，让 TESSY 把模型写盘（我们靠这个才让 `unset-attribute` 生效）；
- 关之前先 `save-db` 全量备份（见 §1）；
- 重启后**第一件事**核对：

```powershell
& $TESSY_CMD list-test-collections
& $TESSY_CMD list-modules -test-collection
# 逐模块 list-test-objects，确认对象数没变少
```

发现某模块对象变 0 → `restore-module` 从 TMB 恢复（§2）。

---

## 7. 临时集合的收尾

`tessycmd` **没有**删除测试集合/测试对象的命令。为验证而建的临时集合
（`_preflight`、`_verify2`、`_dbg3` 之类）只能由用户在 GUI 里右键 → Delete 清掉。
所以：**能不开临时集合就不开**；必须要开时，命名统一加前缀，最后列一份清理清单交给用户。
