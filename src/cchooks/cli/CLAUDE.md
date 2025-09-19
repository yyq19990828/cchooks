[Root Directory](../../../CLAUDE.md) > [src](../../) > [cchooks](../) > **cli**

# CCHooks CLI命令工具

## Module Responsibilities

CLI命令工具模块为 cchooks 库提供完整的命令行接口，实现钩子配置的生命周期管理：

- **钩子管理**: 添加、更新、删除、列出、验证钩子配置
- **模板系统**: 从内置模板生成钩子脚本，注册自定义模板
- **设置文件操作**: 安全操作 `.claude/settings.json` 文件
- **统一用户体验**: 一致的错误处理、进度指示、输出格式

## Entry and Startup

### 主入口点
- **`main.py`**: 统一CLI调度器和动态命令生成
- **命令注册**: `COMMAND_REGISTRY` 中央命令映射表
- **脚本入口**: `pyproject.toml` 中定义的 9 个console scripts

### 使用方式
```bash
# 统一调度器方式
cchooks addhook PreToolUse --command "echo 'Before tool'" --matcher "Write"
cchooks listhooks --format json

# 直接命令方式
cc_addhook PreToolUse --command "echo 'Before tool'" --matcher "Write"
cc_listhooks --format json
```

## External Interfaces

### 钩子管理命令
- **`cc_addhook`** - 添加新的钩子配置到设置文件
- **`cc_updatehook`** - 更新现有钩子配置
- **`cc_removehook`** - 从设置中移除钩子配置
- **`cc_listhooks`** - 列出已配置的钩子 (支持过滤和格式化)
- **`cc_validatehooks`** - 验证钩子配置语法和语义

### 模板管理命令
- **`cc_generatehook`** - 从模板生成Python钩子脚本
- **`cc_registertemplate`** - 注册新的自定义钩子模板
- **`cc_listtemplates`** - 列出可用的钩子模板 (内置+自定义)
- **`cc_unregistertemplate`** - 注销自定义钩子模板

### 工具命令
- **`backup`** - 备份管理工具 (创建、恢复、验证备份)

## Key Dependencies and Configuration

### 核心依赖
- **命令实现**: `commands/` 目录下的具体命令实现
- **参数解析**: `argument_parser.py` 统一的CLI参数处理
- **错误处理**: `exceptions.py` CLI特定异常处理

### CLI框架特性
- **动态命令生成**: 基于 `COMMAND_REGISTRY` 自动生成命令函数
- **性能监控**: 长时间运行命令的执行时间和内存使用监控
- **进度指示器**: 用户友好的spinner和进度提示
- **信号处理**: 优雅处理 SIGINT/SIGTERM 中断

### 环境变量配置
```bash
CCHOOKS_DEBUG=true      # 启用调试模式
CCHOOKS_LOG_LEVEL=INFO  # 设置日志级别
```

## Data Models

### 命令注册模型
```python
COMMAND_REGISTRY = {
    "cc_addhook": (
        "commands.add_hook",           # 模块路径
        "cc_addhook_main",            # 函数名
        "添加新的钩子配置"              # 描述
    ),
    # ... 其他命令映射
}
```

### CLI参数结构
```python
# addhook 命令参数
{
    "event": "PreToolUse",
    "command": "your-script.py",
    "matcher": "Write|Edit",
    "level": "project",           # project/user
    "timeout": 60,
    "add_to_settings": True
}

# listhooks 输出格式
{
    "format": "table|json|yaml",
    "event": "PreToolUse",        # 可选过滤
    "level": "all|project|user"
}
```

### 错误处理框架
```python
# 统一的退出码
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_PERMISSION_ERROR = 3
EXIT_INTERNAL_ERROR = 4
EXIT_INTERRUPTED = 130
```

## Testing and Quality

### 测试覆盖
- **契约测试** (`tests/contract/`): CLI命令的接口契约验证
- **集成测试**: 实际命令执行和文件操作测试
- **参数解析测试**: 各种参数组合的解析正确性

### 测试类型
```bash
# CLI特定测试
tests/contract/test_cli_commands.py        # 主要CLI命令测试
tests/contract/test_cli_commands_isolated.py  # 隔离环境测试
tests/contract/test_cli_commands_minimal.py   # 最小环境测试
tests/contract/test_settings_api.py       # 设置文件API测试
```

### 质量监控
- **性能阈值**: 单个命令执行时间 < 100ms (PERFORMANCE_THRESHOLD_MS)
- **内存监控**: 调试模式下的内存使用跟踪
- **错误处理**: 所有异常都有对应的用户友好错误信息

## Frequently Asked Questions (FAQ)

### Q: 如何添加新的CLI命令？
1. 在 `commands/` 目录创建命令实现模块
2. 在 `COMMAND_REGISTRY` 中注册命令
3. 在 `pyproject.toml` 中添加 console script 入口
4. 添加对应的契约测试

### Q: CLI命令如何处理 settings.json 文件？
CLI命令严格遵循 Claude Code 设置文件格式：
- 只修改 `hooks` 部分，保留其他设置不变
- 钩子对象只包含 `type`、`command`、`timeout` 字段
- 自动备份和恢复机制防止数据丢失

### Q: 如何实现命令的输出格式化？
```python
# 支持多种输出格式
cchooks listhooks --format table   # 默认表格格式
cchooks listhooks --format json    # JSON格式 (机器可读)
cchooks listhooks --format yaml    # YAML格式 (人类可读)
```

### Q: 如何处理长时间运行的命令？
使用 `ProgressIndicator` 类提供用户反馈：
```python
progress = ProgressIndicator("正在验证钩子配置", show_spinner=True)
progress.start()
# ... 执行长时间操作
progress.stop("验证完成")
```

## Related File List

### 核心CLI文件
- `src/cchooks/cli/main.py` - 主入口点和命令调度器
- `src/cchooks/cli/argument_parser.py` - 统一参数解析
- `src/cchooks/cli/exceptions.py` - CLI特定异常

### 命令实现
- `src/cchooks/cli/commands/add_hook.py` - 添加钩子命令
- `src/cchooks/cli/commands/update_hook.py` - 更新钩子命令
- `src/cchooks/cli/commands/remove_hook.py` - 删除钩子命令
- `src/cchooks/cli/commands/list_hooks.py` - 列出钩子命令
- `src/cchooks/cli/commands/validate_hooks.py` - 验证钩子命令
- `src/cchooks/cli/commands/generate_hook.py` - 生成钩子命令
- `src/cchooks/cli/commands/register_template.py` - 注册模板命令
- `src/cchooks/cli/commands/list_templates.py` - 列出模板命令
- `src/cchooks/cli/commands/unregister_template.py` - 注销模板命令

### 相关测试
- `tests/contract/test_cli_commands.py` - CLI命令契约测试
- `tests/contract/test_settings_api.py` - 设置API测试
- `tests/cli/` - CLI特定单元测试

## Change Log (Changelog)

### 2025-09-19 11:24:48 - CLI模块上下文创建
- 为CLI模块创建详细的AI上下文文档
- 记录所有9个CLI命令的接口和用法
- 建立CLI测试策略和开发工作流文档
- 定义命令注册机制和统一错误处理框架