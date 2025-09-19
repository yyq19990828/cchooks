"""
设置文件备份和恢复系统

提供可靠的数据保护机制，包括：
- BackupManager类：自动备份创建和管理
- 备份策略：修改前自动备份、定期备份、增量备份
- 恢复功能：备份文件列出、快速恢复、部分恢复
- 备份验证：完整性检查、数据一致性验证
- 存储管理：备份目录组织、磁盘空间管理
- 元数据系统：创建时间、版本信息、更改摘要
- 安全考虑：权限控制、加密选项
- 跨平台支持：文件系统差异处理
"""

import gzip
import hashlib
import json
import logging
import os
import shutil
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union

from .file_operations import (
    FileOperationError,
    PermissionError,
    SecurityError,
    check_file_permissions,
    ensure_directory_exists,
    get_file_info,
    validate_path_security,
)


class BackupType(Enum):
    """备份类型枚举"""
    MANUAL = "manual"          # 手动备份
    AUTO_PRE_MODIFY = "auto_pre_modify"  # 修改前自动备份
    SCHEDULED = "scheduled"    # 定期备份
    INCREMENTAL = "incremental"  # 增量备份


class BackupStatus(Enum):
    """备份状态枚举"""
    CREATED = "created"        # 已创建
    VERIFIED = "verified"      # 已验证
    CORRUPTED = "corrupted"    # 已损坏
    EXPIRED = "expired"        # 已过期


class CompressionType(Enum):
    """压缩类型枚举"""
    NONE = "none"             # 无压缩
    GZIP = "gzip"             # GZIP压缩


