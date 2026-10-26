# Adapted from jev-mem 0.4.0; MIT, copyright 2026 Daniel Illescas Romero.
# Full notice: LICENSE.jevmem in this package.
"""Local exact vector index; SQLite embeddings remain the source of truth."""
import sqlite3
import numpy as np

class MatrixIndex:
    name = "matrix"

    def __init__(self, db: sqlite3.Connection):
        self.db, self._loaded = db, False
        self.ids = np.zeros(0, dtype=np.int64); self.codes = np.zeros(0, dtype=np.int32); self.scope_code: dict[str, int] = {}
        self.mat = np.zeros((0, 0), dtype=np.float32)
        self._n = 0
        self._dv = None

    def _data_version(self) -> int:
        return self.db.execute("PRAGMA data_version").fetchone()[0]    # bumped only by commits of OTHER connections

    def _load(self) -> None:
        self._dv = self._data_version()
        rows = self.db.execute("SELECT id, scope, emb FROM nodes WHERE emb IS NOT NULL ORDER BY id").fetchall()
        self.ids = np.array([r[0] for r in rows], dtype=np.int64)
        self.scope_code = {}
        self.codes = np.array([self.scope_code.setdefault(r[1], len(self.scope_code)) for r in rows], dtype=np.int32)
        self.mat = np.stack([np.frombuffer(r[2], dtype=np.float32) for r in rows]) if rows else np.zeros((0, 0), np.float32)
        self._n, self._loaded = len(rows), True

    def add(self, nid, scope, vec):
        if not self._loaded:
            return                                    # will be read from SQLite on first search
        vec = vec.astype(np.float32)
        if self._n == 0 or self.mat.shape[1] == 0:
            self.mat = np.zeros((16, len(vec)), np.float32); self.ids = np.zeros(16, np.int64)
            self.codes = np.zeros(16, np.int32)
        elif self._n == len(self.mat):                # amortized doubling
            self.mat = np.vstack([self.mat, np.zeros_like(self.mat)])
            self.ids = np.concatenate([self.ids, np.zeros_like(self.ids)])
            self.codes = np.concatenate([self.codes, np.zeros_like(self.codes)])
        self.mat[self._n], self.ids[self._n] = vec, nid
        self.codes[self._n] = self.scope_code.setdefault(scope, len(self.scope_code))
        self._n += 1

    def remove(self, nid):
        self._loaded = False                          # rare; cheapest correct thing is to reload lazily

    def search(self, q, scopes, k, exclude=frozenset()):
        if not self._loaded or self._data_version() != self._dv:     # another process (hook, CLI) wrote or deleted notes
            self._load()
        if self._n == 0:
            return []
        sims = self.mat[:self._n] @ q.astype(np.float32)
        mask = np.ones(self._n, bool)
        if scopes:
            mask &= np.isin(self.codes[:self._n], [self.scope_code[x] for x in scopes if x in self.scope_code])
        if exclude:
            mask &= ~np.isin(self.ids[:self._n], list(exclude))
        # Round away last-bit differences between BLAS builds and break ties by id, so the same store ranks the same
        # on every platform (argpartition/argsort order ties arbitrarily). Keep every entry tied with the k-th.
        sims = np.where(mask, np.round(sims, 6), -np.inf)
        if self._n > k:
            top = np.flatnonzero(sims >= np.partition(sims, self._n - k)[self._n - k])
        else:
            top = np.arange(self._n)
        top = top[np.lexsort((self.ids[top], -sims[top]))][:k]
        return [(int(self.ids[i]), float(sims[i])) for i in top if np.isfinite(sims[i])]

    def rebuild(self, rows):
        self._loaded = False

    def size(self):
        return None


def make_index(db, dim, path, spec=None, n_nodes=0):
    if spec not in (None, "auto", "matrix"):
        raise ValueError("agemem supports only the local matrix note index")
    return MatrixIndex(db)
