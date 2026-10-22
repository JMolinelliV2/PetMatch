"""Bounded cgroup v2 readings in Docker; no privileged mounts or persistent telemetry."""
from pathlib import Path


def container_resources(root=Path("/sys/fs/cgroup")):
    values={}
    for name,filename in (("memory_bytes","memory.current"),("memory_limit_bytes","memory.max")):
        try:
            value=(root/filename).read_text().strip()
            if value.isdecimal():values[name]=int(value)
        except OSError:pass
    try:
        stats=dict(line.split() for line in (root/"cpu.stat").read_text().splitlines())
        values["cpu_seconds_total"]=int(stats["usage_usec"])/1_000_000
    except (OSError,ValueError,KeyError):pass
    try:
        quota,period=(root/"cpu.max").read_text().split()
        if quota.isdecimal() and int(period)>0:values["cpu_limit_cores"]=int(quota)/int(period)
    except (OSError,ValueError):pass
    return values
