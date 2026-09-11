"""Resolve Stockfish without depending on a manually modified preview image.

Prefer an explicitly configured or installed engine. Fresh Debian-compatible
Linux runtimes can fetch a pinned, integrity-checked Debian package into a
writable cache without sudo, apt, or a package-manager dependency at runtime.
Only the known engine payload is extracted; archive paths are never executed.
"""
import hashlib
import io
import json
import logging
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)
RELEASE = json.loads((Path(__file__).parent / 'stockfish_release.json').read_text())
MAX_PACKAGE_BYTES = 64 * 1024 * 1024


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _engine_payload(package):
    """Read the data member of an ar-format .deb with Python's standard library."""
    if not package.startswith(b'!<arch>\n'):
        raise RuntimeError('Invalid Stockfish package archive.')
    offset = 8
    while offset + 60 <= len(package):
        header = package[offset:offset + 60]
        if header[58:60] != b'`\n':
            raise RuntimeError('Invalid Stockfish package header.')
        name = header[:16].decode('ascii').strip().rstrip('/')
        size = int(header[48:58].decode('ascii').strip())
        offset += 60
        content = package[offset:offset + size]
        if len(content) != size:
            raise RuntimeError('Truncated Stockfish package.')
        if name.startswith('data.tar'):
            with tarfile.open(fileobj=io.BytesIO(content), mode='r:*') as archive:
                for member in archive:
                    if member.name in ('./usr/games/stockfish', 'usr/games/stockfish') and member.isfile():
                        if member.size > MAX_PACKAGE_BYTES:
                            raise RuntimeError('Unexpected Stockfish executable size.')
                        payload = archive.extractfile(member)
                        if payload is not None:
                            return payload.read(MAX_PACKAGE_BYTES + 1)
            break
        offset += size + size % 2
    raise RuntimeError('Pinned package does not contain the Stockfish executable.')


def bootstrap_engine(cache_dir=None):
    machine = platform.machine().lower()
    arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64', 'amd64': 'amd64'}.get(machine)
    if platform.system() != 'Linux' or arch not in RELEASE['platforms']:
        raise RuntimeError('Install Stockfish for this platform and set STOCKFISH_PATH to its executable.')
    artifact = RELEASE['platforms'][arch]
    cache = Path(cache_dir or os.getenv('STOCKFISH_CACHE_DIR') or Path(tempfile.gettempdir()) / 'war-chess-engine')
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = cache / f'stockfish-{RELEASE["version"]}-{arch}'
    if target.is_file() and _sha256(target.read_bytes()) == artifact['binary_sha256']:
        target.chmod(0o700)
        return str(target)
    logger.info('Preparing pinned Stockfish %s for %s', RELEASE['version'], arch)
    request = urllib.request.Request(artifact['url'], headers={'User-Agent': 'WarChess-Engine-Bootstrap/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            package = response.read(MAX_PACKAGE_BYTES + 1)
        if len(package) > MAX_PACKAGE_BYTES or _sha256(package) != artifact['package_sha256']:
            raise RuntimeError('Stockfish package checksum mismatch; refusing to execute it.')
        binary = _engine_payload(package)
        if _sha256(binary) != artifact['binary_sha256']:
            raise RuntimeError('Stockfish executable checksum mismatch; refusing to execute it.')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=cache, prefix='.stockfish-', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(binary)
            temporary.chmod(0o700)
            probe = subprocess.run([str(temporary)], input='uci\nquit\n', text=True, capture_output=True, timeout=15, check=True)
            if 'uciok' not in probe.stdout:
                raise RuntimeError('Stockfish did not complete the UCI startup handshake.')
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except Exception as error:
        raise RuntimeError('Stockfish setup failed. Provide STOCKFISH_PATH or allow the pinned Debian download; Linux needs glibc >= 2.34 and libstdc++6 >= 12.') from error
    return str(target)


def resolve_engine_path():
    configured = os.getenv('STOCKFISH_PATH')
    if configured:
        if not Path(configured).is_file() or not os.access(configured, os.X_OK):
            raise RuntimeError('STOCKFISH_PATH must point to an existing executable.')
        return configured
    for candidate in (shutil.which('stockfish'), '/usr/games/stockfish'):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return bootstrap_engine()