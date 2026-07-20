# cliyard v0.1 MVP 实现计划

## TL;DR

> **Quick Summary**: 构建 cliyard v0.1 — 通用 YAML 驱动 CLI **代码生成框架**。用户写 YAML 描述 API，运行 `cliyard gen --name mytool --defs-path ./specs/` 生成一个独立的 CLI 工具。生成的工具（如 `ketacliv2`）是 cliyard runtime 的薄包装，spec 目录 baked-in 为 package data。
>
> **Deliverables**:
> - 可 pip install 的 Python 包（`cliyard` 命令）
> - `cliyard gen` 命令 — 生成独立 CLI 工具包
> - `cliyard.runtime` — 生成的 CLI 依赖的运行时库（加载器、认证链、命令生成、HTTP 客户端）
> - 目录即服务加载器（`_service.yaml` + 资源 YAML 文件）
> - 3 步认证链（env → login → inject）
> - 5 种字段类型 + 格式校验（string/int/float/bool/enum）
> - 以 ketacli repos.yaml 等效的 cliyard spec 作为示例，用 `cliyard gen` 生成 `ketacliv2` CLI
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: 1 → 7 → 8 → 12 → 18 → 21 → F1-F4

---

## Context

### Original Request
用户希望基于 ketacli 的 YAML 驱动架构，做一个全新的通用 CLI 框架项目（cliyard），不改造现有 ketacli。核心思路：**写 YAML 定义 API → 自动生成 CLI 命令**。项目已创建骨架在 `/data/git-project/cliyard/`。

### Interview Summary
**Key Discussions**:
- **目录即服务**: 一个目录 = 一个 API 服务，`_service.yaml` 管全局，资源 YAML 管端点，`_service.local.yaml` 管本地覆盖（v0.1 延后）
- **认证 = 步骤链**: env → login → inject，每步可插拔；自定义认证通过插件注册（v0.1: 仅 3 种内置类型）
- **字段类型 + 校验**: 11 种类型 → v0.1 选 5 种核心类型（string/int/float/bool/enum），每种带格式校验
- **字段依赖**: `depends_on.eq` 条件必填，`validate` 跨字段规则（v0.1: 仅 depends_on.eq）
- **插件机制**: 4 种扩展点（auth/hooks/types/convert），v0.1 全部延后
- **参数位置声明式**: path/query/header/body/cookie 五种位置，框架自动组装

**Research Findings**:
- ketacli 有 16 个 YAML 文件 + 完整的 SDK 层。核心模式：`asset_map.py` 加载 YAML → `resource.py` 动态生成 Click 命令 → `Template+Jinja2` 渲染 → `client.py` 发 HTTP → `hooks` 格式化输出
- ketacli 的 `make_operation_cmd()` 250+ 行巨型闭包是需要避免的反模式
- ketacli 注入 `__builtins__` 到 Jinja2 是安全隐患，cliyard 必须使用 `SandboxedEnvironment`
- ketacli CLI 入口点 `main()` 函数存在 bug：调用 `cli()` 而非返回可调用对象

### Metis Review
**Identified Gaps** (addressed in plan):
- **CLI 入口点 Bug**: `main()` 不能作为 `console_scripts` entry point → Task 1 修复
- **Jinja2 沙箱缺失**: schema 设计中用了 `{{ env("KEY") }}` 但未指定沙箱策略 → Task 4 使用 `SandboxedEnvironment` + 白名单
- **v0.1 范围过大**: schema 设计覆盖 100% 功能，Metis 建议砍到 ~60% → 本计划锁定 v0.1 MVP
- **`pyproject.toml` + `setup.py` 双重版本**: ketacli 的反模式 → v0.1 只用 `pyproject.toml`
- **验收标准全部缺失**: schema-discussion.md 零验收标准 → 所有 Task 均含可执行 QA 场景
- **分页策略未定义**: → v0.1 仅支持简单 query 参数 pagination，`--all` 延后

---

## Work Objectives

### Core Objective
构建 cliyard v0.1 MVP：**代码生成框架**。用户写 YAML → `cliyard gen` 生成独立 CLI 工具包 → `pip install` 后得到 native CLI 命令。生成的工具依赖 `cliyard.runtime` 提供 HTTP 客户端、认证链、模板渲染、命令生成等能力。

### Concrete Deliverables
- `cliyard` CLI 入口（`cliyard gen` + `cliyard --spec-dir` 双模式）
- `cliyard gen` — 脚手架生成器（生成 pip-installable Python 包）
- `cliyard.runtime` — 运行时库（生成的 CLI 的依赖）
- `cliyard/schema/` — YAML 模型 + 校验器
- `cliyard/engine/` — 服务加载器 + Click 命令生成器 + 请求组装器
- `cliyard/client/` — HTTP 客户端 + 认证链 + Token 缓存
- `cliyard/output/` — 响应处理 + 输出格式化
- `cliyard/validate/` — 字段类型 + 校验 + 依赖
- `examples/ketacli-repos/` — spec 定义 → `cliyard gen` 生成 `ketacliv2` → 安装运行

### Definition of Done
- [ ] `cliyard gen --name ketacliv2 --defs-path examples/ketacli-repos/` 生成可安装的 CLI 包
- [ ] `pip install ./dist/ketacliv2/ && ketacliv2 repos list --help` 输出表格参数
- [ ] `ketacliv2 repos create --help` 显示 --name --repo-type --retention 等字段
- [ ] `cliyard --spec-dir examples/ketacli-repos/ repos list --help` 同样可用（开发/测试模式）
- [ ] 全链路测试通过：spec 加载 → gen 代码生成 → install → CLI 参数解析 → HTTP → 输出

### Must Have
- `cliyard gen --name <name> --defs-path <dir>` 代码生成命令
- 生成的 CLI 工具是 cliyard runtime 的薄包装，spec 目录 baked-in 为 package data
- 生成的包结构：`pyproject.toml` + `main.py`（带 Click entry point）+ `specs/`（package data）
- 目录即服务加载器（`_service.yaml` + 资源 YAML 文件）
- 3 步认证链（env → login → inject）
- 5 种字段类型（string/int/float/bool/enum）+ 校验
- `depends_on.eq` 字段依赖
- Click 动态命令生成（list/get/create/update/delete）
- JSON + Rich 表格输出
- Jinja2 `SandboxedEnvironment` + 白名单 Filter
- 字段参数位置声明式路由（path/query/header/body）
- 清晰的错误消息（参数校验失败、HTTP 错误、认证失败）
- pytest 测试覆盖核心模块

### Must NOT Have (Guardrails)
- **NO** 插件发现/加载机制（不做 Python entry point 扫描、不做 plugins/ 目录扫描）
- **NO** 自定义字段类型或值转换器扩展点
- **NO** `depends_on` 中非 `.eq` 的规则；`validate` 全部延后
- **NO** `_service.local.yaml` 深度合并
- **NO** prompt 交互式认证
- **NO** 多格式输出（json/table 之外）
- **NO** multipart/form-data 文件上传
- **NO** 跨服务编排
- **NO** Jinja2 注入 `__builtins__` 或使用 `eval()`
- **NO** ketacli 风格 250+ 行巨型闭包 — 用 pipeline stages
- **NO** `setup.py` + `pyproject.toml` 双重版本 — 只用 pyproject.toml
- **NO** 与 ketacli 的任何代码耦合

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO（新项目）
- **Automated tests**: YES (tests-after)
- **Framework**: pytest
- **Test setup**: Wave 1 Task 6 建立测试基础设施

### QA Policy
每个 Task 至少包含 1 个 happy path + 1 个 failure/edge case QA 场景。
场景必须可执行、可复现、有明确证据路径。

- **CLI 命令**: 用 `bash -c '...'` 验证命令输出和退出码
- **HTTP 交互**: 用 httpbin.org 或本地 mock server
- **库/模块**: 用 Python REPL import 并调用函数

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation, ALL parallel):
├── Task 1:  Project setup + CLI entry fix         [quick]
├── Task 2:  Schema type definitions               [quick]
├── Task 3:  Schema YAML validator                 [quick]
├── Task 4:  Template engine (Jinja2 sandbox)      [quick]
├── Task 5:  HTTP client base                      [quick]
└── Task 6:  Test infrastructure                   [quick]

Wave 2 (After Wave 1 — core engine, ALL parallel):
├── Task 7:  Service & resource loader             [quick]
├── Task 8:  Click command builder                 [deep]
├── Task 9:  Request assembler                     [quick]
├── Task 10: Response handler + output formatter   [quick]
└── Task 11: Error handler                         [quick]

Wave 3 (After Wave 2 — pipeline + auth + validation, MIXED):
├── Task 12: Runtime pipeline (run_with_spec)      [deep]
├── Task 13: Field type validators                 [quick]
├── Task 14: CLI parameter binding                 [quick]
├── Task 15: Auth chain engine                     [deep]
├── Task 16: Token caching                         [quick]
└── Task 17: Field dependency (depends_on.eq)      [quick]

