import os


def get_config_path():
    base = os.environ.get("MIKE_HOME", os.path.join(os.getcwd(), "config"))
    os.makedirs(base, exist_ok=True)
    return base


def db_path():
    return os.path.join(get_config_path(), "mike.db")