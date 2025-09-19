"""Settings文件操作API - T019实现

这个模块实现高级API层，协调SettingsManager和HookValidator服务，
为CLI命令提供统一的设置文件操作接口。

主要功能：
1. 高级API函数：创建、查找、加载设置文件
2. Hook管理操作：添加、更新、删除、列表查询
3. 级别管理逻辑：处理project/user级别的优先级
4. 事务性操作：原子性hook操作和自动备份
5. CLI友好接口：支持dry-run模式和详细日志

依赖服务：
- SettingsManager: 文件操作和数据管理
- HookValidator: Hook配置验证
- SettingsFile: 设置文件数据模型
- HookConfiguration: Hook配置数据模型
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..exceptions import CCHooksError
from ..models.hook_config import HookConfiguration
from ..models.settings_file import SettingsFile, SettingsFileState
from ..models.validation import ModificationResult as BaseModificationResult
from ..models.validation import ValidationError, ValidationResult
from ..types.enums import HookEventType, SettingsLevel
from ..utils.file_operations import (
    discover_settings_files,
    find_project_root,
    get_home_directory,
    get_settings_file_path,
    validate_path_security,
)
from ..utils.json_handler import SettingsJSONHandler

# 为了T019任务的独立性，我们创建轻量级的服务类
# 这些将在T017/T018完成后被替换为完整实现

class _SimpleSettingsManager:
    """轻量级SettingsManager实现，用于T019独立开发"""

    def load_settings_file(self, path: Path) -> SettingsFile:
        """加载设置文件"""
        # 确定级别
        level = self._determine_level(path)
        settings_file = SettingsFile(path=path, level=level)

        if path.exists():
            settings_file.load()

        return settings_file

    def save_settings_file(self, settings_file: SettingsFile, create_backup: bool = True) -> Optional[Path]:
        """保存设置文件"""
        return settings_file.save(create_backup=create_backup)

    def _determine_level(self, path: Path) -> SettingsLevel:
        """确定设置文件级别"""
        path_str = str(path.resolve())
        home_str = str(get_home_directory().resolve())

        if path_str.startswith(home_str) and '.claude' in path_str:
            return SettingsLevel.USER_GLOBAL
        else:
            return SettingsLevel.PROJECT


class _SimpleHookValidator:
    """轻量级HookValidator实现，用于T019独立开发"""

    def validate_hook(self, hook_config: HookConfiguration) -> ValidationResult:
        """验证单个hook配置"""
        return hook_config.validate()

    def validate_hooks(self, hook_configs: List[HookConfiguration]) -> ValidationResult:
        """验证多个hook配置"""
        overall_result = ValidationResult(is_valid=True)

        for hook in hook_configs:
            result = self.validate_hook(hook)
            overall_result.merge(result)

        return overall_result


@dataclass
class SettingsModificationResult:
    """Settings Hook修改操作的结果（扩展基础ModificationResult）"""
    success: bool
    message: str
    affected_files: List[Path] = field(default_factory=list)
    backup_files: List[Path] = field(default_factory=list)
    validation_result: Optional[ValidationResult] = None
    hooks_modified: int = 0
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式供CLI使用"""
        result = {
            "success": self.success,
            "message": self.message,
            "affected_files": [str(p) for p in self.affected_files],
            "backup_files": [str(p) for p in self.backup_files],
            "hooks_modified": self.hooks_modified,
            "dry_run": self.dry_run
        }

        if self.validation_result:
            result["validation"] = self.validation_result.to_dict()

        return result


# 全局服务实例 - 在T017/T018完成后替换为真实实现
_settings_manager = _SimpleSettingsManager()
_hook_validator = _SimpleHookValidator()


# 主API函数

