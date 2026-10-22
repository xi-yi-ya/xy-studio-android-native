"""Preserve optional certificate policy resources shipped with the build Python.

Some managed Python distributions load this PEM from SSLContext.__new__.
Bundle it unchanged; never bypass the policy or disable certificate validation.
Standard Python distributions do not require this extra file.
"""
from pathlib import Path
from PyInstaller.utils.hooks import get_module_file_attribute

policy = Path(get_module_file_attribute('ssl')).with_name('codex-rejected-cas.pem')
datas = [(str(policy), '.')] if policy.is_file() else []
