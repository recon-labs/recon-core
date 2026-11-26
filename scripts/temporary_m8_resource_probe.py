"""Temporary isolated synthetic experiment. Never merge."""
import json
import os
import resource
import signal
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

MIB = 1024 ** 2
N = 800_000
def log(tag, **data):
    print(tag + " " + json.dumps(data, default=str, sort_keys=True), flush=True)

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None

def rss(pid):
    s = read(f"/proc/{pid}/status") or ""
    for line in s.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None

def size(path):
    logical = allocated = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                st = p.stat()
                logical += st.st_size
                allocated += st.st_blocks * 512
        except OSError:
            pass
    return logical, allocated

def setup(db):
    import duckdb
    with duckdb.connect(str(db), config={"threads": "2", "memory_limit": "512MiB"}) as c:
        c.execute(f"""create table src as select i as k, i%100 as skew, i%17 as amount,
        md5(i::varchar)||md5((i+{N})::varchar)||md5((i+{N*2})::varchar)||md5((i+{N*3})::varchar) as wide
        from range({N}) t(i)""")
        c.execute("create table dst as select * from src")
        c.execute(f"create table small as select i as k, i%100 as skew, i%17 as amount, repeat('x',128) as wide from range({N}) t(i)")
        c.execute("checkpoint")
    log("FIXTURE", rows=N, wide_logical_bytes_per_table=N*128, db_bytes=db.stat().st_size)

def queries(case, c):
    from recon_core.adapters.models import Relation
    from recon_core.adapters.duckdb.renderer_operations import render_compare_counts
    from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
    cat = c.execute("select current_database()").fetchone()[0]
    left = Relation("src", "main", cat)
    right = Relation("dst", "main", cat)
    if case == "count":
        return [render_compare_counts(left, right).sql], "exact_count_renderer"
    if case in ("scalar", "group", "group_skew", "group_os", "group_affinity"):
        grouped = case != "scalar"
        kind = "grouped_aggregate" if grouped else "aggregate"
        ops = []
        for side in ("source", "target"):
            op = {"type": kind, "side": side, "aggregate": "sum", "column": "amount"}
            if grouped:
                op["group_by"] = ["skew" if case == "group_skew" else "wide"]
            ops.append(op)
        ops.append({"type": "compare_grouped_aggregates" if grouped else "compare_aggregates"})
        p = _DuckDbAggregateRuntimeRenderer().render_plan(tuple(ops), source_relation=left, target_relation=right)
        return [*(x.sql for x in p.type_guards), p.domain_guard.sql, p.exact_query.sql], "exact_private_aggregate_renderer"
    if case == "small_group":
        return ["select count(*), sum(v) from (select k, sum(amount) v from small group by k)"], "representative"
    if case == "anti":
        return ["select count(*) from (select distinct k from src) s anti join (select distinct k from dst) d using(k)"], "representative"
    if case in ("spill", "spill_os"):
        return ["select sum(length(wide)+rn%17) from (select wide, row_number() over(order by wide) rn from src)"], "representative_sort"
    if case == "cancel":
        return ["select sum(hash(i+j)) from range(10000) a(i) cross join range(10000) b(j)"], "bounded_synthetic_cancel"
    raise ValueError(case)

