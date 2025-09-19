# CCHooks错误处理系统使用指南

本指南介绍CCHooks统一错误处理系统的使用方法，包括异常处理、日志记录和错误恢复机制。

## 概述

CCHooks错误处理系统提供：

1. **统一异常体系**：中文友好的错误消息和分级处理
2. **智能错误恢复**：自动重试、回滚和降级机制
3. **结构化日志**：多格式日志记录和性能监控
4. **用户友好界面**：清晰的错误提示和解决建议

## 基础使用

### 1. 创建和抛出异常

```python
from cchooks.exceptions import ConfigurationError, ErrorRecoveryAction

# 创建配置错误
error = ConfigurationError(
    "设置文件格式无效",
    config_path="/path/to/settings.json",
    context={"line": 5, "column": 10},
    recovery_actions=[ErrorRecoveryAction.RETRY, ErrorRecoveryAction.ROLLBACK]
)

# 抛出异常
raise error
```

### 2. 捕获和处理异常

```python
from cchooks.exceptions import CCHooksError
from cchooks.utils.error_handler import handle_error

try:
    # 可能出错的操作
    risky_operation()
except CCHooksError as e:
    # 统一错误处理
    handle_error(e, auto_recovery=True, log_error=True)
except Exception as e:
    # 转换标准异常
    from cchooks.exceptions import create_error_from_exception
    cchooks_error = create_error_from_exception(e)
    handle_error(cchooks_error)
```

### 3. 使用装饰器进行异常处理

```python
from cchooks.exceptions import handle_exception_context

@handle_exception_context
def potentially_failing_function():
    # 函数实现
    pass
```

## 异常类型和分类

### 用户错误 (UserError)

用于用户操作错误，如配置错误、参数错误等：

```python
from cchooks.exceptions import ConfigurationError, InvalidArgumentError

# 配置文件错误
config_error = ConfigurationError(
    "钩子配置缺少必需字段",
    config_path="settings.json"
)

# 参数错误
arg_error = InvalidArgumentError(
    "无效的钩子类型",
    argument_name="hook_type",
    valid_values=["pre-tool-use", "post-tool-use"]
)
```

### 系统错误 (SystemError)

用于系统级问题，如权限、网络、IO等：

```python
from cchooks.exceptions import PermissionError, NetworkError

# 权限错误
perm_error = PermissionError(
    "无法写入设置文件",
    path="/etc/claude/settings.json",
    operation="write"
)

# 网络错误
net_error = NetworkError(
    "连接Claude API失败",
    url="https://api.claude.ai"
)
```

### CLI特定错误

```python
from cchooks.cli.exceptions import CommandNotFoundError, CommandSyntaxError

# 命令未找到
cmd_error = CommandNotFoundError(
    "invalidcmd",
    available_commands=["add", "remove", "list"]
)

# 语法错误
syntax_error = CommandSyntaxError(
    "缺少必需参数",
    command_name="add-hook",
    expected_syntax="add-hook <type> <command>"
)
```

## 错误处理器配置

### 基础配置

```python
from cchooks.utils.error_handler import configure_error_handling, ErrorDisplayMode, ColorScheme

# 配置错误处理
configure_error_handling(
    display_mode=ErrorDisplayMode.DETAILED,  # 详细模式
    show_suggestions=True,                   # 显示建议
    show_context=True,                       # 显示上下文
    color_scheme=ColorScheme.BASIC,          # 基础颜色
    enable_recovery_prompts=True,            # 启用恢复提示
    max_context_items=10                     # 最大上下文项目数
)
```

### 交互式错误处理

```python
from cchooks.utils.error_handler import UserFriendlyErrorHandler, ErrorDisplayMode

# 创建交互式处理器
handler = UserFriendlyErrorHandler(
    display_mode=ErrorDisplayMode.INTERACTIVE,
    enable_recovery_prompts=True
)

# 处理错误并获取用户选择
recovery_action = handler.print_error(error)
if recovery_action:
    print(f"用户选择了: {recovery_action}")
```