def create_new_settings_file(path: Union[str, Path], level: SettingsLevel) -> SettingsFile:
    """创建新的设置文件

    Args:
        path: 设置文件路径
        level: 设置级别（project或user）

    Returns:
        创建的SettingsFile对象

    Raises:
        CCHooksError: 如果创建失败
        SecurityError: 如果路径不安全
    """
    logger = logging.getLogger(__name__)

    # 验证路径安全性
    safe_path = validate_path_security(path)

    logger.info(f"创建新设置文件: {safe_path} (级别: {level.value})")

    # 创建SettingsFile对象
    settings_file = SettingsFile(path=safe_path, level=level)

    # 初始化基本结构
    settings_file.content = {
        "hooks": {},
        "metadata": {
            "created": datetime.now().isoformat(),
            "version": "1.0"
        }
    }
    settings_file.state = SettingsFileState.MODIFIED

    # 确保父目录存在
    safe_path.parent.mkdir(parents=True, exist_ok=True)

    # 保存文件
    _settings_manager.save_settings_file(settings_file, create_backup=False)

    logger.info(f"成功创建设置文件: {safe_path}")
    return settings_file


def find_and_load_settings(level: Optional[str] = None) -> List[SettingsFile]:
    """查找并加载设置文件

    Args:
        level: 设置级别过滤器 ("project", "user", "all", None)
               None表示按优先级返回找到的第一个文件

    Returns:
        找到的设置文件列表，按优先级排序（project > user）
    """
    logger = logging.getLogger(__name__)
    logger.info(f"查找设置文件，级别过滤器: {level}")

    settings_files = []

    # 使用discover_settings_files查找所有设置文件
    try:
        discovered_files = discover_settings_files()

        for file_level, file_path in discovered_files:
            # 映射文件级别到我们的级别系统
            mapped_level = None
            if file_level in ["project", "project-local"] and level in [None, "project", "all"]:
                mapped_level = SettingsLevel.PROJECT
            elif file_level == "user" and level in [None, "user", "all"]:
                mapped_level = SettingsLevel.USER_GLOBAL

            if mapped_level:
                try:
                    settings_file = _settings_manager.load_settings_file(file_path)
                    settings_files.append(settings_file)
                    logger.debug(f"找到{mapped_level.value}设置文件: {file_path}")
                except Exception as e:
                    logger.warning(f"加载设置文件 {file_path} 时出错: {e}")

    except Exception as e:
        logger.warning(f"查找设置文件时出错: {e}")

    # 如果level为None，只返回优先级最高的文件
    if level is None and settings_files:
        return [settings_files[0]]  # project优先级更高

    logger.info(f"找到 {len(settings_files)} 个设置文件")
    return settings_files


