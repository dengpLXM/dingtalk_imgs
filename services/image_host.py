"""Upload report images to remote server via SFTP and return HTTP URL."""
import os
from datetime import datetime
import paramiko


def _get_settings() -> dict:
    return {
        "host": os.getenv("UPLOAD_SFTP_HOST", ""),
        "port": int(os.getenv("UPLOAD_SFTP_PORT", "22")),
        "user": os.getenv("UPLOAD_SFTP_USER", ""),
        "password": os.getenv("UPLOAD_SFTP_PASS", ""),
        "remote_dir": os.getenv("UPLOAD_REMOTE_DIR", "/home/imgs"),
        "http_base": os.getenv("UPLOAD_HTTP_BASE", ""),
    }


def upload_image(img_bytes: bytes, task_id: int) -> str:
    """Upload image to remote server via SFTP, return HTTP URL."""
    settings = _get_settings()
    missing = [key for key in ("host", "user", "password", "http_base") if not settings[key]]
    if missing:
        raise RuntimeError(f"图片上传配置缺失: {', '.join(missing)}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{ts}.jpg"
    remote_path = f"{settings['remote_dir']}/{filename}"

    transport = paramiko.Transport((settings["host"], settings["port"]))
    try:
        transport.connect(username=settings["user"], password=settings["password"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.stat(settings["remote_dir"])
        except FileNotFoundError:
            sftp.mkdir(settings["remote_dir"])
        import io
        sftp.putfo(io.BytesIO(img_bytes), remote_path)
        sftp.close()
    finally:
        transport.close()

    return f"{settings['http_base'].rstrip('/')}/{filename}"


def is_configured() -> bool:
    settings = _get_settings()
    return all(settings[key] for key in ("host", "user", "password", "http_base"))
