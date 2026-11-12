# tessycmd 命令速查（TESSY 5.1.x）

所有命令都通过本地 HTTP 服务操作 **正在运行的 TESSY GUI**，因此先确保 GUI 已启动。

```powershell
$TESSY_CMD = & "$env:TESSY_BIN\tessycmd.exe"
```

## 会话与选择

| 命令 | 说明 |
|---|---|
| `connect` | 连接 TESSY（每次脚本开头的第一个命令） |
| `which` | 打印当前选中链（项目/集合/模块/对象） |
| `select-project <name>` | 选工程 |
| `select-test-collection <name>` | 选测试集合 |
| `select-module -test-collection <module>` | 选模块（注意参数名是 `-test-collection`，值是模块名） |
| `select-test-object <name>` | 选测试对象 |
| `list-test-objects` | 列出模块下所有测试对象 |
| `list-modules` / `list-test-collections` / `list-projects` | 列出上层元素 |

## 模块配置

| 命令 | 说明 |
|---|---|
| `new-test-collection <name>` | 新建测试集合 |
| `new-module -env "<环境名>" -test-collection <collection>` | 新建模块 |
| `add-source-file <path>` / `remove-source-file -all` | 增删模块源文件 |
| `add-include-dir <dir>` / `remove-include-dir <dir>` | 头文件目录 |
| `add-define <MACRO=VALUE>` | 预处理宏 |
| `analyze` | 重新分析当前选择（会**清空执行结果**、**清空普通桩桩体**） |
| `restore-module` | 还原模块 |

## 测试数据导入导出

| 命令 | 说明 |
|---|---|
| `export -format xlsx -file <name> <dir>` | 导出模板/数据（xlsx 含 Values/Properties/Stubs 等工作表） |
| `export -format csv -file <name> <dir>` | 导出接口+数据（第 1 行变量名，第 2 行方向 i/o） |
| `export -format xml -file <name> <dir>` | 导出**详情报告**：含 `interfaceReport`（stub 类型/方向）、testcase actual/expected |
| `import [ -append ] <file>` | 导入测试数据（**默认整体替换**，不是追加） |

## 执行

| 命令 | 说明 |
|---|---|
| `exec-test -o <reportDir> <file.tbs>` | 按批处理文件执行测试并生成报告 |
| `exec-test <file.tbs>` | 只执行，不指定输出目录 |

## 批处理 `.tbs` 模板（最常用）

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<batchtest>
  <operations>
    <operation key="executeTest">
      <options>
        <option key="checkInterface" value="true"/>
        <option key="generateDriver" value="true"/>
        <option key="run" value="true"/>
        <option key="createNewTestRun" value="true"/>
        <!-- 覆盖率测量：NONE | TESTOBJECT_ONLY | CALLED_FUNCTIONS -->
        <option key="instrumentationType" value="TESTOBJECT_ONLY"/>
        <option key="defaultCoverage" value="true"/>
        <option key="defaultCoveragePerTestObject" value="false"/>
        <option key="abortOnMissingStubCode" value="false"/>
      </options>
    </operation>
    <operation key="generateBatchReport">
      <options>
        <option key="reportOutputDirectory" value="C:\path\to\reports"/>
        <option key="reportFileNamePattern" value="Gear_UT_Report"/>
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
  <!-- 只用 testcollection 可靠；testobject/module 元素会被静默忽略 -->
  <elements>
    <testcollection name="New Test Collection"/>
  </elements>
  <settings>
    <setting key="reportLogoImage" value=""/>
    <setting key="reportTemplatePath" value=""/>
  </settings>
</batchtest>
```

执行完的报告 XML 结构要点：

```xml
<report success="ok|notok|notexecuted">
  <summary>
    <statistic total="45" ok="45" notok="0" notexecuted="0"/>
  </summary>
  ...
  <tessyobject type="testobject" name="appl_xxx">
    <testcase_statistics total="11" ok="11" notok="0" notexecuted="0"/>
  </tessyobject>
</report>
```

## 环境属性文件（需要 CLI 改配置时）

| 文件 | 说明 |
|---|---|
| `%APPDATA%\Razorcat\TESSY\5.1.10\config\configuration_*.ini` | TEE 环境属性（编译器/目标/调试/覆盖率等）。备份后编辑，**先停 TESSY** |
| `<project>\persist\tessy\project\<x>\<y>\module.xml` | 模块属性（排除列表、Project Target、Use UVSC Flash 等）。模块值会被环境值覆盖 → **两处一起改** |
| `<project>\persist\tessy\project\<x>\<y>\.idb\current\*.xml` | 接口 IDB（只读参考，勿手改） |
| `<project>\persist\tessy\project\<x>\<y>\.tdb\<n>\testresult_*.xml` | 历史执行结果（含 interfaceReport/stub 类型，排错用） |

## 典型执行环境属性（Keil/uVision）

| 属性 | 硬件执行 | 仿真执行 |
|---|---|---|
| `Project File` | `$(PROJECTROOT)\...\xxx.uvprojx` | 同左 |
| `Project Target` | 与 Keil 中 J-Link target 同名 | 与 Keil 中 Simulator target 同名 |
| `Target Install Path` | `C:\Keil_v5\UV4` | 同左 |
| `Use UVSC Flash` | `true`（Flash 下载） | `false`（或改 RAM 调试） |
| `Scatter File` / `Startup File` / `System File` | 指向项目实际文件 | 同左 |
| `TESSYTHCmd` | `$(Target Install Path)\UV4.exe "$(Project File)" -s $(Port) -t"$(Project Target)"` | 同左 |

> 若 `UVSC.dll` 目录下缺 `libUVSC.a`，master 链接会报 `-lUVSC` 找不到，用 `dlltool` 从 `UVSC.dll` 生成后放到 `UV4` 目录。
