[Root Directory](../../../CLAUDE.md) > [src](../../) > [cchooks](../) > **templates**

# CCHooks 钩子模板系统

## Module Responsibilities

钩子模板系统为 cchooks 库提供强大的模板管理和脚本生成功能：

- **内置模板**: 10个生产就绪的钩子模板 (security-guard, auto-formatter等)
- **模板注册**: 自定义模板的注册、发现和管理
- **脚本生成**: 从模板生成可执行的Python钩子脚本
- **参数化配置**: 模板参数替换和自定义配置支持

## Entry and Startup

### 主入口点
- **`registry.py`**: 模板注册中心和发现引擎
- **`base_template.py`**: 所有模板的抽象基类
- **`builtin/`**: 内置模板实现目录

### 模板发现机制
```python
from cchooks.templates import get_template, list_templates

# 获取特定模板
template = get_template("security-guard")

# 列出所有可用模板
templates = list_templates()  # 包含内置+自定义模板
```

## External Interfaces

### 内置模板 (10个)
- **`security-guard`** - 多工具安全防护 (阻止危险命令和敏感文件操作)
- **`auto-formatter`** - 自动代码格式化 (black, isort, prettier等)
- **`auto-linter`** - 代码质量检查 (ruff, flake8, pylint等)
- **`git-auto-commit`** - 自动Git操作 (提交文件变更)
- **`permission-logger`** - 工具使用记录和审计
- **`desktop-notifier`** - 跨平台桌面通知
- **`task-manager`** - 资源清理和任务管理
- **`prompt-filter`** - 敏感信息检测和过滤
- **`context-loader`** - 项目上下文加载
- **`cleanup-handler`** - 会话清理管理

### 模板操作API
```python
# 生成钩子脚本
template.generate(
    event_type="PreToolUse",
    output_path="./hooks/security.py",
    params={
        "matcher": "Bash|Write",
        "dangerous_commands": ["rm -rf", "sudo"],
        "protected_files": [".env", "secrets.json"]
    }
)

# 注册自定义模板
register_template("my-template", MyCustomTemplate)

# 模板验证
template.validate_params(params)
```

## Key Dependencies and Configuration

### 模板系统架构
- **基类系统**: `BaseTemplate` 定义模板接口契约
- **注册机制**: 动态模板发现和加载
- **参数验证**: 模板参数的类型安全验证
- **生成引擎**: Python代码生成和格式化

### 模板定义结构
```python
class BaseTemplate:
    name: str                    # 模板唯一标识符
    description: str             # 人类可读描述
    supported_events: List[str]  # 支持的钩子事件类型
    default_params: Dict         # 默认参数配置
    required_params: List[str]   # 必需参数列表

    def generate() -> str        # 生成钩子脚本代码
    def validate_params()       # 验证输入参数
    def get_help() -> str       # 获取模板使用帮助
```

### 配置文件支持
模板可以从配置文件加载参数：
```yaml
# .cchooks-template.yaml
template: security-guard
params:
  matcher: "Bash|Write|Edit"
  dangerous_commands:
    - "rm -rf"
    - "sudo"
    - "format"
  protected_files:
    - ".env"
    - "secrets.json"
    - "id_rsa"
```

## Data Models

### 模板元数据模型
```python
@dataclass
class TemplateMetadata:
    name: str
    description: str
    author: str
    version: str
    supported_events: List[HookEventType]
    tags: List[str]
    examples: List[str]
    documentation_url: Optional[str]
```

### 生成参数模型
```python
@dataclass
class GenerationParams:
    event_type: HookEventType
    output_path: Path
    template_params: Dict[str, Any]
    add_to_settings: bool = False
    overwrite_existing: bool = False
```

### 内置模板配置
```python
# Security Guard 模板参数
{
    "matcher": "Bash|Write",           # 工具匹配模式
    "dangerous_commands": List[str],   # 危险命令列表
    "protected_files": List[str],      # 受保护文件模式
    "block_mode": "deny|ask",          # 阻止模式
    "log_attempts": bool               # 是否记录尝试
}

# Auto Formatter 模板参数
{
    "formatters": ["black", "isort"],  # 格式化工具列表
    "file_patterns": ["*.py"],         # 文件匹配模式
    "check_only": bool,                # 仅检查不修改
    "config_files": List[str]          # 配置文件路径
}
```

