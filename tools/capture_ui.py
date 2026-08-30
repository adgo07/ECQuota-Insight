from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from uebench.bootstrap import create_context
from uebench.main import configure_application_font
from uebench.ui.main_window import MainWindow


def main() -> None:
    output = Path("work/ui-home.png").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    configure_application_font(app)
    capture_root = Path(os.environ.get("UEBENCH_CAPTURE_ROOT", "work/ui-capture-data")).resolve()
    context = create_context(
        root=capture_root,
        public_key_path=Path("src/uebench/resources/update_public_key.pem").resolve(),
    )
    package = Path(
        os.environ.get(
            "UEBENCH_CAPTURE_PACKAGE",
            "dist/standard-packages/initial-standard-package-published.uebench",
        )
    ).resolve()
    if not context.standards.list_all() and context.package_service is not None and package.exists():
        context.package_service.install(package)
    window = MainWindow(context)
    window.show()
    app.processEvents()
    window.grab().save(str(output))
    print(output)
    window.navigation.setCurrentRow(1)
    window.standard_table.selectRow(0)
    app.processEvents()
    standards_output = output.with_name("ui-standards.png")
    window.grab().save(str(standards_output))
    print(standards_output)


if __name__ == "__main__":
    main()