@dataclass
class BackupMetadata:
    """备份元数据类"""
    backup_id: str
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    source_file_path: str
    backup_file_path: str
    original_size: int
    backup_size: int
    checksum_md5: str
    checksum_sha256: str
    compression: CompressionType
    reason: str = ""
    version: str = "1.0"
    file_permissions: Optional[str] = None
    user_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 转换枚举和datetime为字符串
        data['backup_type'] = self.backup_type.value
        data['status'] = self.status.value
        data['compression'] = self.compression.value
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupMetadata':
        """从字典创建BackupMetadata对象"""
        # 转换字符串为枚举和datetime
        data['backup_type'] = BackupType(data['backup_type'])
        data['status'] = BackupStatus(data['status'])
        data['compression'] = CompressionType(data['compression'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class BackupConfig:
    """备份配置类"""

    def __init__(self):
        # 备份目录配置
        self.backup_root_dir: Optional[Path] = None
        self.auto_create_dirs: bool = True

        # 保留策略
        self.max_backups_per_file: int = 10
        self.retention_days: int = 30
        self.auto_cleanup: bool = True

        # 压缩配置
        self.enable_compression: bool = False
        self.compression_type: CompressionType = CompressionType.GZIP
        self.compress_threshold_kb: int = 100  # 超过100KB才压缩

        # 验证配置
        self.enable_verification: bool = True
        self.checksum_algorithms: List[str] = ['md5', 'sha256']

        # 安全配置
        self.backup_permissions: int = 0o600  # 仅所有者可读写
        self.preserve_original_permissions: bool = True

        # 性能配置
        self.buffer_size: int = 8192  # 8KB buffer
        self.parallel_operations: bool = False


class BackupManager:
    """备份管理器类

    提供完整的设置文件备份和恢复系统，包括：
    - 自动备份创建和管理
    - 备份文件命名和组织
    - 备份保留策略
    - 元数据管理
    - 备份验证和完整性检查
    - 恢复功能
    """

    def __init__(self, config: Optional[BackupConfig] = None):
        """初始化备份管理器

        Args:
            config: 备份配置，如果为None则使用默认配置
        """
        self.config = config or BackupConfig()
        self.logger = logging.getLogger(__name__)

        # 确定备份根目录
        if self.config.backup_root_dir is None:
            self.config.backup_root_dir = self._get_default_backup_dir()

        # 创建备份目录结构
        if self.config.auto_create_dirs:
            self._init_backup_directories()

    def _get_default_backup_dir(self) -> Path:
        """获取默认备份目录"""
        # 使用用户的.claude目录下的backups子目录
        home_dir = Path.home()
        return home_dir / '.claude' / 'backups'

    def _init_backup_directories(self) -> None:
        """初始化备份目录结构"""
        try:
            # 创建主备份目录
            ensure_directory_exists(self.config.backup_root_dir)

            # 创建子目录
            subdirs = ['settings', 'metadata', 'temp']
            for subdir in subdirs:
                ensure_directory_exists(self.config.backup_root_dir / subdir)

        except Exception as e:
            raise FileOperationError(f"初始化备份目录失败: {e}")

    def create_backup(
        self,
        file_path: Union[str, Path],
        backup_type: BackupType = BackupType.MANUAL,
        reason: str = "",
        user_notes: str = ""
    ) -> BackupMetadata:
        """创建文件备份

        Args:
            file_path: 要备份的文件路径
            backup_type: 备份类型
            reason: 备份原因
            user_notes: 用户备注

        Returns:
            备份元数据对象

        Raises:
            FileOperationError: 如果备份失败
        """
        source_path = validate_path_security(file_path)

        # 检查源文件
        if not source_path.exists():
            raise FileOperationError(f"源文件不存在: {source_path}")

        if not source_path.is_file():
            raise FileOperationError(f"源路径不是文件: {source_path}")

        # 检查权限
        if not check_file_permissions(source_path, 'r'):
            raise PermissionError(f"无法读取源文件: {source_path}")

        # 生成备份ID和路径
        backup_id = self._generate_backup_id()
        backup_file_path = self._get_backup_file_path(source_path, backup_id)

        # 获取文件信息
        file_info = get_file_info(source_path)
        original_size = file_info['size']

        # 计算源文件校验和
        checksums = self._calculate_checksums(source_path)

        try:
            # 执行备份操作
            if self._should_compress(original_size):
                backup_size, actual_backup_path = self._create_compressed_backup(source_path, backup_file_path)
                compression = CompressionType.GZIP
            else:
                backup_size, actual_backup_path = self._create_uncompressed_backup(source_path, backup_file_path)
                compression = CompressionType.NONE

            # 更新备份文件路径为实际路径
            backup_file_path = actual_backup_path

            # 设置备份文件权限
            self._set_backup_permissions(backup_file_path, source_path)

            # 获取文件权限（数字形式）
            file_permissions = None
            if self.config.preserve_original_permissions:
                try:
                    file_permissions = oct(source_path.stat().st_mode)
                except OSError:
                    file_permissions = None

            # 创建元数据
            metadata = BackupMetadata(
                backup_id=backup_id,
                backup_type=backup_type,
                status=BackupStatus.CREATED,
                created_at=datetime.now(),
                source_file_path=str(source_path.absolute()),
                backup_file_path=str(backup_file_path.absolute()),
                original_size=original_size,
                backup_size=backup_size,
                checksum_md5=checksums['md5'],
                checksum_sha256=checksums['sha256'],
                compression=compression,
                reason=reason,
                file_permissions=file_permissions,
                user_notes=user_notes
            )

            # 验证备份
            if self.config.enable_verification:
                if self._verify_backup(metadata):
                    metadata.status = BackupStatus.VERIFIED
                else:
                    metadata.status = BackupStatus.CORRUPTED
                    raise FileOperationError("备份验证失败")

            # 保存元数据
            self._save_metadata(metadata)

            # 清理旧备份
            if self.config.auto_cleanup:
                self._cleanup_old_backups(source_path)

            self.logger.info(f"成功创建备份: {backup_id} for {source_path}")
            return metadata

        except Exception as e:
            # 清理失败的备份文件
            try:
                if backup_file_path.exists():
                    backup_file_path.unlink()
            except:
                pass
            raise FileOperationError(f"创建备份失败: {e}")

    def _generate_backup_id(self) -> str:
        """生成唯一的备份ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique_id}"

    def _get_backup_file_path(self, source_path: Path, backup_id: str) -> Path:
        """获取备份文件路径"""
        # 使用源文件名构建备份文件名
        backup_name = f"{source_path.stem}_{backup_id}{source_path.suffix}"
        return self.config.backup_root_dir / 'settings' / backup_name

    def _should_compress(self, file_size: int) -> bool:
        """判断是否应该压缩文件"""
        return (
            self.config.enable_compression and
            file_size > self.config.compress_threshold_kb * 1024
        )

    def _create_compressed_backup(self, source_path: Path, backup_path: Path) -> Tuple[int, Path]:
        """创建压缩备份

        Returns:
            Tuple[int, Path]: 备份文件大小和实际备份文件路径
        """
        compressed_backup_path = backup_path.with_suffix(backup_path.suffix + '.gz')

        with open(source_path, 'rb') as source_file:
            with gzip.open(compressed_backup_path, 'wb') as backup_file:
                shutil.copyfileobj(source_file, backup_file, self.config.buffer_size)

        return compressed_backup_path.stat().st_size, compressed_backup_path

    def _create_uncompressed_backup(self, source_path: Path, backup_path: Path) -> Tuple[int, Path]:
        """创建未压缩备份

        Returns:
            Tuple[int, Path]: 备份文件大小和实际备份文件路径
        """
        shutil.copy2(source_path, backup_path)
        return backup_path.stat().st_size, backup_path

    def _set_backup_permissions(self, backup_path: Path, source_path: Path) -> None:
        """设置备份文件权限"""
        try:
            # 设置基本权限
            backup_path.chmod(self.config.backup_permissions)

            # 如果需要保留原始权限信息（存储在元数据中）
            if self.config.preserve_original_permissions:
                # 权限信息会存储在元数据中，实际文件使用安全权限
                pass

        except OSError as e:
            self.logger.warning(f"设置备份文件权限失败: {e}")

    def _calculate_checksums(self, file_path: Path) -> Dict[str, str]:
        """计算文件校验和"""
        checksums = {}

        with open(file_path, 'rb') as f:
            content = f.read()

            if 'md5' in self.config.checksum_algorithms:
                checksums['md5'] = hashlib.md5(content).hexdigest()

            if 'sha256' in self.config.checksum_algorithms:
                checksums['sha256'] = hashlib.sha256(content).hexdigest()

        return checksums

    def _verify_backup(self, metadata: BackupMetadata) -> bool:
        """验证备份完整性"""
        try:
            backup_path = Path(metadata.backup_file_path)

            if not backup_path.exists():
                return False

            # 检查文件大小
            actual_size = backup_path.stat().st_size
            if actual_size != metadata.backup_size:
                return False

            # 读取备份文件内容
            if metadata.compression == CompressionType.GZIP:
                with gzip.open(backup_path, 'rb') as f:
                    content = f.read()
            else:
                with open(backup_path, 'rb') as f:
                    content = f.read()

            # 验证校验和
            if 'md5' in self.config.checksum_algorithms:
                actual_md5 = hashlib.md5(content).hexdigest()
                if actual_md5 != metadata.checksum_md5:
                    return False

            if 'sha256' in self.config.checksum_algorithms:
                actual_sha256 = hashlib.sha256(content).hexdigest()
                if actual_sha256 != metadata.checksum_sha256:
                    return False

            return True

        except Exception as e:
            self.logger.error(f"验证备份失败: {e}")
            return False

    def _save_metadata(self, metadata: BackupMetadata) -> None:
        """保存备份元数据"""
        metadata_file = self.config.backup_root_dir / 'metadata' / f"{metadata.backup_id}.json"

        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

            # 设置元数据文件权限
            metadata_file.chmod(self.config.backup_permissions)

        except Exception as e:
            raise FileOperationError(f"保存备份元数据失败: {e}")

    def _cleanup_old_backups(self, source_path: Path) -> None:
        """清理旧备份"""
        try:
            # 获取该文件的所有备份
            backups = self.list_backups(source_path)

            # 按创建时间排序
            backups.sort(key=lambda x: x.created_at, reverse=True)

            # 删除超过保留数量的备份
            if len(backups) > self.config.max_backups_per_file:
                for backup in backups[self.config.max_backups_per_file:]:
                    self._delete_backup(backup.backup_id)

            # 删除过期备份
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            for backup in backups:
                if backup.created_at < cutoff_date:
                    self._delete_backup(backup.backup_id)

        except Exception as e:
            self.logger.warning(f"清理旧备份失败: {e}")

    def list_backups(
        self,
        source_path: Optional[Union[str, Path]] = None,
        backup_type: Optional[BackupType] = None,
        status: Optional[BackupStatus] = None
    ) -> List[BackupMetadata]:
        """列出备份

        Args:
            source_path: 源文件路径，如果指定则只返回该文件的备份
            backup_type: 备份类型过滤
            status: 备份状态过滤

        Returns:
            备份元数据列表
        """
        backups = []
        metadata_dir = self.config.backup_root_dir / 'metadata'

        if not metadata_dir.exists():
            return backups

        try:
            for metadata_file in metadata_dir.glob('*.json'):
                try:
                    with open(metadata_file, encoding='utf-8') as f:
                        data = json.load(f)

                    metadata = BackupMetadata.from_dict(data)

                    # 应用过滤条件
                    if source_path is not None:
                        source_abs = str(Path(source_path).absolute())
                        if metadata.source_file_path != source_abs:
                            continue

                    if backup_type is not None and metadata.backup_type != backup_type:
                        continue

                    if status is not None and metadata.status != status:
                        continue

                    backups.append(metadata)

                except Exception as e:
                    self.logger.warning(f"加载备份元数据失败 {metadata_file}: {e}")

            return backups

        except Exception as e:
            self.logger.error(f"列出备份失败: {e}")
            return []

    def get_backup_by_id(self, backup_id: str) -> Optional[BackupMetadata]:
        """根据备份ID获取备份信息

        Args:
            backup_id: 备份ID

        Returns:
            备份元数据对象，如果不存在则返回None
        """
        metadata_file = self.config.backup_root_dir / 'metadata' / f"{backup_id}.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, encoding='utf-8') as f:
                data = json.load(f)

            return BackupMetadata.from_dict(data)

        except Exception as e:
            self.logger.error(f"加载备份元数据失败 {backup_id}: {e}")
            return None

    def restore_backup(
        self,
        backup_id: str,
        target_path: Optional[Union[str, Path]] = None,
        verify_before_restore: bool = True
    ) -> Path:
        """恢复备份

        Args:
            backup_id: 备份ID
            target_path: 恢复目标路径，如果为None则恢复到原始位置
            verify_before_restore: 恢复前是否验证备份

        Returns:
            恢复的文件路径

        Raises:
            FileOperationError: 如果恢复失败
        """
        # 获取备份元数据
        metadata = self.get_backup_by_id(backup_id)
        if metadata is None:
            raise FileOperationError(f"备份不存在: {backup_id}")

        # 验证备份
        if verify_before_restore and not self._verify_backup(metadata):
            raise FileOperationError(f"备份验证失败: {backup_id}")

        # 确定目标路径
        if target_path is None:
            target_path = Path(metadata.source_file_path)
        else:
            target_path = validate_path_security(target_path)

        # 备份当前文件（如果存在）
        if target_path.exists():
            try:
                current_backup = self.create_backup(
                    target_path,
                    BackupType.AUTO_PRE_MODIFY,
                    f"恢复备份前的自动备份 {backup_id}"
                )
                self.logger.info(f"创建恢复前备份: {current_backup.backup_id}")
            except Exception as e:
                self.logger.warning(f"创建恢复前备份失败: {e}")

        try:
            # 确保目标目录存在
            ensure_directory_exists(target_path.parent)

            # 执行恢复
            backup_path = Path(metadata.backup_file_path)

            if metadata.compression == CompressionType.GZIP:
                self._restore_compressed_backup(backup_path, target_path)
            else:
                self._restore_uncompressed_backup(backup_path, target_path)

            # 恢复原始权限（如果保存了）
            if metadata.file_permissions and self.config.preserve_original_permissions:
                try:
                    target_path.chmod(int(metadata.file_permissions, 8))
                except OSError as e:
                    self.logger.warning(f"恢复文件权限失败: {e}")

            self.logger.info(f"成功恢复备份: {backup_id} to {target_path}")
            return target_path

        except Exception as e:
            raise FileOperationError(f"恢复备份失败: {e}")

    def _restore_compressed_backup(self, backup_path: Path, target_path: Path) -> None:
        """恢复压缩备份"""
        with gzip.open(backup_path, 'rb') as backup_file:
            with open(target_path, 'wb') as target_file:
                shutil.copyfileobj(backup_file, target_file, self.config.buffer_size)

    def _restore_uncompressed_backup(self, backup_path: Path, target_path: Path) -> None:
        """恢复未压缩备份"""
        shutil.copy2(backup_path, target_path)

    def restore_latest_backup(
        self,
        source_path: Union[str, Path],
        target_path: Optional[Union[str, Path]] = None
    ) -> Optional[Path]:
        """恢复最新备份

        Args:
            source_path: 源文件路径
            target_path: 恢复目标路径，如果为None则恢复到原始位置

        Returns:
            恢复的文件路径，如果没有备份则返回None
        """
        backups = self.list_backups(source_path, status=BackupStatus.VERIFIED)

        if not backups:
            return None

        # 找到最新的备份
        latest_backup = max(backups, key=lambda x: x.created_at)

        return self.restore_backup(latest_backup.backup_id, target_path)

    def _delete_backup(self, backup_id: str) -> bool:
        """删除备份

        Args:
            backup_id: 备份ID

        Returns:
            是否删除成功
        """
        try:
            metadata = self.get_backup_by_id(backup_id)
            if metadata is None:
                return False

            # 删除备份文件
            backup_path = Path(metadata.backup_file_path)
            if backup_path.exists():
                backup_path.unlink()

            # 删除元数据文件
            metadata_file = self.config.backup_root_dir / 'metadata' / f"{backup_id}.json"
            if metadata_file.exists():
                metadata_file.unlink()

            self.logger.info(f"删除备份: {backup_id}")
            return True

        except Exception as e:
            self.logger.error(f"删除备份失败 {backup_id}: {e}")
            return False

    def cleanup_all_backups(self) -> int:
        """清理所有过期备份

        Returns:
            清理的备份数量
        """
        cleaned_count = 0
        cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)

        all_backups = self.list_backups()

        for backup in all_backups:
            if backup.created_at < cutoff_date:
                if self._delete_backup(backup.backup_id):
                    cleaned_count += 1

        return cleaned_count

    def get_backup_statistics(self) -> Dict[str, Any]:
        """获取备份统计信息

        Returns:
            备份统计信息字典
        """
        all_backups = self.list_backups()

        stats = {
            'total_backups': len(all_backups),
            'by_type': {},
            'by_status': {},
            'total_size': 0,
            'oldest_backup': None,
            'newest_backup': None,
            'unique_files': set()
        }

        for backup in all_backups:
            # 按类型统计
            backup_type = backup.backup_type.value
            stats['by_type'][backup_type] = stats['by_type'].get(backup_type, 0) + 1

            # 按状态统计
            status = backup.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

            # 大小统计
            stats['total_size'] += backup.backup_size

            # 时间统计
            if stats['oldest_backup'] is None or backup.created_at < stats['oldest_backup']:
                stats['oldest_backup'] = backup.created_at

            if stats['newest_backup'] is None or backup.created_at > stats['newest_backup']:
                stats['newest_backup'] = backup.created_at

            # 唯一文件统计
            stats['unique_files'].add(backup.source_file_path)

        stats['unique_files_count'] = len(stats['unique_files'])
        stats['unique_files'] = list(stats['unique_files'])

        return stats

    def verify_all_backups(self) -> Dict[str, Any]:
        """验证所有备份

        Returns:
            验证结果字典
        """
        all_backups = self.list_backups()

        results = {
            'total_checked': 0,
            'verified': 0,
            'corrupted': 0,
            'corrupted_backups': []
        }

        for backup in all_backups:
            results['total_checked'] += 1

            if self._verify_backup(backup):
                results['verified'] += 1
                # 更新状态为已验证
                backup.status = BackupStatus.VERIFIED
                self._save_metadata(backup)
            else:
                results['corrupted'] += 1
                results['corrupted_backups'].append(backup.backup_id)
                # 更新状态为已损坏
                backup.status = BackupStatus.CORRUPTED
                self._save_metadata(backup)

        return results


# 便捷函数

def create_settings_backup(
    settings_path: Union[str, Path],
    reason: str = "手动备份"
) -> BackupMetadata:
    """创建设置文件备份的便捷函数

    Args:
        settings_path: 设置文件路径
        reason: 备份原因

    Returns:
        备份元数据对象
    """
    manager = BackupManager()
    return manager.create_backup(
        settings_path,
        BackupType.MANUAL,
        reason
    )


def restore_latest_settings_backup(
    settings_path: Union[str, Path]
) -> Optional[Path]:
    """恢复最新设置文件备份的便捷函数

    Args:
        settings_path: 设置文件路径

    Returns:
        恢复的文件路径，如果没有备份则返回None
    """
    manager = BackupManager()
    return manager.restore_latest_backup(settings_path)


def list_settings_backups(
    settings_path: Union[str, Path]
) -> List[BackupMetadata]:
    """列出设置文件备份的便捷函数

    Args:
        settings_path: 设置文件路径

    Returns:
        备份元数据列表
    """
    manager = BackupManager()
    return manager.list_backups(settings_path)
