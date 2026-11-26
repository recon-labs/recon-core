"""Temporary bounded synthetic calibration; never merge."""
import json
import os
import resource
import shutil
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
from recon_core.adapters.duckdb.renderer import DuckDbSqlRenderer
from recon_core.adapters.duckdb.runtime_scan_guard import _local_file_identity

MIB = 1024**2
def log(tag, **values):
    print(tag, json.dumps(values, default=str, sort_keys=True), flush=True)

def fixture(root, shape, n):
    db = root / f"{shape}.duckdb"
    if shape == "wide":
        key = "||".join(f"md5((i+{j*n})::varchar)" for j in range(4))
    else:
        key = "i::bigint"
    con = duckdb.connect(str(db), config={"threads":"2","memory_limit":"512MiB"})
    try:
        con.execute(f"create table src as select {key} k,i%17 j,5::bigint v from range({n}) q(i)")
        con.execute("create table dst as select * from src")
        con.execute("checkpoint")
    finally:
        con.close()
    log("FIXTURE",shape=shape,n=n,bytes=db.stat().st_size)
    return db

def child(db, spill, n, op, mem, threads, cap, placement):
    resource.setrlimit(resource.RLIMIT_FSIZE,(512*MIB,512*MIB))
    spill.mkdir()
    config = {"threads":str(threads),"memory_limit":f"{mem}MiB","temp_directory":str(spill)}
    if placement == "startup":
        config["max_temp_directory_size"] = f"{cap}MiB"
    def connect(path, *, read_only):
        con = duckdb.connect(path, read_only=read_only, config=config)
        try:
            if placement == "set":
                con.execute(f"SET max_temp_directory_size='{cap}MiB'")
            log("SETTINGS", values=con.execute("select name,value from duckdb_settings() where name in ('memory_limit','threads','temp_directory','max_temp_directory_size') order by name").fetchall())
            return con
        except BaseException:
            con.close()
            raise
    # Experiment-only native open injection; production session and read path unchanged.
    binding.import_module = lambda name: SimpleNamespace(connect=connect)
    ident = _local_file_identity(ConnectionConfig(name="local",type="duckdb",config={"database":db.name}),db.parent)
    assert ident is not None
    session = binding._OwnedDuckDbSession(ident)
    t=time.monotonic()
    try:
        session.open()
        family = {"group":"grouped_aggregate_diff","sum":"sum_diff","count":"row_count_diff","duplicate":"duplicate_source_keys","missing":"missing_keys"}[op]
        lease=session.bind(check_id="probe",operation=family,source="main.src",target="main.dst")
        assert lease is not None
        scope=lease.scope
        # Non-executing metadata in same connection and snapshot, synthetic only.
        estimates=session._connection.execute("select table_name,estimated_size from duckdb_tables() where table_name in ('src','dst') order by table_name").fetchall()
        log("ESTIMATES",values=estimates)
        if op in ("group","sum"):
            grouped=op=="group"
            ops=tuple({"type":"grouped_aggregate" if grouped else "aggregate","side":side,"aggregate":"sum","column":"v",**({"group_by":["k","j"]} if grouped else {})} for side in ("source","target"))+({"type":"compare_grouped_aggregates" if grouped else "compare_aggregates"},)
            renderer=_DuckDbAggregateRuntimeRenderer()
            render=renderer.render_bound_grouped_plan if grouped else renderer.render_plan
            plan=render(ops,source_relation=scope.source,target_relation=scope.target)
            for guard in plan.type_guards:
                assert session._read_bound_aggregate(lease,scope,guard.sql,expected_columns=("type_check",)).row==(1,)
            proof=session._read_bound_aggregate(lease,scope,plan.domain_guard.sql,expected_columns=("numeric_domain",))
            query=plan.final_query(plan.domain_from_guard(proof)).sql
            expected=(n,0,0,0,0,n,0,0,0) if grouped else (5*n,5*n,0)
            start=time.monotonic()
            result=session._read_bound_aggregate(lease,scope,query,expected_columns=plan.columns)
            assert result.row==expected
        else:
            renderer=DuckDbSqlRenderer()
            if op=="count":
                operation={"type":"compare_counts"}
            elif op=="duplicate":
                operation={"type":"duplicate_key","side":"source","keys":["k","j"]}
            else:
                operation={"type":"key_diff","direction":"source_minus_target","keys":["k","j"]}
            query=renderer.render_operation(operation,source_relation=scope.source,target_relation=scope.target).sql
            if op!="count":
                query=f"select count(*) as failure_count from ({query}) as recon_key_safety_failures"
            start=time.monotonic()
            result=session._read_bound_query(lease,scope,query)
            assert result.rows==((n,n,0),) if op=="count" else result.rows==((0,),)
        log("RESULT",ok=True,query_s=round(time.monotonic()-start,5),elapsed_s=round(time.monotonic()-t,5),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    except Exception as exc:
        log("RESULT",ok=False,error=type(exc).__name__,elapsed_s=round(time.monotonic()-t,5))
    finally:
        log("CLOSE",diagnostics=[d.code for d in session.close()],released=session.released)
def size(path):
    total=0
    for p in path.rglob("*"):
        try:
            if p.is_file(): total+=p.stat().st_size
        except OSError: pass
    return total

def parent():
    log("ENV",version=duckdb.__version__,affinity=len(os.sched_getaffinity(0)),mem_available=next((l for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemAvailable:")),None),cgroup=Path("/proc/self/cgroup").read_text().strip())
    with tempfile.TemporaryDirectory(prefix="recon-m812-") as d:
        root=Path(d)
        log("DISK",free=shutil.disk_usage(root).free)
        assert shutil.disk_usage(root).free>3*1024**3
        for shape,n in (("small",800000),("wide",400000)):
            db=fixture(root,shape,n)
            cases=[("count",128,1,512,"set"),("sum",128,1,512,"set"),("duplicate",256,1,512,"set"),("missing",256,1,512,"set"),("group",128,1,512,"set"),("group",256,1,512,"set"),("group",512,2,512,"set"),("group",128,1,1,"startup"),("group",128,1,1,"set")]
            for i,(op,mem,threads,cap,placement) in enumerate(cases):
                spill=root/f"spill-{shape}-{i}"
                with tempfile.TemporaryFile(mode="w+t") as output:
                    p=subprocess.Popen([sys.executable,__file__,"child",str(db),str(spill),str(n),op,str(mem),str(threads),str(cap),placement],stdout=output,stderr=subprocess.STDOUT)
                    start=time.monotonic(); peak=0; rss=0; stop=None
                    while p.poll() is None:
                        peak=max(peak,size(spill))
                        try:
                            for l in Path(f"/proc/{p.pid}/status").read_text().splitlines():
                                if l.startswith("VmRSS:"):rss=max(rss,int(l.split()[1])*1024)
                        except OSError:pass
                        if time.monotonic()-start>20:stop="deadline"
                        elif peak>768*MIB:stop="sampled_spill_guard"
                        elif rss>1024*MIB:stop="sampled_rss_guard"
                        if stop:p.kill();break
                        time.sleep(.04)
                    p.wait(timeout=5);output.seek(0);print(output.read(),end="",flush=True)
                    log("CASE",shape=shape,n=n,op=op,mem_mib=mem,threads=threads,cap_mib=cap,placement=placement,stop=stop,rc=p.returncode,sampled_peak_spill_bytes=peak,sampled_peak_rss_bytes=rss,spill_after_close=size(spill))
                if spill.exists():shutil.rmtree(spill)
            db.unlink()
        log("COMPLETE",cases=18)
    log("ROOT_CLEANUP",removed=not root.exists())

if __name__=="__main__":
    if len(sys.argv)==1:parent()
    else:child(Path(sys.argv[2]),Path(sys.argv[3]),int(sys.argv[4]),sys.argv[5],int(sys.argv[6]),int(sys.argv[7]),int(sys.argv[8]),sys.argv[9])
