"""Local dashboard. Runs everything on this computer; no outside services, no extra packages.

    python3 app.py            # opens http://127.0.0.1:8765

The page starts pipeline.py as a child process (so it uses your CPU cores), reads the events it writes
to out/run/events.jsonl, and shows moveset convergence, battle progress and the final results live.
"""
import argparse, json, os, random, re, signal, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BASE = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import gens
from pathlib import Path
import uuid
from config import validate
from storage import write_json


def gen_paths(gen):
    """(out dir, run dir, events file, stdout log) for one generation; each keeps its own results and movesets."""
    out = os.path.join(OUT_BASE, f"gen{gen}")
    run = os.path.join(out, "run")
    return out, run, os.path.join(run, "events.jsonl"), os.path.join(run, "stdout.log")


def parse_gen(v):
    if v is None or v=="": v=1
    if isinstance(v,bool) or not isinstance(v,(str,int)): raise ValueError("generation must be an integer")
    g = int(v)
    if g not in [x["id"] for x in gens.available()]:
        raise ValueError(f"generation {g} is not available")
    return g


_run_gen = 1

_proc = None
_lock = threading.Lock()
_engine = {}


def _load_engine(gen=1):
    if gen not in _engine:
        import tournament as T
        g = gens.get(gen)
        _engine[gen] = dict(E=g.E, P=g.P, T=T, brain=g.brain)
    return _engine[gen]


def is_running():
    return _proc is not None and _proc.poll() is None


def start_run(cfg):
    global _proc, _run_gen
    with _lock:
        if is_running():
            return False, "A run is already in progress."
        try:
            cfg=validate(cfg)
            if cfg.get("preset","standard") not in ("quick","standard","thorough"):raise ValueError("unknown preset")
            for flag in ("fresh","skip_search"):
                if flag in cfg and not isinstance(cfg[flag],bool):raise ValueError(f"{flag} must be boolean")
            gen = parse_gen(cfg.get("gen"))
        except (ValueError,TypeError) as ex:
            return False, str(ex)
        out, run, events, stdout = gen_paths(gen)
        args = [sys.executable, "-u", os.path.join(HERE, "pipeline.py"), "--gen", str(gen), "--out", out, "--preset", cfg.get("preset", "standard")]
        for k in ("passes", "sample", "screen_games", "confirm_games", "games", "margin", "minutes", "seed", "procs"):
            v = cfg.get(k)
            if v not in (None, ""):
                args += ["--" + k.replace("_", "-"), str(v)]
        if cfg.get("fresh"):
            args.append("--fresh")
        if cfg.get("skip_search"):
            args.append("--skip-search")
        os.makedirs(run, exist_ok=True)
        if os.path.exists(events):
            os.remove(events)
        identity=uuid.uuid4().hex
        write_json(os.path.join(run,"identity.json"),dict(run_id=identity))
        args += ["--run-id",identity]
        _run_gen = gen
        kw = {}
        if os.name == "posix":
            kw["start_new_session"] = True
        with open(stdout,"w") as log:
            _proc = subprocess.Popen(args, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, **kw)
        return True, "started"


def stop_run():
    with _lock:
        if not is_running():
            return
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(_proc.pid)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        else:
            try:
                os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name=="posix": os.killpg(_proc.pid,signal.SIGKILL)
            else: _proc.kill()
            _proc.wait(timeout=10)
        with open(gen_paths(_run_gen)[2], "a") as f:
            f.write(json.dumps(dict(type="stopped", t=0)) + "\n")


def read_events(since, gen=1):
    events = gen_paths(gen)[2]
    if not os.path.exists(events):
        return [], 0
    with open(events, "rb") as f:
        if since<0: raise ValueError("negative event cursor")
        if since>os.fstat(f.fileno()).st_size: since=0
        f.seek(since)
        data = f.read()
    end = data.rfind(b"\n")
    if end < 0:
        return [], since
    evs = []
    for line in data[:end + 1].splitlines():
        try:
            evs.append(json.loads(line))
        except ValueError:
            pass
    return evs, since + end + 1


def log_tail(n=15, gen=1):
    try:
        return "".join(Path(gen_paths(gen)[3]).read_text(errors="replace").splitlines(keepends=True)[-n:])
    except OSError:
        return ""


LOG_RE = re.compile(r"T(\d+) (?:\[([ab])\] )?(\S+) uses (\S+) \(hp (-?\d+)/(\d+)\) vs (\S+) \(hp (-?\d+)/(\d+)\)")


