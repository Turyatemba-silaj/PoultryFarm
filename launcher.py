import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def app_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_root():
    return Path(getattr(sys, '_MEIPASS', app_root())).resolve()


def prepare_database(root, bundled):
    data_dir = root / 'data'
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / 'db.sqlite3'
    bundled_db = bundled / 'db.sqlite3'
    if not db_path.exists() and bundled_db.exists():
        shutil.copy2(bundled_db, db_path)
    return db_path


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def open_browser(url):
    time.sleep(2)
    webbrowser.open(url)


def main():
    root = app_root()
    bundled = bundle_root()
    db_path = prepare_database(root, bundled)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PoultryFarm.settings')
    os.environ.setdefault('DEBUG', 'True')
    os.environ.setdefault('ALLOWED_HOSTS', 'localhost,127.0.0.1')
    os.environ['BUNDLE_DIR'] = str(bundled)
    os.environ['SQLITE_PATH'] = str(db_path)

    import django
    from django.core.management import call_command, execute_from_command_line

    django.setup()
    call_command('migrate', interactive=False, verbosity=0)

    port = free_port()
    url = f'http://127.0.0.1:{port}/'
    print(f'Poultry Farm is running at {url}')
    print('Keep this window open while using the application.')
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    execute_from_command_line(['PoultryFarm.exe', 'runserver', f'127.0.0.1:{port}', '--noreload'])


if __name__ == '__main__':
    main()