Wave 4 (After Wave 3 — examples + gen + integration, MIXED):
├── Task 18: Ketacli repos example spec            [writing]
├── Task 19: Integration tests                     [unspecified-high]
├── Task 20: README + examples walkthrough         [writing]
└── Task 21: cliyard gen command                   [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit                 [oracle]
├── Task F2: Code quality review                   [unspecified-high]
├── Task F3: Real manual QA                        [unspecified-high]
└── Task F4: Scope fidelity check                  [deep]
```

### Dependency Matrix

- **1-6**: — — 7-11, 12 (all Wave 2 depends on all Wave 1)
- **7**: 2, 3 — 8, 12
- **8**: 7 — 12, 14
- **9**: 4, 5 — 12
- **10**: 5 — 12
- **11**: 5 — 12
- **12**: 7, 8, 9, 10, 11 — 18, 19, 21
- **13**: 2 — 14
- **14**: 8, 13 — 12, 18
- **15**: 5 — 12, 16
- **16**: 15 — 12
- **17**: 13 — 14
- **18**: 12 — 19, 21
- **19**: 18, 12, 15 — F1-F4
- **20**: 18 — —
- **21**: 12, 18 — 19

### Critical Path

```
1 → 7 → 8 → 12 → 18 → 21 → 19 → F1-F4
```

### Agent Dispatch Summary

- **Wave 1**: 6 — T1-T4 → `quick`, T5 → `quick`, T6 → `quick`
- **Wave 2**: 5 — T7 → `quick`, T8 → `deep`, T9-T11 → `quick`
- **Wave 3**: 6 — T12 → `deep`, T13-T14 → `quick`, T15 → `deep`, T16-T17 → `quick`
- **Wave 4**: 4 — T18 → `writing`, T19 → `unspecified-high`, T20 → `writing`, T21 → `deep`
- **FINAL**: 4 — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. 项目骨架修复 + CLI 入口点修正

  **What to do**:
  - 修正 `src/cliyard/cli/__main__.py`：`main()` 函数改为直接暴露 `cli` 对象（`console_scripts` 需要无参可调用对象）
  - 更新 `pyproject.toml`：`cliyard = "cliyard.cli.__main__:cli"` 或统一入口
  - **删除 `setup.py`**（ketacli 双重版本维护是反模式，cliyard 只用 `pyproject.toml`）
  - 初始化 git 仓库：`cd /data/git-project/cliyard && git init`
  - 创建虚拟环境：`python3 -m venv venv && source venv/bin/activate && pip install -e ".[dev]"`
  - 验证 `cliyard --help` 能正常运行

  > **ketacli 参考**: ketacli 的 `ketacli.py:46-50` 中 `start()` 用 `cli(standalone_mode=False)` 和 `except SystemExit: pass` 模式。但 `console_scripts` entry point 应直接指向 `cli` 函数。

  **Must NOT do**:
  - 不要创建 `setup.py`
  - 不要在 `main()` 中调用 `cli()` 然后不返回（entry point bug）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5, 6)

  **Acceptance Criteria**:
  - [ ] `cliyard --help` 输出帮助信息（退出码 0）
  - [ ] `cliyard --version` 输出版本号
  - [ ] `pip install -e .` 成功
  - [ ] 项目目录没有 `setup.py`
  - [ ] git 仓库已初始化

  **QA Scenarios**:
  ```
  Scenario: CLI entry point works
    Tool: Bash
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. pip install -e .
      3. cliyard --help
      4. cliyard --version
    Expected Result: --help exits 0 with usage text; --version shows "0.1.0"
    Evidence: .omo/evidence/task-1-cli-works.txt
  ```

  **Commit**: YES
  - Message: `[refactor]: fix CLI entry point and cleanup project skeleton`
  - Files: `src/cliyard/cli/__main__.py`, `pyproject.toml`, 删除 `setup.py`
  - Pre-commit: `pip install -e . && cliyard --help`

- [x] 2. Schema 类型定义 (TypedDict / dataclass)

  **What to do**:
  - 创建 `src/cliyard/schema/types.py`：定义 YAML spec 中所有数据结构的 Python 类型
  - 覆盖的结构（v0.1 MVP 范围）：

  | Python 类型 | 对应 YAML | ketacli 参考 |
  |------------|----------|-------------|
  | `ServiceSpec` | `_service.yaml` 顶层 | 无直接对应（新概念） |
  | `ServerConfig` | `server:` block | ketacli `~/.keta/config.yaml` 中的 endpoint |
  | `AuthChain` | `auth.steps[]` | ketacli 无（Bear token only） |
  | `AuthStep` | 单个 step（env/login/inject） | 无 |
  | `ResourceSpec` | 资源 YAML 文件顶层 | ketacli `repos.yaml` 中 `repos:` key |
  | `MethodSpec` | `methods.list/get/create/...` | ketacli `repos.yaml:51-163` 的 create 定义 |
  | `ParamSpec` | `params.query/body/...` 项 | ketacli `template_fields` + `query_fields` |
  | `FieldType` | `type: string/int/float/bool/enum` | ketacli `util.py:157-230` extract_template_vars 的 default_type |
  | `OutputSpec` | `output:` block | ketacli `default_fields` + field aliases |

  > **ketacli 示例映射 — repos.yaml:**
  > ```yaml
  > # ketacli repos.yaml 的 create 方法
  > # template_fields → cliyard MethodSpec.params.body
  > # data → cliyard MethodSpec.request_body.template
  > # path → cliyard MethodSpec.http.path
  > ```

  - 使用 `TypedDict`（Python 3.10+ 原生支持）或 `@dataclass`
  - 包含 `to_dict()` 方法用于测试序列化
  - 创建 `src/cliyard/schema/__init__.py` 统一导出

  **Must NOT do**:
  - 不要引入 Pydantic（v0.1 保持零额外依赖）
  - 不要定义 v0.1 范围外的类型（file/date/datetime/cookie/dict）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5, 6)

  **Acceptance Criteria**:
  - [ ] `from cliyard.schema.types import ServiceSpec` 无错误
  - [ ] `ServiceSpec.to_dict()` 往返测试通过
  - [ ] 所有类型有 docstring 说明对应 YAML 结构

  **QA Scenarios**:
  ```
  Scenario: Type definitions import and serialize correctly
    Tool: Bash
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.schema.types import AuthStep, FieldType;
        s = AuthStep(name='test', type='env', config={'name': 'MY_TOKEN'});
        print(s['type']);
        assert s['type'] == 'env';
        print('OK')
      "
    Expected Result: Outputs "env" then "OK"
    Evidence: .omo/evidence/task-2-types-ok.txt
  ```

  **Commit**: YES
  - Message: `[feat(schema)]: add TypedDict schema type definitions`
  - Files: `src/cliyard/schema/types.py`, `src/cliyard/schema/__init__.py`

- [x] 3. YAML Schema 校验器

  **What to do**:
  - 创建 `src/cliyard/schema/validator.py`：在 YAML 加载后校验结构完整性
  - 校验规则（v0.1：不求完备，但核心字段必须检查）：

  | 校验项 | 说明 |
  |--------|------|
  | `ServiceSpec` | `name`, `server.base_url` 必填 |
  | `AuthStep` | `name`, `type` 必填；`type` 必须是 `env`/`login`/`inject` 之一 |
  | `login` step | 必须有 `endpoint` 和 `extract` |
  | `inject` step | 必须有 `into` 和 `name` |
  | `ResourceSpec` | 必须有 `methods` |
  | `MethodSpec` | 必须有 `http.method` |
  | `ParamSpec` | `enum` 类型必须有 `choices` |
  | 路径模板 | `{{ var }}` 中声明的变量必须在 `params.path` 或 `params.body` 中有定义 |

  - **不在运行时才发现配置错误** — 这是 ketacli 缺失的能力
  - 错误消息格式：`{spec_file}:{field_path}: {message}`（如 `repos.yaml:methods.create.http.method: must not be empty`）

  > **ketacli 示例 — 坏味道**: ketacli 的 `asset_map.py:load_yaml_config()` 只是 `yaml.safe_load()` + `merged_config.update()`，零校验。如果 YAML 写错了格式（如 `method` 写了 `get` 但没定义 path），只有在用户实际运行命令时才会报错。

  **Must NOT do**:
  - 不要用 Pydantic（保持零额外依赖，校验器自己写）
  - 不要校验 v0.1 范围外的字段

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5, 6)

  **Acceptance Criteria**:
  - [ ] 有效的 `_service.yaml` 不报错
  - [ ] 缺失 `server.base_url` 的 `_service.yaml` 报清晰错误
  - [ ] `enum` 字段无 `choices` 时报错
  - [ ] 路径模板变量无对应参数定义时报 warn

  **QA Scenarios**:
  ```
  Scenario: Valid YAML passes validation
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.schema.validator import validate_service;
        result = validate_service({'name':'test','server':{'base_url':'https://example.com'}});
        print('PASS' if result.is_valid else 'FAIL')
      "
    Expected Result: "PASS"
    Evidence: .omo/evidence/task-3-valid-pass.txt

  Scenario: Missing base_url is rejected
    Tool: Bash + Python REPL
    Steps:
      1. python3 -c "
        from cliyard.schema.validator import validate_service;
        result = validate_service({'name':'test','server':{}});
        print(result.errors[0] if result.errors else 'PASS')
      "
    Expected Result: Output contains "base_url" and "required"
    Evidence: .omo/evidence/task-3-missing-url.txt
  ```

  **Commit**: YES
  - Message: `[feat(schema)]: add YAML schema validator`
  - Files: `src/cliyard/schema/validator.py`

- [x] 4. Jinja2 沙箱模板引擎

  **What to do**:
  - 创建 `src/cliyard/engine/template.py`：基于 Jinja2 `SandboxedEnvironment` 的模板渲染类
  - **白名单过滤器**（仅这些可用，其余拒绝）：
    - `default(val)` — 变量默认值
    - `env(name)` — 从环境变量读取
    - `upper`, `lower`, `replace`, `join`, `length`, `first`, `last`
    - `tojson` — 将 Python 对象序列化为 JSON 字符串
    - `str_to_list` — 逗号分隔字符串 → 列表（复制 ketacli 模式）
  - **白名单全局函数**（仅这些可用）：`time`, `None`, `True`, `False`
  - **禁用的能力**：`__builtins__`, `import`, `open`, `exec`, `eval`, 所有 Python 模块访问

  > **ketacli 反面教材**:
  > ketacli 的 `Template` 类（`util.py:283-329`）做了两件危险的事：
  > 1. `all_package.update(__builtins__.__dict__)` — 把所有 Python 内置函数注入了模板（你可以 `{{ open('/etc/passwd').read() }}`）
  > 2. `Environment(undefined=StrictUndefined, ...)` — 使用了非沙箱环境
  >
  > cliyard 是通用框架，用户可能从不可信来源获取 YAML 文件（如 GitHub 上别人的 API spec），必须沙箱化。
  >
  > 但复制 ketacli 的好模式：
  > 1. 模板缓存：`_template_cache = {}` 避免重复编译
  > 2. `__KETACLI_OMIT__` 哨兵值模式：空值字段自动从 body 中移除

  - 实现 `render(path_or_body_template, **kwargs) -> str`

  **Must NOT do**:
  - 不要注入 `__builtins__` 或任何 Python 模块
  - 不要使用非沙箱的 `Environment`
  - 不要支持 `{% for %}`, `{% if %}` 等控制流标签（v0.1 仅变量替换 + 过滤器）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5, 6)

  **Acceptance Criteria**:
  - [ ] `render('users/{{ name }}', name='test')` → `'users/test'`
  - [ ] `render('{{ page|default(1) }}')` → `'1'`
  - [ ] `render('{{ TOKEN|env("MY_TOKEN") }}')` → 环境变量值
  - [ ] `render('{{ open("/etc/passwd") }}')` → 抛出异常（沙箱拦截）

  **QA Scenarios**:
  ```
  Scenario: Template renders correctly with safe operations
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.engine.template import Template;
        t = Template('users/{{ user_id }}?page={{ page|default(1) }}');
        result = t.render(user_id='abc123');
        print(result);
        assert result == 'users/abc123?page=1'
      "
    Expected Result: "users/abc123?page=1"
    Evidence: .omo/evidence/task-4-template-ok.txt

  Scenario: Unsafe operations are blocked by sandbox
    Tool: Bash + Python REPL
    Steps:
      1. python3 -c "
        from cliyard.engine.template import Template;
        t = Template('{{ open(\"/etc/passwd\") }}');
        try:
            t.render();
            print('SECURITY FAIL')
        except Exception as e:
            print('SECURITY OK:', type(e).__name__)
      "
    Expected Result: "SECURITY OK: SecurityError" (或类似)
    Evidence: .omo/evidence/task-4-sandbox-block.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add Jinja2 sandbox template engine`
  - Files: `src/cliyard/engine/template.py`, `src/cliyard/engine/__init__.py`

- [x] 5. HTTP 客户端基类

  **What to do**:
  - 创建 `src/cliyard/client/http.py`：封装 `requests` 库的基础 HTTP 客户端
  - 复制 ketacli 的优秀模式：

  | 模式 | ketacli 文件 | cliyard 实现 |
  |------|-------------|-------------|
  | `request(method, path, data, query, headers)` 统一入口 | `client.py:229-286` | 同名函数 |
  | 自动拼接 URL：`endpoint + path`（检测是否含 `http://`） | `client.py:250-256` | 复制逻辑 |
  | Bearer Auth 注入 | `client.py:259` | 接受外部传入 token |
  | `.json()` 响应解析 | 各处 | 在 response handler 中（Task 10） |
  | 分块下载 (`download_file`) | `client.py:289-354` | v0.1 不做（无 download 操作） |
  | 分块上传 (`upload_file`) | `client.py:425-488` | v0.1 不做（无 file 类型） |
  | `400-499 → raise Exception("Bad request", ...)` | `client.py:279-281` | **改为结构化错误**（见 Task 11） |

  > **ketacli 示例**:
  > ketacli 的 `request()` 函数签名：
  > ```python
  > def request(method, path, data=None, query_params=None, custom_headers=None, _gzip=False):
  >     auth_info = get_auth()                     # ← cliyard 改为由 auth chain 注入
  >     url = f"{endpoint}/{ROOT_PATH}/{path}"     # ← cliyard 改为由 loader 提供 base_url
  >     response = requests.request(method, ...)
  >     if 400 <= response.status_code < 500:
  >         raise Exception("Bad request", ...)    # ← cliyard 改为 CliError
  > ```

  - cliyard 差异：
    - 去掉 `ROOT_PATH` 硬编码（由 `server.prefix` 配置）
    - 去掉 `get_auth()` 自动获取（由 auth chain 在请求前注入）
    - 去掉 `_gzip` 参数（KetaDB 特定，不需要）
    - 错误改用自定义 `CliError` 异常（Task 11）
  - 创建 `src/cliyard/client/__init__.py`

  **Must NOT do**:
  - 不要硬编码 `api/v1` 或任何路径前缀
  - 不要在 client 层做认证（留给 auth chain）
  - 不要实现 download/upload

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 6)

  **Acceptance Criteria**:
  - [ ] `GET https://httpbin.org/get` 返回 200
  - [ ] `POST https://httpbin.org/post` with JSON body 正确发送
  - [ ] 带 `query_params` 的 GET 请求 query string 正确
  - [ ] 带 `custom_headers` 的请求 header 正确注入

  **QA Scenarios**:
  ```
  Scenario: HTTP client sends GET with query params
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.client.http import request;
        r = request('get', 'https://httpbin.org/get', query_params={'foo': 'bar'});
        data = r.json();
        print('PASS' if data['args']['foo'] == 'bar' else 'FAIL');
        print('Status:', r.status_code)
      "
    Expected Result: "PASS" + "Status: 200"
    Evidence: .omo/evidence/task-5-http-get.txt
  ```

  **Commit**: YES
  - Message: `[feat(client)]: add HTTP client base layer`
  - Files: `src/cliyard/client/http.py`, `src/cliyard/client/__init__.py`

