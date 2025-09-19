#!/usr/bin/env python3
"""
TemplateValidator使用示例

演示如何使用TemplateValidator验证模板类、配置、生成的脚本、
依赖项和自定义schema。
"""

import sys
import os
from pathlib import Path

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cchooks.templates.validator import TemplateValidator, TemplateValidationError
from cchooks.models.validation import ValidationResult


def example_template_class_validation():
    """示例：模板类验证"""
    print("=== 模板类验证示例 ===")

    # 创建验证器实例
    validator = TemplateValidator(enable_caching=True)

    # 定义一个完整的模板类
    class SecurityGuardTemplate:
        """安全守卫模板 - 在工具执行前进行安全检查"""

        # 必需的属性
        name = "Security Guard"
        description = "Validates tool calls for security compliance before execution"
        version = "1.2.0"
        supported_events = ["PreToolUse"]

        def generate_hook(self, config):
            """生成钩子脚本"""
            security_level = config.get('security_level', 'medium')
            blocked_tools = config.get('blocked_tools', [])

            script = f'''
from cchooks import create_context
import json

def main():
    context = create_context()

    # 获取工具信息
    tool_name = context.tool_input.get("name", "unknown")

    # 安全级别配置
    security_level = "{security_level}"
    blocked_tools = {blocked_tools}

    # 安全检查
    if tool_name in blocked_tools:
        context.output.deny(f"工具 {{tool_name}} 被安全策略阻止")
        return

    if security_level == "high" and tool_name in ["Bash", "Write"]:
        context.output.ask(f"高安全级别模式: 确定要使用 {{tool_name}} 工具吗?")
        return

    # 通过验证
    context.output.allow("安全检查通过")

if __name__ == "__main__":
    main()
'''
            return script.strip()

        def get_default_config(self):
            """获取默认配置"""
            return {
                "security_level": "medium",
                "blocked_tools": [],
                "log_decisions": True
            }

        def validate_config(self, config):
            """验证配置"""
            valid_levels = ["low", "medium", "high"]
            if "security_level" in config:
                if config["security_level"] not in valid_levels:
                    return [f"Invalid security_level. Must be one of: {valid_levels}"]

            if "blocked_tools" in config:
                if not isinstance(config["blocked_tools"], list):
                    return ["blocked_tools must be a list"]

            return True

        def get_config_schema(self):
            """获取配置schema"""
            return {
                "type": "object",
                "properties": {
                    "security_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "medium",
                        "description": "Security check strictness level"
                    },
                    "blocked_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                        "description": "List of tools to always block"
                    },
                    "log_decisions": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to log security decisions"
                    }
                },
                "required": ["security_level"],
                "description": "Security guard template configuration"
            }

    # 验证模板类
    print("验证完整的模板类...")
    result = validator.validate_template_class(SecurityGuardTemplate)
    print_validation_result(result)

    # 验证配置
    print("\n验证模板配置...")
    template = SecurityGuardTemplate()
    config = {
        "security_level": "high",
        "blocked_tools": ["Bash", "Write"],
        "log_decisions": True
    }
    result = validator.validate_template_config(template, config)
    print_validation_result(result)

    # 验证生成的脚本
    print("\n验证生成的脚本...")
    script = template.generate_hook(config)
    result = validator.validate_generated_script(script, "security-guard")
    print_validation_result(result)

    # 验证配置schema
    print("\n验证配置schema...")
    schema = template.get_config_schema()
    result = validator.validate_customization_schema(schema)
    print_validation_result(result)


def example_dependency_validation():
    """示例：依赖项验证"""
    print("\n=== 依赖项验证示例 ===")

    validator = TemplateValidator()

    # 定义复杂的依赖项
    dependencies = {
        "python_packages": {
            "requests": ">=2.25.0",
            "pyyaml": ">=5.4.0",
            "jsonschema": ">=3.2.0"
        },
        "system_tools": {
            "git": {
                "version_command": "git --version",
                "description": "Version control system"
            },
            "curl": {
                "version_command": "curl --version",
                "description": "HTTP client tool"
            }
        },
        "optional": {
            "rich": {
                "type": "python_package",
                "description": "Enhanced terminal output"
            },
            "jq": {
                "type": "system_tool",
                "description": "JSON processor"
            }
        },
        "platform_specific": {
            "linux": {
                "system_tools": {
                    "systemctl": {
                        "description": "Systemd service manager"
                    }
                }
            },
            "windows": {
                "system_tools": {
                    "powershell": {
                        "version_command": "powershell -Command '$PSVersionTable.PSVersion'"
                    }
                }
            }
        }
    }

    print("验证复杂的依赖项配置...")
    result = validator.validate_dependencies(dependencies)
    print_validation_result(result)


