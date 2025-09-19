# TemplateValidator 使用指南

TemplateValidator 是 cchooks 模板系统的核心验证组件，为模板开发提供全面的质量保证和安全检查。

## 概览

TemplateValidator 提供以下功能：

- **模板类完整性验证** - 检查模板类实现的完整性
- **配置参数验证** - 验证模板配置的有效性和安全性
- **生成脚本验证** - 检查生成脚本的语法、安全性和最佳实践
- **依赖项管理** - 验证 Python 包和系统工具的可用性
- **Schema 验证** - 验证自定义配置 schema 的正确性
- **性能优化** - 支持结果缓存和快速验证

## 快速开始

### 基本使用

```python
from cchooks.templates import TemplateValidator

# 创建验证器实例
validator = TemplateValidator()

# 验证模板类
result = validator.validate_template_class(MyTemplateClass)
if result.is_valid:
    print("模板类验证通过!")
else:
    print("验证失败:", result.errors)
```

### 启用缓存

```python
# 启用缓存以提高性能
validator = TemplateValidator(
    enable_caching=True,
    cache_ttl=300  # 缓存有效期5分钟
)
```

## 详细功能说明

### 1. 模板类验证 (`validate_template_class`)

验证模板类是否实现了所有必需的方法和属性。

#### 必需的方法
- `generate_hook(config)` - 生成钩子脚本
- `get_default_config()` - 获取默认配置
- `validate_config(config)` - 验证配置参数

#### 必需的属性
- `name` - 模板名称
- `description` - 模板描述
- `version` - 模板版本
- `supported_events` - 支持的钩子事件类型

#### 示例

```python
class SecurityTemplate:
    name = "Security Guard"
    description = "Pre-tool security validation"
    version = "1.0.0"
    supported_events = ["PreToolUse"]

    def generate_hook(self, config):
        return """
from cchooks import create_context

def main():
    context = create_context()
    # 安全检查逻辑
    context.output.allow("通过安全检查")
"""

    def get_default_config(self):
        return {"security_level": "medium"}

    def validate_config(self, config):
        return True

# 验证模板类
result = validator.validate_template_class(SecurityTemplate)
```

### 2. 配置验证 (`validate_template_config`)

验证模板配置的类型、安全性和完整性。

#### 验证内容
- 配置键的有效性
- 数据类型检查
- 安全敏感信息检测
- 必需参数检查
- 默认值合理性

#### 示例

```python
template = SecurityTemplate()
config = {
    "security_level": "high",
    "blocked_tools": ["Bash"],
    "log_decisions": True
}

result = validator.validate_template_config(template, config)
```

### 3. 生成脚本验证 (`validate_generated_script`)

验证模板生成的 Python 脚本的质量和安全性。

#### 验证内容
- **语法检查** - Python 语法正确性
- **安全验证** - 检测危险模式和安全风险
- **cchooks 集成** - 验证与 cchooks 库的正确集成
- **平台兼容性** - 跨平台兼容性检查
- **性能考虑** - 识别潜在的性能问题

#### 安全检查模式

TemplateValidator 会检测以下危险模式：

```python
# 危险的代码模式
dangerous_patterns = [
    r'exec\s*\(',           # exec() 调用
    r'eval\s*\(',           # eval() 调用
    r'__import__\s*\(',     # 动态导入
    r'os\.system\s*\(',     # 系统调用
    r'subprocess\..*shell\s*=\s*True',  # shell 注入
    # ... 更多模式
]
```

#### 示例

```python
script = '''
from cchooks import create_context
import logging

def main():
    context = create_context()
    logging.info("Script started")
    context.output.allow("Script executed")

if __name__ == "__main__":
    main()
'''

result = validator.validate_generated_script(script, "my-template")
```

### 4. 依赖项验证 (`validate_dependencies`)

检查模板的依赖项可用性和版本兼容性。

#### 支持的依赖类型
- **Python 包** - 通过 importlib 检查
- **系统工具** - 通过 PATH 检查
- **可选依赖** - 非必需的依赖项
- **平台特定依赖** - 根据操作系统的依赖