- [x] 6. 测试基础设施

  **What to do**:
  - 创建 `tests/` 目录和 `tests/__init__.py`
  - 创建 `tests/conftest.py`：pytest 公共 fixture
    - `fixture: cliyard_project_dir` → `/data/git-project/cliyard/`
    - `fixture: valid_service_yaml` → 最小可用的 `_service.yaml` dict
    - `fixture: valid_resource_yaml` → 最小可用的资源 YAML dict
  - 创建测试 fixture 目录 `tests/fixtures/`：
    - `minimal_service.yaml` — 最小可用服务配置
    - `repos_resource.yaml` — 模拟 ketacli repos 的资源定义
    - `bad_service.yaml` — 故意写坏的配置（测校验器）
  - 在 `pyproject.toml` 中补充 `[tool.pytest.ini_options]`：
    ```toml
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    addopts = "-v --tb=short"
    ```
  - 创建并运行一个最小 smoke test：`test_schema_types.py` 验证 Task 2 的类型定义
  - 创建 `run_tests.sh` 脚本（参考 ketacli 的 `run_tests.sh`）

  > **ketacli 参考**:
  > ketacli 的 `tests/` 目录结构：
  > ```
  > tests/
  > ├── conftest.py
  > ├── test_cli_app.py        # CLI 命令生成测试
  > ├── test_resource.py       # asset 命令测试
  > └── test_sdk_*.py          # SDK 模块测试
  > ```
  > 但 ketacli 的测试不够全面 — 缺少 request 组装和 response 处理的单元测试。
  > cliyard 应从一开始就建立更完整的测试覆盖。

  **Must NOT do**:
  - 不要创建复杂的 mock server（v0.1 用 httpbin.org 做集成测试）
  - 不要导入 ketacli 的任何测试代码

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 5)

  **Acceptance Criteria**:
  - [ ] `pytest tests/ -v` 运行成功（至少 1 个 test）
  - [ ] `tests/fixtures/` 包含 3 个 fixture 文件
  - [ ] `./run_tests.sh` 可执行

  **QA Scenarios**:
  ```
  Scenario: Test infrastructure is operational
    Tool: Bash
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. pytest tests/ -v
      3. echo "Exit: $?"
    Expected Result: Test passes, exit code 0
    Evidence: .omo/evidence/task-6-pytest-ok.txt
  ```

  **Commit**: YES
  - Message: `[test]: add pytest infrastructure and fixtures`
  - Files: `tests/`, `run_tests.sh`, `pyproject.toml`