## Testing and Quality

### 模板测试策略
- **生成测试**: 验证模板生成的代码语法正确性
- **参数验证测试**: 测试各种参数组合的验证逻辑
- **执行测试**: 生成的钩子脚本的实际执行测试
- **注册测试**: 自定义模板注册和发现功能测试

### 模板质量标准
```python
# 所有生成的钩子必须通过以下检查
1. Python语法正确性 (ast.parse)
2. 导入cchooks库正确
3. create_context()调用正确
4. 适当的类型断言
5. 正确的输出处理
```

### 测试用例示例
```bash
# 模板生成测试
pytest tests/templates/test_security_guard.py::test_generate_valid_python
pytest tests/templates/test_auto_formatter.py::test_parameter_validation

# 集成测试
pytest tests/integration/test_template_generation.py
```

## Frequently Asked Questions (FAQ)

### Q: 如何创建自定义模板？
1. 继承 `BaseTemplate` 类
2. 实现必需的方法 (`generate`, `validate_params`)
3. 定义模板元数据和参数模式
4. 使用 `register_template()` 注册

```python
class MyCustomTemplate(BaseTemplate):
    name = "my-custom"
    description = "My custom hook template"
    supported_events = ["PreToolUse"]

    def generate(self, event_type, params):
        # 生成Python钩子代码
        return generated_code
```

### Q: 模板参数如何验证？
模板系统使用类型提示和验证函数：
```python
def validate_params(self, params: Dict[str, Any]) -> None:
    if "matcher" not in params:
        raise TemplateValidationError("Missing required parameter: matcher")

    if not isinstance(params["dangerous_commands"], list):
        raise TemplateValidationError("dangerous_commands must be a list")
```

### Q: 如何在生成的钩子中处理模板参数？
模板使用Python字符串格式化或模板引擎：
```python
# 在模板中
dangerous_commands = {dangerous_commands!r}
if any(cmd in command for cmd in dangerous_commands):
    context.output.deny("Dangerous command detected")
```

### Q: 内置模板支持哪些钩子事件？
每个模板在 `supported_events` 中声明支持的事件类型：
- Security Guard: PreToolUse
- Auto Formatter: PostToolUse
- Permission Logger: PreToolUse, PostToolUse
- Task Manager: Stop, SessionEnd
- Context Loader: SessionStart

## Related File List

### 核心模板文件
- `src/cchooks/templates/__init__.py` - 模板系统公共接口
- `src/cchooks/templates/registry.py` - 模板注册和发现引擎
- `src/cchooks/templates/base_template.py` - 模板抽象基类

### 内置模板实现
- `src/cchooks/templates/builtin/__init__.py` - 内置模板包
- `src/cchooks/templates/builtin/security_guard.py` - 安全防护模板
- `src/cchooks/templates/builtin/auto_formatter.py` - 自动格式化模板
- `src/cchooks/templates/builtin/auto_linter.py` - 代码检查模板
- `src/cchooks/templates/builtin/git_auto_commit.py` - Git自动提交模板
- `src/cchooks/templates/builtin/permission_logger.py` - 权限记录模板
- `src/cchooks/templates/builtin/desktop_notifier.py` - 桌面通知模板
- `src/cchooks/templates/builtin/task_manager.py` - 任务管理模板
- `src/cchooks/templates/builtin/prompt_filter.py` - 提示过滤模板
- `src/cchooks/templates/builtin/context_loader.py` - 上下文加载模板
- `src/cchooks/templates/builtin/cleanup_handler.py` - 清理处理模板

### 相关测试
- `tests/templates/` - 模板特定测试
- `tests/integration/test_template_generation.py` - 模板生成集成测试

## Change Log (Changelog)

### 2025-09-19 11:24:48 - 模板系统上下文创建
- 为模板系统创建详细的AI上下文文档
- 记录所有10个内置模板的功能和配置
- 建立模板开发和测试策略文档
- 定义自定义模板创建指南和最佳实践