"""Temporary synthetic calibration of actual project-run resource policy."""
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from dataclasses import replace

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
    policy={"scratch-directory":str(base)}
    if mode in ("fixed","low-disk"):
        policy.update({"threads":1,"managed-memory":{"mib":128},"spill":{"mib":1024}})
    elif mode=="percent":
        policy.update({"managed-memory":{"percent":75},"spill":{"percent":90}})
    elif mode=="auto-one-thread":
        policy["threads"]=1
    elif mode=="quarter":
        policy["managed-memory"]={"percent":25}
    elif mode=="quarter-one-thread":
        policy.update({"managed-memory":{"percent":25},"threads":1})
    elif mode=="half-fixed":
        policy.update({"managed-memory":{"mib":128},"threads":2})
    elif mode=="memory-backed-quarter":
        policy["managed-memory"]={"percent":25}
    _set_project_duckdb_execution(path,policy)
    before=db.stat()
    limit=int((CG/"memory.max").read_text().strip())
    log("ENV",engine=duckdb.__version__,memory_limit=limit,cpu=(CG/"cpu.max").read_text().strip(),disk_free=shutil.disk_usage(base).free,mode=mode,kind=kind,database_bytes=before.st_size)
    if kind=="large" and limit==512*MIB:
        assert before.st_size>limit
    observe=binding._observe_local_resources
    facts_seen=[]
    recommendations=binding._read_native_recommendations
    def measured_native(connection):
        native=recommendations(connection)
        log("NATIVE_RECOMMENDATION",memory=native.memory_bytes,threads=native.threads)
        return native
    binding._read_native_recommendations=measured_native
    def measured(scratch):
        facts=observe(scratch)
        log("OBSERVATION",headroom=facts.memory_headroom_bytes,cpu=facts.cpu_capacity,free=facts.scratch_free_bytes,memory_backed=facts.scratch_memory_backed)
        assert facts.memory_headroom_bytes is not None and 0<facts.memory_headroom_bytes<=limit
        facts_seen.append(facts)
        return facts
    binding._observe_local_resources=measured
    original_calculate=binding._calculate_local_resource_targets
    def candidate(policy,inputs):
        if mode=="guide125-quarter" and policy.managed_memory_bytes is None and policy.managed_memory_percent is None:
            policy=replace(policy,managed_memory_percent=25)
        targets=original_calculate(policy,inputs)
        if mode.startswith("guide") and policy.threads is None and targets.threads is not None and targets.managed_memory_bytes is not None and targets.threads>0:
            # Candidate only: documented native sizing guidance, no admission minimum.
            per_thread=125_000_000 if "125" in mode else 1_000_000_000
            threads=min(targets.threads,max(1,targets.managed_memory_bytes//per_thread))
            targets=replace(targets,threads=threads)
        return targets
    binding._calculate_local_resource_targets=candidate
    original_open=binding._OwnedDuckDbSession.open
    opened=[]
    def open_session(session):
        original_open(session)
        request=session._native_controls
        opened.append(session)
        log("TARGET",memory=request.memory_bytes,threads=request.threads,spill=request.spill_bytes)
        if facts_seen[-1].scratch_memory_backed is True:
            facts=facts_seen[-1]
            assert facts.scratch_memory_backed is True
            assert request.spill_bytes<=facts.memory_headroom_bytes-request.memory_bytes
    binding._OwnedDuckDbSession.open=open_session
    stop=threading.Event()
    peak=[0]
    sample_errors=[]
    def walk_error(error):
        if not isinstance(error, FileNotFoundError):
            sample_errors.append(type(error).__name__)
    def sample():
        while not stop.wait(.005):
            total=0
            for parent,_,names in os.walk(base,onerror=walk_error):
                for name in names:
                    try:total+=(Path(parent)/name).stat().st_size
                    except FileNotFoundError:pass
                    except OSError as error:sample_errors.append(type(error).__name__)
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
        elif mode.startswith("memory-backed"):
            assert any("memory-backed" in d.message for d in result.diagnostics)
            assert check.status in (CheckStatus.PASS,CheckStatus.ERROR)
            if check.status is CheckStatus.ERROR:
                assert not check.executed and "RC_ADAPTER_QUERY_FAILED" in codes
        else:
            assert check.status in (CheckStatus.PASS,CheckStatus.ERROR)
            if check.status is CheckStatus.ERROR:
                assert not check.executed and "RC_ADAPTER_QUERY_FAILED" in codes
            else:
                assert result.exit_category is ExitCategory.SUCCESS and check.executed
    finally:
        stop.set();sampler.join(5);observer.close()
    assert not sampler.is_alive() and not sample_errors, sample_errors
    assert not list(base.iterdir()),"Owned scratch residue"
    after=db.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    _assert_no_runtime_outputs(path)
    log("CLEANUP",released=True,observer_unchanged=True,scratch_empty=True,database_unchanged=True)

if sys.argv[1]=="setup":
    setup(Path(sys.argv[2]))
else:
    run(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],sys.argv[5])
