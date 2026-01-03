try:
    import config
    import roms
    import input
    import ui
    import main
    print("All modules imported successfully.")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Error: {e}")
