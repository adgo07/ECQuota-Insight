from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from typing import Iterator

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class StandardRow(Base):
    __tablename__ = "standards"

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_id: Mapped[str] = mapped_column(String(128), nullable=False)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
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
        Index("ux_standards_id_version", "standard_id", "version", unique=True),
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
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
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

    def initialize(self) -> None:
        from alembic import command
        from alembic.config import Config

        # PyInstaller 6 one-folder builds may expose ``_MEIPASS`` as either
        # the collected ``_internal`` directory or the application folder,
        # depending on bootloader/platform version.  Resolve both layouts so
        # a frozen install never stalls before the database is created merely
        # because the migration resource is one level deeper.
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
        config = Config()
        config.set_main_option("script_location", str(migrations))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{self.path.as_posix()}")
        # Early development builds created the same schema with SQLAlchemy
        # before Alembic was wired in.  A complete such database is safe to
        # adopt: stamp the initial migration instead of attempting to create
        # tables that already exist.  Partial databases are refused so we do
        # not silently mask a damaged or incompatible data directory.
        managed_tables = {
            "standards",
            "evaluations",
            "audit_log",
            "standard_packages",
            "import_batches",
        }
        existing_tables = set(inspect(self.engine).get_table_names())
        needs_stamp = False
        if managed_tables.issubset(existing_tables):
            if "alembic_version" not in existing_tables:
                needs_stamp = True
            else:
                with self.engine.connect() as connection:
                    has_version = connection.execute(text("SELECT 1 FROM alembic_version LIMIT 1")).first()
                needs_stamp = has_version is None
        if needs_stamp:
            # 旧版无Alembic标记的完整数据库按0001接管，再执行增量迁移；
            # 若生命周期字段已经存在，则直接标记为最新，避免重复加列。
            standard_columns = {column["name"] for column in inspect(self.engine).get_columns("standards")}
            command.stamp(config, "head" if "lifecycle_status" in standard_columns else "0001")
        command.upgrade(config, "head")

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
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", future=True)
        event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory.configure(bind=self.engine)