def child(db, spill, case, mem, threads, cap, mode, profile):
    import duckdb
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**3, 1024**3))
    spill.mkdir()
    if case == "spill_os":
        resource.setrlimit(resource.RLIMIT_FSIZE, (16*MIB, 16*MIB))
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    if case == "group_os":
        resource.setrlimit(resource.RLIMIT_AS, (768*MIB, 768*MIB))
    if case == "group_affinity":
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    cfg = {"memory_limit": f"{mem}MiB", "threads": str(threads), "temp_directory": str(spill)}
    if mode == "startup":
        cfg["max_temp_directory_size"] = f"{cap}MiB"
    c = None
    start = time.monotonic()
    log("CHILD_ENV", affinity=sorted(os.sched_getaffinity(0)), as_limit=resource.getrlimit(resource.RLIMIT_AS), file_limit=resource.getrlimit(resource.RLIMIT_FSIZE))
    result = None
    error = None
    canceled = False
    requested = threading.Event()
    done = threading.Event()
    thread = None
    baseline_rss = rss(os.getpid())
    try:
        c = duckdb.connect(str(db), read_only=True, config=cfg)
        if mode == "set":
            c.execute(f"set max_temp_directory_size='{cap}MiB'")
        settings = c.execute("select name, value, scope from duckdb_settings() where name in ('memory_limit','max_memory','threads','temp_directory','max_temp_directory_size') order by name").fetchall()
        log("SETTINGS", case=case, mode=mode, memory=mem, cap=cap, settings=settings)
        qs, source = queries(case,c)
        estimate = c.execute("select table_name,estimated_size from duckdb_tables() where table_name in ('src','dst','small') order by table_name").fetchall()
        # Observe estimated cardinality only; never execute preflight data scans.
        log("CATALOG", case=case, estimate=estimate, sql_source=source)
        if case == "cancel":
            def interrupt():
                if not done.wait(.10):
                    requested.set()
                    c.interrupt()
            thread = threading.Thread(target=interrupt)
            thread.start()
        for i,q in enumerate(qs):
            if profile and i == len(qs)-1:
                try:
                    c.execute("set enable_profiling='json'")
                    c.execute("set profiling_output='" + str(spill.parent / "profile.json") + "'")
                except Exception as e:
                    log("PROFILE_SETUP_UNAVAILABLE", error=type(e).__name__)
            log("STAGE", case=case, index=i, phase="execute_start")
            cur = c.execute(q)
            log("STAGE", case=case, index=i, phase="execute_return")
            result = cur.fetchmany(2)
            log("STAGE", case=case, index=i, phase="fetch_return")
            if len(result) > 1:
                raise RuntimeError("unbounded result")
        if case in ("group", "group_affinity", "group_os"):
            assert result == [(N,0,0,0,0,N,0,0,0)], result
        if case == "count":
            assert result == [(N,N,0)], result
        elif case == "anti":
            assert result == [(0,)], result
        elif case == "small_group":
            assert result == [(N, sum(i%17 for i in range(N)))], result
    except Exception as e:
        error = type(e).__name__ + ": " + str(e)[:450]
        canceled = "interrupt" in error.lower()
    finally:
        done.set()
        if thread:
            thread.join(timeout=3)
        if c is not None:
            if case == "cancel":
                try:
                    log("CANCEL_REUSE", result=c.execute("select 1").fetchone())
                except Exception as e:
                    log("CANCEL_REUSE", error=type(e).__name__)
            try:
                c.close()
            except Exception as e:
                log("CLOSE_ERROR", error=type(e).__name__)
        p = spill.parent / "profile.json"
        if p.is_file():
            try:
                d=json.loads(p.read_text())
                log("PROFILE", fields={k:d.get(k) for k in ("system_peak_buffer_memory","system_peak_temp_dir_size","total_bytes_read","total_bytes_written","cumulative_rows_scanned","rows_returned","result_set_size","cpu_time","latency") if k in d})
            except Exception as e:
                log("PROFILE_READ_ERROR", error=type(e).__name__)
        log("CASE_RESULT", final_query_succeeded=error is None, case=case, mem_mib=mem, threads=threads, cap_mib=cap, mode=mode, elapsed_s=round(time.monotonic()-start,4), peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024, baseline_rss_bytes=baseline_rss, cpu_s=round(resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,4), result=result, error=error, cancel_requested=requested.is_set(), interrupted=canceled, after_close=size(spill))
    # expected resource failure is evidence, not a successful query.