- [x] 7. 服务 & 资源加载器

  **What to do**:
  - 创建 `src/cliyard/engine/loader.py`：从目录加载 API 服务的 YAML 配置
  - 实现 `load_service(spec_dir: str) -> ServiceSpec`：
    1. 读取 `{spec_dir}/_service.yaml`，解析为 `ServiceSpec`
    2. 遍历 `{spec_dir}/*.yaml`（排除 `_service.yaml` 和 `_service.*.yaml`），每个文件解析为 `ResourceSpec`
    3. 用 Task 3 的 validator 校验
    4. 返回填满的 `ServiceSpec`（含 `resources: list[ResourceSpec]`）
  - 实现 `load_resource(yaml_path: str) -> ResourceSpec`：单个资源文件加载

  > **ketacli 对照**:
  > ketacli 的 **加载器** = `asset_map.py:37-75` (`load_yaml_config()`) 只做文件名扫描 + `yaml.safe_load()` + `merged_config.update()`。
  >
  > ketacli 的 **解析器** = 无（直接操作 raw dict，运行时才发现配置错误）。
  >
  > cliyard 的 **加载器** = 扫描 + 解析 + 校验，三合一。

  - 文件名 → 资源名映射：`users.yaml` → 资源名 `users`；`admin.yaml` → 资源名 `admin`
  - 目录不存在时抛出明确错误（`SpecDirNotFoundError`）
  - 目录中无 YAML 文件时给出警告

  **Must NOT do**:
  - 不要加载 `_service.local.yaml`（v0.1 延后）
  - 不要加载 `plugins/` 目录

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8, 9, 10, 11)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 2, 3

  **Acceptance Criteria**:
  - [ ] `load_service("tests/fixtures/minimal_service_dir")` 返回带 resources 的 ServiceSpec
  - [ ] 空目录给出警告
  - [ ] 损坏的 YAML 给出行号精确错误
  - [ ] 文件名映射正确：`repos.yaml` → resource name `repos`

  **QA Scenarios**:
  ```
  Scenario: Service loader reads valid spec directory
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.engine.loader import load_service;
        svc = load_service('tests/fixtures');
        print('Resources:', [r['name'] for r in svc.get('resources',[])])
      "
    Expected Result: "Resources: ['repos']"
    Evidence: .omo/evidence/task-7-loader-ok.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add service and resource YAML loader`
  - Files: `src/cliyard/engine/loader.py`

- [x] 8. Click 命令动态生成器

  **What to do**:
  - 创建 `src/cliyard/engine/builder.py`：核心模块，从 YAML 配置动态生成 Click 命令
  - 函数结构（**pipeline stages，不是 ketacli 的巨型闭包**）：

  ```
  1. build_resource_group(resource: ResourceSpec) → click.Group
     ↓
  2. build_list_command(resource: ResourceSpec) → click.Command
     ↓
  3. build_operation_command(resource: ResourceSpec, method: MethodSpec) → click.Command
     ↓
  4. merge_params_and_build_options(params: ParamSpec[]) → list[click.Option]
  ```

  - 每个 stage 独立可测试
  - 命令命名规则：资源名 = Click Group 名，方法名 = Click Command 名
  - 生成的命令结构：`cliyard --spec-dir ./my-api/ repos list/client/get/create/update/delete`

  > **ketacli 参考 — 好的模式**:
  > ```python
  > # ketacli resource.py — 注册结构
  > def register_asset_commands(cli):
  >     resources = get_resources()
  >     asset_group = click.Group(name='asset', help='...')
  >     for resource_name, config in resources.items():
  >         group = _build_resource_group(resource_name, config)
  >         asset_group.add_command(group)
  >     cli.add_command(asset_group)
  > ```

  > **ketacli 参考 — 需要改进的模式**:
  > ketacli 的 `make_operation_cmd()` 是一个 **250+ 行、20+ 个局部变量的巨型闭包**。
  > 所有逻辑（参数解析 → pre-hook → 模板渲染 → HTTP 请求 → render-hook → 输出）塞在一个 `callback()` 里。
  >
  > cliyard **必须**把这些拆成独立的 pipeline stages：
  > ```python
  > # cliyard 模式 — 清晰的 pipeline
  > def callback(**kwargs):
  >     params = bind_and_validate(kwargs, method_spec)   # stage 1: 参数绑定+校验
  >     auth_ctx = run_auth_chain(service.auth, client)    # stage 2: 认证链
  >     request = assemble_request(method_spec, params)    # stage 3: 请求组装
  >     response = client.execute(request)                 # stage 4: HTTP
  >     output = format_response(response, method_spec)    # stage 5: 输出
  >     console.print(output)
  > ```

  - v0.1 不支持的功能（但预留扩展点）：

  | ketacli 功能 | cliyard v0.1 状态 |
  |-------------|------------------|
  | `--watch` (Live 刷新) | 不做，Click option 不生成 |
  | `--format json/table` | 只做默认行为，不做 `--format` 选项 |
  | `pre_hooks` / `render_hooks` | 不做，pipeline 中有预留空位 |
  | `options` (opt-level hooks) | 不做 |
  | 操作级 `query_params` | 不做 |

  **Must NOT do**:
  - 不要在单个函数中封装所有逻辑（>100行 → 拆分）
  - 不要在 v0.1 中生成 `--watch`, `--format` 等额外选项

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 9, 10, 11)
  - **Blocks**: Tasks 12, 14
  - **Blocked By**: Task 7

  **Acceptance Criteria**:
  - [ ] `build_resource_group()` 返回的 click.Group 含 `list` + 所有 method 命令
  - [ ] `cliyard --spec-dir tests/fixtures/ user list --help` 显示参数
  - [ ] `enum` 类型的参数有 `--role [admin|user|viewer]` 提示
  - [ ] 生成的命令可以 import 并调用 `cmd.make_context()` 验证参数绑定

  **QA Scenarios**:
  ```
  Scenario: Generated CLI shows correct help for list command
    Tool: Bash
    Steps:
      1. mkdir -p /tmp/cliyard-test && cp -r tests/fixtures/* /tmp/cliyard-test/
      2. cd /data/git-project/cliyard && source venv/bin/activate
      3. python3 -c "
        from cliyard.engine.loader import load_service;
        from cliyard.engine.builder import build_service_commands;
        import click;
        svc = load_service('/tmp/cliyard-test');
        cli = click.Group(name='cliyard');
        build_service_commands(cli, svc);
        runner = click.testing.CliRunner();
        result = runner.invoke(cli, ['repos', 'list', '--help']);
        print(result.output)
      "
    Expected Result: Output contains "--page" and "--per-page"
    Evidence: .omo/evidence/task-8-cli-help.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add Click dynamic command builder`
  - Files: `src/cliyard/engine/builder.py`

- [x] 9. 请求组装器

  **What to do**:
  - 创建 `src/cliyard/engine/assembler.py`：将用户参数 + YAML 模板渲染为完整 HTTP 请求对象
  - 实现 `assemble_request(method_spec: MethodSpec, params: dict, base_url: str, prefix: str) -> Request`：
    ```
    1. 渲染 path 模板:  Template("users/{{ user_id }}").render(user_id="abc") → "users/abc"
    2. 拼接 query 参数: {page: 1, per_page: 20} → ?page=1&per_page=20
    3. 注入 header 参数:  X-Request-Id: abc123 → headers dict
    4. 渲染 body 模板:  {"name": "{{ name }}"} → {"name": "test-user"}
    5. 构建完整 Request: Request(method, url, headers, query, body)
    ```

  - `params` dict 中 `key` 对应参数声明中的 `name`
  - 参数根据声明的位置（path/query/header/body）自动路由到请求的正确位置

  > **ketacli 参考**:
  > ketacli 的请求组装分散在多个地方：
  > - `resource.py:491-493` 渲染 path
  > - `resource.py:495-502` 构建 query_params
  > - `resource.py:504-512` 渲染 body JSON
  > - `resource.py:568` 调用 `request(http_method, rendered_path, data=body_dict, query_params=...)`
  >
  > cliyard 把这些集中到 `assemble_request()` 一个函数中。

  - `Request` 对象：简单的 dataclass：
    ```python
    @dataclass
    class Request:
        method: str        # GET / POST / PUT / DELETE
        url: str           # 完整 URL
        headers: dict      # 请求头
        query_params: dict # query 参数
        body: dict | None  # JSON 请求体
    ```

  **Must NOT do**:
  - 不要在 assembler 中做 HTTP 请求（只组装，不发送）
  - 不要处理 cookie/multipart/form-data

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 10, 11)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 4, 5

  **Acceptance Criteria**:
  - [ ] path 模板 `users/{{ user_id }}` + `user_id=abc` → `url = ".../users/abc"`
  - [ ] query 参数 `{page: 1}` → `query_params = {"page": "1"}`
  - [ ] body 模板 `{"name": "{{name}}"}` + `name=test` → `body = {"name": "test"}`
  - [ ] 未使用的参数给出 warn（不是 error）

  **QA Scenarios**:
  ```
  Scenario: Request assembler builds correct GET request
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.engine.assembler import assemble_request;
        # mock method_spec
        method_spec = {
            'http': {'method': 'GET', 'path': 'repos'},
            'params': {'query': [{'name': 'page', 'type': 'int', 'default': 1}]},
            'request_body': {}
        };
        req = assemble_request(method_spec, {'page': 3}, 'https://httpbin.org', '/api/v1');
        print('URL:', req.url);
        print('Query:', req.query_params);
        assert req.url.endswith('/repos');
        assert req.query_params.get('page') == '3'
      "
    Expected Result: URL ends with /repos, query_params has page=3
    Evidence: .omo/evidence/task-9-assembler-get.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add HTTP request assembler`
  - Files: `src/cliyard/engine/assembler.py`

