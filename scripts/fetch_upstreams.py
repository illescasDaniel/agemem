"""Fetch source into ignored vendor/ at reviewed commits. Does not install or start services."""
import subprocess
from pathlib import Path

UPSTREAMS = {
    "RAW-RAG": ("https://github.com/Litmeb/RAW-RAG.git", "95639191e9547219b426710e50fe1a36235e26fc"),
    "TencentDB-Agent-Memory": ("https://github.com/TencentCloud/TencentDB-Agent-Memory.git", "65730e979a5a590c54adc181ba8a375055410b84"),
}


def main():
    Path("vendor").mkdir(exist_ok=True)
    for name, (url, sha) in UPSTREAMS.items():
        path = Path("vendor") / name
        if path.exists():
            actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
            if actual != sha:
                raise RuntimeError(f"Existing {name} has another revision; refusing to reset it")
            print(name, actual, "already present")
            continue
        subprocess.run(["git", "init", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", url], check=True)
        subprocess.run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", sha], check=True)
        subprocess.run(["git", "-C", str(path), "checkout", "--detach", "FETCH_HEAD"], check=True)


if __name__ == "__main__":
    main()
