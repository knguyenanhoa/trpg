#!/usr/bin/env python3
"""X-LRPG: A TUI RPG for real life."""

import sys

from app.tui.screen_manager import ScreenManager


def main():
    sm = ScreenManager()
    try:
        sm.run()
    except KeyboardInterrupt:
        pass
    finally:
        sm.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    main()
