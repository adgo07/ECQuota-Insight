"""安全备份文件名的唯一构造器（Phase 7 阻塞项修复）。

产品里有三条**自动**安全备份路径：迁移前（``pre-migration-``）、安装/升级前
（``pre-package-``）、恢复前（``pre-restore-``）。它们过去各自拼名字，其中两条只精确到
**秒**，而 ``BackupService.create`` 会直接写入给定路径：同一秒内的两次操作得到同一个
路径，第二次静默覆盖第一次，被保护的状态从此不可恢复。

本模块是这三条路径**唯一**的命名实现：调用方只给目录和前缀，不再自己拼时间戳，也不
再自己处理碰撞。命名规则：

    <prefix>YYYYMMDD-HHMMSS-ffffff-<short-uuid>.uebackup

* 微秒精度 + 短 uuid：同一秒、同一微秒内的连续或并发调用都能得到不同的名字；
* 预订用 ``O_CREAT | O_EXCL`` **独占创建**，并在占位文件里写入一条**本进程专属的随机
  令牌**，因此选择与占用是同一步操作，time-of-check/time-of-use 竞态被关闭：两个并发
  调用不可能选中同一个路径，已存在的文件（哪怕是理论上的重名）也不会被覆盖；
* 只有**持有令牌**的一方才能接管那个名字（:func:`claim_reserved_backup_path`）：真正的
  归档随后写到同目录的临时文件，再用 ``os.replace`` 原子接管。所以「把一份已有备份当
  作自己的预留去覆盖」在实现上不可能发生，而进程中途崩死留下的也只是带令牌的占位文件
  （``validate`` 直接拒绝），不是一个半截（会损坏）的 ``.uebackup``；
* 预订名在同一微秒内被抢占（文件、目录、只要有目录项）时换一个 uuid 重试，重试用尽则
  显式抛 :class:`BackupPathError` —— 明确失败，绝不静默覆盖。
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

#: 自动安全备份前缀。既有代码与工具按这些前缀 glob，必须保持不变。
PRE_RESTORE_PREFIX = "pre-restore-"
PRE_MIGRATION_PREFIX = "pre-migration-"
PRE_PACKAGE_PREFIX = "pre-package-"

#: 备份扩展名（``BackupService.validate`` 只校验内容，扩展名是文件名约定）。
BACKUP_SUFFIX = ".uebackup"

#: 短 uuid 取前 8 个十六进制字符：名字够短，同一微秒内也足够区分。
_UNIQUE_TOKEN_LENGTH = 8

#: 同一微秒内的预订重试次数（每次换一个新 uuid）。
_RESERVATION_ATTEMPTS = 64

#: 预订文件名的时间戳格式：``YYYYMMDD-HHMMSS-ffffff``（含微秒）。
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S-%f"


class BackupPathError(RuntimeError):
    """无法为安全备份拿到一个全新路径（绝不退化为覆盖已有文件）。"""


def _token() -> str:
    return uuid4().hex[:_UNIQUE_TOKEN_LENGTH]


def _candidate(directory: Path, prefix: str) -> Path:
    stamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    return directory / f"{prefix}{stamp}-{_token()}{BACKUP_SUFFIX}"


#: 预订占位文件的内容前缀。占位文件不是归档（内容不是 ZIP），任何人都不能用它充当
#: 备份：``BackupService.validate`` 会直接拒绝，而真正的归档接管后这里的内容就被替换。
RESERVATION_MARKER_PREFIX = b"uebench-backup-reservation-v1:"


def _reservation_marker() -> bytes:
    return RESERVATION_MARKER_PREFIX + uuid4().hex.encode("ascii") + b"\n"


def _write_reservation(descriptor: int) -> None:
    """把预订令牌写进刚独占创建的文件（写失败则删掉占位，不留孤儿）。"""

    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_reservation_marker())


def _reserve(directory: Path, prefix: str) -> Path:
    """独占创建并返回一个此前不存在的备份路径（写入本进程专属预订令牌）。

    ``O_CREAT | O_EXCL`` 是全部关键：路径存在（普通文件、孤儿文件，甚至同名目录）时
    内核直接拒绝，调用方换名重试，任何情况下都不会打开已有文件做写入。
    """

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for _ in range(_RESERVATION_ATTEMPTS):
        candidate = _candidate(directory, prefix)
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        try:
            _write_reservation(descriptor)
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
        return candidate
    raise BackupPathError(
        f"无法为 {prefix}*.uebackup 预订一个未被占用的备份名（已重试 {_RESERVATION_ATTEMPTS} 次）："
        f"{directory}"
    )


def claim_reserved_backup_path(path: Path) -> Path:
    """接管一个**由本方法预订**的备份名，返回它的路径；否则显式失败。

    只有内容确实是预订令牌的文件才会被接管，所以 ``BackupService.create`` 的
    ``reserve=True`` 通道不可能把一份**已有备份**当成自己的预留去覆盖：真正的
    ``.uebackup`` 归档是 ZIP，读到的是 ``PK`` 魔数，这里直接抛
    :class:`BackupPathError`（并且不会打开那个文件做任何写入）。
    """

    path = Path(path)
    try:
        marker = path.read_bytes()
    except OSError as exc:
        raise BackupPathError(f"预订单据不可读，安全备份名未独占占用：{path}（{exc}）") from exc
    if not marker.startswith(RESERVATION_MARKER_PREFIX):
        raise BackupPathError(
            f"该路径不是本进程预订的安全备份名（未独占占用），拒绝覆盖：{path}"
        )
    return path


def reserve_unique_backup_path(directory: Path, prefix: str) -> Path:
    """预订一个全新的安全备份路径并返回它（调用方只给目录和前缀）。

    这是**唯一**的自动安全备份命名入口（pre-restore / pre-migration /
    pre-package 全部走它）：名字生成与独占占用发生在同一步，因此同一秒、同一微秒、
    甚至跨进程并发的调用都不可能拿到同一个路径，也不可能覆盖任何已存在的文件。
    调用方随后用 ``BackupService.create(path, reserve=True)`` 原子接管这个预定名。
    """

    return _reserve(directory, prefix)