## 日志记录

### 基础日志配置

```python
from cchooks.utils.logging import configure_logging, LogLevel, LogFormat

# 配置日志
configure_logging(
    log_dir="/var/log/claude",
    log_level=LogLevel.INFO,
    log_format=LogFormat.JSON,  # JSON格式便于解析
    enable_console=True,
    enable_file=True
)
```

### 结构化日志记录

```python
from cchooks.utils.logging import get_logger

logger = get_logger()

# 基础日志
logger.info("钩子执行开始", hook_type="pre-tool-use", user="alice")
logger.warning("配置文件版本过旧", version="1.0", latest="2.0")
logger.error("钩子执行失败", error=exception, context={"tool": "bash"})

# 审计日志
logger.audit(
    action="hook_added",
    user="alice",
    resource="settings.json",
    result="success"
)

# 性能监控
with logger.operation_timer("hook_execution") as timer:
    execute_hook()
```

### 操作监控装饰器

```python
from cchooks.utils.logging import log_operation

@log_operation("data_processing")
def process_data(data):
    # 处理数据
    return processed_data

# 使用上下文管理器
with log_operation("file_backup", file_path="/path/to/file"):
    create_backup()
```

## 错误恢复机制

### 基础恢复配置

```python
from cchooks.utils.recovery import configure_recovery, RetryPolicy, CircuitBreakerConfig

# 配置恢复策略
configure_recovery(
    retry_policy=RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        backoff_factor=2.0,
        jitter=True
    ),
    circuit_breaker_config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0,
        success_threshold=2
    )
)
```

### 自动恢复装饰器

```python
from cchooks.utils.recovery import with_recovery, RecoveryStrategy

@with_recovery([RecoveryStrategy.EXPONENTIAL_BACKOFF, RecoveryStrategy.DEGRADED])
def unreliable_operation():
    # 可能失败的操作
    if random.random() < 0.5:
        raise NetworkError("网络暂时不可用")
    return "success"

# 提供降级操作
@with_recovery(
    strategies=[RecoveryStrategy.DEGRADED],
    context={"fallback_operation": lambda: "使用缓存数据"}
)
def fetch_remote_data():
    # 获取远程数据
    pass
```

### 手动恢复管理

```python
from cchooks.utils.recovery import get_recovery_manager

recovery_manager = get_recovery_manager()

# 尝试恢复操作
result = recovery_manager.attempt_recovery(
    error=network_error,
    operation=lambda: fetch_data(),
    strategies=[RecoveryStrategy.RETRY, RecoveryStrategy.CIRCUIT_BREAKER],
    context={"operation_name": "data_fetch", "timeout": 30}
)

if result.success:
    print(f"恢复成功，使用策略: {result.strategy_used}")
else:
    print(f"恢复失败: {result.error}")
```

### 备份和回滚

```python
# 创建备份
backup_path = recovery_manager.create_backup(
    resource_id="settings_file",
    source_path=Path("settings.json")
)

# 注册健康检查
def check_service_health():
    try:
        response = requests.get("http://localhost:8080/health")
        return response.status_code == 200
    except:
        return False

recovery_manager.register_health_check("api_service", check_service_health)

# 执行健康检查
health_status = recovery_manager.perform_health_check()
print(f"服务状态: {health_status}")
```

## 完整示例

### CLI命令错误处理

```python
from cchooks.cli.exceptions import CLIError, create_cli_usage_error
from cchooks.utils.error_handler import get_error_handler
from cchooks.utils.logging import get_logger

def execute_cli_command(command, args):
    logger = get_logger()

    try:
        logger.audit("command_started", user="system", resource=command)

        if command == "add-hook":
            if len(args) < 2:
                raise create_cli_usage_error(
                    command_name="add-hook",
                    expected_usage="add-hook <type> <command>",
                    provided_args=args
                )

            # 执行命令
            result = add_hook(args[0], args[1])
            logger.audit("command_completed", user="system", resource=command, result="success")
            return result

    except CLIError as e:
        logger.error("CLI命令失败", error=e, command=command, args=args)

        # 显示用户友好错误
        handler = get_error_handler()
        handler.print_error(e)

        return None
```

