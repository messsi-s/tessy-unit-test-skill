# 建桩请求模板（发给用户直接复制）

TIE 配置存在 TESSY 工程数据库里，没有 CLI 入口，只能请用户在 GUI 里操作。
把下面的模板按项目改名后发给用户；用户建完（或建不了）会回复，你再继续生成用例。

---

## 模板 A：需要"按用例控制返回值"（推荐 Advanced Stub）

```text
请在 TESSY 的 TIE（Test Interface Editor）里为下列测试对象建桩，建完回复我，我来生成用例：

测试对象：<对象名>
  1) <函数名>        → 建 Advanced Stub（返回值用于控制 <分支说明>）
  2) <函数名>        → 建 Advanced Stub（返回值类型 <类型>）
测试对象：<对象名2>
  3) <本地函数名>（在 Local Functions 分组里）→ 建 Advanced Stub

操作要点：
- 右键函数 → 选 "Create Advanced Stub"（不要选 "Create Stub"）。
- 作用域选"当前测试对象"（或全局高级桩，但全局会影响其他对象的数据接口）。
- 高级桩建好后，接口里会出现 `函数名()` / `函数名().成员` / `函数名(参数名)` 变量，
  这些变量的方向（IN/OUT）由 TESSY 自动决定，不需要你手工改。
- 建完请点一次 Analyze（或告诉我，我来 Analyze）。
```

## 模板 B：只需要隔离外部依赖（普通桩即可）

```text
请在 TESSY 的 TIE 里为 <对象名> 建普通桩：
  函数：<函数名>  → 右键 "Create Stub"
我这边会用 Stubs 表为每条用例写桩体（返回确定值），不需要你写代码。
```

## 模板 C：建不了/找不到函数时的排查

```text
如果 TIE 里找不到该函数，请确认：
1) 该函数是否在当前测试对象的 External Functions / Local Functions 列表里；
2) 模块是否已 Analyze（源码刚改过的话先 Analyze）；
3) 函数名是否带有参数签名（TIE 显示的是完整签名，按函数名找到即可）。
```

---

## 建桩后如何验证（你来做，避免用户白建）

```powershell
# 1) 看函数是不是 advanced
python scripts\check_stubs.py <对象名> <函数名...>
# 2) 看接口里有没有高级桩变量（高级桩才会有）
python scripts\inspect_interface.py <对象名>
# 3) 若仍是 none：让用户确认是否点了 "Create Advanced Stub"、是否 Analyze 过
```

## 如果用户坚持不建高级桩

用**普通桩**也能完成用例：Stubs 表写桩体（`return 1u;`、结构体返回 `GEAR_HALL_DATA_TYPE d; d.alpha_angle=86U; return d;`）。
但**不要**在高级桩生效时写普通桩桩体——会被静默忽略。
