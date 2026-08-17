import os
import tempfile
import urllib.request
import urllib.parse
import hashlib
from typing import Tuple, Optional

TEMP_DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "open_matrix_downloads")
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

def is_remote_url(file_path: str) -> bool:
    """Check if the provided path is an HTTP/HTTPS remote URL."""
    if not file_path:
        return False
    lower = file_path.strip().lower()
    return lower.startswith("http://") or lower.startswith("https://")

def download_remote_video(url: str) -> Tuple[str, bool]:
    """
    Downloads a video from a remote URL to a local temporary file.
    Returns: (local_file_path, is_temp)
    """
    if not is_remote_url(url):
        return url, False

    try:
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
        parsed = urllib.parse.urlparse(url)
        base_name = os.path.basename(parsed.path) or f"video_{url_hash}.mp4"
        if not base_name.endswith((".mp4", ".mov", ".mkv", ".avi", ".flv")):
            base_name += ".mp4"
        
        target_path = os.path.join(TEMP_DOWNLOAD_DIR, f"{url_hash}_{base_name}")
        
        # If already cached, reuse
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1024:
            print(f"[URL Downloader] Reusing cached video: {target_path}")
            return target_path, True

        print(f"[URL Downloader] Streaming remote video from: {url}")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=120) as response, open(target_path, 'wb') as out_file:
            chunk_size = 1024 * 1024 # 1MB chunks
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
        
        print(f"[URL Downloader] Successfully downloaded {os.path.getsize(target_path)} bytes to {target_path}")
        return target_path, True
    except Exception as e:
        print(f"[URL Downloader Error] Failed to download {url}: {e}")
        raise RuntimeError(f"无法下载远程视频: {url}, 错误: {e}")

def cleanup_temp_video(file_path: str):
    """Purge temporary downloaded video file."""
    try:
        if file_path and file_path.startswith(TEMP_DOWNLOAD_DIR) and os.path.exists(file_path):
            os.remove(file_path)
            print(f"[URL Downloader] Purged temporary video: {file_path}")
    except Exception as e:
        print(f"[URL Downloader Warning] Cleanup failed: {e}")
