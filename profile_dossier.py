"""Private deterministic profile products shared by the app and astrologist.

The app supplies its existing chart key. LLM prose is indexed separately and is
never a deterministic product or a reason to invalidate one.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'astrologist'))
import _paths
import pa_dossier
from l4_progressive import prepare, routed_for
from l4_routing import route, RoutingResult

DEFAULT_ROOT = ROOT / 'backend/.local-data/dossier'
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def locked(path):
    """OS locks release on process death; threads serialize before taking one."""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(str(path.resolve()), threading.Lock())
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as stream:
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                while True:
                    try:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(.02)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)


@lru_cache(maxsize=32)
def load_corpus(path, sha):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_hash(*paths):
    h = hashlib.sha256()
    for path in paths:
        h.update(Path(path).read_bytes())
    return h.hexdigest()


class Dossier:
    def __init__(self, root=DEFAULT_ROOT, versions=None):
        self.root = Path(root)
        self.versions = {
            'natal_corpus': file_hash(pa_dossier.CORPUS_PATH),
            'grounding': file_hash(ROOT / 'principles_grounding/ground.py'),
            'routing': pa_dossier.routing_version(),
            'plan': file_hash(ROOT / 'Interpretation_layer/l4_progressive.py'),
            'pa': file_hash(ROOT / 'astrologist/pa_dossier.py', ROOT / 'astrologist/pa_catalogue.py'),
            **(versions or {}),
        }

    def folder(self, chart_key):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,96}', chart_key):
            raise ValueError('Invalid chart identity')
        return self.root / chart_key

    def manifest(self, chart_key):
        return json.loads((self.folder(chart_key) / 'manifest.json').read_text(encoding='utf-8'))

    def register(self, chart_key, chart, birth=None, aliases=None):
        folder = self.folder(chart_key)
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            path = folder / 'manifest.json'
            if path.exists():
                manifest = self.manifest(chart_key)
                if manifest['chart_sha256'] != digest(chart):
                    raise ValueError('Chart identity collision')
                return manifest
            atomic(folder / 'a0/chart.json', chart)
            manifest = {'schema_version': 'profile-dossier-1', 'chart_key': chart_key,
                        'chart_sha256': digest(chart), 'birth': birth, 'aliases': aliases or {},
                        'versions': self.versions, 'products': {}}
            manifest['products']['chart'] = self._entry('chart', 'a0/chart.json', chart, {}, 0)
            atomic(path, manifest)
            return manifest

    def _entry(self, name, path, value, dependencies, elapsed, anchor=None):
        return {'name': name, 'tier': path.split('/')[0], 'anchor': anchor, 'path': path,
                'sha256': digest(value), 'depends_on': dependencies, 'status': 'ok', 'absence': None,
                'computed_at': datetime.now(timezone.utc).isoformat(), 'duration_ms': round(elapsed * 1000, 3)}

    def _cached(self, chart_key, product, dependencies):
        manifest = self.manifest(chart_key)
        entry = manifest['products'].get(product)
        if entry and entry['status'] == 'ok' and entry['depends_on'] == dependencies:
            path = self.folder(chart_key) / entry['path']
            if path.exists():
                value = json.loads(path.read_text(encoding='utf-8'))
                if digest(value) == entry['sha256']:
                    return value
        return None

    def get(self, chart_key, product, anchor=None):
        if product == 'chart':
            return json.loads((self.folder(chart_key) / 'a0/chart.json').read_text(encoding='utf-8'))
        if product not in ('natal_grounding', 'natal_plan', 'pa_dossier'):
            from dossier_products import get_product
            return get_product(self, chart_key, product, anchor)
        # Resolve dependencies outside the product lock (no recursive OS locks).
        grounded = self.get(chart_key, 'natal_grounding') if product != 'natal_grounding' else None
        plan = self.get(chart_key, 'natal_plan') if product == 'pa_dossier' else None
        names = ['natal_corpus', 'grounding']
        if product != 'natal_grounding':
            names += ['routing', 'plan' if product == 'natal_plan' else 'pa']
        dependencies = {name: self.versions[name] for name in names}
        dependencies['chart'] = self.manifest(chart_key)['chart_sha256']
        value = self._cached(chart_key, product, dependencies)
        if value is not None:
            return value
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            value = self._cached(chart_key, product, dependencies)
            if value is not None:
                return value
            start = time.perf_counter()
            chart = self.get(chart_key, 'chart')
            if product == 'natal_grounding':
                corpus = load_corpus(pa_dossier.CORPUS_PATH, self.versions['natal_corpus'])
                value = pa_dossier.ground_chart(chart, corpus)
            else:
                routing = (RoutingResult({k: routed_for(plan, k) for k in plan['order']}) if plan
                           else route(grounded['principles'], chart))
                value = (prepare(chart, grounded['principles'], chart_key=chart_key, routing=routing)
                         if product == 'natal_plan' else pa_dossier.build_dossier(
                             chart_key, chart, personal_principles=grounded, routing=routing,
                             corpus_sha=self.versions['natal_corpus']))
            path = f'a0/{product}.json'
            atomic(self.folder(chart_key) / path, value)
            manifest = self.manifest(chart_key)
            manifest['versions'].update(self.versions)
            manifest['products'][product] = self._entry(product, path, value, dependencies, time.perf_counter() - start)
            atomic(self.folder(chart_key) / 'manifest.json', manifest)
            return value

    def build_a0(self, chart_key, chart, birth=None):
        self.register(chart_key, chart, birth)
        return {name: self.get(chart_key, name) for name in ('chart', 'natal_grounding', 'natal_plan', 'pa_dossier')}

    def readings(self, chart_key):
        path = self.folder(chart_key) / 'readings.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def publish_section(self, chart_key, section):
        """First finalized text wins; translations add a language, never replace TR."""
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            index = self.readings(chart_key)
            existing = index.get(section['key'], {})
            value = {**section, **existing}
            for lang in ('tr', 'en'):
                field = 'text_' + lang
                if not existing.get(field) and section.get(field):
                    value[field] = section[field]
            index[section['key']] = value
            atomic(self.folder(chart_key) / 'readings.json', index)
            return value

    def retain(self, chart_key, reference):
        if not re.fullmatch(r'[a-f0-9]{64}', reference):
            raise ValueError('Invalid profile reference')
        folder = self.folder(chart_key)
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            if not (folder / 'manifest.json').exists():
                raise ValueError('Unknown dossier')
            path = folder / 'references.json'
            refs = json.loads(path.read_text()) if path.exists() else []
            atomic(path, sorted(set(refs + [reference])))

    def release(self, chart_key, reference):
        """Remove only a known reference; only its last release removes this chart."""
        import shutil
        folder = self.folder(chart_key)
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            path = folder / 'references.json'
            if not path.exists():
                return False  # Untracked legacy data is never erased by inference.
            refs = json.loads(path.read_text())
            if reference not in refs:
                return False
            remaining = [r for r in refs if r != reference]
            if remaining:
                atomic(path, remaining)
                return False
            # Resolve immediately before deletion, including symlinks/junctions.
            target, root = folder.resolve(), self.root.resolve()
            if target.parent != root or target == root:
                raise ValueError('Dossier deletion escaped its chart directory')
            shutil.rmtree(target)
            return True

    def memo(self, chart_key, product, anchor, dependencies, build, *, tier='a1', codec=None):
        """Versioned single-flight for deterministic products, including NPZ arrays."""
        if not re.fullmatch(r'[a-z0-9_]+', product):
            raise ValueError('Invalid product name')
        identity = product + ('-' + digest(anchor)[:24] if anchor is not None else '')
        relative = f"{tier}/{identity}.{'npz' if codec else 'json'}"
        path = self.folder(chart_key) / relative
        dependencies = {**dependencies, 'chart': self.manifest(chart_key)['chart_sha256']}
        def cached():
            entry = self.manifest(chart_key)['products'].get(identity)
            if entry and entry['depends_on'] == dependencies and entry['status'] in ('ok', 'absent') and path.exists() and file_hash(path) == entry['sha256']:
                return (codec[0](str(path)) if codec else json.loads(path.read_text(encoding='utf-8'))), True
            return None, False
        # Producers resolve their dossier dependencies before calling memo. Holding
        # the chart lifecycle lock through publication prevents last-reference
        # deletion from racing a build and resurrecting private files.
        with locked(self.root / '.locks' / (chart_key + '.lock')):
            value, hit = cached()
            if hit:
                return value
            start = time.perf_counter()
            try:
                value = build()
                if codec:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    fd, temporary = tempfile.mkstemp(suffix='.npz', dir=path.parent)
                    os.close(fd)
                    try:
                        codec[1](value, temporary)
                        os.replace(temporary, path)
                    finally:
                        if os.path.exists(temporary):
                            os.unlink(temporary)
                else:
                    atomic(path, value)
            except Exception as error:
                manifest = self.manifest(chart_key)
                entry = self._entry(product, relative, None, dependencies, time.perf_counter()-start, anchor)
                entry.update(status='failed', sha256=None, error_type=type(error).__name__)
                manifest['products'][identity] = entry
                atomic(self.folder(chart_key)/'manifest.json', manifest)
                raise
            manifest = self.manifest(chart_key)
            entry = self._entry(product, relative, {} if codec else value, dependencies, time.perf_counter()-start, anchor)
            entry['sha256'] = file_hash(path)
            if isinstance(value, dict) and value.get('status') == 'absent':
                entry.update(status='absent', absence=value.get('absence'))
            manifest['products'][identity] = entry
            atomic(self.folder(chart_key)/'manifest.json', manifest)
            return value

    def product_sha(self, chart_key, product, anchor=None):
        identity = product + ('-' + digest(anchor)[:24] if anchor is not None else '')
        return self.manifest(chart_key)['products'][identity]['sha256']
