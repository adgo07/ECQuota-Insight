from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import logging
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Iterator

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .paths import AppPaths

logger = logging.getLogger(__name__)

MANAGED_TABLES = frozenset(
    {
        "standards",
        "evaluations",
        "audit_log",
        "standard_packages",
        "import_batches",
    }
)


def resolve_migrations_directory() -> Path:
    """Locate the Alembic ``migrations/`` directory (source tree or frozen build).

    PyInstaller 6 one-folder builds may expose ``_MEIPASS`` as either
    the collected ``_internal`` directory or the application folder,
    depending on bootloader/platform version.  Resolve both layouts so
    a frozen install never stalls before the database is created merely
    because the migration resource is one level deeper.

    Raised as ``RuntimeError`` when no candidate exists — the same
    failure :meth:`DatabaseManager.initialize` has always produced.
    """

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is None:
        migration_candidates = [Path(__file__).resolve().parents[3] / "migrations"]
    else:
        root = Path(frozen_root)
        migration_candidates = [root / "migrations", root / "_internal" / "migrations"]
        executable_root = Path(sys.executable).resolve().parent
        migration_candidates.extend(
            [executable_root / "migrations", executable_root / "_internal" / "migrations"]
        )
    migrations = next((path for path in migration_candidates if path.exists()), None)
    if migrations is None:
        searched = ", ".join(str(path) for path in migration_candidates)
        raise RuntimeError(f"数据库迁移资源缺失，已搜索：{searched}")
    return migrations


def alembic_config(database_path: Path) -> Config:
    """Build the Alembic ``Config`` for ``database_path``.

    One shared construction for every consumer (schema upgrade *and* the
    restore-time schema compatibility check), so the restore path can never
    disagree with the migration path about where the migrations live.
    """

    config = Config()
    config.set_main_option("script_location", str(resolve_migrations_directory()))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{Path(database_path).as_posix()}")
    return config


class Base(DeclarativeBase):
    pass


class StandardRow(Base):
    __tablename__ = "standards"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_id: Mapped[str] = mapped_column(String(128), nullable=False)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_family_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    rule_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    obsolete_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    replaced_by_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    supersedes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    package_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    definition_json: Mapped[str] = mapped_column(Text, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("ux_standards_id_version_revision", "standard_id", "version", "rule_revision", unique=True),
        Index("ix_standards_number", "number"),
    )


class EvaluationRow(Base):
    __tablename__ = "evaluations"

    evaluation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    standard_id: Mapped[str] = mapped_column(String(128), nullable=False)
    standard_number: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    rule_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_evaluations_created", "created_at"),
        Index("ix_evaluations_standard", "standard_id"),
    )


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(128), default="LocalUser", nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class PackageRow(Base):
    __tablename__ = "standard_packages"

    package_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class ImportBatchRow(Base):
    __tablename__ = "import_batches"

    import_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    source_file: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    validation_json: Mapped[str] = mapped_column(Text, nullable=False)


