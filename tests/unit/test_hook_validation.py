"""单元测试：Hook配置验证

T009任务：在tests/unit/test_hook_validation.py中创建Hook配置验证测试

基于data-model.md和Claude Code格式约束，测试包括：
1. HookConfiguration验证
2. 9种Hook事件类型的特定验证规则
3. ValidationResult模型
4. 边界情况和错误处理

注意：这些是TDD测试，预期在相应的验证器实现完成之前会失败。
"""

import pytest
from typing import Dict, Any, List, Optional
from unittest.mock import Mock

# 导入cchooks现有类型用于语义验证
from cchooks.exceptions import HookValidationError
from cchooks.types.enums import HookEventType, SettingsLevel

# 这些导入在实际实现完成前会失败 - 这是TDD的预期行为
try:
    from cchooks.models.hook_config import HookConfiguration
    from cchooks.models.validation import ValidationResult, ValidationError
except ImportError:
    # TDD阶段：模拟需要实现的类
    HookConfiguration = Mock
    ValidationResult = Mock
    ValidationError = Mock

# HookValidator还未实现，单独处理
try:
    from cchooks.services.hook_validator import HookValidator
except ImportError:
    HookValidator = Mock


class TestHookConfiguration:
    """测试HookConfiguration模型的验证规则"""

    def test_hook_config_type_must_be_command(self):
        """type字段必须为"command" - Claude Code规范要求"""
        # 有效配置
        valid_config = {
            "type": "command",
            "command": "echo 'test'"
        }
        hook = HookConfiguration(**valid_config)
        assert hook.type == "command"

        # 无效的type值
        invalid_configs = [
            {"type": "script", "command": "test"},
            {"type": "function", "command": "test"},
            {"type": "", "command": "test"},
            {"type": None, "command": "test"}
        ]

        for config in invalid_configs:
            with pytest.raises((ValueError, HookValidationError)):
                HookConfiguration(**config)

    def test_command_must_be_non_empty_string(self):
        """command字段必须为非空字符串"""
        # 有效命令
        valid_commands = [
            "echo 'hello'",
            "python script.py",
            "ls -la",
            "cmd.exe /c dir"  # Windows兼容
        ]

        for cmd in valid_commands:
            config = {"type": "command", "command": cmd}
            hook = HookConfiguration(**config)
            assert hook.command == cmd
            assert len(hook.command.strip()) > 0

        # 无效命令
        invalid_commands = [
            "",           # 空字符串
            "   ",        # 只有空格
            None,         # None值
            123,          # 非字符串
            [],           # 列表
        ]

        for cmd in invalid_commands:
            config = {"type": "command", "command": cmd}
            with pytest.raises((ValueError, HookValidationError, TypeError)):
                HookConfiguration(**config)

    def test_timeout_must_be_positive_integer(self):
        """timeout必须为正整数（可选）"""
        base_config = {"type": "command", "command": "echo test"}

        # 有效的timeout值
        valid_timeouts = [1, 30, 60, 300, 3600]
        for timeout in valid_timeouts:
            config = {**base_config, "timeout": timeout}
            hook = HookConfiguration(**config)
            assert hook.timeout == timeout

        # timeout为None（可选）
        hook_no_timeout = HookConfiguration(**base_config)
        assert hook_no_timeout.timeout is None

        # 无效的timeout值
        invalid_timeouts = [
            0,           # 零值
            -1,          # 负数
            -30,         # 负数
            1.5,         # 浮点数
            "60",        # 字符串
            [],          # 列表
        ]

        for timeout in invalid_timeouts:
            config = {**base_config, "timeout": timeout}
            with pytest.raises((ValueError, HookValidationError, TypeError)):
                HookConfiguration(**config)

    def test_no_additional_fields_allowed(self):
        """禁止额外字段 - Claude Code格式约束"""
        base_config = {"type": "command", "command": "echo test"}

        # 尝试添加禁止的字段
        forbidden_fields = [
            {"description": "test hook"},
            {"enabled": True},
            {"priority": 1},
            {"env": {"VAR": "value"}},
            {"working_dir": "/tmp"},
            {"shell": "/bin/bash"},
            {"user": "root"},
            {"args": ["arg1", "arg2"]},
        ]

        for extra_field in forbidden_fields:
            config = {**base_config, **extra_field}
            with pytest.raises((ValueError, HookValidationError)):
                HookConfiguration(**config)

    def test_matcher_required_for_tool_hooks(self):
        """matcher字段对PreToolUse/PostToolUse是必需的"""
        base_config = {"type": "command", "command": "echo test"}

        # PreToolUse和PostToolUse需要matcher
        tool_event_types = [HookEventType.PRE_TOOL_USE.value, HookEventType.POST_TOOL_USE.value]

        for event_type in tool_event_types:
            # 没有matcher应该失败
            with pytest.raises((ValueError, HookValidationError)):
                HookConfiguration(
                    **base_config,
                    event_type=event_type
                )

            # 有matcher应该成功
            hook_with_matcher = HookConfiguration(
                **base_config,
                event_type=event_type,
                matcher="Write"
            )
            assert hook_with_matcher.matcher == "Write"
            assert hook_with_matcher.event_type == event_type

    def test_matcher_optional_for_non_tool_hooks(self):
        """matcher字段对其他事件类型是可选的"""
        base_config = {"type": "command", "command": "echo test"}

        # 其他事件类型不需要matcher
        other_event_types = [
            HookEventType.NOTIFICATION.value,
            HookEventType.USER_PROMPT_SUBMIT.value,
            HookEventType.STOP.value,
            HookEventType.SUBAGENT_STOP.value,
            HookEventType.PRE_COMPACT.value,
            HookEventType.SESSION_START.value,
            HookEventType.SESSION_END.value
        ]

        for event_type in other_event_types:
            # 没有matcher应该成功
            hook_no_matcher = HookConfiguration(
                **base_config,
                event_type=event_type
            )
            assert hook_no_matcher.event_type == event_type
            assert hook_no_matcher.matcher is None

            # 有matcher也应该成功
            hook_with_matcher = HookConfiguration(
                **base_config,
                event_type=event_type,
                matcher="SomePattern"
            )
            assert hook_with_matcher.matcher == "SomePattern"