def add_hook_to_settings(
    level: str,
    hook_config: Dict[str, Any],
    matcher: Optional[str] = None,
    event_type: Optional[str] = None,
    dry_run: bool = False
) -> SettingsModificationResult:
    """向设置文件添加Hook配置

    Args:
        level: 目标级别 ("project" 或 "user")
        hook_config: Hook配置字典
        matcher: 工具匹配器（用于PreToolUse/PostToolUse）
        event_type: Hook事件类型
        dry_run: 是否为预览模式

    Returns:
        修改操作结果
    """
    logger = logging.getLogger(__name__)
    logger.info(f"添加Hook到设置文件，级别: {level}, 事件类型: {event_type}, dry_run: {dry_run}")

    try:
        # 验证级别
        try:
            settings_level = SettingsLevel.from_string(level)
        except ValueError as e:
            return SettingsModificationResult(
                success=False,
                message=f"无效的设置级别: {level}",
                dry_run=dry_run
            )

        # 验证事件类型
        hook_event_type = None
        if event_type:
            try:
                hook_event_type = HookEventType.from_string(event_type)
            except ValueError:
                return SettingsModificationResult(
                    success=False,
                    message=f"无效的Hook事件类型: {event_type}",
                    dry_run=dry_run
                )

        # 创建Hook配置对象进行验证
        try:
            hook = HookConfiguration.from_dict(
                hook_config,
                event_type=hook_event_type,
                matcher=matcher
            )
        except (ValueError, TypeError) as e:
            return SettingsModificationResult(
                success=False,
                message=f"Hook配置无效: {e}",
                dry_run=dry_run
            )

        # 验证Hook配置
        validation_result = _hook_validator.validate_hook(hook)
        if not validation_result.is_valid:
            return SettingsModificationResult(
                success=False,
                message="Hook配置验证失败",
                validation_result=validation_result,
                dry_run=dry_run
            )

        # 查找或创建目标设置文件
        settings_files = find_and_load_settings(level)
        target_file = None

        if settings_files:
            target_file = settings_files[0]
        else:
            # 创建新文件
            if settings_level == SettingsLevel.PROJECT:
                project_root = find_project_root()
                if project_root:
                    target_path = project_root / ".claude" / "settings.json"
                else:
                    target_path = Path.cwd() / ".claude" / "settings.json"
            else:
                target_path = get_home_directory() / ".claude" / "settings.json"

            target_file = create_new_settings_file(target_path, settings_level)

        if dry_run:
            return SettingsModificationResult(
                success=True,
                message=f"预览：将添加Hook到 {target_file.path}",
                affected_files=[target_file.path],
                hooks_modified=1,
                validation_result=validation_result,
                dry_run=True
            )

        # 添加Hook到设置文件
        _add_hook_to_settings_file(target_file, hook, hook_event_type, matcher)

        # 保存文件
        backup_path = _settings_manager.save_settings_file(target_file, create_backup=True)

        result = SettingsModificationResult(
            success=True,
            message=f"成功添加Hook到 {target_file.path}",
            affected_files=[target_file.path],
            hooks_modified=1,
            validation_result=validation_result
        )

        if backup_path:
            result.backup_files = [backup_path]

        logger.info(f"成功添加Hook: {hook}")
        return result

    except Exception as e:
        logger.error(f"添加Hook时出错: {e}")
        return SettingsModificationResult(
            success=False,
            message=f"添加Hook失败: {e}",
            dry_run=dry_run
        )


def update_hook_in_settings(
    level: str,
    event_type: str,
    index: int,
    updates: Dict[str, Any],
    dry_run: bool = False
) -> SettingsModificationResult:
    """更新设置文件中的Hook配置

    Args:
        level: 设置级别
        event_type: Hook事件类型
        index: Hook在列表中的索引
        updates: 要更新的字段
        dry_run: 是否为预览模式

    Returns:
        修改操作结果
    """
    logger = logging.getLogger(__name__)
    logger.info(f"更新Hook，级别: {level}, 事件: {event_type}, 索引: {index}, dry_run: {dry_run}")

    try:
        # 查找设置文件
        settings_files = find_and_load_settings(level)
        if not settings_files:
            return SettingsModificationResult(
                success=False,
                message=f"未找到级别为 {level} 的设置文件",
                dry_run=dry_run
            )

        target_file = settings_files[0]

        # 找到要更新的Hook
        hooks_section = target_file.get_hooks_section()
        if event_type not in hooks_section:
            return SettingsModificationResult(
                success=False,
                message=f"未找到事件类型 {event_type} 的Hook配置",
                dry_run=dry_run
            )

        # 查找具体的Hook
        hook_found = False
        current_index = 0

        for config in hooks_section[event_type]:
            if "hooks" in config and isinstance(config["hooks"], list):
                if current_index <= index < current_index + len(config["hooks"]):
                    hook_index_in_config = index - current_index
                    target_hook = config["hooks"][hook_index_in_config]

                    if dry_run:
                        return SettingsModificationResult(
                            success=True,
                            message=f"预览：将更新 {target_file.path} 中的Hook (索引 {index})",
                            affected_files=[target_file.path],
                            hooks_modified=1,
                            dry_run=True
                        )

                    # 应用更新
                    target_hook.update(updates)

                    # 验证更新后的Hook
                    try:
                        updated_hook = HookConfiguration.from_dict(target_hook)
                        validation_result = _hook_validator.validate_hook(updated_hook)

                        if not validation_result.is_valid:
                            return SettingsModificationResult(
                                success=False,
                                message="更新后的Hook配置验证失败",
                                validation_result=validation_result,
                                dry_run=dry_run
                            )
                    except Exception as e:
                        return SettingsModificationResult(
                            success=False,
                            message=f"Hook配置更新无效: {e}",
                            dry_run=dry_run
                        )

                    # 标记文件为已修改
                    target_file.state = SettingsFileState.MODIFIED

                    # 保存文件
                    backup_path = _settings_manager.save_settings_file(target_file, create_backup=True)

                    result = SettingsModificationResult(
                        success=True,
                        message=f"成功更新Hook (索引 {index})",
                        affected_files=[target_file.path],
                        hooks_modified=1,
                        validation_result=validation_result
                    )

                    if backup_path:
                        result.backup_files = [backup_path]

                    hook_found = True
                    break

                current_index += len(config["hooks"])

        if not hook_found:
            return SettingsModificationResult(
                success=False,
                message=f"未找到索引为 {index} 的Hook",
                dry_run=dry_run
            )

        return result

    except Exception as e:
        logger.error(f"更新Hook时出错: {e}")
        return SettingsModificationResult(
            success=False,
            message=f"更新Hook失败: {e}",
            dry_run=dry_run
        )


