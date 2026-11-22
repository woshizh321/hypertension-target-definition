"""Local identity checks using a separately trusted private authority."""
import hashlib
import json
import os
import stat
from pathlib import Path

REFERENCE_SCHEMA = 'stab01-frozen-reference-v1'
AUTHORITY_SCHEMA = 'stab01-private-authority-v1'
REQUIRED = frozenset({'protocol','plan','feasibility','model_code','executed_common','analytic','oof','folds','lock'})

class IdentityError(ValueError):
    """The private authority, frozen reference, or input files are unavailable or inconsistent."""

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IdentityError('Duplicate JSON key')
        result[key] = value
    return result

def _sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _digest(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def verify_frozen_inputs(reference_path, input_records):
    """Check inputs using an independently provisioned, locally trusted authority."""
    try:
        authority_name = os.environ.get('STAB01_PRIVATE_AUTHORITY')
        if not authority_name:
            raise IdentityError('Trusted private authority is required')
        authority_path = Path(authority_name)
        info = authority_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise IdentityError('Private authority must be an owner-only regular file')
        if hasattr(os,'getuid') and info.st_uid != os.getuid():
            raise IdentityError('Private authority owner mismatch')
        authority = json.loads(authority_path.read_bytes(),object_pairs_hook=_unique)
        if not isinstance(authority,dict) or set(authority) != {'schema','reference_sha256'} or authority['schema'] != AUTHORITY_SCHEMA or not _digest(authority['reference_sha256']):
            raise IdentityError('Invalid private authority')
        raw = Path(reference_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != authority['reference_sha256']:
            raise IdentityError('Private reference does not match trusted authority')
        ref = json.loads(raw, object_pairs_hook=_unique)
        canonical = (json.dumps(ref,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
        if raw != canonical or set(ref) != {'schema','source_sha256','input_sha256'}:
            raise IdentityError('Noncanonical frozen reference')
        if ref['schema'] != REFERENCE_SCHEMA or not _digest(ref['source_sha256']):
            raise IdentityError('Invalid reference version or source identity')
        fingerprints = ref['input_sha256']
        if not isinstance(fingerprints,dict) or set(fingerprints) != REQUIRED:
            raise IdentityError('Incomplete frozen reference')
        if not isinstance(input_records,dict) or set(input_records) != REQUIRED:
            raise IdentityError('Incorrect input manifest names')
        verified = {}
        for name in sorted(REQUIRED):
            expected = fingerprints[name]
            record = input_records[name]
            if not _digest(expected):
                raise IdentityError('Invalid frozen fingerprint')
            if not isinstance(record,dict) or set(record) != {'path','sha256'} or record['sha256'] != expected:
                raise IdentityError('Input record differs from private reference: '+name)
            path = Path(record['path']).resolve(strict=True)
            if not path.is_file() or _sha(path) != expected:
                raise IdentityError('Input bytes differ from private reference: '+name)
            verified[name] = (path, expected)
        return verified
    except IdentityError:
        raise
    except (OSError,ValueError,KeyError,TypeError,UnicodeError) as exc:
        raise IdentityError('Unable to verify private authority and inputs') from exc
