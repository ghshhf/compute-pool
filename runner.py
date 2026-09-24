#!/usr/bin/env python3
"""compute-pool runner: 读 jobs/queue.json 逐个执行，结果写 results/。任务=python 表达式或 url 抓取。"""
import json, os, time, urllib.request, hashlib

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def do(job):
    kind = job.get("kind")
    if kind == "py":
        env = dict(os.environ)
        exec(job["code"], {"env": env, "out": []}, {"out": []})
        return {"ok": True}
    if kind == "fetch":
        req = urllib.request.Request(job["url"], headers={"User-Agent": "Mozilla/5.0"})
        txt = urllib.request.urlopen(req, timeout=60).read(200000).decode("utf-8", "replace")
        dest = job.get("save", "")
        if dest:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            open(dest, "w", encoding="utf-8").write(txt)
        return {"ok": True, "bytes": len(txt), "head": txt[:200]}
    return {"ok": False, "err": "unknown kind"}

def main():
    jobs = []
    if os.path.exists("jobs/queue.json"):
        jobs = json.load(open("jobs/queue.json", encoding="utf-8"))
    dt = os.environ.get("DISPATCH_TASK", "").strip()
    if dt:
        jobs = [{"kind": "py", "code": dt, "name": "dispatch"}]
    os.makedirs("results", exist_ok=True)
    log = []
    for j in jobs:
        name = j.get("name", hashlib.md5(json.dumps(j).encode()).hexdigest()[:8])
        t0 = time.time()
        try:
            r = do(j)
        except Exception as e:
            r = {"ok": False, "err": str(e)[:300]}
        r.update({"name": name, "secs": round(time.time() - t0, 1), "at": now()})
        log.append(r)
        print(name, "->", json.dumps(r, ensure_ascii=False)[:200])
    open("results/last_run.json", "w", encoding="utf-8").write(json.dumps(log, ensure_ascii=False, indent=1))
    # 消费掉队列（一次性）
    if jobs and os.path.exists("jobs/queue.json"):
        os.remove("jobs/queue.json")

main()