class DatabaseManager:
    def __init__(self, path: Path, *, paths: "AppPaths | None" = None) -> None:
        self.path = path.resolve()
        self.paths = paths
        self.last_migration_backup: Path | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", future=True)
        event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    @staticmethod
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=FULL")
        cursor.close()

    def initialize(self, *, allow_pre_migration_backup: bool = True) -> Path | None:
        """Bring the schema to the Alembic head, backing the database up first.

        A pre-migration backup is written *only* when a real schema change is
        pending (or when a complete legacy database is about to be adopted).
        A database that is already at head is never backed up again, so repeated
        launches do not fill ``backups/`` with identical copies.

        Returns the path of the pre-migration backup, or ``None`` when no backup
        was needed.  The same value is kept on ``last_migration_backup``.
        """

        # 迁移脚本目录的定位（源码树 / 冻结安装两种布局）与 Alembic Config 的构造
        # 已抽成模块级函数，恢复前的 Schema 兼容性校验复用同一份实现，避免两条
        # 路径对“迁移在哪里”得出不同结论。
        config = alembic_config(self.path)
        # Early development builds created the same schema with SQLAlchemy
        # before Alembic was wired in.  A complete such database is safe to
        # adopt: stamp the initial migration instead of attempting to create
        # tables that already exist.  Partial databases are refused so we do
        # not silently mask a damaged or incompatible data directory.
        existing_tables = set(inspect(self.engine).get_table_names())
        needs_stamp = False
        if MANAGED_TABLES.issubset(existing_tables):
            if "alembic_version" not in existing_tables:
                needs_stamp = True
            else:
                with self.engine.connect() as connection:
                    has_version = connection.execute(text("SELECT 1 FROM alembic_version LIMIT 1")).first()
                needs_stamp = has_version is None
        script = ScriptDirectory.from_config(config)
        self.last_migration_backup = (
            self._create_pre_migration_backup(script)
            if allow_pre_migration_backup
            else None
        )
        if needs_stamp:
            # 旧版无Alembic标记的完整数据库按0001接管，再执行增量迁移；
            # 若生命周期字段已经存在，则直接标记为最新，避免重复加列。
            standard_columns = {column["name"] for column in inspect(self.engine).get_columns("standards")}
            command.stamp(config, "head" if "lifecycle_status" in standard_columns else "0001")
        command.upgrade(config, "head")
        return self.last_migration_backup

    def current_revision(self) -> str | None:
        """Return the applied Alembic revision, or ``None`` when unknown.

        ``None`` means "no usable ``alembic_version`` marker" (fresh database,
        pre-Alembic database) or "marker not present in this script directory".
        Both cases are treated as a pending migration.
        """

        with self.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

    def script_head(self, script: ScriptDirectory) -> str | None:
        head = script.get_current_head()
        return str(head) if head is not None else None

    def _create_pre_migration_backup(self, script: ScriptDirectory) -> Path | None:
        """Back the database up when ``command.upgrade`` is about to change it."""

        if not self.path.exists():
            logger.info("数据库尚不存在，跳过迁移前备份：%s", self.path)
            return None
        existing_tables = set(inspect(self.engine).get_table_names())
        if not existing_tables.intersection(MANAGED_TABLES):
            logger.info("数据库尚无业务表，跳过迁移前备份：%s", self.path)
            return None
        try:
            current = self.current_revision()
        except CommandError as exc:
            logger.warning("无法读取数据库当前版本，将按需迁移：%s", exc)
            current = None
        try:
            head = self.script_head(script)
        except CommandError as exc:
            logger.warning("无法读取迁移脚本目标版本，将执行迁移：%s", exc)
            head = None
        if current is not None and current == head:
            logger.info("数据库已在迁移目标版本 %s，无需迁移前备份", current)
            return None
        from .backup import BackupService
        from .backup_paths import PRE_MIGRATION_PREFIX, reserve_unique_backup_path

        # Reuse the sqlite online backup API through BackupService so the
        # snapshot is transactionally consistent: copying the live
        # ``.sqlite3``/``-wal``/``-shm`` files directly can lose committed
        # data or capture a torn database.
        #
        # One shared namer for every automatic safety backup: microsecond stamp
        # plus a short uuid, and the name is exclusively reserved before it is
        # written.  Two migrations in the same second therefore produce two
        # backups instead of the second silently overwriting the first.
        backups_dir = self.paths.backups if self.paths is not None else self.path.parent / "backups"
        backup_path = reserve_unique_backup_path(backups_dir, PRE_MIGRATION_PREFIX)

        logger.info(
            "检测到数据库迁移（当前版本 %s → 目标版本 %s），创建迁移前备份：%s",
            current if current is not None else "无标记",
            head if head is not None else "未知",
            backup_path,
        )
        return BackupService(self.paths, self).create(backup_path, reserve=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()

    def reconnect(self) -> None:
        """Replace the engine with a fresh one, disposing the previous engine first.

        Swapping the engine without disposing the old one leaks its pooled
        connection.  On Windows that leaked connection keeps the ``-wal`` /
        ``-shm`` sidecars open (``WinError 32``), which is exactly the "somebody
        still holds the old database file" state the restore chain must never
        leave behind.
        """
        self.dispose()
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", future=True)
        event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory.configure(bind=self.engine)
