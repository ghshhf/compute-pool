#!/usr/bin/env python3
"""compute-pool runner: 读 jobs/queue.json 逐个执行，结果写 results/。任务=python 表达式或 url 抓取。

target 字段（2026-10-16 加）：
  缺省 / "gh"      -> GitHub Actions 执行（本 runner）
  "phone"          -> 手机 worker 专属，本 runner 跳过，且置空队列时予以保留
"""
import json, os, time, urllib.request, hashlib

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def is_phone(j):
    return str(j.get("target", "")).lower() == "phone"

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
    queued = []
    if os.path.exists("jobs/queue.json"):
        try:
            queued = json.load(open("jobs/queue.json", encoding="utf-8")) or []
        except Exception as e:
            queued = []
            print("queue parse error:", e)
    dt = os.environ.get("DISPATCH_TASK", "").strip()
    # dispatch 任务优先级最高，且不动队列
    jobs = [{"kind": "py", "code": dt, "name": "dispatch"}] if dt else [j for j in queued if not is_phone(j)]
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
    # 消费掉队列（一次性）：置空而不是删除文件。
    # 删除只发生在 runner VM 上、永远进不了仓库（workflow 只 add results/），
    # 结果就是同一批任务每轮都被重复执行；置空后随 git add jobs/ 落库。
    # phone 任务本 runner 不执行，保留在队列里等手机 worker 领走（手机侧按内容 hash 去重）。
    if not dt and queued:
        rest = [j for j in queued if is_phone(j)]
        open("jobs/queue.json", "w", encoding="utf-8").write(
            json.dumps(rest, ensure_ascii=False, indent=1) + "\n")

main()
