from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python __main__.py` in addition to `python -m pac_framework`.
if not __package__:
    sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    from PyQt6.QtWidgets import QApplication
    from pac_framework.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