- [x] 10. 响应处理器 + 输出格式化器

  **What to do**:
  - 创建 `src/cliyard/output/handler.py`：处理 HTTP 响应
    - `parse_response(response: requests.Response, output_spec: OutputSpec) -> dict`：
      1. 提取 JSON 响应
      2. 用 `items_path` JSONPath 定位数据列表
      3. 用 `total_path` 提取总数（可选）
      4. 返回 `{"items": [...], "total": N}`
    - `parse_single_response(response: requests.Response) -> dict`：
      get/update/create/delete 操作，直接返回 JSON body
  - 创建 `src/cliyard/output/formatter.py`：格式化输出
    - `format_as_json(data: dict) -> str`
    - `format_as_table(data: dict, fields: list[FieldSpec]) -> str`
    - 使用 Rich `Table` 渲染表格
    - 字段别名映射（`fields[].alias` → 列标题）
  - 创建 `src/cliyard/output/__init__.py`

  > **ketacli 对照**:
  > ketacli 的输出处理 = `sdk/output/output.py` + `sdk/output/format.py` + `sdk/converters.py`。
  > - `find_result_field()` 扫描 resp.keys() → 智能定位列表字段（ketacli 硬编码了常见的 keys 如 `items`, `repos`, `alerts`）
  > - `make_records_to_table()` 用 field aliases 生成表头
  > - `OutputTable` 类包裹 Rich Table / PrettyTable
  > - `format_table(table, format)` 选择渲染器
  >
  > cliyard 用 JSONPath 替代 `find_result_field()` 的智能猜测，更精确。简化版只做 JSON + Rich table。

  **Must NOT do**:
  - 不要实现 `find_result_field()` 智能定位（用 JSONPath 精确指定）
  - 不要支持 latex/html/csv 等额外格式
  - 不要实现字段值转换器（convert registry — v0.1 延后）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9, 11)
  - **Blocks**: Task 12
  - **Blocked By**: Task 5

  **Acceptance Criteria**:
  - [ ] `format_as_json({"items":[{"id":1}]})` → 格式化的 JSON 字符串
  - [ ] `format_as_table(..., [{"name":"id","alias":"ID"}])` → Rich 表格含 "ID" 列
  - [ ] `parse_response()` 用 items_path JSONPath 正确定位数据

  **QA Scenarios**:
  ```
  Scenario: Response is formatted as Rich table
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.output.formatter import format_as_table;
        data = {'items': [{'id': 1, 'name': 'test'}], 'total': 1};
        fields = [{'name': 'id', 'alias': 'ID'}, {'name': 'name', 'alias': 'Name'}];
        result = format_as_table(data, fields);
        assert 'ID' in str(result);
        assert 'test' in str(result);
        print('PASS')
      "
    Expected Result: "PASS"
    Evidence: .omo/evidence/task-10-table-ok.txt
  ```

  **Commit**: YES
  - Message: `[feat(output)]: add response handler and table/JSON formatter`
  - Files: `src/cliyard/output/handler.py`, `src/cliyard/output/formatter.py`, `src/cliyard/output/__init__.py`

- [x] 11. 错误处理器

  **What to do**:
  - 创建 `src/cliyard/engine/errors.py`：结构化错误类
  - 错误类型：

  | 错误类 | HTTP Code | 使用场景 | ketacli 对应 |
  |--------|-----------|---------|-------------|
  | `CliyError` | — | 基类 | Exception |
  | `ValidationError` | — | 参数校验失败 | 无（ketacli 不发请求就不知道参数错） |
  | `AuthError` | — | 认证失败（env 不存在/jsonpath 提取失败/login 响应非 200） | RuntimeError("Not authenticated") |
  | `ApiError` | 400-599 | API 返回错误 | Exception("Bad request", ...) |
  | `SpecError` | — | YAML 配置错误 | 无（ketacli 运行时才报错） |

  - 创建 `src/cliyard/engine/error_handler.py`：
    - `handle_api_error(response: requests.Response) -> None`：解析 API 错误响应，提取 `code`/`message` 字段
    - 优化 ketacli 的错误处理模式（ketacli 用 `eval()` 处理错误消息字符串，有安全隐患）

  > **ketacli 反面教材**:
  > ```python
  > # ketacli client.py:279-281 — 用 eval() 包裹字符串
  > if 400 <= response.status_code < 500:
  >     raise Exception("Bad request", response.status_code, url, method, response.text)
  > # 然后在 ketacli.py:56 用 eval(error_msg) 解析！安全隐患！
  > parts = eval(error_msg)
  > ```
  > cliyard 改为此模式：
  > ```python
  > # cliyard — 结构化错误
  > if response.status_code >= 400:
  >     raise ApiError(
  >         status=response.status_code,
  >         url=response.url,
  >         body=response.json()
  >     )
  > # 在顶层 catch 时格式化输出
  > ```

  - 错误消息格式：`[{status}] {code}: {message}`

  **Must NOT do**:
  - 不要使用 `eval()` 或字符串解析错误
  - 不要在错误处理中做错误 recovery（v0.1 只报错退出）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9, 10)
  - **Blocks**: Task 12
  - **Blocked By**: Task 5

  **Acceptance Criteria**:
  - [ ] `ApiError(status=404, url="...", body={"message":"not found"})` → `str()` 含 "404" 和 "not found"
  - [ ] `ValidationError(field="email", value="bad", reason="invalid email")` → `str()` 含 field name
  - [ ] `AuthError("env var MY_TOKEN not set")` → `str()` 含 variable name

  **QA Scenarios**:
  ```
  Scenario: ApiError formats clearly
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.engine.errors import ApiError;
        e = ApiError(status=404, url='https://api.example.com/users/999', body={'message':'User not found'});
        msg = str(e);
        print(msg);
        assert '404' in msg;
        assert 'User not found' in msg
      "
    Expected Result: Message contains "404" and "User not found"
    Evidence: .omo/evidence/task-11-error-format.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add structured error types and handler`
  - Files: `src/cliyard/engine/errors.py`, `src/cliyard/engine/error_handler.py`

- [x] 12. Runtime 管线函数 `run_with_spec()`

  **What to do**:
  - 创建 `src/cliyard/runtime/__init__.py` 和 `src/cliyard/runtime/runner.py`
  - 实现 `run_with_spec(spec_dir: str) -> None` — 生成的 CLI 调用的唯一入口
  - 核心流程：
    ```
    1. load_service(spec_dir)                      → ServiceSpec
    2. build_service_commands(cli, service)         → 动态生成 Click 子命令
    3. cli(standalone_mode=False)                   → 执行 CLI
    ```
  - `build_service_commands(cli, service)`:
    - 遍历 service.resources
    - 为每个 resource 调用 `build_resource_group()`（Task 8）
    - 注册到根 Click group
  - 这个函数是 **生成的 CLI 的唯一运行时入口**。generated `ketacliv2/main.py` 只需：
    ```python
    from cliyard.runtime import run_with_spec
    import importlib.resources
    SPEC_DIR = str(importlib.resources.files('ketacliv2') / 'specs')
    def main():
        run_with_spec(SPEC_DIR)
    ```
  - 也更新 `__main__.py` 中的 `--spec-dir` 模式复用这个函数（开发/测试用）

  > **ketacli 对照**:
  > ketacli 没有这个抽象 — `ketacli.py:46` 中 `cli(standalone_mode=False)` 直接调用根 Click group，所有命令预先在 `ketacli.py` 中逐一 import 并注册。cliyard 通过 `run_with_spec()` 把"加载 spec → 注册命令 → 执行 CLI"封装成一个调用。

  **Must NOT do**:
  - 不要在 `run_with_spec()` 中包含 HTTP 请求逻辑（那是 Click 回调的事）
  - 不要硬编码 spec 路径

  **Recommended Agent Profile**: `deep`
  **Parallelization**: Wave 3 (with Tasks 13, 14, 15, 16, 17) | **Blocks**: Tasks 18, 19, 21 | **Blocked By**: Tasks 7, 8, 9, 10, 11

  **Acceptance Criteria**:
  - [ ] `run_with_spec("tests/fixtures/")` 注册 Click 命令成功
  - [ ] `cli.invoke(["repos", "list", "--help"])` 正确输出
  - [ ] 从 Python 代码中调用 `run_with_spec()` 不抛异常

  **QA Scenarios**:
  ```
  Scenario: run_with_spec registers commands and handles --help
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.runtime.runner import run_with_spec;
        from click.testing import CliRunner;
        import click;
        # build a CLI...
        print('PASS: import ok')
      "
    Expected Result: "PASS: import ok"
    Evidence: .omo/evidence/task-12-runtime-ok.txt
  ```

  **Commit**: YES — Message: `[feat(runtime)]: add run_with_spec pipeline entry point` — Files: `src/cliyard/runtime/`

