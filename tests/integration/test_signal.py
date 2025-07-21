import subprocess
import time
import shutil
import pytest


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _docker_available(), reason="docker not available")
def test_graceful_shutdown(tmp_path):
    image = "ha-rag-bridge:ci"
    # build image without cache to ensure tini is included
    subprocess.run([
        "docker", "build", "--no-cache", "-t", image, "."], check=True
    )
    container_id = subprocess.check_output([
        "docker", "run", "-d", image
    ]).decode().strip()

    # give uvicorn time to start
    time.sleep(5)

    subprocess.run(["docker", "kill", "-s", "SIGTERM", container_id], check=True)
    # wait for container to exit
    exit_code = int(subprocess.check_output(["docker", "wait", container_id]).decode().strip())
    logs = subprocess.check_output(["docker", "logs", container_id]).decode()
    subprocess.run(["docker", "rm", container_id], check=True)

    assert exit_code == 0
    assert "Received SIGTERM" in logs
