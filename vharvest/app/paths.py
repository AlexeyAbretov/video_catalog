from urllib.parse import quote


def _parts(relative: str) -> list[str]:
    return [part for part in relative.replace("\\", "/").split("/") if part and part != "."]


def parent_relative(relative: str) -> str:
    parts = _parts(relative)
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def parent_dir_name(relative: str) -> str:
    parts = _parts(parent_relative(relative))
    if not parts:
        return ""
    return parts[-1]


def unc_path(host: str, share: str, relative: str) -> str:
    tail = "\\".join(_parts(relative))
    base = f"\\\\{host}\\{share}"
    if not tail:
        return base
    return base + "\\" + tail


def smb_url(host: str, share: str, relative: str) -> str:
    chunks = [quote(share, safe="")]
    chunks.extend(quote(part, safe="") for part in _parts(relative))
    return f"smb://{host}/" + "/".join(chunks)


def smb_dir_url(host: str, share: str, relative: str) -> str:
    url = smb_url(host, share, relative)
    if not url.endswith("/"):
        url += "/"
    return url
