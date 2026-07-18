"""KetaDB file upload hook — adds resumable upload fields."""

import hashlib
import os
import time

from cliyard.engine.assembler import Request
from cliyard.plugin import register_hook


@register_hook("keta_upload")
def add_resumable_fields(req: Request) -> Request:
    """Add KetaDB resumable upload fields to query params."""
    if not req.files:
        return req

    file_path = None
    for val in req.files.values():
        # Value is either (filename, fileobj, type) or just fileobj
        if isinstance(val, tuple) and len(val) >= 2:
            fobj = val[1]
        else:
            fobj = val
        if hasattr(fobj, 'name'):
            file_path = fobj.name
            break

    if not file_path or not os.path.exists(file_path):
        return req

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    file_md5 = md5.hexdigest()

    req.query_params.setdefault("resumableChunkNumber", "1")
    req.query_params.setdefault("resumableChunkSize", str(max(file_size, 1)))
    req.query_params.setdefault("resumableCurrentChunkSize", str(file_size))
    req.query_params.setdefault("resumableTotalSize", str(file_size))
    req.query_params.setdefault("resumableType", "application/zip")
    req.query_params.setdefault("resumableIdentifier", file_md5)
    req.query_params.setdefault("resumableFilename", file_name)
    req.query_params.setdefault("resumableRelativePath", file_name)
    req.query_params.setdefault("resumableTotalChunks", "1")
    req.query_params.setdefault("resumableFileMd5", file_md5)
    req.query_params.setdefault("resumableModifyTime", str(int(time.time() * 1000)))

    return req