- [x] 21. `cliyard gen` 代码生成命令

  **What to do**:
  - 创建 `src/cliyard/cli/gen.py`：实现 `cliyard gen` CLI 命令
  - 命令参数：`--name` (生成的 CLI 工具名)、`--defs-path` (spec 目录)、`--output` (输出目录，默认 `./dist/<name>/`)
  - `cliyard gen` 的执行流程：
    ```
    1. 校验 defs-path 存在 + 含 _service.yaml
    2. 创建 output/<name>/ 目录
    3. 生成 pyproject.toml（name=<name>, dependency=cliyard>=0.1.0, entry_point=<name>.main:main）
    4. 生成 src/<name>/__init__.py
    5. 生成 src/<name>/main.py（薄包装调用 run_with_spec）
    6. 复制 spec 目录到 src/<name>/specs/（作为 package data）
    7. 生成 README.md（使用说明）
    ```
  - 生成的 `main.py` 模板：
    ```python
    from cliyard.runtime import run_with_spec
    import importlib.resources
    _SPEC_DIR = str(importlib.resources.files('__PACKAGE__') / 'specs')
    def main():
        run_with_spec(_SPEC_DIR)
    ```
  - 生成的 `pyproject.toml` 模板：
    ```toml
    [project]
    name = "ketacliv2"
    version = "0.1.0"
    requires-python = ">=3.10"
    dependencies = ["cliyard>=0.1.0"]
    [project.scripts]
    ketacliv2 = "ketacliv2.main:main"
    ```

  > **ketacli 对照**: 这个功能在 ketacli 中不存在（ketacli 是为 KetaDB 定制的工具，不可泛化）。它是 cliyard 作为**框架**的核心差异化能力。

  **Must NOT do**:
  - 不要生成 setup.py（只生成 pyproject.toml）
  - 不要在生成的代码中包含任何业务逻辑

  **Recommended Agent Profile**: `deep`
  **Parallelization**: Wave 4 (with Tasks 18, 19, 20) | **Blocks**: Task 19 | **Blocked By**: Tasks 12, 18

  **Acceptance Criteria**:
  - [ ] `cliyard gen --name ketacliv2 --defs-path examples/ketacli-repos/` 生成 `dist/ketacliv2/`
  - [ ] 生成的 pyproject.toml 含 entry_point `ketacliv2 = ketacliv2.main:main`
  - [ ] `pip install ./dist/ketacliv2/ && ketacliv2 repos list --help` 正常工作

  **QA Scenarios**:
  ```
  Scenario: cliyard gen generates installable CLI package
    Tool: Bash
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. cliyard gen --name ketacliv2 --defs-path examples/ketacli-repos/ --output /tmp/ketacliv2/
      3. pip install /tmp/ketacliv2/
      4. ketacliv2 repos list --help
    Expected Result: Shows --with-doc-size, --page, --per-page options
    Evidence: .omo/evidence/task-21-gen-ketacliv2.txt
  ```

  **Commit**: YES — Message: `[feat(cli)]: add cliyard gen code generation command` — Files: `src/cliyard/cli/gen.py`

- [x] 13. 字段类型校验器

  **What to do**:
  - 创建 `src/cliyard/validate/types.py`：5 种核心字段类型的校验逻辑
  - 每种类型的校验规则：

  | 类型 | 校验 | 错误消息模板 |
  |------|------|-------------|
  | `string` | `pattern` (regex), `min_length`, `max_length` | `"user.email": value "xx" does not match pattern "..."` |
  | `int` | `min`, `max`（值为整数） | `"page": expected int, got "abc"` |
  | `float` | `min`, `max`（值为浮点数） | `"ratio": expected float, got "abc"` |
  | `bool` | true/false | `"enabled": expected bool, got "abc"` |
  | `enum` | 值必须在 `choices` 中 | `"role": "superadmin" not in [admin, user, viewer]` |

  - 创建一个统一的 `validate_field(field_spec: ParamSpec, value: Any) -> Result[Any, ValidationError]` 调度函数
  - 校验在 HTTP 请求前执行（pipeline stage 4 之前）

  > **ketacli 参考**:
  > ketacli 没有独立的字段校验层。参数类型只在 `extract_template_vars()` 中根据 `default()` 值自动推断，但没有校验。
  > 例如：YAML 中 `type: int`，用户传 `--capacity-size-value abc`，Click 会报 "abc is not a valid integer"，但这是 Click 的内置行为。
  > cliyard 比 Click 多做一层：**业务级校验**（枚举值范围、正则 pattern、最小值/最大值等）。

  **Must NOT do**:
  - 不要支持 v0.1 范围外的类型（array/dict/file/date/datetime/secret）
  - 不要在校验器中做 HTTP 请求

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 14, 15, 16, 17)
  - **Blocks**: Task 14
  - **Blocked By**: Task 2

  **Acceptance Criteria**:
  - [ ] `validate_field({"type":"enum","choices":["a","b"]},"c")` → error with "not in"
  - [ ] `validate_field({"type":"int","min":0,"max":100},101)` → error with "max 100"
  - [ ] `validate_field({"type":"string","pattern":"^\\w+$"},"hello world")` → error
  - [ ] `validate_field({"type":"int","default":1},3)` → passes

  **QA Scenarios**:
  ```
  Scenario: Enum validation rejects invalid choice
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.validate.types import validate_field;
        try:
            validate_field({'type':'enum','choices':['admin','user']}, 'superadmin');
            print('FAIL: should have raised')
        except Exception as e:
            print('PASS:', str(e))
      "
    Expected Result: "PASS: ... not in [admin, user]"
    Evidence: .omo/evidence/task-13-enum-reject.txt

  Scenario: Int validation rejects non-integer
    Tool: Bash + Python REPL
    Steps:
      1. python3 -c "
        from cliyard.validate.types import validate_field;
        try:
            validate_field({'type':'int'}, 'not-a-number');
            print('FAIL')
        except Exception as e:
            print('PASS:', type(e).__name__)
      "
    Expected Result: "PASS: ValidationError"
    Evidence: .omo/evidence/task-13-int-reject.txt
  ```

  **Commit**: YES
  - Message: `[feat(validate)]: add field type validators`
  - Files: `src/cliyard/validate/types.py`, `src/cliyard/validate/__init__.py`

- [x] 14. CLI 参数绑定器

  **What to do**:
  - 创建 `src/cliyard/engine/binder.py`：将 Click 收集的 `**kwargs` 绑定到 MethodSpec 的参数声明
  - 实现 `bind_and_validate(kwargs: dict, method_spec: MethodSpec) -> ValidatedParams`：
    1. 遍历 `method_spec.params` 中所有字段
    2. 从 `kwargs` 中取值（key = field name）
    3. 没有传值但有 `default` 的 → 用默认值
    4. `required=True` 且无值 → 报错
    5. 调用 `validate_field()` 校验值
    6. 返回干净的 `ValidatedParams` 字典
  - `ValidatedParams` 是一个瘦包装：
    ```python
    class ValidatedParams:
        path: dict       # 给 path 模板用的变量
        query: dict      # 给 query string 用的参数
        header: dict     # 给 header 用的参数
        body: dict       # 给 body 模板用的变量
    ```
  - 参数自动按 `params.{path|query|header|body}` 分组

  > **ketacli 对照**:
  > ketacli 的参数绑定逻辑内嵌在 `make_operation_cmd.callback()` 里（第 461-487 行），混在 HTTP 请求逻辑中。独立出来的 binder 可以做纯函数测试。

  **Must NOT do**:
  - 不要在 binder 中做 HTTP 请求
  - 不要在 binder 中处理 auth

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 15, 16, 17)
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 8, 13

  **Acceptance Criteria**:
  - [ ] required 字段缺失 → `ValidationError`
  - [ ] path 参数正确分组到 `ValidatedParams.path`
  - [ ] query 参数正确分组到 `ValidatedParams.query`
  - [ ] 带 default 值未传参 → default 被填入

  **QA Scenarios**:
  ```
  Scenario: Parameter binding groups params by location
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.engine.binder import bind_and_validate;
        method_spec = {
            'params': {
                'path': [{'name': 'user_id', 'type': 'string', 'required': True}],
                'query': [{'name': 'page', 'type': 'int', 'default': 1}]
            }
        };
        result = bind_and_validate({'user_id': 'abc123'}, method_spec);
        print('path:', result.path);
        print('query:', result.query);
        assert result.path['user_id'] == 'abc123';
        assert result.query['page'] == 1
      "
    Expected Result: path: {'user_id': 'abc123'} + query: {'page': 1}
    Evidence: .omo/evidence/task-14-binder-groups.txt

  Scenario: Missing required field raises error
    Tool: Bash + Python REPL
    Steps:
      1. python3 -c "
        from cliyard.engine.binder import bind_and_validate;
        try:
            bind_and_validate({}, {'params': {'path': [{'name':'id','type':'string','required':True}]}});
            print('FAIL')
        except Exception as e:
            print('PASS:', type(e).__name__)
      "
    Expected Result: "PASS: ValidationError"
    Evidence: .omo/evidence/task-14-binder-required.txt
  ```

  **Commit**: YES
  - Message: `[feat(engine)]: add CLI parameter binder with validation`
  - Files: `src/cliyard/engine/binder.py`

