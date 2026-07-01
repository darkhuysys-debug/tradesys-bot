import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import tarfile
import io
import shutil
import threading
import time

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BOT_DIR, "backups")
UPDATE_DIR = os.path.join(BOT_DIR, "updates")
GITHUB_API = "https://api.github.com"
GITHUB_REPO = "darkhuysys-debug/tradesys-bot"

_update_status = {
    "checking": False,
    "available": False,
    "downloading": False,
    "installing": False,
    "done": False,
    "error": None,
    "remote_version": None,
    "local_version": None,
    "files": [],
    "log": [],
    "progress": 0,
}


def get_status():
    return _update_status


def get_local_version():
    try:
        with open(os.path.join(BOT_DIR, "VERSION")) as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _log(msg):
    _update_status["log"].append(msg)
    if len(_update_status["log"]) > 50:
        _update_status["log"] = _update_status["log"][-50:]


def _md5(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _github_latest_release_tag():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "TradeSys-Bot"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            tarball = data.get("tarball_url", "")
            return tag, tarball, data
    except Exception as e:
        _log(f"GitHub API error: {e}")
        return None, None, None


def _download_file(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "TradeSys-Bot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)


def check_update_async():
    if _update_status["checking"]:
        return
    _update_status["checking"] = True
    _update_status["available"] = False
    _update_status["error"] = None
    _update_status["log"] = []
    _update_status["files"] = []
    _update_status["progress"] = 0

    def _check():
        try:
            local_ver = get_local_version()
            remote_ver, tarball_url, release_data = _github_latest_release_tag()
            _update_status["local_version"] = local_ver

            if not remote_ver or not tarball_url:
                _update_status["error"] = "Cannot reach GitHub API or no releases found"
                _log("Failed to fetch release info")
                _update_status["checking"] = False
                return

            _update_status["remote_version"] = remote_ver
            _log(f"Local: {local_ver}, Remote: {remote_ver}")

            if remote_ver <= local_ver.lstrip("v"):
                _log("Already up to date")
                _update_status["available"] = False
                _update_status["checking"] = False
                return

            _download_file(tarball_url, os.path.join(UPDATE_DIR, "update.tar.gz"))
            _update_status["files"] = [{"path": "manifest (from tarball)", "type": "stable", "note": "full tarball"}]
            _update_status["available"] = True
            _log(f"Update available: v{remote_ver} (full tarball apply)")

            _update_status["error"] = None
        except Exception as e:
            _update_status["error"] = str(e)
            _log(f"Check error: {e}")
        finally:
            _update_status["checking"] = False

    t = threading.Thread(target=_check, daemon=True)
    t.start()


def _version_key(v):
    parts = v.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    result.append(len(v))
    return result


def install_update_async():
    if _update_status["downloading"] or _update_status["installing"]:
        return

    files = _update_status.get("files", [])
    if not files:
        _update_status["error"] = "No files to install. Please Scan Update first."
        return

    _update_status["downloading"] = True
    _update_status["installing"] = True
    _update_status["done"] = False
    _update_status["error"] = None
    _update_status["progress"] = 0
    _update_status["log"] = []
    total = len(files)

    remote_ver = _update_status.get("remote_version", get_local_version())
    tarball = os.path.join(UPDATE_DIR, "update.tar.gz")

    def _install():
        try:
            if not os.path.exists(tarball):
                raise ValueError("Update tarball not found. Please re-scan.")

            _log("Creating backup...")
            backup_name = f"v{get_local_version()}_{int(time.time())}"
            backup_path = os.path.join(BACKUP_DIR, backup_name)
            os.makedirs(backup_path, exist_ok=True)

            for item in os.listdir(BOT_DIR):
                if item in ("updates", "backups", "__pycache__"):
                    continue
                src = os.path.join(BOT_DIR, item)
                dst = os.path.join(backup_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(src, dst)
            _log(f"Backup saved: {backup_name}")

            _log("Extracting update...")
            with tarfile.open(tarball, "r:gz") as tar:
                members = [m for m in tar.getmembers() if not m.name.endswith(".git/") and not m.name.startswith(".git/")]
                for idx, member in enumerate(members):
                    if member.name in (".", "./"):
                        continue
                    dest = os.path.join(BOT_DIR, member.name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    fobj = tar.extractfile(member)
                    if fobj:
                        with open(dest, "wb") as out:
                            out.write(fobj.read())
                        _log(f"Updated: {member.name}")
                        _update_status["progress"] = int((idx + 1) / len(members) * 100)

            _log("Cleaning up old artifacts...")
            bad_dir = os.path.join(BOT_DIR, "tradesys-pkg")
            if os.path.isdir(bad_dir):
                shutil.rmtree(bad_dir, ignore_errors=True)
                _log(f"Removed bad directory: {bad_dir}")

            _log("Clearing cache...")
            for root, dirs, files in os.walk(BOT_DIR):
                for d in list(dirs):
                    if d == "__pycache__":
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                        dirs.remove(d)

            with open(os.path.join(BOT_DIR, "VERSION"), "w") as f:
                f.write("v" + remote_ver + "\\n")

            _update_status["progress"] = 100
            _update_status["done"] = True
            _update_status["available"] = False
            _log(f"Update complete: v{remote_ver}")
        except Exception as e:
            _update_status["error"] = str(e)
            _log(f"Update failed: {e}")
        finally:
            _update_status["downloading"] = False
            _update_status["installing"] = False

    t = threading.Thread(target=_install, daemon=True)
    t.start()


def rollback_async():
    if _update_status["downloading"] or _update_status["installing"]:
        _update_status["error"] = "Busy"
        return

    backups = sorted(os.listdir(BACKUP_DIR), reverse=True) if os.path.isdir(BACKUP_DIR) else []
    if not backups:
        _update_status["error"] = "No backups found"
        _log("Rollback failed: no backups")
        return

    latest = os.path.join(BACKUP_DIR, backups[0])

    def _rollback():
        try:
            _log(f"Rolling back to {backups[0]}...")
            for item in os.listdir(latest):
                src = os.path.join(latest, item)
                dst = os.path.join(BOT_DIR, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(src, dst)

            for root, dirs, files in os.walk(BOT_DIR):
                for d in list(dirs):
                    if d == "__pycache__":
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                        dirs.remove(d)

            _log(f"Rollback complete: {backups[0]}")
            _update_status["done"] = True
            _update_status["error"] = None
        except Exception as e:
            _update_status["error"] = str(e)
            _log(f"Rollback failed: {e}")

    t = threading.Thread(target=_rollback, daemon=True)
    t.start()