def remove_hook_from_settings(
    level: str,
    event_type: str,
    index: int,
    dry_run: bool = False
) -> SettingsModificationResult:
    """从设置文件中删除Hook配置

    Args:
        level: 设置级别
        event_type: Hook事件类型
        index: Hook在列表中的索引
        dry_run: 是否为预览模式

    Returns:
        修改操作结果
    """
    logger = logging.getLogger(__name__)
    logger.info(f"删除Hook，级别: {level}, 事件: {event_type}, 索引: {index}, dry_run: {dry_run}")

    try:
        # 查找设置文件
        settings_files = find_and_load_settings(level)
        if not settings_files:
            return SettingsModificationResult(
                success=False,
                message=f"未找到级别为 {level} 的设置文件",
                dry_run=dry_run
            )

        target_file = settings_files[0]

        # 找到要删除的Hook
        hooks_section = target_file.get_hooks_section()
        if event_type not in hooks_section:
            return SettingsModificationResult(
                success=False,
                message=f"未找到事件类型 {event_type} 的Hook配置",
                dry_run=dry_run
            )

        # 查找具体的Hook
        hook_found = False
        current_index = 0

        for config in hooks_section[event_type]:
            if "hooks" in config and isinstance(config["hooks"], list):
                if current_index <= index < current_index + len(config["hooks"]):
                    hook_index_in_config = index - current_index

                    if dry_run:
                        return SettingsModificationResult(
                            success=True,
                            message=f"预览：将从 {target_file.path} 中删除Hook (索引 {index})",
                            affected_files=[target_file.path],
                            hooks_modified=1,
                            dry_run=True
                        )

                    # 删除Hook
                    del config["hooks"][hook_index_in_config]

                    # 如果hooks列表为空，也删除整个配置
                    if not config["hooks"]:
                        hooks_section[event_type].remove(config)

                    # 如果事件类型下没有配置了，删除整个事件类型
                    if not hooks_section[event_type]:
                        del hooks_section[event_type]

                    # 标记文件为已修改
                    target_file.state = SettingsFileState.MODIFIED

                    # 保存文件
                    backup_path = _settings_manager.save_settings_file(target_file, create_backup=True)

                    result = SettingsModificationResult(
                        success=True,
                        message=f"成功删除Hook (索引 {index})",
                        affected_files=[target_file.path],
                        hooks_modified=1
                    )

                    if backup_path:
                        result.backup_files = [backup_path]

                    hook_found = True
                    break

                current_index += len(config["hooks"])

        if not hook_found:
            return SettingsModificationResult(
                success=False,
                message=f"未找到索引为 {index} 的Hook",
                dry_run=dry_run
            )

        return result

    except Exception as e:
        logger.error(f"删除Hook时出错: {e}")
        return SettingsModificationResult(
            success=False,
            message=f"删除Hook失败: {e}",
            dry_run=dry_run
        )


