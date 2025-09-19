"""
pathlib文件操作工具模块

提供跨平台文件操作、设置文件发现、安全文件处理等核心功能。
使用pathlib库和Python标准库实现跨平台兼容性。

主要功能：
- 跨平台路径处理
- .claude/settings.json文件发现逻辑（项目级和用户级）
- 安全的文件读写操作
- 文件权限检查和验证
- 备份和恢复功能
- 目录创建和验证
- 防止路径遍历攻击的安全措施
"""

import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# 导入新的权限处理模块
try:
    from .permissions import (
        PermissionDiagnostic,
        PermissionInfo,
        PermissionLevel,
        PlatformType,
        check_permission,
        ensure_directory_writable,
        get_current_platform,
        get_permission_info,
        validate_claude_directory_permissions,
    )
    _PERMISSIONS_AVAILABLE = True
except ImportError:
    _PERMISSIONS_AVAILABLE = False


class FileOperationError(Exception):
    """文件操作相关异常（增强版）"""

    def __init__(self, message: str, error_code: str = None, suggested_fix: str = None,
                 alternative_solutions: List[str] = None, file_path: Union[str, Path] = None,
                 original_error: Exception = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "FILE_OPERATION_ERROR"
        self.suggested_fix = suggested_fix or "检查文件路径和权限"
        self.alternative_solutions = alternative_solutions or []
        self.file_path = str(file_path) if file_path else None
        self.original_error = original_error

    def __str__(self):
        error_msg = f"[{self.error_code}] {self.message}"
        if self.file_path:
            error_msg += f"\n文件路径: {self.file_path}"
        if self.suggested_fix:
            error_msg += f"\n建议解决方案: {self.suggested_fix}"
        if self.alternative_solutions:
            error_msg += f"\n其他解决方案: {'; '.join(self.alternative_solutions)}"
        if self.original_error:
            error_msg += f"\n原始错误: {self.original_error}"
        return error_msg

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于JSON序列化"""
        return {
            "error_type": "FileOperationError",
            "error_code": self.error_code,
            "message": self.message,
            "file_path": self.file_path,
            "suggested_fix": self.suggested_fix,
            "alternative_solutions": self.alternative_solutions,
            "original_error": str(self.original_error) if self.original_error else None
        }


class PermissionError(FileOperationError):
    """权限相关异常"""

    def __init__(self, message: str, file_path: Union[str, Path] = None,
                 required_permission: str = None, **kwargs):
        super().__init__(message, error_code="PERMISSION_DENIED", file_path=file_path, **kwargs)
        self.required_permission = required_permission

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error_type"] = "PermissionError"
        result["required_permission"] = self.required_permission
        return result


class SecurityError(FileOperationError):
    """安全相关异常"""

    def __init__(self, message: str, security_risk: str = None, **kwargs):
        super().__init__(message, error_code="SECURITY_VIOLATION", **kwargs)
        self.security_risk = security_risk

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error_type"] = "SecurityError"
        result["security_risk"] = self.security_risk
        return result


class SettingsFileNotFoundError(FileOperationError):
    """设置文件未找到异常"""

    def __init__(self, message: str, search_paths: List[str] = None, **kwargs):
        super().__init__(message, error_code="SETTINGS_FILE_NOT_FOUND", **kwargs)
        self.search_paths = search_paths or []

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error_type"] = "SettingsFileNotFoundError"
        result["search_paths"] = self.search_paths
        return result


def create_user_friendly_error(operation: str, file_path: Union[str, Path],
                              original_error: Exception) -> FileOperationError:
    """
    创建用户友好的错误消息

    Args:
        operation: 操作类型（如'read', 'write', 'create'等）
        file_path: 文件路径
        original_error: 原始异常

    Returns:
        增强的FileOperationError实例
    """
    path_str = str(file_path)

    # 根据操作类型和错误类型生成具体的错误消息和建议
    if isinstance(original_error, (IOError, OSError)):
        errno = getattr(original_error, 'errno', 0)

        if errno == 2:  # 文件不存在
            if operation == 'read':
                return FileOperationError(
                    message="无法读取文件，文件不存在",
                    error_code="FILE_NOT_FOUND",
                    suggested_fix="检查文件路径是否正确",
                    alternative_solutions=[
                        "确认文件名拼写正确",
                        "检查文件是否被移动或删除",
                        "使用绝对路径而不是相对路径"
                    ],
                    file_path=file_path,
                    original_error=original_error
                )
            elif operation == 'write':
                parent_dir = Path(file_path).parent
                return FileOperationError(
                    message="无法写入文件，父目录不存在",
                    error_code="PARENT_DIR_NOT_FOUND",
                    suggested_fix=f"先创建父目录: {parent_dir}",
                    alternative_solutions=[
                        f"mkdir -p {parent_dir}",
                        "使用ensure_directory_exists()函数",
                        "检查路径权限"
                    ],
                    file_path=file_path,
                    original_error=original_error
                )

        elif errno == 13:  # 权限拒绝
            platform = get_current_platform() if _PERMISSIONS_AVAILABLE else None
            suggestions = []

            if platform and platform.value == "windows":
                suggestions = [
                    "右键以管理员身份运行程序",
                    "检查文件是否被其他程序占用",
                    "确保文件不在受保护的系统目录中"
                ]
            else:
                suggestions = [
                    f"chmod +rw {path_str}",
                    f"sudo chown $USER {path_str}",
                    "检查父目录权限"
                ]

            return PermissionError(
                message=f"权限不足无法{operation}文件",
                suggested_fix=suggestions[0] if suggestions else "检查文件权限",
                alternative_solutions=suggestions[1:] if len(suggestions) > 1 else [],
                file_path=file_path,
                required_permission=operation,
                original_error=original_error
            )

        elif errno == 28:  # 磁盘空间不足
            return FileOperationError(
                message="磁盘空间不足",
                error_code="NO_SPACE_LEFT",
                suggested_fix="清理磁盘空间",
                alternative_solutions=[
                    "删除不需要的文件",
                    "选择其他存储位置",
                    "检查磁盘使用情况"
                ],
                file_path=file_path,
                original_error=original_error
            )

    elif isinstance(original_error, UnicodeDecodeError):
        return FileOperationError(
            message="文件编码错误，无法解码文件内容",
            error_code="ENCODING_ERROR",
            suggested_fix="尝试使用不同的编码格式读取文件",
            alternative_solutions=[
                "使用encoding='utf-8'参数",
                "使用encoding='gbk'参数（中文Windows）",
                "使用encoding='latin-1'参数（二进制模式）",
                "检查文件是否为二进制文件"
            ],
            file_path=file_path,
            original_error=original_error
        )

    elif isinstance(original_error, json.JSONDecodeError):
        return FileOperationError(
            message="JSON格式错误，无法解析文件内容",
            error_code="JSON_DECODE_ERROR",
            suggested_fix="检查JSON文件格式是否正确",
            alternative_solutions=[
                "使用JSON验证工具检查语法",
                "检查是否有多余的逗号或缺少引号",
                "确保文件内容是有效的JSON格式",
                "尝试手动修复JSON语法错误"
            ],
            file_path=file_path,
            original_error=original_error
        )

    # 默认通用错误
    return FileOperationError(
        message=f"执行{operation}操作时发生错误",
        error_code="OPERATION_FAILED",
        suggested_fix="重试操作或检查系统状态",
        alternative_solutions=[
            "重新启动程序",
            "检查系统资源使用情况",
            "联系技术支持"
        ],
        file_path=file_path,
        original_error=original_error
    )


def validate_path_security(path: Union[str, Path], base_path: Optional[Union[str, Path]] = None,
                          allow_symlinks: bool = False, max_path_length: int = 4096) -> Path:
    """
    验证路径安全性，防止路径遍历攻击和其他安全风险（增强版）

    Args:
        path: 要验证的路径
        base_path: 基础路径，如果提供，验证path是否在base_path内
        allow_symlinks: 是否允许符号链接
        max_path_length: 最大路径长度限制

    Returns:
        验证后的Path对象

    Raises:
        SecurityError: 如果路径不安全
    """
    try:
        # 初始路径对象
        path_obj = Path(path)
        path_str = str(path)

        # 1. 基本安全检查
        if len(path_str) > max_path_length:
            raise SecurityError(
                message=f"路径长度超过限制 ({len(path_str)} > {max_path_length})",
                security_risk="路径长度攻击",
                suggested_fix="使用较短的路径名称",
                alternative_solutions=["检查路径是否包含重复部分", "使用相对路径"]
            )

        # 2. 检查空字节注入
        if '\x00' in path_str:
            raise SecurityError(
                message="路径包含空字节",
                security_risk="空字节注入攻击",
                suggested_fix="移除路径中的空字节",
                alternative_solutions=["检查路径来源是否可信"]
            )

        # 3. 检查可疑的路径模式
        suspicious_patterns = {
            '..': "路径遍历",
            '//': "双斜杠",
            '\\\\': "双反斜杠",
            './': "当前目录引用",
            '%': "URL编码",
            '<': "脚本注入字符",
            '>': "脚本注入字符",
            '|': "命令注入字符",
            ':': "驱动器分隔符（可疑）" if (_PERMISSIONS_AVAILABLE and get_current_platform() != PlatformType.WINDOWS) else None,
            '*': "通配符",
            '?': "通配符",
            '"': "引号字符"
        }

        for pattern, risk in suspicious_patterns.items():
            if risk and pattern in path_str:
                # 特殊处理：Windows上的驱动器分隔符是正常的
                if pattern == ':' and _PERMISSIONS_AVAILABLE and get_current_platform() == PlatformType.WINDOWS:
                    # 检查是否为正常的驱动器路径
                    if len(path_str) >= 2 and path_str[1] == ':' and path_str[0].isalpha():
                        continue  # 正常的C:、D:等驱动器路径

                raise SecurityError(
                    message=f"路径包含可疑模式: {pattern}",
                    security_risk=risk,
                    suggested_fix="移除或转义可疑字符",
                    alternative_solutions=["使用安全的路径构建方法", "验证路径来源"]
                )

        # 4. 解析路径
        try:
            resolved_path = path_obj.resolve()
        except OSError as e:
            raise SecurityError(
                message=f"无法解析路径: {e}",
                security_risk="路径解析失败",
                suggested_fix="检查路径格式是否正确",
                alternative_solutions=["使用绝对路径", "检查路径权限"]
            )

        # 5. 符号链接检查
        if not allow_symlinks and path_obj.is_symlink():
            raise SecurityError(
                message="不允许使用符号链接",
                security_risk="符号链接攻击",
                suggested_fix="使用实际文件路径而不是符号链接",
                alternative_solutions=["设置allow_symlinks=True以允许符号链接"]
            )

        # 6. 路径遍历检查
        if base_path is not None:
            base_resolved = Path(base_path).resolve()
            try:
                resolved_path.relative_to(base_resolved)
            except ValueError:
                raise SecurityError(
                    message="路径越界访问",
                    security_risk="路径遍历攻击",
                    suggested_fix=f"确保路径在 {base_path} 目录内",
                    alternative_solutions=[
                        "使用相对路径",
                        "检查路径构建逻辑"
                    ],
                    file_path=path
                )

        # 7. 平台特定安全检查
        platform = get_current_platform() if _PERMISSIONS_AVAILABLE else None
        if platform:
            _validate_platform_specific_security(resolved_path, platform)

        # 8. 检查是否在敏感系统目录中
        _check_sensitive_directories(resolved_path)

        return resolved_path

    except SecurityError:
        raise  # 重新抛出SecurityError
    except Exception as e:
        raise SecurityError(
            message=f"路径验证失败: {e}",
            security_risk="未知安全风险",
            suggested_fix="检查路径格式和权限",
            alternative_solutions=["使用不同的路径", "联系技术支持"],
            original_error=e
        )


def _validate_platform_specific_security(path: Path, platform: 'PlatformType') -> None:
    """平台特定的安全验证"""
    path_str = str(path).lower()

    if platform == PlatformType.WINDOWS:
        # Windows特定检查
        forbidden_names = [
            'con', 'prn', 'aux', 'nul',
            'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
            'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        ]

        name_lower = path.name.lower()
        name_without_ext = name_lower.split('.')[0] if '.' in name_lower else name_lower

        if name_without_ext in forbidden_names:
            raise SecurityError(
                message=f"Windows保留设备名: {path.name}",
                security_risk="Windows设备名冲突",
                suggested_fix="使用不同的文件名",
                alternative_solutions=["在文件名前添加前缀", "使用下划线替代"]
            )

        # 检查尾随空格和点（Windows问题）
        if path.name.endswith(' ') or path.name.endswith('.'):
            raise SecurityError(
                message="文件名以空格或点结尾",
                security_risk="Windows文件名解析问题",
                suggested_fix="移除文件名末尾的空格或点",
                alternative_solutions=["使用不同的文件名"]
            )

    elif platform and platform in [PlatformType.LINUX, PlatformType.MACOS]:
        # Unix/Linux特定检查
        if path_str.startswith('/proc/'):
            raise SecurityError(
                message="尝试访问/proc文件系统",
                security_risk="系统信息泄露",
                suggested_fix="避免访问/proc目录",
                alternative_solutions=["使用专门的系统信息API"]
            )

        if path_str.startswith('/dev/'):
            raise SecurityError(
                message="尝试访问设备文件",
                security_risk="设备访问安全风险",
                suggested_fix="避免直接访问设备文件",
                alternative_solutions=["使用适当的设备API"]
            )


def _check_sensitive_directories(path: Path) -> None:
    """检查是否在敏感目录中"""
    path_str = str(path).lower()
    platform = get_current_platform() if _PERMISSIONS_AVAILABLE else None

    sensitive_paths = []

    if platform and platform == PlatformType.WINDOWS:
        sensitive_paths.extend([
            'c:\\windows\\system32',
            'c:\\windows\\syswow64',
            'c:\\program files',
            'c:\\program files (x86)',
            'c:\\programdata'
        ])
    elif platform and platform in [PlatformType.LINUX, PlatformType.MACOS]:
        sensitive_paths.extend([
            '/etc',
            '/usr/bin',
            '/usr/sbin',
            '/bin',
            '/sbin',
            '/boot',
            '/root'
        ])

        if platform == PlatformType.MACOS:
            sensitive_paths.extend([
                '/system',
                '/library',
                '/applications'
            ])

    for sensitive_path in sensitive_paths:
        if path_str.startswith(sensitive_path.lower()):
            # 这是警告而不是错误，但记录安全风险
            pass  # 可以在这里添加日志记录


def get_home_directory() -> Path:
    """
    获取用户主目录，跨平台兼容

    Returns:
        用户主目录的Path对象
    """
    return Path.home()


def find_project_root(start_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """
    查找项目根目录（包含.claude目录的目录）

    Args:
        start_path: 开始搜索的路径，默认为当前工作目录

    Returns:
        项目根目录的Path对象，如果未找到则返回None
    """
    current = Path(start_path) if start_path else Path.cwd()
    current = current.resolve()

    # 向上查找包含.claude目录的目录
    for parent in [current] + list(current.parents):
        claude_dir = parent / '.claude'
        if claude_dir.exists() and claude_dir.is_dir():
            return parent

    return None


def discover_settings_files() -> List[Tuple[str, Path]]:
    """
    发现所有可用的设置文件，按优先级排序

    Returns:
        (level, path)元组列表，按优先级从高到低排序：
        1. project - .claude/settings.json (项目级，最高优先级)
        2. project-local - .claude/settings.local.json (本地项目级)
        3. user - ~/.claude/settings.json (用户级，最低优先级)
    """
    settings_files = []

    # 1. 项目级设置文件
    project_root = find_project_root()
    if project_root:
        project_settings = project_root / '.claude' / 'settings.json'
        if project_settings.exists():
            settings_files.append(('project', project_settings))

        # 项目本地设置文件
        project_local_settings = project_root / '.claude' / 'settings.local.json'
        if project_local_settings.exists():
            settings_files.append(('project-local', project_local_settings))

    # 2. 用户级设置文件
    user_settings = get_home_directory() / '.claude' / 'settings.json'
    if user_settings.exists():
        settings_files.append(('user', user_settings))

    return settings_files


def get_settings_file_path(level: str = 'auto') -> Path:
    """
    获取指定级别的设置文件路径

    Args:
        level: 设置级别 ('project', 'user', 'auto')
               'auto' 表示自动选择最高优先级的文件

    Returns:
        设置文件的Path对象

    Raises:
        SettingsFileNotFoundError: 如果指定级别的设置文件不存在
        ValueError: 如果level参数无效
    """
    if level == 'auto':
        settings_files = discover_settings_files()
        if not settings_files:
            raise SettingsFileNotFoundError("未找到任何设置文件")
        return settings_files[0][1]

    elif level == 'project':
        project_root = find_project_root()
        if not project_root:
            raise SettingsFileNotFoundError("未找到项目根目录")
        project_settings = project_root / '.claude' / 'settings.json'
        if not project_settings.exists():
            raise SettingsFileNotFoundError(f"项目设置文件不存在: {project_settings}")
        return project_settings

    elif level == 'user':
        user_settings = get_home_directory() / '.claude' / 'settings.json'
        if not user_settings.exists():
            raise SettingsFileNotFoundError(f"用户设置文件不存在: {user_settings}")
        return user_settings

    else:
        raise ValueError(f"无效的设置级别: {level}")


def check_file_permissions(file_path: Union[str, Path],
                          need_read: bool = True,
                          need_write: bool = False) -> bool:
    """
    检查文件权限（已增强跨平台支持）

    Args:
        file_path: 文件路径
        need_read: 是否需要读权限
        need_write: 是否需要写权限

    Returns:
        如果权限满足要求返回True，否则返回False
    """
    # 使用新的权限模块如果可用
    if _PERMISSIONS_AVAILABLE:
        try:
            if need_read and need_write:
                permission_level = PermissionLevel.READ_WRITE
            elif need_write:
                permission_level = PermissionLevel.WRITE
            else:
                permission_level = PermissionLevel.READ

            has_permission, error = check_permission(file_path, permission_level)
            return has_permission
        except Exception:
            # 如果新模块失败，回退到原始实现
            pass

    # 原始实现作为后备
    path = Path(file_path)

    try:
        if not path.exists():
            # 如果文件不存在，检查父目录的写权限
            parent = path.parent
            if not parent.exists():
                return False
            return os.access(parent, os.W_OK if need_write else os.R_OK)

        # 检查文件权限
        if need_read and not os.access(path, os.R_OK):
            return False
        if need_write and not os.access(path, os.W_OK):
            return False

        return True

    except (OSError, ValueError):
        return False


def ensure_directory_exists(dir_path: Union[str, Path], mode: int = 0o755) -> Path:
    """
    确保目录存在，如果不存在则创建（已增强跨平台支持）

    Args:
        dir_path: 目录路径
        mode: 目录权限模式（Unix/Linux系统）

    Returns:
        目录的Path对象

    Raises:
        FileOperationError: 如果无法创建目录
    """
    path = validate_path_security(dir_path)

    # 使用新的权限模块如果可用
    if _PERMISSIONS_AVAILABLE:
        try:
            success, error = ensure_directory_writable(path, create_if_missing=True)
            if success:
                return path
            elif error:
                # 提供详细的错误信息和修复建议
                raise FileOperationError(
                    f"无法创建目录 '{path}': {error.message}\n"
                    f"建议解决方案: {error.suggested_fix}\n"
                    f"替代方案: {'; '.join(error.alternative_solutions)}"
                )
        except Exception:
            # 如果新模块失败，回退到原始实现
            pass

    # 原始实现作为后备
    try:
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        return path
    except (OSError, PermissionError) as e:
        raise FileOperationError(f"无法创建目录 '{path}': {e}")


def create_backup(file_path: Union[str, Path], backup_suffix: str = None) -> Path:
    """
    创建文件备份

    Args:
        file_path: 要备份的文件路径
        backup_suffix: 备份文件后缀，默认为时间戳

    Returns:
        备份文件的Path对象

    Raises:
        FileOperationError: 如果备份失败
    """
    source_path = validate_path_security(file_path)

    if not source_path.exists():
        raise FileOperationError(f"源文件不存在: {source_path}")

    if backup_suffix is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_suffix = f".backup.{timestamp}"

    backup_path = source_path.with_suffix(source_path.suffix + backup_suffix)

    try:
        shutil.copy2(source_path, backup_path)
        return backup_path
    except (OSError, shutil.Error) as e:
        raise FileOperationError(f"创建备份失败: {e}")


def restore_from_backup(backup_path: Union[str, Path], target_path: Union[str, Path] = None) -> Path:
    """
    从备份恢复文件

    Args:
        backup_path: 备份文件路径
        target_path: 目标文件路径，如果为None则从备份文件名推断

    Returns:
        恢复的文件Path对象

    Raises:
        FileOperationError: 如果恢复失败
    """
    backup = validate_path_security(backup_path)

    if not backup.exists():
        raise FileOperationError(f"备份文件不存在: {backup}")

    if target_path is None:
        # 从备份文件名推断原始文件名
        name = backup.name
        if '.backup.' in name:
            original_name = name.split('.backup.')[0]
            target_path = backup.parent / original_name
        else:
            raise FileOperationError("无法从备份文件名推断原始文件名")

    target = validate_path_security(target_path)

    try:
        shutil.copy2(backup, target)
        return target
    except (OSError, shutil.Error) as e:
        raise FileOperationError(f"恢复备份失败: {e}")


def read_json_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> Dict[str, Any]:
    """
    安全地读取JSON文件（增强错误处理）

    Args:
        file_path: JSON文件路径
        encoding: 文件编码

    Returns:
        解析后的JSON数据

    Raises:
        FileOperationError: 如果读取失败
    """
    try:
        path = validate_path_security(file_path)

        if not check_file_permissions(path, need_read=True):
            raise PermissionError(
                message="没有读取文件的权限",
                file_path=path,
                required_permission="read",
                suggested_fix="检查文件权限设置",
                alternative_solutions=[
                    "使用管理员权限运行程序",
                    "修改文件权限",
                    "确保文件不被其他程序占用"
                ]
            )

        with path.open('r', encoding=encoding) as f:
            return json.load(f)

    except OSError as e:
        raise create_user_friendly_error('read', file_path, e)
    except json.JSONDecodeError as e:
        raise create_user_friendly_error('read', file_path, e)
    except Exception as e:
        raise create_user_friendly_error('read', file_path, e)


def write_json_file(file_path: Union[str, Path],
                   data: Dict[str, Any],
                   encoding: str = 'utf-8',
                   indent: int = 2,
                   create_backup: bool = True) -> Optional[Path]:
    """
    安全地写入JSON文件

    Args:
        file_path: JSON文件路径
        data: 要写入的数据
        encoding: 文件编码
        indent: JSON缩进空格数
        create_backup: 是否在写入前创建备份

    Returns:
        如果创建了备份，返回备份文件路径，否则返回None

    Raises:
        FileOperationError: 如果写入失败
    """
    path = validate_path_security(file_path)

    # 确保父目录存在
    ensure_directory_exists(path.parent)

    # 检查写权限
    if not check_file_permissions(path, need_write=True):
        raise PermissionError(f"没有写入文件的权限: {path}")

    backup_path = None

    # 如果文件存在且需要备份，先创建备份
    if path.exists() and create_backup:
        # 为了避免名称冲突，使用全局命名空间中的create_backup函数
        import sys
        current_module = sys.modules[__name__]
        backup_func = current_module.create_backup
        backup_path = backup_func(path)

    try:
        # 写入临时文件然后原子性地移动
        temp_path = path.with_suffix('.tmp')
        with temp_path.open('w', encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        # 原子性地替换原文件
        temp_path.replace(path)

        return backup_path

    except OSError as e:
        # 如果写入失败且创建了备份，尝试恢复
        if backup_path and backup_path.exists():
            try:
                restore_from_backup(backup_path, path)
            except Exception:
                pass  # 恢复失败不抛出异常，避免掩盖原始错误
        raise FileOperationError(f"无法写入文件 '{path}': {e}")
    except Exception as e:
        # 清理临时文件
        temp_path = path.with_suffix('.tmp')
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise FileOperationError(f"写入JSON文件时发生错误: {e}")


def read_text_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """
    安全地读取文本文件

    Args:
        file_path: 文件路径
        encoding: 文件编码

    Returns:
        文件内容字符串

    Raises:
        FileOperationError: 如果读取失败
    """
    path = validate_path_security(file_path)

    if not check_file_permissions(path, need_read=True):
        raise PermissionError(f"没有读取文件的权限: {path}")

    try:
        with path.open('r', encoding=encoding) as f:
            return f.read()
    except OSError as e:
        raise FileOperationError(f"无法读取文件 '{path}': {e}")
    except UnicodeDecodeError as e:
        raise FileOperationError(f"文件编码错误 '{path}': {e}")


def write_text_file(file_path: Union[str, Path],
                   content: str,
                   encoding: str = 'utf-8',
                   create_backup: bool = True) -> Optional[Path]:
    """
    安全地写入文本文件

    Args:
        file_path: 文件路径
        content: 文件内容
        encoding: 文件编码
        create_backup: 是否在写入前创建备份

    Returns:
        如果创建了备份，返回备份文件路径，否则返回None

    Raises:
        FileOperationError: 如果写入失败
    """
    path = validate_path_security(file_path)

    # 确保父目录存在
    ensure_directory_exists(path.parent)

    # 检查写权限
    if not check_file_permissions(path, need_write=True):
        raise PermissionError(f"没有写入文件的权限: {path}")

    backup_path = None

    # 如果文件存在且需要备份，先创建备份
    if path.exists() and create_backup:
        backup_path = create_backup(path)

    try:
        with path.open('w', encoding=encoding) as f:
            f.write(content)
        return backup_path
    except OSError as e:
        # 如果写入失败且创建了备份，尝试恢复
        if backup_path and backup_path.exists():
            try:
                restore_from_backup(backup_path, path)
            except Exception:
                pass  # 恢复失败不抛出异常，避免掩盖原始错误
        raise FileOperationError(f"无法写入文件 '{path}': {e}")


def safe_delete_file(file_path: Union[str, Path], create_backup: bool = True) -> Optional[Path]:
    """
    安全地删除文件

    Args:
        file_path: 要删除的文件路径
        create_backup: 是否在删除前创建备份

    Returns:
        如果创建了备份，返回备份文件路径，否则返回None

    Raises:
        FileOperationError: 如果删除失败
    """
    path = validate_path_security(file_path)

    if not path.exists():
        return None

    backup_path = None

    # 如果需要备份，先创建备份
    if create_backup:
        backup_path = create_backup(path)

    try:
        path.unlink()
        return backup_path
    except (OSError, PermissionError) as e:
        raise FileOperationError(f"无法删除文件 '{path}': {e}")


def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    获取文件信息（已增强跨平台支持）

    Args:
        file_path: 文件路径

    Returns:
        包含文件信息的字典

    Raises:
        FileOperationError: 如果获取信息失败
    """
    path = validate_path_security(file_path)

    try:
        if not path.exists():
            return {'exists': False}

        # 使用新的权限模块获取详细信息
        if _PERMISSIONS_AVAILABLE:
            try:
                perm_info = get_permission_info(path)
                platform = get_current_platform()

                # 构建增强的文件信息
                stat_info = path.stat()
                info = {
                    'exists': True,
                    'is_file': path.is_file(),
                    'is_dir': path.is_dir(),
                    'size': stat_info.st_size,
                    'created': datetime.fromtimestamp(stat_info.st_ctime),
                    'modified': datetime.fromtimestamp(stat_info.st_mtime),
                    'accessed': datetime.fromtimestamp(stat_info.st_atime),
                    'permissions': stat.filemode(stat_info.st_mode),
                    'readable': perm_info.is_readable,
                    'writable': perm_info.is_writable,
                    'executable': perm_info.is_executable,
                    'platform': platform.value,
                    'detailed_permissions': {
                        'owner': {
                            'read': perm_info.owner_readable,
                            'write': perm_info.owner_writable,
                            'execute': perm_info.owner_executable
                        },
                        'group': {
                            'read': perm_info.group_readable,
                            'write': perm_info.group_writable,
                            'execute': perm_info.group_executable
                        },
                        'others': {
                            'read': perm_info.other_readable,
                            'write': perm_info.other_writable,
                            'execute': perm_info.other_executable
                        }
                    },
                    'platform_specific': perm_info.platform_specific
                }
                return info
            except Exception:
                # 如果新模块失败，回退到原始实现
                pass

        # 原始实现作为后备
        stat_info = path.stat()

        return {
            'exists': True,
            'is_file': path.is_file(),
            'is_dir': path.is_dir(),
            'size': stat_info.st_size,
            'created': datetime.fromtimestamp(stat_info.st_ctime),
            'modified': datetime.fromtimestamp(stat_info.st_mtime),
            'accessed': datetime.fromtimestamp(stat_info.st_atime),
            'permissions': stat.filemode(stat_info.st_mode),
            'readable': os.access(path, os.R_OK),
            'writable': os.access(path, os.W_OK),
            'executable': os.access(path, os.X_OK),
        }
    except (OSError, ValueError) as e:
        raise FileOperationError(f"无法获取文件信息 '{path}': {e}")


# 导出所有核心函数
__all__ = [
    # 异常类
    'FileOperationError',
    'PermissionError',
    'SecurityError',
    'SettingsFileNotFoundError',
    # 安全和路径处理
    'validate_path_security',
    'get_home_directory',
    'find_project_root',
    # 设置文件发现
    'discover_settings_files',
    'get_settings_file_path',
    # 权限和目录操作
    'check_file_permissions',
    'ensure_directory_exists',
    # 备份和恢复
    'create_backup',
    'restore_from_backup',
    # 文件读写操作
    'read_json_file',
    'write_json_file',
    'read_text_file',
    'write_text_file',
    'safe_delete_file',
    # 文件信息
    'get_file_info',
]
