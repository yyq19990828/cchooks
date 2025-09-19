"""JSON操作工具模块，专门处理Claude Code settings.json文件的解析、格式化和操作。

该模块提供以下核心功能：
1. 安全的JSON解析和生成
2. 格式化保持功能（保留原始缩进和顺序）
3. Claude Code settings.json特定的处理逻辑
4. hooks节点操作（增删改查）
5. 数据验证和错误处理
6. 备份功能集成

关键约束：
- 只能使用Python标准库的json模块
- 必须保持现有JSON格式不变
- 只允许修改"hooks"部分
- 禁止添加、修改或删除其他顶级字段
- Hook对象只能包含：type, command, timeout（可选）
- type字段始终为"command"
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..exceptions import CCHooksError, HookValidationError, ParseError


class SettingsJSONHandler:
    """Claude Code settings.json文件的专门处理器。

    该类遵循Claude Code的严格规范：
    - 只能修改"hooks"部分
    - Hook对象格式固定：{type: "command", command: str, timeout?: int}
    - 保持原有文件格式和非hooks配置不变
    """

    def __init__(self, file_path: Union[str, Path], preserve_formatting: bool = True):
        """初始化处理器。

        Args:
            file_path: settings.json文件路径
            preserve_formatting: 是否保持原有格式（缩进、顺序等）
        """
        self.file_path = Path(file_path)
        self.preserve_formatting = preserve_formatting
        self._original_content: Optional[str] = None
        self._parsed_data: Optional[Dict[str, Any]] = None
        self._indent_size = 2  # Claude Code默认缩进

    def exists(self) -> bool:
        """检查文件是否存在。"""
        return self.file_path.exists()

    def create_backup(self, suffix: Optional[str] = None) -> Path:
        """创建文件备份。

        Args:
            suffix: 备份文件后缀，默认使用时间戳

        Returns:
            备份文件路径

        Raises:
            CCHooksError: 备份创建失败
        """
        if not self.exists():
            raise CCHooksError(f"Cannot backup non-existent file: {self.file_path}")

        if suffix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = f"bak_{timestamp}"

        backup_path = self.file_path.with_suffix(f".{suffix}")

        try:
            shutil.copy2(self.file_path, backup_path)
            return backup_path
        except OSError as e:
            raise CCHooksError(f"Failed to create backup: {e}")

    def load(self, create_if_missing: bool = False) -> Dict[str, Any]:
        """加载并解析JSON文件。

        Args:
            create_if_missing: 如果文件不存在，是否创建空的settings结构

        Returns:
            解析后的JSON数据

        Raises:
            ParseError: JSON解析失败
            CCHooksError: 文件读取失败
        """
        if not self.exists():
            if create_if_missing:
                empty_settings = {"hooks": {}}
                self._parsed_data = empty_settings
                return empty_settings
            else:
                raise CCHooksError(f"Settings file not found: {self.file_path}")

        try:
            self._original_content = self.file_path.read_text(encoding='utf-8')
        except OSError as e:
            raise CCHooksError(f"Failed to read settings file: {e}")

        try:
            self._parsed_data = json.loads(self._original_content)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON in settings file: {e}")

        # 验证基本结构
        if not isinstance(self._parsed_data, dict):
            raise ParseError("Settings file must contain a JSON object")

        # 确保hooks节点存在
        if "hooks" not in self._parsed_data:
            self._parsed_data["hooks"] = {}
        elif not isinstance(self._parsed_data["hooks"], dict):
            raise ParseError("'hooks' section must be a JSON object")

        return self._parsed_data

    def save(self, data: Optional[Dict[str, Any]] = None, create_dirs: bool = True) -> None:
        """保存JSON数据到文件。

        Args:
            data: 要保存的数据，默认使用已加载的数据
            create_dirs: 是否创建不存在的父目录

        Raises:
            CCHooksError: 保存失败
            HookValidationError: 数据验证失败
        """
        if data is None:
            if self._parsed_data is None:
                raise CCHooksError("No data to save. Call load() first or provide data.")
            data = self._parsed_data
        else:
            # 验证提供的数据
            self._validate_settings_structure(data)
            self._parsed_data = data

        # 创建父目录
        if create_dirs:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if self.preserve_formatting and self._original_content:
                # 尝试保持原有格式
                formatted_content = self._preserve_original_formatting(data)
            else:
                # 使用标准格式化
                formatted_content = json.dumps(
                    data,
                    indent=self._indent_size,
                    ensure_ascii=False,
                    separators=(',', ': ')
                )

            self.file_path.write_text(formatted_content, encoding='utf-8')

        except OSError as e:
            raise CCHooksError(f"Failed to save settings file: {e}")

    def get_hooks_for_event(self, event_type: str) -> List[Dict[str, Any]]:
        """获取指定事件类型的所有hooks配置。

        Args:
            event_type: 事件类型 (如 "PreToolUse", "PostToolUse" 等)

        Returns:
            该事件类型下的所有hook配置列表
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        hooks_section = self._parsed_data.get("hooks", {})
        event_configs = hooks_section.get(event_type, [])

        if not isinstance(event_configs, list):
            return []

        # 扁平化所有hooks
        all_hooks = []
        for config in event_configs:
            if isinstance(config, dict) and "hooks" in config:
                hooks_list = config["hooks"]
                if isinstance(hooks_list, list):
                    matcher = config.get("matcher", "")
                    for hook in hooks_list:
                        if isinstance(hook, dict):
                            # 添加matcher信息到hook中（仅用于返回，不保存到文件）
                            hook_with_matcher = hook.copy()
                            hook_with_matcher["_matcher"] = matcher
                            all_hooks.append(hook_with_matcher)

        return all_hooks

    def add_hook(self, event_type: str, command: str, matcher: str = "",
                 timeout: Optional[int] = None) -> None:
        """添加新的hook配置。

        Args:
            event_type: 事件类型
            command: 要执行的命令
            matcher: 工具匹配器模式
            timeout: 超时时间（秒）

        Raises:
            HookValidationError: Hook配置验证失败
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        # 验证hook配置
        hook_config = {"type": "command", "command": command}
        if timeout is not None:
            if not isinstance(timeout, int) or timeout <= 0:
                raise HookValidationError("Timeout must be a positive integer")
            hook_config["timeout"] = timeout

        self._validate_hook_config(hook_config)

        # 确保hooks结构存在
        hooks_section = self._parsed_data.setdefault("hooks", {})
        event_configs = hooks_section.setdefault(event_type, [])

        # 查找是否已存在相同matcher的配置
        target_config = None
        for config in event_configs:
            if isinstance(config, dict) and config.get("matcher") == matcher:
                target_config = config
                break

        # 如果不存在，创建新的matcher配置
        if target_config is None:
            target_config = {"matcher": matcher, "hooks": []}
            event_configs.append(target_config)

        # 添加hook到对应的matcher配置中
        if "hooks" not in target_config:
            target_config["hooks"] = []
        target_config["hooks"].append(hook_config)

    def remove_hook(self, event_type: str, command: str, matcher: str = "") -> bool:
        """移除指定的hook配置。

        Args:
            event_type: 事件类型
            command: 命令内容（用于精确匹配）
            matcher: 工具匹配器模式

        Returns:
            是否成功移除了hook
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        hooks_section = self._parsed_data.get("hooks", {})
        event_configs = hooks_section.get(event_type, [])

        for config in event_configs:
            if isinstance(config, dict) and config.get("matcher") == matcher:
                hooks_list = config.get("hooks", [])
                for i, hook in enumerate(hooks_list):
                    if isinstance(hook, dict) and hook.get("command") == command:
                        # 移除找到的hook
                        hooks_list.pop(i)

                        # 如果hooks列表为空，移除整个matcher配置
                        if not hooks_list:
                            event_configs.remove(config)

                        # 如果事件类型下没有配置了，移除整个事件类型
                        if not event_configs:
                            del hooks_section[event_type]

                        return True

        return False

    def update_hook(self, event_type: str, old_command: str, new_command: str,
                   matcher: str = "", timeout: Optional[int] = None) -> bool:
        """更新existing hook配置。

        Args:
            event_type: 事件类型
            old_command: 原命令内容
            new_command: 新命令内容
            matcher: 工具匹配器模式
            timeout: 新的超时时间

        Returns:
            是否成功更新了hook
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        hooks_section = self._parsed_data.get("hooks", {})
        event_configs = hooks_section.get(event_type, [])

        for config in event_configs:
            if isinstance(config, dict) and config.get("matcher") == matcher:
                hooks_list = config.get("hooks", [])
                for hook in hooks_list:
                    if isinstance(hook, dict) and hook.get("command") == old_command:
                        # 验证新的hook配置
                        new_hook_config = {"type": "command", "command": new_command}
                        if timeout is not None:
                            if not isinstance(timeout, int) or timeout <= 0:
                                raise HookValidationError("Timeout must be a positive integer")
                            new_hook_config["timeout"] = timeout
                        elif "timeout" in hook:
                            # 保持原有timeout
                            new_hook_config["timeout"] = hook["timeout"]

                        self._validate_hook_config(new_hook_config)

                        # 更新hook配置
                        hook.clear()
                        hook.update(new_hook_config)
                        return True

        return False

    def list_all_hooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有hook配置。

        Returns:
            按事件类型组织的所有hook配置
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        result = {}
        hooks_section = self._parsed_data.get("hooks", {})

        for event_type in hooks_section:
            hooks_for_event = self.get_hooks_for_event(event_type)
            if hooks_for_event:
                result[event_type] = hooks_for_event

        return result

    def validate_hooks_section(self) -> Tuple[List[str], List[str]]:
        """验证整个hooks section的配置。

        Returns:
            (错误列表, 警告列表)
        """
        if self._parsed_data is None:
            raise CCHooksError("No data loaded. Call load() first.")

        errors = []
        warnings = []

        hooks_section = self._parsed_data.get("hooks", {})
        if not isinstance(hooks_section, dict):
            errors.append("'hooks' section must be a JSON object")
            return errors, warnings

        for event_type, event_configs in hooks_section.items():
            if not isinstance(event_configs, list):
                errors.append(f"Event type '{event_type}' must have a list of configurations")
                continue

            for i, config in enumerate(event_configs):
                if not isinstance(config, dict):
                    errors.append(f"Event '{event_type}' config {i} must be an object")
                    continue

                if "hooks" not in config:
                    errors.append(f"Event '{event_type}' config {i} missing 'hooks' field")
                    continue

                hooks_list = config["hooks"]
                if not isinstance(hooks_list, list):
                    errors.append(f"Event '{event_type}' config {i} 'hooks' must be a list")
                    continue

                matcher = config.get("matcher", "")
                for j, hook in enumerate(hooks_list):
                    try:
                        self._validate_hook_config(hook)
                    except HookValidationError as e:
                        errors.append(f"Event '{event_type}', matcher '{matcher}', hook {j}: {e}")

        return errors, warnings

    def _validate_settings_structure(self, data: Dict[str, Any]) -> None:
        """验证settings.json的整体结构。

        Args:
            data: 要验证的数据

        Raises:
            HookValidationError: 结构验证失败
        """
        if not isinstance(data, dict):
            raise HookValidationError("Settings must be a JSON object")

        if "hooks" in data:
            hooks_section = data["hooks"]
            if not isinstance(hooks_section, dict):
                raise HookValidationError("'hooks' section must be a JSON object")

    def _validate_hook_config(self, hook: Dict[str, Any]) -> None:
        """验证单个hook配置。

        Args:
            hook: Hook配置对象

        Raises:
            HookValidationError: Hook配置验证失败
        """
        if not isinstance(hook, dict):
            raise HookValidationError("Hook configuration must be an object")

        # 验证必需字段
        if "type" not in hook:
            raise HookValidationError("Hook must have 'type' field")
        if hook["type"] != "command":
            raise HookValidationError("Hook type must be 'command'")

        if "command" not in hook:
            raise HookValidationError("Hook must have 'command' field")
        if not isinstance(hook["command"], str) or not hook["command"].strip():
            raise HookValidationError("Hook command must be a non-empty string")

        # 验证可选字段
        if "timeout" in hook:
            timeout = hook["timeout"]
            if not isinstance(timeout, int) or timeout <= 0:
                raise HookValidationError("Hook timeout must be a positive integer")

        # 验证不允许的字段
        allowed_fields = {"type", "command", "timeout"}
        extra_fields = set(hook.keys()) - allowed_fields
        if extra_fields:
            raise HookValidationError(f"Hook contains disallowed fields: {', '.join(extra_fields)}")

    def _preserve_original_formatting(self, data: Dict[str, Any]) -> str:
        """尝试保持原有的JSON格式。

        Args:
            data: 要格式化的数据

        Returns:
            格式化后的JSON字符串
        """
        if not self._original_content:
            # 如果没有原始内容，使用标准格式
            return json.dumps(data, indent=self._indent_size, ensure_ascii=False)

        # 检测原始缩进
        indent_match = re.search(r'\n(\s+)"', self._original_content)
        if indent_match:
            original_indent = len(indent_match.group(1))
            self._indent_size = original_indent

        # 使用检测到的缩进格式化
        return json.dumps(
            data,
            indent=self._indent_size,
            ensure_ascii=False,
            separators=(',', ': ')
        )


# 便捷函数，供外部模块使用

def load_settings_file(file_path: Union[str, Path],
                      create_if_missing: bool = False) -> Tuple[SettingsJSONHandler, Dict[str, Any]]:
    """加载settings.json文件的便捷函数。

    Args:
        file_path: 文件路径
        create_if_missing: 如果文件不存在是否创建

    Returns:
        (处理器实例, 解析后的数据)
    """
    handler = SettingsJSONHandler(file_path)
    data = handler.load(create_if_missing=create_if_missing)
    return handler, data


def save_settings_file(file_path: Union[str, Path], data: Dict[str, Any],
                      create_backup: bool = True) -> Optional[Path]:
    """保存settings.json文件的便捷函数。

    Args:
        file_path: 文件路径
        data: 要保存的数据
        create_backup: 是否创建备份

    Returns:
        备份文件路径（如果创建了备份）
    """
    handler = SettingsJSONHandler(file_path)
    backup_path = None

    if create_backup and handler.exists():
        backup_path = handler.create_backup()

    handler.save(data)
    return backup_path


def validate_hook_configuration(hook: Dict[str, Any]) -> None:
    """验证单个hook配置的便捷函数。

    Args:
        hook: Hook配置对象

    Raises:
        HookValidationError: 配置验证失败
    """
    # 创建临时处理器进行验证
    temp_handler = SettingsJSONHandler("/tmp/temp")
    temp_handler._validate_hook_config(hook)


def create_empty_settings() -> Dict[str, Any]:
    """创建空的settings.json结构。

    Returns:
        空的settings结构
    """
    return {"hooks": {}}