#### 依赖配置格式

```python
dependencies = {
    "python_packages": {
        "requests": ">=2.25.0",
        "pyyaml": ">=5.4.0"
    },
    "system_tools": {
        "git": {
            "version_command": "git --version",
            "description": "版本控制系统"
        }
    },
    "optional": {
        "rich": {
            "type": "python_package",
            "description": "增强终端输出"
        }
    },
    "platform_specific": {
        "linux": {
            "system_tools": {
                "systemctl": {"description": "系统服务管理"}
            }
        },
        "windows": {
            "system_tools": {
                "powershell": {"version_command": "powershell -V"}
            }
        }
    }
}
```

#### 示例

```python
result = validator.validate_dependencies(dependencies)
if not result.is_valid:
    print("缺失依赖:")
    for error in result.errors:
        print(f"  - {error.message}")
```

### 5. Schema 验证 (`validate_customization_schema`)

验证 JSON Schema 定义的正确性和最佳实践。

#### 验证内容
- Schema 结构完整性
- 属性类型定义
- 约束条件合理性
- 默认值有效性
- 最佳实践建议

#### 示例 Schema

```python
schema = {
    "type": "object",
    "description": "安全模板配置",
    "properties": {
        "security_level": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "default": "medium",
            "description": "安全检查严格程度"
        },
        "blocked_tools": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": "禁用的工具列表"
        },
        "max_file_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1048576,  # 1MB
            "default": 10240,    # 10KB
            "description": "文件大小限制(字节)"
        }
    },
    "required": ["security_level"],
    "examples": [
        {
            "security_level": "high",
            "blocked_tools": ["Bash", "Write"]
        }
    ]
}

result = validator.validate_customization_schema(schema)
```

## 验证结果处理

### ValidationResult 类

所有验证方法都返回 `ValidationResult` 对象，包含：

```python
class ValidationResult:
    is_valid: bool                    # 整体验证结果
    errors: List[ValidationError]     # 错误列表
    warnings: List[ValidationWarning] # 警告列表
    suggestions: List[str]            # 改进建议
```

### 错误和警告处理

```python
def handle_validation_result(result: ValidationResult):
    if result.is_valid:
        print("✅ 验证通过")
    else:
        print("❌ 验证失败")

    # 处理错误
    for error in result.errors:
        print(f"错误 [{error.error_code}]: {error.message}")
        if error.suggested_fix:
            print(f"  建议修复: {error.suggested_fix}")

    # 处理警告
    for warning in result.warnings:
        print(f"警告 [{warning.warning_code}]: {warning.message}")

    # 处理建议
    for suggestion in result.suggestions:
        print(f"建议: {suggestion}")
```

## 性能优化

### 缓存机制

TemplateValidator 支持结果缓存以提高重复验证的性能：

```python
# 启用缓存
validator = TemplateValidator(
    enable_caching=True,
    cache_ttl=300  # 5分钟缓存
)

# 清除缓存
cleared_count = validator.clear_cache()
```

### 快速失败

验证器采用快速失败策略，在遇到严重错误时立即停止，避免不必要的计算。

## 错误码参考

### 模板类验证错误码

- `NOT_A_CLASS` - 提供的对象不是类
- `MISSING_METHOD` - 缺少必需方法
- `METHOD_NOT_CALLABLE` - 方法不可调用
- `MISSING_PROPERTY` - 缺少必需属性

### 配置验证错误码

- `EMPTY_CONFIGURATION` - 配置为空
- `MISSING_REQUIRED_CONFIG` - 缺少必需配置项
- `TEMPLATE_VALIDATION_FAILED` - 模板自定义验证失败

### 脚本验证错误码

- `EMPTY_SCRIPT` - 脚本内容为空
- `SYNTAX_ERROR` - Python 语法错误
- `PARSING_ERROR` - 脚本解析错误

### 依赖项验证错误码

- `MISSING_PYTHON_PACKAGE` - Python 包不可用
- `MISSING_SYSTEM_TOOL` - 系统工具不可用

### Schema 验证错误码

