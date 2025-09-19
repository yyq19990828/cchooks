"""错误处理系统集成测试。

测试完整的错误处理流程，包括异常创建、格式化、日志记录和恢复机制。
"""

import pytest
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch
from io import StringIO

from src.cchooks.exceptions import (
    CCHooksError, UserError, SystemError, InternalError, ExternalError,
    ErrorSeverity, ErrorCategory, ErrorRecoveryAction,
    ConfigurationError, PermissionError, NetworkError,
    create_error_from_exception, handle_exception_context
)
from src.cchooks.cli.exceptions import (
    CLIError, CommandNotFoundError, CommandSyntaxError,
    create_cli_usage_error, suggest_command_alternatives
)
from src.cchooks.settings.exceptions import (
    SettingsError, SettingsFileNotFoundError, SettingsValidationError,
    create_settings_recovery_suggestion, is_settings_recoverable
)
from src.cchooks.utils.error_handler import (
    UserFriendlyErrorHandler, ErrorDisplayMode, ColorScheme,
    get_error_handler, configure_error_handling, handle_error
)
from src.cchooks.utils.logging import (
    StructuredLogger, LogLevel, LogFormat,
    get_logger, configure_logging, log_error, log_operation
)
from src.cchooks.utils.recovery import (
    ErrorRecoveryManager, RecoveryStrategy, RetryPolicy,
    get_recovery_manager, configure_recovery, with_recovery
)


