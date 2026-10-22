"""Atomic JSON writes: readers see either the previous or the complete new file."""
import json
import os
import tempfile
from pathlib import Path

def write_json(path, value, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, **kwargs)
            f.flush()
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


from contextlib import contextmanager

@contextmanager
def atomic_text(path, **kwargs):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',**kwargs) as f:
            yield f
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