def run_battle(a, b, seed, gen=1):
    e = _load_engine(gen)
    E, P, T = e["E"], e["P"], e["T"]
    keys = list(E.D["mons"])
    if a not in E.D["mons"] or b not in E.D["mons"]:
        return dict(error="unknown pokemon")
    ms = T.load_movesets(os.path.join(gen_paths(gen)[0], "movesets.json"), keys, gen)
    sa, sb = E.make_spec(a, ms[a]), E.make_spec(b, ms[b])
    log = []
    bt = E.Battle(sa, sb, random.Random(seed), e["brain"], log=log)
    res = bt.run()
    turns = []
    for line in log:
        m = LOG_RE.match(line)
        if m:
            t, side, who, mv, hp, mx, opp, ohp, omx = m.groups()
            turns.append(dict(turn=int(t), side=side, actor=who, move=mv, hp=int(hp), maxhp=int(mx),
                              opp=opp, opp_hp=int(ohp), opp_maxhp=int(omx)))
    return dict(a=dict(key=a, name=sa["name"], moves=sa.get("build", sa["moves"]), hp=sa["hp"], level=sa["lvl"],required_item=sa.get("item")),
                b=dict(key=b, name=sb["name"], moves=sb.get("build", sb["moves"]), hp=sb["hp"], level=sb["lvl"],required_item=sb.get("item")),
                result=res, winner=[sa["name"], sb["name"], None][res], turns=turns,
                final=dict(a_hp=max(0, bt.a.hp), b_hp=max(0, bt.b.hp)), seed=seed)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", extra=None):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _guard(self):
        """Only this machine's own dashboard page may talk to the server (blocks other sites and DNS rebinding)."""
        host = self.headers.get("Host", "") or ""
        if host.rsplit(":", 1)[0].strip("[]") not in ("127.0.0.1", "localhost"):
            return False
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).netloc == host

    def do_GET(self):
        if not self._guard():
            return self.send(403, dict(error="forbidden"))
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):
            return self.send(200, Path(HERE,"ui.html").read_bytes(), "text/html; charset=utf-8")
        try:
            gen = parse_gen(q.get("gen"))
        except (ValueError,TypeError):
            return self.send(400, dict(error="unknown generation"))
        out = gen_paths(gen)[0]
        if u.path == "/api/gens":
            return self.send(200, dict(gens=gens.available(), running_gen=_run_gen if is_running() else None))
        if u.path == "/api/events":
            try:
                since=int(q.get('since',0))
                if since<0:raise ValueError()
            except ValueError:return self.send(400,dict(error='invalid event cursor'))
            with _lock:
                identity_path=os.path.join(gen_paths(gen)[1],'identity.json')
                identity=json.loads(Path(identity_path).read_text()).get('run_id') if os.path.exists(identity_path) else None
                if q.get('run_id')!=identity: since=0
                evs,nxt=read_events(since,gen)
            mine = _run_gen == gen
            running = is_running() and mine
            rc = None if (_proc is None or not mine) else _proc.poll()
            return self.send(200, dict(events=evs, next=nxt, run_id=identity, running=running, returncode=rc,
                                       error=log_tail(15, gen) if (rc not in (None, 0) and not running) else "",
                                       busy_gen=_run_gen if (is_running() and not mine) else None))
        if u.path == "/api/last_results":
            p = os.path.join(out, "results.json")
            return self.send(200, json.loads(Path(p).read_text()) if os.path.exists(p) else dict(cards=[]))
        if u.path == "/api/pokemon":
            try:
                e = _load_engine(gen)
                E = e["E"]
                keys = list(E.D["mons"])
                # Keep roster discovery available even when an older saved build is invalid.
                return self.send(200, dict(mons=[dict(key=k, name=E.D["mons"][k]["name"], required_item=E.D["mons"][k].get("required_item")) for k in keys],
                                           cpus=os.cpu_count() or 1))
            except Exception as ex:
                return self.send(500, dict(error=f"Could not load Gen {gen} data: {ex}"))
        if u.path == "/api/battle":
            try:
                return self.send(200, run_battle(q["a"], q["b"], int(q.get("seed", random.randrange(10 ** 6))), gen))
            except Exception as ex:  # noqa
                return self.send(500, dict(error=str(ex)))
        if u.path in ("/download/results.csv", "/download/results.json", "/download/movesets.json"):
            p = os.path.join(out, os.path.basename(u.path))
            if not os.path.exists(p):
                return self.send(404, dict(error="not found"))
            return self.send(200, Path(p).read_bytes(), "application/octet-stream",
                             {"Content-Disposition": f"attachment; filename={os.path.basename(p)}"})
        self.send(404, dict(error="not found"))

    def do_POST(self):
        if not self._guard():
            return self.send(403, dict(error="forbidden"))
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n < 0 or n > 1_000_000:
                raise ValueError("body size")
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
        except Exception:
            return self.send(400, dict(error="bad request body"))
        if u.path == "/api/start":
            try: ok, msg = start_run(body)
            except (OSError,ValueError,TypeError) as ex:return self.send(400,dict(ok=False,message=str(ex)))
            return self.send(200 if ok else 409, dict(ok=ok, message=msg))
        if u.path == "/api/stop":
            stop_run()
            return self.send(200, dict(ok=True))
        self.send(404, dict(error="not found"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = None
    for port in range(a.port, a.port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("No free port found")
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"Poke Sim build 0.12.0 running at {url}  (Ctrl+C to quit)")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_run()


if __name__ == "__main__":
    main()