class TestHookEventTypes:
    """测试9种Hook事件类型的特定验证规则"""

    def test_all_event_types_supported(self):
        """确保支持所有9种Claude Code事件类型"""
        expected_events = [
            HookEventType.PRE_TOOL_USE.value,
            HookEventType.POST_TOOL_USE.value,
            HookEventType.NOTIFICATION.value,
            HookEventType.USER_PROMPT_SUBMIT.value,
            HookEventType.STOP.value,
            HookEventType.SUBAGENT_STOP.value,
            HookEventType.PRE_COMPACT.value,
            HookEventType.SESSION_START.value,
            HookEventType.SESSION_END.value
        ]

        # 验证所有枚举值都被覆盖
        assert len(expected_events) == 9

        # HookEventType应该包含所有预期事件
        # 这里我们检查类型定义是否包含所有必需的事件
        for event in expected_events:
            # 创建配置测试每个事件类型
            config = {
                "type": "command",
                "command": "echo test",
                "event_type": event
            }

            if event in [HookEventType.PRE_TOOL_USE.value, HookEventType.POST_TOOL_USE.value]:
                config["matcher"] = "TestTool"

            hook = HookConfiguration(**config)
            assert hook.event_type == event

    def test_pre_tool_use_validation(self):
        """PreToolUse特定验证规则"""
        # 必须有matcher
        config = {
            "type": "command",
            "command": "echo 'Pre-tool validation'",
            "event_type": HookEventType.PRE_TOOL_USE.value,
            "matcher": "Write"
        }
        hook = HookConfiguration(**config)
        assert hook.event_type == HookEventType.PRE_TOOL_USE.value
        assert hook.matcher == "Write"

        # 测试常见的工具匹配模式
        valid_matchers = ["Write", "Read", "Bash", "*", "Write|Read"]
        for matcher in valid_matchers:
            config["matcher"] = matcher
            hook = HookConfiguration(**config)
            assert hook.matcher == matcher

    def test_post_tool_use_validation(self):
        """PostToolUse特定验证规则"""
        config = {
            "type": "command",
            "command": "echo 'Post-tool processing'",
            "event_type": HookEventType.POST_TOOL_USE.value,
            "matcher": "Bash"
        }
        hook = HookConfiguration(**config)
        assert hook.event_type == HookEventType.POST_TOOL_USE.value
        assert hook.matcher == "Bash"

    def test_notification_validation(self):
        """Notification事件验证"""
        config = {
            "type": "command",
            "command": "notify-send 'Claude notification'",
            "event_type": HookEventType.NOTIFICATION.value
        }
        hook = HookConfiguration(**config)
        assert hook.event_type == HookEventType.NOTIFICATION.value
        assert hook.matcher is None  # 不需要matcher

    def test_user_prompt_submit_validation(self):
        """UserPromptSubmit事件验证"""
        config = {
            "type": "command",
            "command": "echo 'User submitted prompt'",
            "event_type": HookEventType.USER_PROMPT_SUBMIT.value
        }
        hook = HookConfiguration(**config)
        assert hook.event_type == HookEventType.USER_PROMPT_SUBMIT.value

    def test_stop_events_validation(self):
        """Stop和SubagentStop事件验证"""
        for stop_type in [HookEventType.STOP.value, HookEventType.SUBAGENT_STOP.value]:
            config = {
                "type": "command",
                "command": f"echo 'Handling {stop_type}'",
                "event_type": stop_type
            }
            hook = HookConfiguration(**config)
            assert hook.event_type == stop_type

    def test_session_lifecycle_validation(self):
        """SessionStart和SessionEnd事件验证"""
        for session_event in [HookEventType.SESSION_START.value, HookEventType.SESSION_END.value]:
            config = {
                "type": "command",
                "command": f"echo 'Session {session_event.lower()}'",
                "event_type": session_event
            }
            hook = HookConfiguration(**config)
            assert hook.event_type == session_event

    def test_pre_compact_validation(self):
        """PreCompact事件验证"""
        config = {
            "type": "command",
            "command": "echo 'Before transcript compaction'",
            "event_type": HookEventType.PRE_COMPACT.value
        }
        hook = HookConfiguration(**config)
        assert hook.event_type == HookEventType.PRE_COMPACT.value