class TestErrorHandlingIntegration:
    """错误处理集成测试。"""

    def setup_method(self):
        """测试前设置。"""
        self.temp_dir = Path(tempfile.mkdtemp())

        # 配置日志
        configure_logging(
            log_dir=self.temp_dir / "logs",
            log_level=LogLevel.DEBUG,
            enable_console=False,
            enable_file=True
        )

        # 配置错误处理
        configure_error_handling(
            display_mode=ErrorDisplayMode.DETAILED,
            show_suggestions=True,
            show_context=True,
            color_scheme=ColorScheme.NONE
        )

        # 配置恢复
        configure_recovery()

    def teardown_method(self):
        """测试后清理。"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_error_flow(self):
        """测试完整的错误处理流程。"""
        # 1. 创建一个用户错误
        error = ConfigurationError(
            "配置文件格式无效",
            config_path=self.temp_dir / "settings.json",
            context={"line": 5, "column": 10}
        )

        # 2. 验证错误属性
        assert error.error_code == "USER_CONFIG_INVALID"
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.category == ErrorCategory.USER
        assert ErrorRecoveryAction.RETRY in error.recovery_actions
        assert error.error_id is not None
        assert error.help_url is not None

        # 3. 测试错误格式化
        handler = get_error_handler()
        formatted = handler.format_error(error)

        assert "配置文件格式无效" in formatted
        assert "建议解决方案" in formatted
        assert "详细信息" in formatted
        assert str(error.error_id) in formatted

        # 4. 测试日志记录
        logger = get_logger()
        logger.error("测试错误", error=error)

        # 验证日志文件
        error_log = self.temp_dir / "logs" / "error.log"
        assert error_log.exists()

        log_content = error_log.read_text(encoding='utf-8')
        assert "配置文件格式无效" in log_content
        assert error.error_id in log_content

        # 5. 测试错误恢复
        recovery_manager = get_recovery_manager()

        def failing_operation():
            raise error

        result = recovery_manager.attempt_recovery(
            error, failing_operation,
            strategies=[RecoveryStrategy.RETRY],
            context={"operation_name": "test_config_load"}
        )

        assert not result.success  # 因为操作总是失败
        assert result.strategy_used == RecoveryStrategy.RETRY

    def test_cli_error_integration(self):
        """测试CLI错误集成。"""
        # 创建CLI错误
        error = CommandNotFoundError(
            "invalidcmd",
            available_commands=["add", "remove", "list", "validate"]
        )

        # 测试命令建议
        suggestions = suggest_command_alternatives("ad", ["add", "remove", "list"])
        assert "add" in suggestions

        # 测试错误格式化
        handler = UserFriendlyErrorHandler(
            display_mode=ErrorDisplayMode.DETAILED,
            color_scheme=ColorScheme.NONE
        )

        formatted = handler.format_error(error)
        assert "未知命令" in formatted
        assert "可用命令" in formatted

    def test_settings_error_integration(self):
        """测试设置错误集成。"""
        # 创建设置文件错误
        settings_file = self.temp_dir / "settings.json"
        error = SettingsFileNotFoundError(settings_file, level="user")

        # 测试恢复建议
        recovery_suggestion = create_settings_recovery_suggestion(error)
        assert "cchooks init" in recovery_suggestion

        # 测试可恢复性
        assert is_settings_recoverable(error)

        # 测试错误处理
        handler = get_error_handler()
        formatted = handler.format_error(error)
        assert "找不到设置文件" in formatted
        assert "用户级别" in formatted

    def test_exception_conversion(self):
        """测试异常转换。"""
        # 测试标准异常转换
        std_error = FileNotFoundError("File not found")
        converted = create_error_from_exception(std_error)

        assert isinstance(converted, UserError)
        assert converted.error_code == "USER_FILE_NOT_FOUND"
        assert converted.original_error == std_error

        # 测试装饰器异常处理
        @handle_exception_context
        def problematic_function():
            raise ValueError("Invalid value")

        with pytest.raises(UserError) as exc_info:
            problematic_function()

        error = exc_info.value
        assert error.error_code == "USER_INVALID_INPUT"
        assert "problematic_function" in error.context["function_name"]

    def test_structured_logging_integration(self):
        """测试结构化日志集成。"""
        logger = get_logger()

        # 测试操作计时
        with logger.operation_timer("test_operation", user="test_user") as op_id:
            time.sleep(0.1)  # 模拟操作

        # 验证性能日志
        perf_log = self.temp_dir / "logs" / "performance.log"
        assert perf_log.exists()

        log_content = perf_log.read_text()
        assert "test_operation" in log_content
        assert "completed" in log_content

        # 测试审计日志
        logger.audit("hook_added", user="test_user", resource="settings.json")

        audit_log = self.temp_dir / "logs" / "audit.log"
        assert audit_log.exists()

        audit_content = audit_log.read_text()
        assert "hook_added" in audit_content
        assert "test_user" in audit_content

    def test_recovery_manager_integration(self):
        """测试恢复管理器集成。"""
        recovery_manager = get_recovery_manager()

        # 注册健康检查
        def mock_health_check():
            return True

        recovery_manager.register_health_check("test_component", mock_health_check)

        # 执行健康检查
        health_status = recovery_manager.perform_health_check()
        assert "test_component" in health_status

        # 测试备份功能
        test_file = self.temp_dir / "test.txt"
        test_file.write_text("test content")

        backup_path = recovery_manager.create_backup("test_resource", test_file)
        assert backup_path.exists()
        assert "test_resource" in backup_path.name

    def test_error_hierarchy(self):
        """测试错误继承层次。"""
        # 测试基础异常
        base_error = CCHooksError("基础错误")
        assert isinstance(base_error, Exception)

        # 测试分类异常
        user_error = UserError("用户错误")
        assert isinstance(user_error, CCHooksError)
        assert user_error.category == ErrorCategory.USER

        system_error = SystemError("系统错误")
        assert isinstance(system_error, CCHooksError)
        assert system_error.category == ErrorCategory.SYSTEM

        # 测试具体异常
        config_error = ConfigurationError("配置错误")
        assert isinstance(config_error, UserError)
        assert isinstance(config_error, CCHooksError)

    def test_error_serialization(self):
        """测试错误序列化。"""
        error = NetworkError(
            "网络连接失败",
            url="https://example.com",
            context={"timeout": 30, "retries": 3}
        )

        # 测试JSON序列化
        error_dict = error.get_full_details()
        json_str = json.dumps(error_dict, ensure_ascii=False)

        # 验证序列化内容
        assert error.error_id in json_str
        assert "网络连接失败" in json_str
        assert "https://example.com" in json_str

        # 测试反序列化（基本验证）
        deserialized = json.loads(json_str)
        assert deserialized["error_code"] == "SYSTEM_NETWORK_ERROR"
        assert deserialized["message"] == "网络连接失败"

    def test_interactive_error_handling(self):
        """测试交互式错误处理。"""
        error = UserError(
            "需要用户确认",
            recovery_actions=[ErrorRecoveryAction.RETRY, ErrorRecoveryAction.SKIP]
        )

        handler = UserFriendlyErrorHandler(
            display_mode=ErrorDisplayMode.INTERACTIVE,
            color_scheme=ColorScheme.NONE
        )

        formatted = handler.format_error(error)
        assert "可执行的恢复动作" in formatted
        assert "重试操作" in formatted
        assert "跳过当前操作继续" in formatted

    def test_multilevel_error_handling(self):
        """测试多级错误处理。"""
        # 模拟嵌套错误处理
        try:
            try:
                raise ValueError("原始错误")
            except ValueError as e:
                raise ConfigurationError("配置处理失败", original_error=e)
        except ConfigurationError as e:
            # 验证错误链
            assert e.original_error is not None
            assert isinstance(e.original_error, ValueError)
            assert str(e.original_error) == "原始错误"

            # 测试完整错误信息
            handler = get_error_handler()
            formatted = handler.format_error(e)
            assert "配置处理失败" in formatted

    def test_performance_monitoring(self):
        """测试性能监控。"""
        logger = get_logger()

        # 测试操作监控装饰器
        @log_operation("test_decorated_operation")
        def monitored_function():
            time.sleep(0.05)
            return "success"

        with monitored_function():
            pass

        # 验证性能日志
        perf_log = self.temp_dir / "logs" / "performance.log"
        assert perf_log.exists()

    def test_error_recovery_with_backoff(self):
        """测试带退避的错误恢复。"""
        recovery_manager = get_recovery_manager()
        attempt_count = 0

        def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise NetworkError("网络临时故障")
            return "success"

        # 使用装饰器进行恢复
        @with_recovery([RecoveryStrategy.EXPONENTIAL_BACKOFF])
        def decorated_operation():
            return flaky_operation()

        start_time = time.time()
        result = decorated_operation()
        duration = time.time() - start_time

        assert result == "success"
        assert attempt_count == 3
        assert duration > 1.0  # 应该有退避延迟

    def test_circuit_breaker_pattern(self):
        """测试断路器模式。"""
        recovery_manager = get_recovery_manager()
        failure_count = 0

        def failing_operation():
            nonlocal failure_count
            failure_count += 1
            raise SystemError(f"失败 #{failure_count}")

        # 多次调用失败操作
        for i in range(10):
            result = recovery_manager.attempt_recovery(
                SystemError("测试错误"),
                failing_operation,
                strategies=[RecoveryStrategy.CIRCUIT_BREAKER],
                context={"operation_name": "test_circuit_breaker"}
            )

            if i >= 5:  # 断路器应该在失败阈值后开启
                # 检查是否被断路器拒绝
                assert not result.success

    def test_comprehensive_error_report(self):
        """测试综合错误报告。"""
        error = ConfigurationError(
            "复杂配置错误",
            config_path=self.temp_dir / "complex.json",
            context={
                "section": "hooks",
                "validation_errors": ["missing required field", "invalid format"],
                "line_number": 42
            },
            recovery_actions=[ErrorRecoveryAction.ROLLBACK, ErrorRecoveryAction.MANUAL]
        )

        handler = get_error_handler()
        report = handler.create_error_report(error)

        # 验证报告内容
        assert report["error_id"] == error.error_id
        assert report["error_code"] == error.error_code
        assert report["message"] == error.message
        assert "validation_errors" in report["context"]
        assert len(report["recovery_actions"]) == 2

        # 验证报告完整性
        required_fields = [
            "error_id", "error_code", "message", "category", "severity",
            "timestamp", "context", "recovery_actions", "report_generated_at"
        ]
        for field in required_fields:
            assert field in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])