- [x] 15. 认证链引擎

  **What to do**:
  - 创建 `src/cliyard/client/auth.py`：执行多步认证链
  - 实现 `run_auth_chain(auth_spec: AuthChain, http_client: HttpClient) -> dict`：
    ```
    1. 初始化 auth_state = {}
    2. for step in auth_spec.steps:
       switch step.type:
         case "env":
           auth_state[step.name] = os.environ[step.config.name]
         case "login":
           resp = http_client.request(step.config)
           auth_state[step.name] = jsonpath(resp, step.extract)
         case "inject":
           # 注入到 http_client 的默认 header/query/cookie
           http_client.set_default_auth(step.config)
    3. return auth_state
    ```
  - 3 种内置 step 的实现：
    - `env`: `os.environ.get(name)` → 不存在则 `AuthError`
    - `login`: 发 HTTP 请求 → 用 JSONPath 提取 → 存到 `auth_state`
    - `inject`: 将 `auth_state` 中的 token 注入后续请求（修改 `http_client` 的默认 headers/query）

  > **ketacli 参考**:
  > ketacli 没有认证链概念。认证是硬编码的 Bearer token：
  > ```python
  > # ketacli client.py:257-260
  > headers = {'Authorization': f"Bearer {token}", 'Content-Type': "application/json"}
  > ```
  > 如果用户想换一种认证方式（如放在 query 或 cookie），需要改 Python 代码。
  > cliyard 通过 YAML 配置 `inject.into: query` 即可切换。

  > **ketacli 示例 — 如果 cliyard 包装 KetaDB API，认证配置为**:
  > ```yaml
  > auth:
  >   steps:
  >     - name: token
  >       type: env
  >       config:
  >         name: KETA_SERVICE_TOKEN
  >     - name: inject
  >       type: inject
  >       config:
  >         into: header
  >         name: Authorization
  >         prefix: "Bearer "
  > ```

  **Must NOT do**:
  - 不要实现 prompt/file/sign/plugin:xxx 类型
  - 不要在 auth chain 中做 token 刷新（401 → re-auth → retry）

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 14, 16, 17)
  - **Blocks**: Task 16
  - **Blocked By**: Task 5

  **Acceptance Criteria**:
  - [ ] `env` step 读取环境变量成功
  - [ ] `login` step 发 HTTP 请求并用 JSONPath 提取成功
  - [ ] `inject` step 注入 header 成功（后续请求带该 header）
  - [ ] 环境变量不存在 → `AuthError`

  **QA Scenarios**:
  ```
  Scenario: Auth chain injects token into header
    Tool: Bash + Python REPL
    Steps:
      1. export TEST_TOKEN=my-secret-token
      2. cd /data/git-project/cliyard && source venv/bin/activate
      3. python3 -c "
        import os;
        os.environ['TEST_TOKEN'] = 'my-secret-token';
        from cliyard.client.http import HttpClient;
        from cliyard.client.auth import run_auth_chain;
        client = HttpClient('https://httpbin.org');
        auth_spec = {
            'steps': [
                {'name': 'token', 'type': 'env', 'config': {'name': 'TEST_TOKEN'}},
                {'name': 'inject', 'type': 'inject', 'config': {'into': 'header', 'name': 'X-Auth-Token'}}
            ]
        };
        state = run_auth_chain(auth_spec, client);
        print('Token:', state.get('token'));
        assert 'my-secret-token' in client.default_headers.get('X-Auth-Token','')
      "
    Expected Result: Token value printed correctly
    Evidence: .omo/evidence/task-15-auth-chain.txt
  ```

  **Commit**: YES
  - Message: `[feat(client)]: add auth chain engine (env/login/inject)`
  - Files: `src/cliyard/client/auth.py`

- [x] 16. Token 缓存

  **What to do**:
  - 在 `src/cliyard/client/auth.py` 中增加 token 缓存逻辑
  - 当 `login` step 的 `extract` 中有 `ttl` 字段时：
    - 记录 `(token_value, expires_at)` 到内存缓存
    - 后续请求复用 token，不重新 login
    - token 过期（`time.time() > expires_at`）时重新 login
  - 缓存 Key = `(step_name, endpoint_url)` 组合
  - 缓存生命周期 = 单次 CLI 运行（进程内），不持久化到磁盘

  > **ketacli 参考**:
  > ketacli 没有 token TTL 处理 — token 永久存储到 `~/.keta/config.yaml`，由用户手动 `ketacli config refresh` 或重新 login。
  > cliyard 的做法是进程内自动管理 token 生命周期。

  **Must NOT do**:
  - 不要持久化 token 到文件（安全的考虑，v0.1 不做）
  - 不要做 401 → re-auth → retry 逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 14, 15, 17)
  - **Blocked By**: Task 15

  **Acceptance Criteria**:
  - [ ] 第一次调用 login → 缓存 token + expiry
  - [ ] 第二次调用 → 命中缓存，不重复 login
  - [ ] expiry 过后再调用 → 重新 login

  **QA Scenarios**:
  ```
  Scenario: Token is cached and not re-requested within TTL
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.client.auth import TokenCache;
        cache = TokenCache();
        cache.set('my-step', {'token': 'abc'}, ttl=3600);
        assert cache.get('my-step') == {'token': 'abc'};
        # Simulate expiry
        cache.set('exp-step', {'token': 'old'}, ttl=-1);
        assert cache.get('exp-step') is None;
        print('PASS: cache works')
      "
    Expected Result: "PASS: cache works"
    Evidence: .omo/evidence/task-16-cache.txt
  ```

  **Commit**: YES
  - Message: `[feat(client)]: add in-memory token TTL cache`
  - Files: `src/cliyard/client/auth.py`

- [x] 17. 字段依赖（depends_on.eq）

  **What to do**:
  - 创建 `src/cliyard/validate/dependency.py`：处理字段间的条件依赖
  - 实现 `check_dependencies(params: dict, field_specs: list[ParamSpec]) -> list[ValidationError]`：
    - 遍历所有 `depends_on` 声明的字段
    - v0.1 仅支持 `eq` 条件
    - 条件满足（如 `deploy_strategy == "rolling_update"`）时：
      - 字段有 `required: true` → 无值则报错
      - 字段无值但条件满足 → 不报错（可选字段）
    - 条件不满足时，该字段**完全忽略**（不校验，不注入到请求）

  > **ketacli 示例 — 场景**:
  > 在 ketacli 的 `repos.yaml` 中，`create` 方法的 `template_fields` 中不同存储类型需要不同参数。
  > 例如：`store_type: RETENTION` 需要 `retention` 字段，`store_type: RAW` 不需要。
  > 当前 ketacli 无法表达这种依赖 — 所有参数全部暴露给用户。
  >
  > cliyard 配置：
  > ```yaml
  > - name: retention
  >   type: int
  >   depends_on:
  >     field: store_type
  >     eq: RETENTION
  >   description: 保留天数
  > ```

  **Must NOT do**:
  - 不要实现 `in`, `gt`, `lt`, `required_if`, `mutually_exclusive` 等规则
  - 不要实现条件可见/隐藏（v0.1 所有字段始终可见，仅条件必填）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 12, 13, 14, 15, 16)
  - **Blocks**: Task 14
  - **Blocked By**: Task 13

  **Acceptance Criteria**:
  - [ ] `field.eq` 条件满足 + `required=true` + 无值 → 报错
  - [ ] `field.eq` 条件不满足 + `required=true` → 不报错（该字段被忽略）
  - [ ] `field.eq` 条件满足 + 有值 → 正常通过

  **QA Scenarios**:
  ```
  Scenario: depends_on.eq makes field conditionally required
    Tool: Bash + Python REPL
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. python3 -c "
        from cliyard.validate.dependency import check_dependencies;
        field_specs = [
            {'name': 'deploy_strategy', 'type': 'enum', 'choices': ['rolling','recreate']},
            {'name': 'max_surge', 'type': 'int', 'required': True,
             'depends_on': {'field': 'deploy_strategy', 'eq': 'rolling'}}
        ];
        # Case 1: condition met, field missing → error
        errors = check_dependencies({'deploy_strategy': 'rolling'}, field_specs);
        assert len(errors) == 1;
        print('Case1 PASS: error for missing max_surge');
        # Case 2: condition not met, field missing → no error
        errors = check_dependencies({'deploy_strategy': 'recreate'}, field_specs);
        assert len(errors) == 0;
        print('Case2 PASS: no error when condition not met')
      "
    Expected Result: Both cases PASS
    Evidence: .omo/evidence/task-17-depends-on.txt
  ```

  **Commit**: YES
  - Message: `[feat(validate)]: add field dependency support (depends_on.eq)`
  - Files: `src/cliyard/validate/dependency.py`