class TestValidationResult:
    """测试ValidationResult模型"""

    def test_validation_result_structure(self):
        """测试ValidationResult的基本结构"""
        # 成功的验证结果
        success_result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            suggestions=[]
        )

        assert success_result.is_valid is True
        assert len(success_result.errors) == 0
        assert len(success_result.warnings) == 0
        assert len(success_result.suggestions) == 0

    def test_validation_result_with_errors(self):
        """测试包含错误的ValidationResult"""
        error = ValidationError(
            field_name="command",
            error_code="EMPTY_COMMAND",
            message="命令不能为空",
            suggested_fix="提供一个有效的shell命令"
        )

        result = ValidationResult(
            is_valid=False,
            errors=[error],
            warnings=[],
            suggestions=["考虑使用绝对路径"]
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].field_name == "command"
        assert result.errors[0].error_code == "EMPTY_COMMAND"
        assert len(result.suggestions) == 1

    def test_validation_result_with_warnings(self):
        """测试包含警告的ValidationResult"""
        # 创建验证警告
        warning = {
            "field_name": "command",
            "warning_code": "POTENTIAL_SHELL_INJECTION",
            "message": "命令可能存在shell注入风险"
        }

        result = ValidationResult(
            is_valid=True,  # 有警告但仍然有效
            errors=[],
            warnings=[warning],
            suggestions=["使用参数化命令以避免注入"]
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0]["warning_code"] == "POTENTIAL_SHELL_INJECTION"

    def test_validation_error_structure(self):
        """测试ValidationError的结构"""
        error = ValidationError(
            field_name="timeout",
            error_code="INVALID_TIMEOUT",
            message="超时值必须为正整数",
            suggested_fix="使用大于0的整数值"
        )

        assert error.field_name == "timeout"
        assert error.error_code == "INVALID_TIMEOUT"
        assert error.message == "超时值必须为正整数"
        assert error.suggested_fix == "使用大于0的整数值"


