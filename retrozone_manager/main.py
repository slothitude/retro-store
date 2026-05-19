"""RetroZone Manager — entry point."""
import sys
import os

# Add parent dir so we can import from retro-store
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrozone_manager.app import RetroZoneApp


def main():
    app = RetroZoneApp()
    app.mainloop()


if __name__ == "__main__":
    main()