- [x] 18. Ketacli repos 示例 spec

  **What to do**:
  - 创建 `examples/ketacli-repos/` 目录，包含完整的 ketacli repos 资源 cliyard 化定义
  - 创建 `examples/ketacli-repos/_service.yaml`：服务器 + 认证配置
  - 创建 `examples/ketacli-repos/repos.yaml`：等价于 ketacli `sdk/request/api/repos.yaml`

  > **目标工作流**:
  > ```bash
  > cliyard gen --name ketacliv2 --defs-path examples/ketacli-repos/ --output ./dist/ketacliv2/
  > pip install ./dist/ketacliv2/
  > ketacliv2 repos list --help     # → 显示 --with-doc-size --page --per-page
  > ketacliv2 repos create --help   # → 显示 --name --repo-type --capacity-size-value --retention
  > ```

  > **映射关系 — ketacli → cliyard**:
  >
  > | ketacli 概念 | cliyard 配置 |
  > |------------|------------|
  > | `~/.keta/config.yaml` 中的 `endpoint` + `token` | `_service.yaml` 中 `server.base_url` + `auth.steps` |
  > | `ROOT_PATH = "api/v1"` | `server.prefix: /api/v1` |
  > | `ketacli asset repos list` | `cliyard --spec-dir examples/ketacli-repos/ repos list` |
  > | `ketacli repos.yaml:51-163` (create 方法) | `examples/ketacli-repos/repos.yaml` (对应结构) |

  - 创建 `examples/ketacli-repos/repos.yaml`：等价于 ketacli `sdk/request/api/repos.yaml`
    - `list` 操作：`query_fields` → `params.query`；`default_fields` → `output.fields`
    - `get` 操作：路径模板 `repos/{{ name }}` → `http.path: repos/{{ name }}`
    - `create` 操作：`template_fields` + `data` → `params.body` + `request_body.template`
    - `update` / `delete` / `download` 同上模式
  - 创建 `examples/ketacli-repos/README.md`

  > **ketacli repos.yaml → cliyard repos.yaml 对照**:
  >
  > ketacli:
  > ```yaml
  > repos:
  >   path: repos
  >   desc: 仓库
  >   methods:
  >     list:
  >       query_fields:
  >         - field: withDocSize
  >           required: true
  >           default: true
  >       default_fields:
  >         - name: name
  >           alias: 仓库名称
  > ```
  >
  > cliyard:
  > ```yaml
  > description: 仓库管理
  > path: repos
  > methods:
  >   list:
  >     http:
  >       method: GET
  >     params:
  >       query:
  >         - name: with_doc_size
  >           type: bool
  >           default: true
  >     output:
  >       items_path: $.repos
  >       fields:
  >         - name: name
  >           alias: 仓库名称
  > ```

  **Must NOT do**:
  - 不要复制 ketacli 的所有 16 个 YAML（只做 repos 一个）
  - 不要在示例中包含真实 token

  **Recommended Agent Profile**: `writing`
  **Parallelization**: Wave 4 (with Tasks 19, 20) | **Blocks**: Task 19 | **Blocked By**: Task 12

  **Acceptance Criteria**:
  - [ ] `cliyard --spec-dir examples/ketacli-repos/ repos list --help` 显示所有参数
  - [ ] `cliyard --spec-dir examples/ketacli-repos/ repos create --help` 显示 --name, --repo-type, --retention 等

  **QA Scenarios**:
  ```
  Scenario: Ketacli repos example generates correct CLI help
    Tool: Bash
    Steps:
      1. cd /data/git-project/cliyard && source venv/bin/activate
      2. cliyard --spec-dir examples/ketacli-repos/ repos list --help
    Expected Result: Shows --with-doc-size, --page, --per-page
    Evidence: .omo/evidence/task-18-ketacli-help.txt
  ```

  **Commit**: YES — Message: `[feat(examples)]: add ketacli repos cliyard spec example` — Files: `examples/ketacli-repos/`

- [x] 19. 集成测试

  **What to do**:
  - 创建 `tests/test_integration.py`：端到端集成测试
  - 6 个测试场景：list request / create request / auth injection / validation blocks request / depends_on / error formatting
  - 用 `click.testing.CliRunner` 或直接调用 pipeline；用 httpbin.org 或 `unittest.mock`

  **Recommended Agent Profile**: `unspecified-high`
  **Parallelization**: Wave 4 (after Task 18) | **Blocks**: F1-F4 | **Blocked By**: Tasks 18, 12, 15

  **Acceptance Criteria**: [ ] 6 个测试全通过 | [ ] `pytest tests/test_integration.py -v` 绿色

  **QA Scenarios**:
  ```
  Scenario: All integration tests pass
    Tool: Bash
    Steps: 1. cd /data/git-project/cliyard && source venv/bin/activate
           2. pytest tests/test_integration.py -v
    Expected Result: 6+ tests pass
    Evidence: .omo/evidence/task-19-integration.txt
  ```

  **Commit**: YES — Message: `[test]: add end-to-end integration tests` — Files: `tests/test_integration.py`

- [x] 20. README + 示例文档

  **What to do**:
  - 更新 `README.md`：从单文件 YAML 描述改为目录即服务描述
  - 包含：简介、安装、快速开始（跑 ketacli-repos 示例）、概念图、与 ketacli 对比表
  - 创建 `examples/README.md`

  **Recommended Agent Profile**: `writing`
  **Parallelization**: Wave 4 (with Tasks 18, 19) | **Blocked By**: Task 18

  **Acceptance Criteria**: [ ] 快速开始可照做 | [ ] 对比表展示通用性 | [ ] 无过时内容

  **QA Scenarios**:
  ```
  Scenario: README quickstart is actionable
    Tool: Bash
    Steps: Follow README steps → pip install -e . → cliyard --help
    Expected Result: CLI starts successfully
    Evidence: .omo/evidence/task-20-readme-quickstart.txt
  ```

  **Commit**: YES — Message: `[docs]: update README with directory-as-service guide` — Files: `README.md`, `examples/README.md`

---

## Final Verification Wave

> **ALL 4 reviewers must APPROVE**. Present results to user and await explicit "okay".

- [x] F1. **Plan Compliance Audit** — `oracle`

  Read plan end-to-end. For each Must Have: verify implementation exists (read file, run command). For each Must NOT Have: grep codebase for forbidden patterns (eval, __builtins__, setup.py). Verify evidence files.

  **Output**: `Must Have [6/6] | Must NOT Have [12/12] | Tasks [20/20] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`

  Run `pytest tests/ -v`. Review all files for: `eval()`, `__builtins__`, `exec(`, bare `except:`, >100 line functions. Verify `SandboxedEnvironment`. Verify no `setup.py`.

  **Output**: `Tests [N/N] | Lint [PASS/FAIL] | Security [CLEAN/N issues] | VERDICT: APPROVE/REJECT`

- [x] F3. **Real Manual QA** — `unspecified-high`

  From clean venv: execute all QA scenarios. Test: CLI entry → spec load → auth chain → HTTP → output. Edge cases: missing env var, invalid YAML, API 500, empty response, 204.

  **Output**: `Scenarios [N/N] | Integration [N tested] | Edge [N tested] | VERDICT: APPROVE/REJECT`

- [x] F4. **Scope Fidelity Check** — `deep`

  For each task: read spec vs git diff. Verify 1:1 — all built, nothing extra. Check Must NOT Do. Flag scope creep. Verify no ketacli coupling.

  **Output**: `Tasks [20/20 compliant] | Creep [CLEAN/N] | Coupling [CLEAN/N] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

- **1**: `[refactor]: fix CLI entry point and cleanup project skeleton`
- **2**: `[feat(schema)]: add TypedDict schema type definitions`
- **3**: `[feat(schema)]: add YAML schema validator`
- **4**: `[feat(engine)]: add Jinja2 sandbox template engine`
- **5**: `[feat(client)]: add HTTP client base layer`
- **6**: `[test]: add pytest infrastructure and fixtures`
- **7**: `[feat(engine)]: add service and resource YAML loader`
- **8**: `[feat(engine)]: add Click dynamic command builder`
- **9**: `[feat(engine)]: add HTTP request assembler`
- **10**: `[feat(output)]: add response handler and table/JSON formatter`
- **11**: `[feat(engine)]: add structured error types and handler`
- **12**: `[feat(runtime)]: add run_with_spec runtime entry point`
- **13**: `[feat(validate)]: add field type validators`
- **14**: `[feat(engine)]: add CLI parameter binder with validation`
- **15**: `[feat(client)]: add auth chain engine (env/login/inject)`
- **16**: `[feat(client)]: add in-memory token TTL cache`
- **17**: `[feat(validate)]: add field dependency support (depends_on.eq)`
- **18**: `[feat(examples)]: add ketacli repos cliyard spec example`
- **19**: `[test]: add end-to-end integration tests`
- **20**: `[docs]: update README with directory-as-service guide`
- **21**: `[feat(cli)]: add cliyard gen code generation command`

---

## Success Criteria

### Verification Commands

```bash
# Core — cliyard itself
cliyard --help
cliyard --version

# Code generation
cliyard gen --name ketacliv2 --defs-path examples/ketacli-repos/ --output /tmp/test-ketacliv2/

# Generated CLI
pip install /tmp/test-ketacliv2/
ketacliv2 repos list --help
ketacliv2 repos create --help

# Dev/test mode (direct spec loading)
cliyard --spec-dir examples/ketacli-repos/ repos list --help

# Tests
pytest tests/ -v

# Security
grep -r 'eval(' src/cliyard/ || echo "NO eval — PASS"
grep -r '__builtins__' src/cliyard/ || echo "NO builtins — PASS"
grep -r 'SandboxedEnvironment' src/cliyard/engine/ || echo "MISSING SANDBOX"
ls setup.py 2>/dev/null || echo "NO setup.py — PASS"
```

### Final Checklist
- [ ] All "Must Have" present（7 项，含 gen 命令）
- [ ] All "Must NOT Have" absent（12 guardrails）
- [ ] All 21 tasks complete
- [ ] `cliyard gen` 生成可安装的 CLI 包
- [ ] `ketacliv2 repos list --help` 正常输出
- [ ] `cliyard --spec-dir examples/ketacli-repos/ repos list --help` 正常输出（dev mode）
- [ ] Integration tests pass
- [ ] Zero `eval()`, zero `__builtins__` injection
- [ ] Jinja2 uses `SandboxedEnvironment`
- [ ] Single version source (`pyproject.toml` only)
- [ ] No >100 line functions, no giant closures