class TestHookValidator:
    """测试HookValidator服务"""

    def test_validator_validate_hook_config(self):
        """测试钩子配置验证"""
        validator = HookValidator()

        # 有效配置
        valid_config = {
            "type": "command",
            "command": "echo 'test'",
            "timeout": 30
        }

        result = validator.validate_hook_config(valid_config, HookEventType.NOTIFICATION.value)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    def test_validator_invalid_config(self):
        """测试无效配置的验证"""
        validator = HookValidator()

        # 无效配置：空命令
        invalid_config = {
            "type": "command",
            "command": "",
            "timeout": 30
        }

        result = validator.validate_hook_config(invalid_config, HookEventType.NOTIFICATION.value)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validator_tool_hooks_need_matcher(self):
        """测试工具钩子需要matcher"""
        validator = HookValidator()

        # PreToolUse没有matcher
        config_no_matcher = {
            "type": "command",
            "command": "echo 'test'"
        }

        result = validator.validate_hook_config(config_no_matcher, HookEventType.PRE_TOOL_USE.value)
        assert result.is_valid is False

        # 查找与matcher相关的错误
        matcher_errors = [e for e in result.errors
                         if "matcher" in e.field_name.lower()]
        assert len(matcher_errors) > 0

    def test_validator_security_warnings(self):
        """测试安全性警告检测"""
        validator = HookValidator()

        # 可能有shell注入风险的命令
        risky_commands = [
            "rm -rf $1",
            "eval $(cat file)",
            "sh -c \"$USER_INPUT\"",
            "echo $USER_DATA > file"
        ]

        for cmd in risky_commands:
            config = {
                "type": "command",
                "command": cmd
            }

            result = validator.validate_hook_config(config, HookEventType.NOTIFICATION.value)
            # 应该有警告但配置仍可能有效
            assert len(result.warnings) > 0


