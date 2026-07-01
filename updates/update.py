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
GITHUB_REPO = "darkhuysys-debug/tradesys-update"

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


def _github_latest_release():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "TradeSys-Bot"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tag_name", "").lstrip("v"), data.get("body", ""), data.get("html_url", ""), data
    except Exception as e:
        _log(f"GitHub API error: {e}")
        return None, None, None, None


def _download_file(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "TradeSys-Bot"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)


def _get_asset_url(release_data, filename):
    for asset in release_data.get("assets", []):
        if asset["name"] == filename:
            return asset["browser_download_url"]
    return None


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
            remote_ver, notes, url, release_data = _github_latest_release()
            _update_status["local_version"] = local_ver

            if not remote_ver:
                _update_status["error"] = "Cannot reach GitHub API"
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

            asset_name = f"TradeSys_update_v{remote_ver}.tar.gz"
            asset_url = _get_asset_url(release_data, asset_name)
            if not asset_url:
                _update_status["error"] = f"Missing asset: {asset_name}"
                _log(f"Asset not found in release")
                _update_status["checking"] = False
                return

            _download_file(asset_url, os.path.join(UPDATE_DIR, "update.tar.gz"))
            with tarfile.open(os.path.join(UPDATE_DIR, "update.tar.gz"), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("version.json"):
                        fobj = tar.extractfile(member)
                        if fobj:
                            meta = json.loads(fobj.read().decode())
                            _update_status["files"] = meta.get("files", [])
                            _update_status["available"] = True
                            _log(f"Update available: v{remote_ver} ({len(meta.get('files', []))} files)")
                            break
                else:
                    _update_status["files"] = []
                    _update_status["available"] = True
                    _log(f"Update available: v{remote_ver} (no manifest)")

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
        _update_status["error"] = "No files to install"
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
                raise ValueError("Update tarball not found. Please re-download.")

            # Step 1: Backup
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

            # Step 2: Extract and apply files from tarball
            _log("Extracting update...")
            with tarfile.open(tarball, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("version.json"):
                        continue
                    dest = os.path.join(BOT_DIR, member.name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    fobj = tar.extractfile(member)
                    if fobj:
                        with open(dest, "wb") as out:
                            out.write(fobj.read())
                        _log(f"Updated: {member.name}")
                        _update_status["progress"] = int((tar.getmembers().index(member) + 1) / total * 100)

            # Step 3: Clear cache
            _log("Clearing cache...")
            for root, dirs, files in os.walk(BOT_DIR):
                for d in list(dirs):
                    if d == "__pycache__":
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                        dirs.remove(d)

            # Step 4: Update VERSION
            with open(os.path.join(BOT_DIR, "VERSION"), "w") as f:
                f.write("v" + remote_ver + "\n")

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
