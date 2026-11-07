"""Container entrypoint: prepare /data, drop privileges, migrate, start API.

Runs as root only to fix ownership of the mounted volume, then permanently
drops to the unprivileged ``appuser`` before touching application code.
"""

import os
import pwd
import subprocess
import sys


def ensure_dirs(data_dir: str, uid: int, gid: int) -> None:
    import pathlib

    for sub in ("database", "objects", "staging"):
        path = pathlib.Path(data_dir) / sub
        path.mkdir(parents=True, exist_ok=True)
    if os.getuid() == 0:
        for root, dirs, files in os.walk(data_dir):
            os.chown(root, uid, gid)
            for name in dirs + files:
                os.chown(os.path.join(root, name), uid, gid)


def drop_privileges(uid: int, gid: int) -> None:
    if os.getuid() != 0:
        return
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)


def main() -> None:
    try:
        appuser = pwd.getpwnam("appuser")
    except KeyError:
        print("appuser missing", file=sys.stderr)
        sys.exit(1)
    data_dir = os.environ.get("MUSIC_GATHERINGS_DATA_DIR", "/data")
    ensure_dirs(data_dir, appuser.pw_uid, appuser.pw_gid)
    drop_privileges(appuser.pw_uid, appuser.pw_gid)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd="/app",
        check=True,
    )
    args = sys.argv[1:]
    if args and (args[0] == "-m" or args[0].endswith(".py")):
        os.execvp(sys.executable, [sys.executable, *args])
    os.execvp("uvicorn", ["uvicorn", *args])


if __name__ == "__main__":
    main()
