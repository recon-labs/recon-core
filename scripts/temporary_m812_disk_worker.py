"""Temporary synthetic disk-backed spill and owned-worker experiments."""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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

def bytes_in(root):
    total=0
    for p in root.rglob("*"):
        try:
            if p.is_file():total+=p.stat().st_size
        except OSError:pass
    return total

def setup(root):
    db=root/"large.duckdb"
    n=3000000
    wide="||".join(f"md5((i+{j*n})::varchar)" for j in range(8))
    c=duckdb.connect(str(db),config={"threads":"2","memory_limit":"768MiB"})
    try:
        c.execute(f"create table src as select i k,{wide} wide,5::bigint v from range({n}) q(i)")
        c.execute("create table dst as select * from src")
        c.execute("checkpoint")
    finally:c.close()
    assert db.stat().st_size>512*MIB
    log("FIXTURE",n=n,bytes=db.stat().st_size)

def connect(db,spill,mem,threads,cap):
    c=duckdb.connect(str(db),read_only=True,config={"threads":str(threads),"memory_limit":f"{mem}MiB","temp_directory":str(spill)})
    try:
        c.execute(f"SET max_temp_directory_size='{cap}MiB'")
        log("SETTINGS",values=c.execute("select current_setting('memory_limit'),current_setting('threads'),current_setting('max_temp_directory_size')").fetchone())
        return c
    except BaseException:
        c.close();raise

def child(root,scratch,key,mem,threads,cap):
    db=root/"large.duckdb"
    spill=scratch/"spill"
    spill.mkdir()
    ident=_local_file_identity(ConnectionConfig(name="local",type="duckdb",config={"database":db.name}),root)
    assert ident is not None
    binding.import_module=lambda name:SimpleNamespace(connect=lambda path,read_only:connect(path,spill,mem,threads,cap))
    s=binding._OwnedDuckDbSession(ident)
    try:
        s.open()
        lease=s.bind(check_id="synthetic",operation="grouped_aggregate_diff",source="main.src",target="main.dst")
        assert lease is not None
        ops=tuple({"type":"grouped_aggregate","side":side,"aggregate":"sum","column":"v","group_by":[key]} for side in ("source","target"))+({"type":"compare_grouped_aggregates"},)
        plan=_DuckDbAggregateRuntimeRenderer().render_bound_grouped_plan(ops,source_relation=lease.scope.source,target_relation=lease.scope.target)
        for g in plan.type_guards:
            assert s._read_bound_aggregate(lease,lease.scope,g.sql,expected_columns=("type_check",)).row==(1,)
        proof=s._read_bound_aggregate(lease,lease.scope,plan.domain_guard.sql,expected_columns=("numeric_domain",))
        (scratch/"active").touch()
        t=time.monotonic()
        result=s._read_bound_aggregate(lease,lease.scope,plan.final_query(plan.domain_from_guard(proof)).sql,expected_columns=plan.columns)
        assert result.row==(3000000,0,0,0,0,3000000,0,0,0)
        log("RESULT",ok=True,seconds=round(time.monotonic()-t,4))
    except Exception as e:
        log("RESULT",ok=False,error=type(e).__name__)
    finally:
        log("CLOSE",released=s.close()==() and s.released,spill_remaining=bytes_in(spill))

def parent(root,mode,key,mem,threads,cap):
    base=Path("/scratch")
    assert (base/"probe-owned").is_file()
    scratch=Path(tempfile.mkdtemp(prefix="case-",dir=base))
    cg=Path("/sys/fs/cgroup")
    log("ENV",version=duckdb.__version__,memory_max=(cg/"memory.max").read_text().strip(),cpu_max=(cg/"cpu.max").read_text().strip(),scratch_free=shutil.disk_usage(base).free)
    db=root/"large.duckdb"
    observer=None
    fill=None
    if mode=="cancel":
        observer=duckdb.connect(str(db),read_only=True,config={"memory_limit":"96MiB","threads":"1","temp_directory":str(scratch/"observer")})
        before=observer.execute("select current_setting('memory_limit'),current_setting('threads')").fetchone()
    if mode=="full":
        fill=scratch/"filler"
        free=shutil.disk_usage(base).free
        with fill.open("wb") as f:os.posix_fallocate(f.fileno(),0,max(0,free-8*MIB))
        log("LOW_DISK",free=shutil.disk_usage(base).free)
    try:
        with tempfile.TemporaryFile(mode="w+t") as out:
            proc=subprocess.Popen([sys.executable,__file__,"child",str(root),str(scratch),key,str(mem),str(threads),str(cap)],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            peak=0; reason=None; t=time.monotonic()
            try:
                while proc.poll() is None:
                    peak=max(peak,bytes_in(scratch/"spill"))
                    if mode=="cancel" and (scratch/"active").is_file() and peak>0:
                        reason="active_spill_cancel";break
                    if time.monotonic()-t>55:
                        reason="deadline";break
                    time.sleep(.02)
                if reason is not None and proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
            out.seek(0);print(out.read(),end="",flush=True)
            log("SUPERVISOR",reason=reason,exit=proc.returncode,peak_spill_bytes=peak,stopped=proc.poll() is not None,spill_after_exit=bytes_in(scratch/"spill"))
        if observer is not None:
            after=observer.execute("select current_setting('memory_limit'),current_setting('threads')").fetchone()
            assert observer.execute("select count(*) from main.src").fetchone()==(3000000,)
            log("ISOLATION",before=before,after=after,unchanged=before==after)
    finally:
        if observer is not None:observer.close()
        shutil.rmtree(scratch)
        log("CLEANUP",removed=not scratch.exists(),free=shutil.disk_usage(base).free)
if __name__=="__main__":
    if sys.argv[1]=="setup":setup(Path(sys.argv[2]))
    elif sys.argv[1]=="child":child(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]))
    else:parent(Path(sys.argv[2]),sys.argv[3],sys.argv[4],int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7]))