class TestBoundaryConditions:
    """测试边界情况和错误处理"""

    def test_empty_configuration(self):
        """测试空配置"""
        with pytest.raises((ValueError, HookValidationError, TypeError)):
            HookConfiguration({})

    def test_invalid_json_structure(self):
        """测试无效的JSON结构"""
        validator = HookValidator()

        invalid_structures = [
            None,
            "not a dict",
            123,
            [],
            {"wrong": "structure"}
        ]

        for structure in invalid_structures:
            with pytest.raises((ValueError, TypeError)):
                validator.validate_hook_config(structure, HookEventType.NOTIFICATION.value)

    def test_missing_required_fields(self):
        """测试缺失必需字段"""
        incomplete_configs = [
            {"type": "command"},  # 缺少command
            {"command": "echo test"},  # 缺少type
        ]

        for config in incomplete_configs:
            with pytest.raises((ValueError, HookValidationError)):
                HookConfiguration(**config)

    def test_extremely_long_command(self):
        """测试超长命令"""
        # 创建一个非常长的命令
        long_command = "echo " + "a" * 10000

        config = {
            "type": "command",
            "command": long_command
        }

        validator = HookValidator()
        result = validator.validate_hook_config(config, HookEventType.NOTIFICATION.value)

        # 应该有警告关于命令长度
        length_warnings = [w for w in result.warnings
                          if "length" in w.get("message", "").lower()]
        assert len(length_warnings) > 0

    def test_invalid_timeout_values(self):
        """测试各种无效的超时值"""
        base_config = {"type": "command", "command": "echo test"}

        invalid_timeouts = [
            -1, -100,      # 负数
            0,             # 零
            1.5, 2.7,      # 浮点数
            "30", "abc",   # 字符串
            [], {},        # 容器类型
            float('inf'),  # 无穷大
            float('nan'),  # NaN
        ]

        for timeout in invalid_timeouts:
            config = {**base_config, "timeout": timeout}
            with pytest.raises((ValueError, HookValidationError, TypeError)):
                HookConfiguration(**config)

    def test_unicode_and_special_characters(self):
        """测试Unicode和特殊字符处理"""
        special_commands = [
            "echo '你好世界'",  # 中文
            "echo 'café'",     # 重音符
            "echo '🎉'",       # emoji
            "echo 'test\n\t'", # 转义字符
            "echo 'test\"quote'", # 引号
        ]

        for cmd in special_commands:
            config = {
                "type": "command",
                "command": cmd
            }

            # 应该能够处理Unicode字符
            hook = HookConfiguration(**config)
            assert hook.command == cmd

    def test_cross_platform_command_validation(self):
        """测试跨平台命令验证"""
        platform_commands = {
            "linux": ["ls -la", "grep pattern", "find /path"],
            "windows": ["dir", "findstr pattern", "where program"],
            "macos": ["ls -la", "grep pattern", "find /path"]
        }

        validator = HookValidator()

        for platform, commands in platform_commands.items():
            for cmd in commands:
                config = {
                    "type": "command",
                    "command": cmd
                }

                result = validator.validate_hook_config(config, HookEventType.NOTIFICATION.value)
                # 所有平台命令都应该能够验证
                assert isinstance(result, ValidationResult)

    def test_settings_level_integration(self):
        """测试与SettingsLevel的集成"""
        validator = HookValidator()

        config = {
            "type": "command",
            "command": "echo 'test'"
        }

        # 测试所有设置级别
        for level in [SettingsLevel.PROJECT.value, SettingsLevel.USER_GLOBAL.value]:
            # 验证器应该能够处理不同的设置级别
            result = validator.validate_hook_config(
                config, HookEventType.NOTIFICATION.value, settings_level=level
            )
            assert isinstance(result, ValidationResult)

    def test_semantic_validation_with_cchooks_types(self):
        """测试与cchooks库类型的语义验证"""
        # 使用cchooks.types.enums中定义的实际类型进行验证
        validator = HookValidator()

        config = {
            "type": "command",
            "command": "echo 'semantic test'"
        }

        # 测试所有有效的事件类型
        valid_events = [
            HookEventType.PRE_TOOL_USE.value,
            HookEventType.POST_TOOL_USE.value,
            HookEventType.NOTIFICATION.value,
            HookEventType.USER_PROMPT_SUBMIT.value,
            HookEventType.STOP.value,
            HookEventType.SUBAGENT_STOP.value,
            HookEventType.PRE_COMPACT.value,
            HookEventType.SESSION_START.value,
            HookEventType.SESSION_END.value
        ]

        for event in valid_events:
            if event in [HookEventType.PRE_TOOL_USE.value, HookEventType.POST_TOOL_USE.value]:
                test_config = {**config, "matcher": "TestTool"}
            else:
                test_config = config.copy()

            result = validator.validate_hook_config(test_config, event)
            assert isinstance(result, ValidationResult)

    def test_validation_performance(self):
        """测试验证性能（基本性能要求）"""
        import time

        validator = HookValidator()

        config = {
            "type": "command",
            "command": "echo 'performance test'"
        }

        # 验证应该在合理时间内完成（< 100ms）
        start_time = time.time()
        result = validator.validate_hook_config(config, HookEventType.NOTIFICATION.value)
        end_time = time.time()

        validation_time = end_time - start_time
        assert validation_time < 0.1  # 100ms限制
        assert isinstance(result, ValidationResult)


class TestIntegrationWithClaude:
    """测试与Claude Code格式的集成"""

    def test_claude_code_format_compliance(self):
        """测试Claude Code格式合规性"""
        # 这个测试验证我们的配置完全符合Claude Code格式
        validator = HookValidator()

        # 典型的Claude Code钩子配置
        claude_config = {
            "type": "command",
            "command": "python /path/to/script.py",
            "timeout": 60
        }

        result = validator.validate_hook_config(claude_config, HookEventType.PRE_TOOL_USE.value,
                                              matcher="Write")
        assert result.is_valid is True

        # 验证没有格式合规性错误
        format_errors = [e for e in result.errors
                        if "format" in e.message.lower()]
        assert len(format_errors) == 0

    def test_preserve_existing_settings(self):
        """测试保持现有设置不变的能力"""
        # 这个测试确保验证器不会干扰现有的非钩子设置
        validator = HookValidator()

        # 模拟包含其他Claude设置的完整配置
        full_claude_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo 'validation test'"
                            }
                        ]
                    }
                ]
            },
            "other_setting": "should be preserved",
            "ui_preferences": {"theme": "dark"}
        }

        # 验证器应该只关心钩子部分
        hook_config = full_claude_settings["hooks"]["PreToolUse"][0]["hooks"][0]
        result = validator.validate_hook_config(hook_config, HookEventType.PRE_TOOL_USE.value,
                                              matcher="Write")

        assert result.is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])