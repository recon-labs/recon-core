"""Temporary synthetic calibration of actual project-run resource policy."""
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import duckdb
from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.check_engine import CheckStatus
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services.test_run_service_aggregate_admission import (
    _aggregate_check,
    _CapturingAggregateEngine,
    _set_project_duckdb_execution,
)
from tests.services._run_service_fixtures import (
    write_compiled_checks, write_duckdb_row_count_run_inputs, _assert_no_runtime_outputs,
)

MIB=1<<20
CG=Path("/sys/fs/cgroup")
def log(tag,**values):
    print(tag,json.dumps(values,sort_keys=True,default=str),flush=True)

def setup(root):
    n=3000000
    for kind in ("large","small"):
        path=root/kind
        path.mkdir()
        db=path/"warehouse.duckdb"
        c=duckdb.connect(str(db),config={"threads":"2","memory_limit":"768MiB"})
        try:
            c.execute("create schema qa")
            if kind=="large":
                wide="||".join(f"md5((i+{j*n})::varchar)" for j in range(8))
                sql=f"select i as customer_id,1 as month,5::bigint as revenue,{wide} as padding from range({n}) q(i)"
            else:
                sql="select repeat('long-prefix-',32)||i::varchar as customer_id,1 as month,5::bigint as revenue from range(1000000) q(i)"
            c.execute("create table qa.source_customers as "+sql)
            c.execute("create table qa.target_customers as select * from qa.source_customers")
            c.execute("checkpoint")
        finally:
            c.close()
        log("FIXTURE",kind=kind,bytes=db.stat().st_size)
        if kind=="large":
            assert db.stat().st_size>512*MIB
        write_duckdb_row_count_run_inputs(path,db)
        write_compiled_checks(path,checks=[_aggregate_check(grouped=True)])

def run(root,base,kind,mode):
    path=root/kind
    db=path/"warehouse.duckdb"
    policy={"scratch-directory":str(base),"threads":1}
    if mode in ("fixed","low-disk"):
        policy.update({"managed-memory":{"mib":128},"spill":{"mib":1024}})
    elif mode=="percent":
        policy.update({"managed-memory":{"percent":75},"spill":{"percent":90}})
    elif mode=="capable":
        policy["threads"]=2
    _set_project_duckdb_execution(path,policy)
    before=db.stat()
    limit=int((CG/"memory.max").read_text().strip())
    log("ENV",engine=duckdb.__version__,memory_limit=limit,cpu=(CG/"cpu.max").read_text().strip(),disk_free=shutil.disk_usage(base).free,mode=mode,kind=kind,database_bytes=before.st_size)
    if kind=="large" and mode!="capable":
        assert before.st_size>limit
    observe=binding._observe_local_resources
    def measured(scratch):
        facts=observe(scratch)
        log("OBSERVATION",headroom=facts.memory_headroom_bytes,cpu=facts.cpu_capacity,free=facts.scratch_free_bytes,memory_backed=facts.scratch_memory_backed)
        assert facts.memory_headroom_bytes is not None and 0<facts.memory_headroom_bytes<=limit
        return facts
    binding._observe_local_resources=measured
    original_open=binding._OwnedDuckDbSession.open
    opened=[]
    def open_session(session):
        original_open(session)
        request=session._native_controls
        opened.append(session)
        log("TARGET",memory=request.memory_bytes,threads=request.threads,spill=request.spill_bytes)
    binding._OwnedDuckDbSession.open=open_session
    stop=threading.Event()
    peak=[0]
    def sample():
        while not stop.wait(.005):
            total=0
            for entry in base.rglob("*"):
                try:
                    if entry.is_file():total+=entry.stat().st_size
                except FileNotFoundError:
                    pass
            peak[0]=max(peak[0],total)
    sampler=threading.Thread(target=sample,daemon=True)
    observer=duckdb.connect(str(db),read_only=True)
    query="select current_setting('memory_limit'),current_setting('threads'),current_setting('temp_directory'),current_setting('max_temp_directory_size')"
    baseline=observer.execute(query).fetchone()
    engine=_CapturingAggregateEngine()
    start=time.monotonic()
    sampler.start()
    try:
        result=RunService(start_path=path,engine=engine).execute()
        assert engine.result is not None
        check=engine.result.contract_results[0].check_results[0]
        codes=[d.code for d in result.diagnostics]
        log("OUTCOME",status=check.status.value,executed=check.executed,exit=result.exit_category.value,codes=codes,seconds=round(time.monotonic()-start,3),peak_spill_bytes=peak[0],cgroup_peak=int((CG/"memory.peak").read_text().strip()))
        assert observer.execute(query).fetchone()==baseline
        assert observer.execute("SELECT 42").fetchone()==(42,)
        assert len(opened)==1 and opened[0].released
        if mode=="low-disk":
            assert check.status is CheckStatus.ERROR and not check.executed
            assert "RC_ADAPTER_QUERY_FAILED" in codes
        elif kind=="large":
            assert result.exit_category is ExitCategory.SUCCESS and check.status is CheckStatus.PASS
            assert check.executed
            if mode=="fixed":
                assert peak[0]>0, "No real spill observed under constrained fixed policy"
        else:
            assert check.status in (CheckStatus.PASS,CheckStatus.ERROR)
            if check.status is CheckStatus.ERROR:
                assert not check.executed and "RC_ADAPTER_QUERY_FAILED" in codes
    finally:
        stop.set();sampler.join(5);observer.close()
    assert not list(base.iterdir()),"Owned scratch residue"
    after=db.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    _assert_no_runtime_outputs(path)
    log("CLEANUP",released=True,observer_unchanged=True,scratch_empty=True,database_unchanged=True)

if sys.argv[1]=="setup":
    setup(Path(sys.argv[2]))
else:
    run(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],sys.argv[5])