def example_advanced_script_validation():
    """示例：高级脚本验证"""
    print("\n=== 高级脚本验证示例 ===")

    validator = TemplateValidator()

    # 创建一个复杂但安全的脚本
    advanced_script = '''
#!/usr/bin/env python3
"""
Git提交钩子 - 在工具执行后自动提交更改
"""

import json
import subprocess
import sys
import logging
from pathlib import Path
from cchooks import create_context

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_git_status():
    """获取Git状态"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        logger.error("Git状态检查超时")
        return None
    except Exception as e:
        logger.error(f"获取Git状态失败: {e}")
        return None

def create_commit_message(tool_name, file_changes):
    """创建提交消息"""
    if not file_changes:
        return f"chore: 使用{tool_name}工具进行更改"

    # 分析文件更改
    added_files = [line[3:] for line in file_changes if line.startswith('A  ')]
    modified_files = [line[3:] for line in file_changes if line.startswith('M  ')]
    deleted_files = [line[3:] for line in file_changes if line.startswith('D  ')]

    parts = []
    if added_files:
        parts.append(f"添加了{len(added_files)}个文件")
    if modified_files:
        parts.append(f"修改了{len(modified_files)}个文件")
    if deleted_files:
        parts.append(f"删除了{len(deleted_files)}个文件")

    summary = ", ".join(parts) if parts else "进行了文件更改"
    return f"feat: 使用{tool_name}工具{summary}"

def main():
    """主函数"""
    try:
        context = create_context()

        # 获取工具执行结果
        tool_name = context.tool_input.get("name", "unknown")
        tool_success = getattr(context.tool_response, 'success', False)

        # 只在工具成功执行后处理
        if not tool_success:
            logger.info("工具执行失败，跳过Git提交")
            context.output.continue_flow("工具执行失败，跳过提交")
            return

        # 检查Git状态
        git_status = get_git_status()
        if not git_status:
            logger.info("没有Git更改或不在Git仓库中")
            context.output.continue_flow("没有需要提交的更改")
            return

        # 解析更改
        changes = git_status.split('\\n')
        logger.info(f"发现{len(changes)}个文件更改")

        # 创建提交消息
        commit_msg = create_commit_message(tool_name, changes)

        # 添加所有更改到暂存区
        subprocess.run(["git", "add", "."], check=True, timeout=30)

        # 创建提交
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True,
            timeout=30
        )

        logger.info(f"成功创建提交: {commit_msg}")
        context.output.continue_flow(f"已自动创建Git提交: {commit_msg}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Git命令执行失败: {e}")
        context.output.continue_flow("Git提交失败，但继续执行")
    except subprocess.TimeoutExpired:
        logger.error("Git命令执行超时")
        context.output.continue_flow("Git提交超时，但继续执行")
    except Exception as e:
        logger.error(f"意外错误: {e}")
        context.output.continue_flow("自动提交过程中出错，但继续执行")

if __name__ == "__main__":
    main()
'''

    print("验证高级脚本...")
    result = validator.validate_generated_script(advanced_script, "git-auto-commit")
    print_validation_result(result)


def print_validation_result(result: ValidationResult):
    """打印验证结果"""
    status = "✅ 通过" if result.is_valid else "❌ 失败"
    print(f"验证结果: {status}")

    if result.errors:
        print(f"  错误 ({len(result.errors)}):")
        for error in result.errors[:3]:  # 只显示前3个错误
            message = error.message if hasattr(error, 'message') else str(error)
            print(f"    • {message}")
        if len(result.errors) > 3:
            print(f"    ... 还有 {len(result.errors) - 3} 个错误")

    if result.warnings:
        print(f"  警告 ({len(result.warnings)}):")
        for warning in result.warnings[:3]:  # 只显示前3个警告
            message = warning.message if hasattr(warning, 'message') else str(warning)
            print(f"    • {message}")
        if len(result.warnings) > 3:
            print(f"    ... 还有 {len(result.warnings) - 3} 个警告")

    if result.suggestions:
        print(f"  建议 ({len(result.suggestions)}):")
        for suggestion in result.suggestions[:3]:  # 只显示前3个建议
            print(f"    • {suggestion}")
        if len(result.suggestions) > 3:
            print(f"    ... 还有 {len(result.suggestions) - 3} 个建议")


def example_caching_performance():
    """示例：缓存性能测试"""
    print("\n=== 缓存性能示例 ===")

    import time

    # 创建测试数据
    class TestTemplate:
        name = "Test"
        description = "Test template"
        version = "1.0"
        supported_events = ["PreToolUse"]

        def generate_hook(self, config):
            return "print('test')"

        def get_default_config(self):
            return {}

        def validate_config(self, config):
            return True

    # 测试缓存性能
    print("测试缓存性能...")

    # 启用缓存的验证器
    validator_cached = TemplateValidator(enable_caching=True, cache_ttl=60)

    # 第一次验证（缓存miss）
    start_time = time.time()
    result1 = validator_cached.validate_template_class(TestTemplate)
    first_time = time.time() - start_time

    # 第二次验证（缓存hit）
    start_time = time.time()
    result2 = validator_cached.validate_template_class(TestTemplate)
    second_time = time.time() - start_time

    print(f"  第一次验证（缓存miss）: {first_time:.4f}秒")
    print(f"  第二次验证（缓存hit）: {second_time:.4f}秒")
    print(f"  性能提升: {(first_time / second_time):.1f}x")

    # 清除缓存
    cleared = validator_cached.clear_cache()
    print(f"  清除了 {cleared} 个缓存条目")


if __name__ == "__main__":
    print("TemplateValidator 高级使用示例")
    print("=" * 50)

    try:
        example_template_class_validation()
        example_dependency_validation()
        example_advanced_script_validation()
        example_caching_performance()

        print("\n" + "=" * 50)
        print("所有示例运行完成！")

    except Exception as e:
        print(f"\n示例运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)