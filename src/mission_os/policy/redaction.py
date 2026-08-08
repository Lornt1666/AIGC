"""Recursive secret redaction."""
import re
_SECRET_KEYS=re.compile(r"(token|password|secret|authorization|private[_-]?key|cookie)",re.I)
_SECRET_VALUE=re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|Bearer\s+\S+)",re.I)
def redact(value):
    if isinstance(value,dict):
        return {k:("[REDACTED]" if _SECRET_KEYS.search(str(k)) else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(x) for x in value]
    if isinstance(value,str): return _SECRET_VALUE.sub("[REDACTED]",value)
    return value
def contains_secret(value):
    if isinstance(value,dict): return any(_SECRET_KEYS.search(str(k)) or contains_secret(v) for k,v in value.items())
    if isinstance(value,list): return any(contains_secret(x) for x in value)
    return isinstance(value,str) and bool(_SECRET_VALUE.search(value))
