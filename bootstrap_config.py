from modules.config_defaults import ensure_local_config

if __name__ == "__main__":
    path = ensure_local_config(silent=False)
    print(f"[CONFIG] Ready: {path}")