def supervised(args, root, timeout, spill=None):
    with tempfile.TemporaryFile(mode="w+t") as out:
        p=subprocess.Popen([sys.executable, __file__, *map(str,args)], stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        start=time.monotonic()
        peak_rss=peak_spill=peak_alloc=0
        stopped=None
        while p.poll() is None:
            peak_rss=max(peak_rss,rss(p.pid) or 0)
            if spill:
                a,b=size(spill)
                peak_spill=max(peak_spill,a); peak_alloc=max(peak_alloc,b)
            if time.monotonic()-start > timeout:
                stopped="deadline"
            elif size(root)[0]>2*1024**3:
                stopped="scratch_guard"
            elif peak_rss>1024*MIB:
                stopped="sampled_rss_guard"
            if stopped:
                p.kill()
                break
            time.sleep(.05)
        p.wait(timeout=5)
        out.seek(0)
        print(out.read(),end="",flush=True)
        log("SUPERVISOR", elapsed_s=round(time.monotonic()-start,3), args=[str(x) for x in args[0:1]+args[3:]], returncode=p.returncode, stopped=stopped, sampled_peak_rss_bytes=peak_rss, sampled_peak_spill_logical_bytes=peak_spill, sampled_peak_spill_allocated_bytes=peak_alloc)
        return p.returncode

def cgroup_v2():
    # Resolve mount root + membership, then inspect every visible ancestor.
    membership=next((x.split(":",2)[2] for x in (read("/proc/self/cgroup") or "").splitlines() if x.startswith("0::")),None)
    mounts=[]
    for line in (read("/proc/self/mountinfo") or "").splitlines():
        left,sep,right=line.partition(" - ")
        if not sep or right.split()[0]!="cgroup2": continue
        parts=left.split()
        decode=lambda v: re.sub(r"\\([0-7]{3})",lambda m: chr(int(m[1],8)),v)
        mounts.append((Path(decode(parts[3])),Path(decode(parts[4]))))
    candidates=[]
    for mount_root,mountpoint in mounts:
        if membership is None: continue
        try: rel=Path(membership).relative_to(mount_root)
        except ValueError: continue
        p=mountpoint/rel
        chain=[]
        for q in (p,*p.parents):
            if not q.is_relative_to(mountpoint): break
            vals={k:read(q/k) for k in ("memory.max","memory.current","memory.high","cpu.max","cpuset.cpus.effective")}
            chain.append({"path":str(q),**vals})
            if q==mountpoint: break
        candidates.append({"mount_root":str(mount_root),"mount":str(mountpoint),"chain":chain})
    log("CGROUP",membership=membership,candidates=candidates)
    remaining=[]
    for c in candidates:
        for v in c["chain"]:
            if (v["memory.max"] or "").isdigit() and (v["memory.current"] or "").isdigit():
                remaining.append(max(0,int(v["memory.max"])-int(v["memory.current"])))
    return min(remaining) if remaining else None

def parent():
    import duckdb
    with tempfile.TemporaryDirectory(prefix="recon-resource-probe-") as t:
        root=Path(t); db=root/"fixture.duckdb"
        meminfo=read("/proc/meminfo") or ""
        avail=int(next(x.split()[1] for x in meminfo.splitlines() if x.startswith("MemAvailable:")))*1024
        cg={k:read("/sys/fs/cgroup/"+k) for k in ("memory.max","memory.current","memory.high","cpu.max","cpuset.cpus.effective")}
        headroom=cgroup_v2()
        remaining=min(avail,headroom) if headroom is not None else avail
        log("ENV", version=duckdb.__version__, available_bytes=avail, cgroup=cg, cgroup_path=read("/proc/self/cgroup"), affinity=len(os.sched_getaffinity(0)), disk_free=shutil.disk_usage(root).free, remaining_estimate=remaining)
        if remaining<2*1024**3 or shutil.disk_usage(root).free<4*1024**3:
            raise RuntimeError("insufficient runner headroom")
        if supervised(["setup",db],root,80)!=0:
            raise RuntimeError("fixture creation failed")
        cases=[
            ("group",128,2,512,"set",0),("group",256,1,512,"set",0),
            ("group",256,2,512,"set",0),("group",512,1,512,"set",0),
            ("group",512,2,512,"set",0),("group",768,1,512,"set",0),
            ("group_affinity",512,2,512,"set",0),
            ("group_os",256,1,512,"set",0),
            ("spill",64,1,1,"startup",0),("spill",64,1,1,"set",0),
            ("spill_os",64,1,512,"set",0),("spill",64,1,512,"set",0),
        ]
        for i,(case,mem,threads,cap,mode,profile) in enumerate(cases):
            case_root=root/f"case{i}"
            case_root.mkdir(); spill=case_root/"spill"
            supervised(["child",db,spill,case,mem,threads,cap,mode,profile],root,18,spill)
            log("CLEANUP", case=case, before_remove=size(case_root))
            shutil.rmtree(case_root)
            assert not case_root.exists()
        log("COMPLETE", cases=len(cases), db_bytes=db.stat().st_size)
    log("ROOT_CLEANUP", removed=not root.exists())

if __name__=="__main__":
    if len(sys.argv)==1:
        parent()
    elif sys.argv[1]=="setup":
        setup(Path(sys.argv[2]))
    else:
        _,_,db,spill,case,mem,threads,cap,mode,profile=sys.argv
        child(Path(db),Path(spill),case,int(mem),int(threads),int(cap),mode,int(profile))
