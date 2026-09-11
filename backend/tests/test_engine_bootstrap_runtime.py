import hashlib
import os
import shutil
import stat
from pathlib import Path

import chess
import chess.engine
import pytest

import engine_bootstrap


# Stockfish bootstrap runtime tests for cold cache, integrity, fallback, and path precedence.


@pytest.fixture(scope='module')
def cold_cache_dir(tmp_path_factory):
    cache = tmp_path_factory.mktemp('stockfish-cold-cache')
    yield cache
    shutil.rmtree(cache, ignore_errors=True)


@pytest.fixture(scope='module')
def bootstrapped_engine_path(cold_cache_dir):
    path = engine_bootstrap.bootstrap_engine(cache_dir=str(cold_cache_dir))
    return Path(path)


def _artifact_for_current_arch():
    machine = engine_bootstrap.platform.machine().lower()
    arch = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64', 'amd64': 'amd64'}.get(machine)
    assert arch in engine_bootstrap.RELEASE['platforms'], f'Unsupported test host arch: {machine}'
    return arch, engine_bootstrap.RELEASE['platforms'][arch]


def test_cold_bootstrap_download_and_cache_real_binary(bootstrapped_engine_path, cold_cache_dir):
    assert bootstrapped_engine_path.exists()
    assert str(bootstrapped_engine_path).startswith(str(cold_cache_dir))
    assert str(bootstrapped_engine_path) != '/usr/games/stockfish'

    mode = bootstrapped_engine_path.stat().st_mode
    assert bool(mode & stat.S_IXUSR)

    _, artifact = _artifact_for_current_arch()
    digest = hashlib.sha256(bootstrapped_engine_path.read_bytes()).hexdigest()
    assert digest == artifact['binary_sha256']


def test_bootstrapped_binary_runs_uci_and_plays_legal_move_not_system(bootstrapped_engine_path):
    assert str(bootstrapped_engine_path) != '/usr/games/stockfish'

    board = chess.Board()
    with chess.engine.SimpleEngine.popen_uci(str(bootstrapped_engine_path), timeout=15) as engine:
        result = engine.play(board, chess.engine.Limit(time=0.05, depth=4))

    assert result.move is not None
    assert result.move in board.legal_moves


def test_cached_verified_binary_reused_when_network_unavailable(cold_cache_dir, monkeypatch):
    monkeypatch.setattr(engine_bootstrap.urllib.request, 'urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('network disabled')))
    reused = Path(engine_bootstrap.bootstrap_engine(cache_dir=str(cold_cache_dir)))
    assert reused.exists()


def test_corrupted_cached_binary_not_trusted_without_network(cold_cache_dir, monkeypatch):
    path = Path(engine_bootstrap.bootstrap_engine(cache_dir=str(cold_cache_dir)))
    path.write_bytes(path.read_bytes() + b'corruption')

    monkeypatch.setattr(engine_bootstrap.urllib.request, 'urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('network disabled')))
    with pytest.raises(RuntimeError, match='Stockfish setup failed'):
        engine_bootstrap.bootstrap_engine(cache_dir=str(cold_cache_dir))


def test_checksum_mismatch_fails_closed_before_execution(monkeypatch, tmp_path):
    arch, artifact = _artifact_for_current_arch()
    payload = b'not-a-real-debian-archive'

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _size=-1):
            return payload

    release_copy = {
        'version': engine_bootstrap.RELEASE['version'],
        'platforms': dict(engine_bootstrap.RELEASE['platforms']),
    }
    platform_entry = dict(artifact)
    platform_entry['package_sha256'] = '0' * 64
    release_copy['platforms'][arch] = platform_entry

    probe_called = {'value': False}

    def _probe(*_args, **_kwargs):
        probe_called['value'] = True
        raise AssertionError('UCI probe should not run on checksum mismatch')

    monkeypatch.setattr(engine_bootstrap, 'RELEASE', release_copy)
    monkeypatch.setattr(engine_bootstrap.urllib.request, 'urlopen', lambda *args, **kwargs: _Resp())
    monkeypatch.setattr(engine_bootstrap.subprocess, 'run', _probe)

    with pytest.raises(RuntimeError, match='Stockfish setup failed'):
        engine_bootstrap.bootstrap_engine(cache_dir=str(tmp_path / 'checksum-fail-cache'))
    assert probe_called['value'] is False


def test_invalid_archive_fails_closed_without_execution(monkeypatch, tmp_path):
    arch, artifact = _artifact_for_current_arch()
    payload = b'invalid-ar-format'
    package_sha = hashlib.sha256(payload).hexdigest()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _size=-1):
            return payload

    release_copy = {
        'version': engine_bootstrap.RELEASE['version'],
        'platforms': dict(engine_bootstrap.RELEASE['platforms']),
    }
    platform_entry = dict(artifact)
    platform_entry['package_sha256'] = package_sha
    release_copy['platforms'][arch] = platform_entry

    probe_called = {'value': False}

    def _probe(*_args, **_kwargs):
        probe_called['value'] = True
        raise AssertionError('UCI probe should not run on invalid archive')

    monkeypatch.setattr(engine_bootstrap, 'RELEASE', release_copy)
    monkeypatch.setattr(engine_bootstrap.urllib.request, 'urlopen', lambda *args, **kwargs: _Resp())
    monkeypatch.setattr(engine_bootstrap.subprocess, 'run', _probe)

    with pytest.raises(RuntimeError, match='Stockfish setup failed'):
        engine_bootstrap.bootstrap_engine(cache_dir=str(tmp_path / 'archive-fail-cache'))
    assert probe_called['value'] is False


def test_unsupported_platform_returns_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(engine_bootstrap.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(engine_bootstrap.platform, 'machine', lambda: 'arm64')
    with pytest.raises(RuntimeError, match='Install Stockfish for this platform and set STOCKFISH_PATH'):
        engine_bootstrap.bootstrap_engine(cache_dir=str(tmp_path / 'unsupported-platform'))


def test_invalid_explicit_stockfish_path_returns_clear_error(monkeypatch):
    monkeypatch.setenv('STOCKFISH_PATH', '/tmp/definitely-not-an-engine')
    with pytest.raises(RuntimeError, match='STOCKFISH_PATH must point to an existing executable'):
        engine_bootstrap.resolve_engine_path()


def test_resolve_engine_path_precedence_explicit_then_system_then_bootstrap(monkeypatch, tmp_path):
    fake_engine = tmp_path / 'fake-stockfish'
    fake_engine.write_text('#!/bin/sh\necho fake\n')
    fake_engine.chmod(0o700)

    monkeypatch.setenv('STOCKFISH_PATH', str(fake_engine))
    monkeypatch.setattr(engine_bootstrap.shutil, 'which', lambda _name: '/usr/games/stockfish')
    assert engine_bootstrap.resolve_engine_path() == str(fake_engine)

    monkeypatch.delenv('STOCKFISH_PATH', raising=False)
    monkeypatch.setattr(engine_bootstrap.shutil, 'which', lambda _name: '/usr/games/stockfish')
    assert engine_bootstrap.resolve_engine_path() == '/usr/games/stockfish'

    original_is_file = Path.is_file

    def _is_file(self):
        if str(self) == '/usr/games/stockfish':
            return False
        return original_is_file(self)

    monkeypatch.setattr(Path, 'is_file', _is_file)
    monkeypatch.setattr(engine_bootstrap.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(engine_bootstrap, 'bootstrap_engine', lambda cache_dir=None: '/tmp/bootstrap-stockfish')

    assert engine_bootstrap.resolve_engine_path() == '/tmp/bootstrap-stockfish'
