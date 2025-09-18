[Root Directory](../CLAUDE.md) > **tests**

# CCHooks Test Suite

## Module Responsibilities

测试套件为 cchooks 库提供全面的测试覆盖，确保所有9种钩子类型的正确性、可靠性和性能。测试架构包括：

- **单元测试**: 每个钩子上下文和输出类的独立验证
- **集成测试**: 端到端工作流和现实场景验证
- **固定装置**: 标准化的测试数据和辅助函数
- **覆盖率监控**: 详细的代码覆盖分析和报告

## Entry and Startup

### 测试配置
- **`conftest.py`**: pytest 配置和共享固定装置
- **`pytest.ini_options`**: 在 `pyproject.toml` 中定义的测试配置

### 运行测试
```bash
# 完整测试套件 (包含覆盖率)
make test

# 快速测试 (无覆盖率)
make test-quick

# 特定测试文件
uv run pytest tests/contexts/test_pre_tool_use.py -v

# 单个测试用例
uv run pytest tests/contexts/test_pre_tool_use.py::test_pre_tool_use_allow -v
```

## External Interfaces

### 测试分类

#### 核心功能测试
- `test_context_creation.py` - 工厂函数 `create_context()` 测试
- `test_types.py` - 类型定义和验证测试
- `test_utils.py` - 工具函数测试
- `test_exceptions.py` - 异常处理测试

#### 钩子上下文测试 (`contexts/`)
- `test_pre_tool_use.py` - 工具执行前钩子 (最复杂)
- `test_post_tool_use.py` - 工具执行后钩子
- `test_notification.py` - 通知处理钩子
- `test_user_prompt_submit.py` - 用户提示提交钩子
- `test_stop.py` / `test_subagent_stop.py` - 停止行为钩子
- `test_pre_compact.py` - 转录压缩前钩子
- `test_session_start.py` / `test_session_end.py` - 会话生命周期钩子

#### 集成测试 (`integration/`)
- `test_real_world.py` - 现实场景端到端测试
- `test_user_prompt_submit_scenarios.py` - 用户提示特定场景测试

## Key Dependencies and Configuration

### 测试框架
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src/cchooks",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
    "-v"
]
```

### 测试依赖
- `pytest` - 主测试框架
- `pytest-cov` - 覆盖率报告生成
- `pytest-mock` - 模拟和stubbing支持

## Data Models

### 测试固定装置

#### 共享固定装置 (`conftest.py`)
```python
@pytest.fixture
def mock_stdin():
    """模拟stdin用于JSON输入测试"""

@pytest.fixture
def capture_stdout/stderr():
    """捕获输出用于输出验证"""

@pytest.fixture
def sample_[hook_type]_data():
    """各钩子类型的示例数据"""
```

#### 测试数据 (`fixtures/sample_data.py`)
包含现实的 Claude Code 钩子输入示例：

```python
# PreToolUse示例
SAMPLE_PRE_TOOL_USE_WRITE = {
    "hook_event_name": "PreToolUse",
    "session_id": "sess_abc123def456",
    "tool_name": "Write",
    "tool_input": {"file_path": "/path/to/file.py", "content": "..."}
}

# 危险命令示例
SAMPLE_PRE_TOOL_USE_DANGEROUS = {
    "tool_name": "Bash",
    "tool_input": {"command": "rm -rf /"}
}
```

### 测试覆盖场景

#### 正常流程测试
- ✅ 有效输入的正确处理
- ✅ 各钩子类型的特定行为验证
- ✅ 输出格式的正确性 (JSON/简单模式)

#### 错误处理测试
- ✅ 无效JSON输入
- ✅ 缺失必需字段
- ✅ 未知钩子类型
- ✅ 类型验证失败

#### 边缘情况测试
- ✅ 空输入处理
- ✅ 大数据输入
- ✅ 特殊字符处理

## Testing and Quality

### 覆盖率目标
- **总体覆盖率**: > 95%
- **关键模块覆盖率**: 100% (`__init__.py`, `types.py`, `base.py`)
- **钩子上下文覆盖率**: > 90% 每个上下文类

### 测试报告
```bash
# 生成覆盖率报告
make test

# 查看HTML覆盖率报告
open htmlcov/index.html

# 检查覆盖率XML (CI/CD集成)
coverage.xml
```

### 质量检查集成
测试套件是质量检查流程的一部分：
```bash
make check  # 包含: lint + type-check + format-check + test
```

## Frequently Asked Questions (FAQ)

### Q: 如何为新钩子类型添加测试？
1. 在 `tests/contexts/` 中创建 `test_[hook_name].py`
2. 在 `fixtures/sample_data.py` 中添加示例数据
3. 在 `conftest.py` 中添加相关固定装置
4. 按照现有测试模式编写测试用例

### Q: 如何测试stdin/stdout交互？
使用提供的固定装置：
```python
def test_context_creation(mock_stdin):
    stdin_mock = mock_stdin(sample_data)
    context = create_context(stdin_mock)
    assert isinstance(context, ExpectedContextType)
```

### Q: 如何运行特定的测试子集？
```bash
# 只运行上下文测试
uv run pytest tests/contexts/ -v

# 只运行集成测试
uv run pytest tests/integration/ -v

# 按标记过滤 (如果设置了标记)
uv run pytest -m "slow" -v
```

### Q: 如何处理测试中的异常验证？
```python
def test_invalid_input():
    with pytest.raises(HookValidationError, match="Missing required field"):
        PreToolUseContext(invalid_data)
```

## Related File List

### 核心测试文件
- `tests/conftest.py` - pytest配置和共享固定装置
- `tests/fixtures/sample_data.py` - 现实场景测试数据
- `tests/test_context_creation.py` - 工厂函数测试

### 钩子特定测试
- `tests/contexts/test_pre_tool_use.py` - PreToolUse钩子测试 (最复杂)
- `tests/contexts/test_post_tool_use.py` - PostToolUse钩子测试
- `tests/contexts/test_notification.py` - Notification钩子测试
- `tests/contexts/test_user_prompt_submit.py` - UserPromptSubmit钩子测试
- `tests/contexts/test_stop.py` - Stop钩子测试
- `tests/contexts/test_subagent_stop.py` - SubagentStop钩子测试
- `tests/contexts/test_pre_compact.py` - PreCompact钩子测试
- `tests/contexts/test_session_start.py` - SessionStart钩子测试
- `tests/contexts/test_session_end.py` - SessionEnd钩子测试

### 工具和集成测试
- `tests/test_utils.py` - 工具函数测试
- `tests/test_types.py` - 类型系统测试
- `tests/test_exceptions.py` - 异常处理测试
- `tests/integration/test_real_world.py` - 端到端集成测试
- `tests/integration/test_user_prompt_submit_scenarios.py` - 特定场景测试

## Change Log (Changelog)

### 2025-09-18 16:35:48 - 测试套件上下文创建
- 为测试模块创建完整的AI上下文文档
- 记录所有测试类别和覆盖策略
- 建立测试数据管理和质量保证流程