### 设置文件操作

```python
from cchooks.settings.exceptions import SettingsFileNotFoundError, SettingsValidationError
from cchooks.utils.recovery import get_recovery_manager
from pathlib import Path

def load_settings(settings_path):
    recovery_manager = get_recovery_manager()

    # 创建备份（如果文件存在）
    if settings_path.exists():
        backup_path = recovery_manager.create_backup("settings", settings_path)
        logger.info(f"创建设置备份: {backup_path}")

    try:
        with open(settings_path) as f:
            settings = json.load(f)

        # 验证设置
        validate_settings(settings)
        return settings

    except FileNotFoundError:
        raise SettingsFileNotFoundError(settings_path, level="user")

    except json.JSONDecodeError as e:
        raise SettingsValidationError(
            settings_path,
            validation_errors=[f"JSON解析错误: {e}"]
        )
```

### 钩子执行监控

```python
from cchooks.utils.logging import get_logger
from cchooks.exceptions import ExternalToolError

def execute_hook(hook_config):
    logger = get_logger()

    with logger.operation_timer("hook_execution",
                               hook_type=hook_config["type"],
                               command=hook_config["command"]) as timer:
        try:
            logger.info("开始执行钩子", hook_config=hook_config)

            # 执行钩子命令
            result = subprocess.run(
                hook_config["command"],
                capture_output=True,
                text=True,
                timeout=hook_config.get("timeout", 30)
            )

            if result.returncode != 0:
                raise ExternalToolError(
                    "钩子执行失败",
                    tool_name=hook_config["command"],
                    exit_code=result.returncode,
                    context={
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                )

            logger.info("钩子执行成功", output=result.stdout)
            return result.stdout

        except subprocess.TimeoutExpired:
            raise ExternalToolError(
                "钩子执行超时",
                tool_name=hook_config["command"],
                context={"timeout": hook_config.get("timeout", 30)}
            )
```

## 最佳实践

### 1. 异常创建

- 使用具体的异常类型而不是基础类
- 提供清晰的中文错误消息
- 包含有用的上下文信息
- 指定适当的恢复动作

### 2. 错误处理

- 在适当的层级捕获和处理异常
- 使用统一的错误处理函数
- 记录足够的上下文信息
- 为用户提供可操作的建议

### 3. 日志记录

- 使用结构化日志格式
- 记录操作的开始和结束
- 包含相关的上下文信息
- 定期清理旧日志文件

### 4. 恢复机制

- 为不同类型的错误配置适当的恢复策略
- 实现健康检查和监控
- 定期创建备份
- 测试恢复流程

### 5. 性能考虑

- 避免在热路径中进行昂贵的日志操作
- 使用异步日志记录（如果需要）
- 合理设置重试次数和间隔
- 监控错误恢复的性能影响

## 故障排除

### 常见问题

1. **日志文件权限问题**
   ```bash
   chmod 755 /var/log/claude
   chown $USER:$USER /var/log/claude
   ```

2. **恢复策略不生效**
   - 检查错误类型是否匹配
   - 验证恢复策略配置
   - 查看恢复日志

3. **错误消息不是中文**
   - 检查locale设置
   - 确认使用了CCHooks异常类型

### 调试技巧

1. **启用调试日志**
   ```python
   configure_logging(log_level=LogLevel.DEBUG)
   ```

2. **使用调试格式**
   ```python
   configure_error_handling(display_mode=ErrorDisplayMode.DEBUG)
   ```

3. **查看恢复统计**
   ```python
   recovery_manager = get_recovery_manager()
   stats = recovery_manager.get_recovery_stats()
   print(json.dumps(stats, indent=2))
   ```

## 相关资源

- [CCHooks API文档](./api_reference.md)
- [错误代码参考](./error_codes.md)
- [日志格式规范](./log_format.md)
- [恢复策略配置](./recovery_config.md)