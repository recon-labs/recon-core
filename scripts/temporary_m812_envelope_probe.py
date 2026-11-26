"""Temporary synthetic resource-envelope experiments; never merge."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace

import duckdb
from recon_core.adapters import ConnectionConfig
from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
from recon_core.adapters.duckdb.runtime_scan_guard import _local_file_identity

MIB=1024**2
def log(tag,**values):
    print(tag,json.dumps(values,sort_keys=True,default=str),flush=True)
def text(path):
    try:return Path(path).read_text().strip()
    except OSError:return None
def env():
    c=Path("/sys/fs/cgroup")
    fields={k:text(c/k) for k in ("memory.max","memory.current","memory.peak","memory.events","memory.swap.max","cpu.max","cpuset.cpus.effective")}
    log("ENV",version=duckdb.__version__,affinity=len(os.sched_getaffinity(0)),cgroup=text("/proc/self/cgroup"),limits=fields,disk=shutil.disk_usage("/scratch").free)
    return fields
def connect(db,spill,mem,threads,cap):
    c=duckdb.connect(str(db),read_only=True,config={"memory_limit":f"{mem}MiB","threads":str(threads),"temp_directory":str(spill)})
    try:
        c.execute(f"SET max_temp_directory_size='{cap}MiB'")
        return c
    except BaseException:
        c.close();raise
def size(path):
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
def setup(root):
    db=root/"large.duckdb"
    c=duckdb.connect(str(db),config={"threads":"2","memory_limit":"512MiB"})
    try:
        c.execute("create table src as select i k,md5(i::varchar)||md5((i+1000000)::varchar)||md5((i+2000000)::varchar)||md5((i+3000000)::varchar) wide,5::bigint v from range(1000000) q(i)")
        c.execute("create table dst as select * from src")
        c.execute("checkpoint")
    finally:c.close()
    assert db.stat().st_size>64*MIB
    log("FIXTURE",bytes=db.stat().st_size,n=1000000)
def isolation(db,root):
    # Same native instance sharing and subsequent fresh instance restoration.
    first=connect(db,root/"a",128,1,128)
    try:
        before=first.execute("select current_setting('memory_limit'),current_setting('threads')").fetchone()
        try:
            second=duckdb.connect(str(db),read_only=True)
            try:
                second.execute("SET memory_limit='256MiB'")
                second.execute("SET threads=2")
                after=first.execute("select current_setting('memory_limit'),current_setting('threads')").fetchone()
                log("ISOLATION",before=before,after=after,shared=before!=after)
            finally:second.close()
        except Exception as e:log("ISOLATION",second_open_error=type(e).__name__)
    finally:first.close()
    fresh=connect(db,root/"b",128,1,128)
    try:log("FRESH",values=fresh.execute("select current_setting('memory_limit'),current_setting('threads')").fetchone())
    finally:fresh.close()
def run(root,mem,threads,cap,mode):
    fields=env()
    assert fields["memory.max"] not in (None,"max")
    db=root/"large.duckdb"
    spill=Path("/scratch")/"spill"
    spill.mkdir(exist_ok=False)
    if mode=="isolation":
        isolation(db,spill);return
    binding.import_module=lambda name:SimpleNamespace(connect=lambda path,read_only:connect(path,spill,mem,threads,cap))
    identity=_local_file_identity(ConnectionConfig(name="local",type="duckdb",config={"database":db.name}),root)
    assert identity is not None
    session=binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease=session.bind(check_id="synthetic",operation="grouped_aggregate_diff",source="main.src",target="main.dst")
        assert lease is not None
        key="wide" if mode=="wide" else "k"
        ops=tuple({"type":"grouped_aggregate","side":s,"aggregate":"sum","column":"v","group_by":[key]} for s in ("source","target"))+({"type":"compare_grouped_aggregates"},)
        plan=_DuckDbAggregateRuntimeRenderer().render_bound_grouped_plan(ops,source_relation=lease.scope.source,target_relation=lease.scope.target)
        for g in plan.type_guards:assert session._read_bound_aggregate(lease,lease.scope,g.sql,expected_columns=("type_check",)).row==(1,)
        proof=session._read_bound_aggregate(lease,lease.scope,plan.domain_guard.sql,expected_columns=("numeric_domain",))
        t=time.monotonic()
        result=session._read_bound_aggregate(lease,lease.scope,plan.final_query(plan.domain_from_guard(proof)).sql,expected_columns=plan.columns)
        assert result.row==(1000000,0,0,0,0,1000000,0,0,0)
        log("RESULT",ok=True,seconds=round(time.monotonic()-t,5))
    except Exception as e:log("RESULT",ok=False,error=type(e).__name__)
    finally:
        log("CLOSE",released=session.close()==() and session.released,remaining_bytes=size(spill))
        log("CGROUP_AFTER",memory_peak=text("/sys/fs/cgroup/memory.peak"),events=text("/sys/fs/cgroup/memory.events"))
if __name__=="__main__":
    if sys.argv[1]=="setup":setup(Path(sys.argv[2]))
    else:run(Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),sys.argv[6])