def list_hooks_from_settings(
    level: Optional[str] = None,
    event_filter: Optional[str] = None
) -> List[HookConfiguration]:
    """从设置文件中列出Hook配置

    Args:
        level: 设置级别过滤器 ("project", "user", "all", None)
        event_filter: 事件类型过滤器

    Returns:
        找到的Hook配置列表
    """
    logger = logging.getLogger(__name__)
    logger.info(f"列出Hook配置，级别: {level}, 事件过滤器: {event_filter}")

    hooks = []

    try:
        # 查找设置文件
        settings_files = find_and_load_settings(level)

        for settings_file in settings_files:
            hooks_section = settings_file.get_hooks_section()

            for event_type, event_configs in hooks_section.items():
                # 应用事件类型过滤器
                if event_filter and event_type != event_filter:
                    continue

                for config in event_configs:
                    if "hooks" in config and isinstance(config["hooks"], list):
                        matcher = config.get("matcher", "")

                        for hook_data in config["hooks"]:
                            try:
                                # 尝试解析事件类型
                                hook_event_type = None
                                try:
                                    hook_event_type = HookEventType.from_string(event_type)
                                except ValueError:
                                    logger.warning(f"未知的事件类型: {event_type}")

                                hook = HookConfiguration.from_dict(
                                    hook_data,
                                    event_type=hook_event_type,
                                    matcher=matcher
                                )
                                hooks.append(hook)
                            except Exception as e:
                                logger.warning(f"解析Hook配置失败: {e}")

        logger.info(f"找到 {len(hooks)} 个Hook配置")

    except Exception as e:
        logger.error(f"列出Hook配置时出错: {e}")

    return hooks


def validate_all_hooks(level: Optional[str] = None) -> ValidationResult:
    """验证所有Hook配置

    Args:
        level: 设置级别过滤器 ("project", "user", "all", None)

    Returns:
        总体验证结果
    """
    logger = logging.getLogger(__name__)
    logger.info(f"验证所有Hook配置，级别: {level}")

    try:
        # 获取所有Hook配置
        hooks = list_hooks_from_settings(level)

        if not hooks:
            return ValidationResult.success(["未找到Hook配置"])

        # 验证所有Hook
        overall_result = _hook_validator.validate_hooks(hooks)

        logger.info(f"验证了 {len(hooks)} 个Hook配置，有效: {overall_result.is_valid}")
        return overall_result

    except Exception as e:
        logger.error(f"验证Hook配置时出错: {e}")
        return ValidationResult.failure(
            errors=[ValidationError(
                field_name="general",
                error_code="VALIDATION_FAILED",
                message=f"验证过程失败: {e}"
            )]
        )


# 辅助函数

def _add_hook_to_settings_file(
    settings_file: SettingsFile,
    hook: HookConfiguration,
    event_type: HookEventType,
    matcher: Optional[str]
) -> None:
    """将Hook添加到设置文件的内部实现"""

    hooks_section = settings_file.get_hooks_section()
    event_name = event_type.value

    # 确保事件类型存在
    if event_name not in hooks_section:
        hooks_section[event_name] = []

    # 查找匹配的配置或创建新的
    target_config = None
    for config in hooks_section[event_name]:
        if config.get("matcher") == (matcher or ""):
            target_config = config
            break

    if target_config is None:
        target_config = {
            "matcher": matcher or "",
            "hooks": []
        }
        hooks_section[event_name].append(target_config)

    # 添加Hook配置
    target_config["hooks"].append(hook.to_dict())

    # 更新设置文件
    settings_file.set_hooks_section(hooks_section)


# 导出的公共API
__all__ = [
    "create_new_settings_file",
    "find_and_load_settings",
    "add_hook_to_settings",
    "update_hook_in_settings",
    "remove_hook_from_settings",
    "list_hooks_from_settings",
    "validate_all_hooks",
    "SettingsModificationResult"
]
