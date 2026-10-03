"""RS05：Alembic 迁移前自动备份。

Verifies that ``DatabaseManager.initialize`` writes a transactionally
consistent ``backups/pre-migration-*.uebackup`` snapshot exactly when a schema
change is pending — never on a fresh database, never without managed tables,
and never on a repeated launch that is already at the migration head.
"""

from __future__ import annotations

import shutil
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from uebench.bootstrap import create_context


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO_ROOT / "migrations"
HEAD = "0003"


def migrations_config(database_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def backups(paths) -> list[str]:
    return sorted(item.name for item in paths.backups.iterdir())


def revision_of(database_path: Path) -> str | None:
    """Read ``alembic_version.version_num`` with a plain sqlite3 connection."""

    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def extract_backup_database(backup: Path, destination: Path) -> Path:
    with zipfile.ZipFile(backup) as archive:
        assert "uebench.sqlite3" in archive.namelist()
        destination.write_bytes(archive.read("uebench.sqlite3"))
    return destination


def standard_numbers(database_path: Path) -> list[str]:
    with closing(sqlite3.connect(database_path)) as connection:
        return [str(row[0]) for row in connection.execute("SELECT number FROM standards ORDER BY number")]


def standard_columns(database_path: Path) -> set[str]:
    with closing(sqlite3.connect(database_path)) as connection:
        return {str(row[1]) for row in connection.execute("PRAGMA table_info(standards)")}


def standard_row_values(number: str) -> dict[str, object]:
    """Candidate values for one ``standards`` row, covering every revision."""

    return {
        "standard_id": f"sid-{number}",
        "number": number,
        "title": "title",
        "version": "2019",
        "status": "current",
        "publication_date": "2019-01-01",
        "effective_date": "2020-01-01",
        "source_file": "source.pdf",
        "source_sha256": "0" * 64,
        "definition_json": "{}",
        "installed_at": "2026-01-01 00:00:00",
        "package_id": None,
        "lifecycle_status": "active",
        "obsolete_date": None,
        "replaced_by_json": "[]",
        "supersedes_json": "[]",
        "standard_family_id": "GB",
        "rule_revision": 1,
    }


def standard_insert(database_path: Path, number: str, placeholder: str) -> tuple[str, dict[str, object]]:
    """Build an INSERT that only names columns the current revision provides.

    At revision ``0001`` the ``standards`` table has none of the lifecycle or
    version-identity columns, so a fixed column list cannot work across the
    pre/post-upgrade states this module deliberately exercises.
    """

    values = standard_row_values(number)
    selected = [name for name in values if name in standard_columns(database_path)]
    statement = (
        f"INSERT INTO standards ({', '.join(selected)}) "
        f"VALUES ({', '.join(placeholder.format(name=name) for name in selected)})"
    )
    return statement, {name: values[name] for name in selected}


def insert_standard_sql(database_path: Path, number: str) -> None:
    """Insert one ``standards`` row through raw sqlite3 (no SQLAlchemy engine)."""

    statement, parameters = standard_insert(database_path, number, ":{name}")
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(statement, parameters)
        connection.commit()


def insert_standard(context, number: str) -> None:
    """Insert one ``standards`` row through the managed SQLAlchemy engine."""

    statement, parameters = standard_insert(context.paths.database, number, ":{name}")
    with context.database.session() as session:
        session.execute(text(statement), parameters)


def database_at_0001(context) -> None:
    """Roll the managed database back to revision 0001 through real Alembic."""

    context.database.dispose()
    command.downgrade(migrations_config(context.paths.database), "0001")
    assert revision_of(context.paths.database) == "0001"


def test_fresh_database_creates_schema_without_backup(tmp_path: Path) -> None:
    context = create_context(tmp_path / "appdata")
    try:
        assert context.database.current_revision() == HEAD
        assert backups(context.paths) == []
        assert context.database.last_migration_backup is None
    finally:
        context.database.dispose()


def test_repeated_initialize_at_head_creates_no_backup(tmp_path: Path) -> None:
    root = tmp_path / "appdata"
    first = create_context(root)
    first.database.dispose()
    assert backups(first.paths) == []

    second = create_context(root)
    try:
        # ``create_context`` already ran ``initialize`` once on an at-head
        # database; run it twice more and confirm nothing is written.
        assert second.database.initialize() is None
        assert second.database.initialize() is None
        assert second.database.current_revision() == HEAD
        assert backups(second.paths) == []
    finally:
        second.database.dispose()


def test_pending_upgrade_backs_up_pre_upgrade_database(tmp_path: Path) -> None:
    context = create_context(tmp_path / "appdata")
    try:
        database_at_0001(context)
        insert_standard(context, "GB 11111-2019")
        # 0003 introduces the column; its absence proves the backup below is a
        # genuine pre-upgrade snapshot and not the already-migrated database.
        assert revision_of(context.paths.database) == "0001"
        assert "standard_family_id" not in standard_columns(context.paths.database)

        created = context.database.initialize()
        assert created is not None
        assert created == context.database.last_migration_backup
        assert created.parent == context.paths.backups
        assert created.name.startswith("pre-migration-")
        assert created.name.endswith(".uebackup")
        assert backups(context.paths) == [created.name]

        assert revision_of(context.paths.database) == HEAD
        assert standard_numbers(context.paths.database) == ["GB 11111-2019"]

        snapshot = extract_backup_database(created, tmp_path / "snapshot.sqlite3")
        assert revision_of(snapshot) == "0001"
        assert "standard_family_id" not in standard_columns(snapshot)
        assert standard_numbers(snapshot) == ["GB 11111-2019"]
    finally:
        context.database.dispose()


def test_failed_upgrade_keeps_database_and_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = create_context(tmp_path / "appdata")
    try:
        database_at_0001(context)
        insert_standard(context, "GB 22222-2019")

        def boom(*_args, **_kwargs):
            raise RuntimeError("simulated alembic upgrade failure")

        # ``alembic.command`` is imported as a module by ``initialize``, so
        # patching the attribute is enough; the sqlite backup path is untouched.
        monkeypatch.setattr("alembic.command.upgrade", boom)

        with pytest.raises(RuntimeError, match="simulated alembic upgrade failure"):
            context.database.initialize()

        # 1. the original database is kept and still intact at the old revision
        assert context.paths.database.exists()
        assert revision_of(context.paths.database) == "0001"
        assert standard_numbers(context.paths.database) == ["GB 22222-2019"]

        # 2. the pre-migration backup is kept as well and holds the same data
        monkeypatch.undo()
        assert context.database.last_migration_backup is not None
        assert context.database.last_migration_backup.exists()
        assert backups(context.paths) == [context.database.last_migration_backup.name]
        snapshot = extract_backup_database(context.database.last_migration_backup, tmp_path / "failed.sqlite3")
        assert revision_of(snapshot) == "0001"
        assert standard_numbers(snapshot) == ["GB 22222-2019"]

        # 3. a later successful initialize still upgrades to head
        context.database.initialize()
        assert revision_of(context.paths.database) == HEAD
    finally:
        context.database.dispose()


def test_backup_contains_rows_committed_to_wal(tmp_path: Path) -> None:
    context = create_context(tmp_path / "appdata")
    try:
        database_at_0001(context)
        insert_standard(context, "GB 33333-2019")

        # Fold the WAL back into the main file, then keep writing through a
        # second connection so the newest committed row can live in the WAL.
        with closing(sqlite3.connect(context.paths.database)) as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.commit()
        raw_writer = sqlite3.connect(context.paths.database)
        assert raw_writer.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        statement, parameters = standard_insert(context.paths.database, "GB 44444-2019", ":{name}")
        raw_writer.execute(statement, parameters)
        raw_writer.commit()
        raw_writer.close()

        created = context.database.initialize()
        assert created is not None
        snapshot = extract_backup_database(created, tmp_path / "wal.sqlite3")
        # The committed WAL data is present in the snapshot ...
        assert standard_numbers(snapshot) == ["GB 33333-2019", "GB 44444-2019"]
        # ... while a naive copy of only the main database file would miss it,
        # which is exactly why the online backup API is used instead.
        raw_copy = tmp_path / "raw-main-file.sqlite3"
        shutil.copy2(context.paths.database, raw_copy)
        assert standard_numbers(raw_copy) != ["GB 33333-2019", "GB 44444-2019"]

        assert revision_of(context.paths.database) == HEAD
        assert standard_numbers(context.paths.database) == ["GB 33333-2019", "GB 44444-2019"]
    finally:
        context.database.dispose()


def test_backup_archive_is_valid_uebackup(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    context = create_context(tmp_path / "appdata")
    try:
        database_at_0001(context)
        insert_standard(context, "GB 55555-2019")
        with caplog.at_level("INFO", logger="uebench.infrastructure.database"):
            created = context.database.initialize()
        assert created is not None

        with zipfile.ZipFile(created) as archive:
            names = set(archive.namelist())
        assert {"uebench.sqlite3", "manifest.json"} <= names

        manifest = context.backup_service.validate(created)
        assert manifest["schema_version"] == "1.0"
        assert "uebench.sqlite3" in manifest["files"]
        assert context.paths.database.exists()

        assert any(
            "创建迁移前备份" in record.getMessage() and record.levelno == 20
            for record in caplog.records
        ), caplog.text
    finally:
        context.database.dispose()


def test_pre_alembic_adoption_creates_backup(tmp_path: Path) -> None:
    """The legacy stamp path changes schema state, so it is backed up too."""

    from uebench.infrastructure.database import Base, DatabaseManager
    from uebench.infrastructure.paths import AppPaths

    paths = AppPaths.from_root(tmp_path / "legacy")
    paths.ensure()
    legacy = DatabaseManager(paths.database, paths=paths)
    Base.metadata.create_all(legacy.engine)
    legacy.dispose()

    adopted = create_context(tmp_path / "legacy")
    try:
        assert revision_of(paths.database) == HEAD
        assert backups(paths) == [adopted.database.last_migration_backup.name]
        assert adopted.database.last_migration_backup.name.startswith("pre-migration-")
    finally:
        adopted.database.dispose()