- `INVALID_SCHEMA_TYPE` - Schema 类型无效
- `MISSING_SCHEMA_FIELD` - 缺少必需的 Schema 字段
- `INVALID_PROPERTY_TYPE` - 属性类型无效

## 最佳实践

### 1. 模板开发

```python
class MyTemplate(BaseTemplate):
    """遵循最佳实践的模板实现"""

    # 完整的元数据
    name = "My Template"
    description = "详细的模板描述，说明用途和功能"
    version = "1.0.0"
    supported_events = ["PreToolUse", "PostToolUse"]

    # 可选：模板元数据
    __template_metadata__ = {
        "author": "Your Name",
        "tags": ["security", "automation"],
        "min_cchooks_version": "1.0.0"
    }

    def generate_hook(self, config):
        """生成高质量的钩子脚本"""
        return '''
#!/usr/bin/env python3
"""
模板生成的钩子脚本
"""
from cchooks import create_context
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    try:
        context = create_context()
        logger.info("钩子脚本开始执行")

        # 实现钩子逻辑
        context.output.allow("钩子执行成功")

    except Exception as e:
        logger.error(f"钩子执行出错: {e}")
        context.output.deny("钩子执行失败")

if __name__ == "__main__":
    main()
'''
```

### 2. 依赖管理

```python
# 明确声明所有依赖
def get_dependencies(self):
    return {
        "python_packages": {
            "requests": ">=2.25.0",  # 明确版本要求
        },
        "system_tools": {
            "git": {
                "version_command": "git --version",
                "description": "Git 版本控制系统"
            }
        },
        "optional": {
            "colorama": {
                "type": "python_package",
                "description": "彩色终端输出（可选）"
            }
        }
    }
```

### 3. 配置验证

```python
def validate_config(self, config):
    """实现严格的配置验证"""
    errors = []

    # 类型检查
    if "timeout" in config:
        if not isinstance(config["timeout"], int):
            errors.append("timeout 必须为整数")
        elif config["timeout"] <= 0:
            errors.append("timeout 必须大于 0")

    # 业务逻辑验证
    if config.get("enable_notifications", False):
        if not config.get("notification_url"):
            errors.append("启用通知时必须提供 notification_url")

    return errors if errors else True
```

### 4. 错误处理

```python
# 在生成的脚本中包含适当的错误处理
def generate_hook(self, config):
    return '''
def main():
    try:
        context = create_context()

        # 主要逻辑
        result = perform_operation()

        if result.success:
            context.output.allow(result.message)
        else:
            context.output.deny(result.error)

    except CCHooksError as e:
        # cchooks 特定错误
        logger.error(f"CCHooks 错误: {e}")
        context.output.deny(str(e))
    except Exception as e:
        # 通用错误处理
        logger.error(f"未预期错误: {e}", exc_info=True)
        context.output.deny("内部错误")
'''
```

## 集成示例

### 在模板开发流程中集成验证

```python
def develop_and_validate_template():
    """模板开发和验证的完整流程"""
    validator = TemplateValidator(enable_caching=True)

    # 1. 验证模板类
    class_result = validator.validate_template_class(MyTemplate)
    if not class_result.is_valid:
        print("模板类验证失败，请修复错误后继续")
        return False

    # 2. 验证默认配置
    template = MyTemplate()
    default_config = template.get_default_config()
    config_result = validator.validate_template_config(template, default_config)

    # 3. 验证生成的脚本
    script = template.generate_hook(default_config)
    script_result = validator.validate_generated_script(script, "my-template")

    # 4. 验证依赖项
    deps = template.get_dependencies()
    deps_result = validator.validate_dependencies(deps)

    # 5. 验证配置 Schema
    schema = template.get_config_schema()
    schema_result = validator.validate_customization_schema(schema)

    # 汇总结果
    all_results = [class_result, config_result, script_result, deps_result, schema_result]
    all_valid = all(r.is_valid for r in all_results)

    print(f"模板验证完成: {'通过' if all_valid else '失败'}")
    return all_valid
```

这个完整的 TemplateValidator 系统为 cchooks 模板系统提供了可靠的质量保证，确保模板的安全性、正确性和最佳实践合规性。