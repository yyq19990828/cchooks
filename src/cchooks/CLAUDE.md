[Root Directory](../../CLAUDE.md) > [src](../) > **cchooks**

# CCHooks Core Module

## Module Responsibilities

cchooks 核心模块是 Claude Code 钩子库的主要实现，提供：

- **自动钩子类型检测**: 基于输入JSON自动识别和创建适当的钩子上下文
- **类型安全接口**: 为所有9种钩子类型提供强类型Python接口
- **统一输出处理**: 支持简单模式 (退出码) 和高级模式 (JSON输出)
- **异常处理**: 完整的自定义异常层次结构用于错误处理

## Entry and Startup

### 主入口点
- **`__init__.py`**: 包含工厂函数 `create_context()` 和所有公共接口
- **工厂模式**: 自动从stdin读取JSON并创建相应的上下文类型

### 使用示例
```python
from cchooks import create_context

# 自动检测钩子类型并创建上下文
context = create_context()

# 根据钩子类型进行特定处理
if isinstance(context, PreToolUseContext):
    # 工具执行前决策
    context.output.allow("操作安全")
elif isinstance(context, PostToolUseContext):
    # 工具执行后反馈
    context.output.continue_flow("操作完成")
```

## External Interfaces

### 钩子上下文类
- `PreToolUseContext` - 工具执行前的审批/拒绝决策
- `PostToolUseContext` - 工具执行后的反馈和附加上下文
- `NotificationContext` - 处理通知消息，无决策控制
- `UserPromptSubmitContext` - 用户提示提交后处理
- `StopContext` / `SubagentStopContext` - 控制停止行为
- `PreCompactContext` - 转录压缩前处理
- `SessionStartContext` / `SessionEndContext` - 会话生命周期处理

### 输出接口
每个上下文都有对应的输出类，提供：
- **JSON模式**: 结构化输出 (`continue`, `decision`, `reason`)
- **简单模式**: 退出码 (0/1/2)
- **特定方法**: 如 `allow()`, `deny()`, `ask()` 用于PreToolUse

## Key Dependencies and Configuration

### 核心依赖
- **Python 3.8+**: 最低版本要求
- **标准库**: 仅使用Python标准库，无外部运行时依赖

### 开发依赖 (仅开发环境)
- `pytest` - 测试框架
- `pytest-cov` - 覆盖率报告
- `pytest-mock` - 模拟和stubbing
- `ruff` - 代码检查和格式化
- `pyright` - 类型检查

### 配置文件
- `pyproject.toml` - 项目配置、依赖和工具设置
- `Makefile` - 开发工作流自动化

## Data Models

### 钩子输入类型
```python
HookEventType = Literal[
    "PreToolUse", "PostToolUse", "Notification",
    "UserPromptSubmit", "Stop", "SubagentStop",
    "PreCompact", "SessionStart", "SessionEnd"
]

# 常见字段
CommonInputFields = {
    "session_id": str,
    "transcript_path": str,
    "hook_event_name": HookEventType
}
```

### 输出结构
```python
# JSON模式输出
{
    "continue": bool,
    "stopReason": str,
    "suppressOutput": bool,
    "systemMessage": Optional[str],
    "hookSpecificOutput": {
        "hookEventName": str,
        # 钩子特定字段...
    }
}
```

## Testing and Quality

### 测试覆盖
- **单元测试**: 每个上下文类的独立测试
- **工厂测试**: `create_context()` 自动检测逻辑
- **异常测试**: 错误处理和验证逻辑
- **输入/输出测试**: JSON解析和输出格式

### 质量工具
```bash
make check        # 运行所有质量检查
make lint         # ruff 代码检查
make type-check   # pyright 类型验证
make format       # 代码格式化
make test         # 测试 + 覆盖率
```

### 测试数据
测试使用现实的 Claude Code 钩子输入示例：
- 工具调用场景 (Write, Bash, 等)
- 不同钩子生命周期事件
- 错误和边缘情况

## Frequently Asked Questions (FAQ)

### Q: 如何添加新的钩子类型？
1. 在 `types.py` 中添加新的 `HookEventType`
2. 在 `contexts/` 中创建新的上下文和输出类
3. 更新 `__init__.py` 中的 `_HOOK_TYPE_MAP`
4. 添加相应的测试

### Q: 如何处理钩子输入验证错误？
使用 `HookValidationError` 异常，在上下文构造函数中验证必需字段：
```python
if not self._input_data.get("required_field"):
    raise HookValidationError("Missing required field: required_field")
```

### Q: 简单模式 vs JSON模式的选择？
- **简单模式**: 快速原型和简单逻辑，使用退出码
- **JSON模式**: 复杂逻辑、需要详细反馈和Claude集成

## Related File List

### 核心文件
- `src/cchooks/__init__.py` - 主入口点和工厂函数
- `src/cchooks/types.py` - 完整类型定义系统
- `src/cchooks/exceptions.py` - 自定义异常层次结构
- `src/cchooks/utils.py` - JSON解析和验证工具
- `src/cchooks/output_utils.py` - 输出处理工具函数

### 上下文实现
- `src/cchooks/contexts/base.py` - 抽象基类
- `src/cchooks/contexts/pre_tool_use.py` - 最复杂的钩子实现
- `src/cchooks/contexts/[hook_name].py` - 其他8种钩子实现

### 相关测试
- `tests/test_context_creation.py` - 工厂函数测试
- `tests/contexts/test_*.py` - 各上下文的专门测试
- `tests/fixtures/sample_data.py` - 现实场景测试数据

## Change Log (Changelog)

### 2025-09-18 16:35:48 - 模块上下文创建
- 为核心模块创建详细的AI上下文文档
- 记录所有9种钩子类型的接口和用法
- 建立测试策略和开发工作流文档