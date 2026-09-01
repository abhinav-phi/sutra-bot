import json, re, os, time, subprocess, sys, tempfile
import urllib.request, urllib.error
from pathlib import Path

BASE = "https://api.b.ai/v1/chat/completions"


def _key_from_env_file():
    p = Path(__file__).resolve().parents[1] / "sutra" / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("CUSTOM_LLM_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


KEY = os.environ.get("BAI_API_KEY") or _key_from_env_file()
MODELS = [
    "deepseek-v4-flash",
    "deepseek-v4-flash-vision-exp",
    "hy3",
    "mimo-v2.5",
    "glm-5.3-flash",
    "qwen3.8-flash",
]
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
os.makedirs(OUTDIR, exist_ok=True)
PACE = 6.5  # seconds between calls (rolling per-minute limit on this key)

TESTS = {
    "exact": "Reply with exactly this text and nothing else: MAGICPIN_RULES_2026",
    "math": "A shopkeeper gives 20% discount on a Rs 500 item, then adds 10% tax on the discounted price. What is the final price in rupees? Reply with ONLY the number.",
    "json": "Return ONLY a valid JSON object with keys: name, offer_text, discount_percent, city. The offer is: Chai Point Bangalore, 50% off on masala chai, valid till tomorrow. No markdown, no explanation, just the JSON object.",
    "code": "Write a Python function def second_largest(nums): that returns the second largest number in a list without sorting the list. Reply with ONLY the code, no markdown fences, no explanation.",
    "hindi": "Ek WhatsApp offer message likho max 30 words mein: Chai Point Bangalore mein masala chai pe 50% off. Sirf message do, koi explanation nahi.",
}
WEIGHTS = {"exact": 15, "math": 20, "json": 25, "code": 15, "hindi": 10}


def call(model, prompt, max_tokens=400):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(BASE, data=body, headers={
        "Authorization": "Bearer " + KEY,
        "Content-Type": "application/json",
    })
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
            dt = time.perf_counter() - t0
            msg = data["choices"][0]["message"]
            return {"ok": True, "time": dt, "content": (msg.get("content") or ""),
                    "finish": data["choices"][0].get("finish_reason")}
    except urllib.error.HTTPError as e:
        try: err = e.read().decode("utf-8")[:200]
        except Exception: err = str(e)
        return {"ok": False, "time": time.perf_counter() - t0, "error": "HTTP %s: %s" % (e.code, err)}
    except Exception as e:
        return {"ok": False, "time": time.perf_counter() - t0, "error": str(e)[:200]}


def call_with_retry(model, prompt):
    for attempt, wait in enumerate([0, 10, 25, 45]):
        if wait: time.sleep(wait)
        r = call(model, prompt)
        if r["ok"]: return r
        print("      (retry %d: %s)" % (attempt + 1, r["error"][:90]), flush=True)
    return r


def strip_fences(text):
    m = re.search(r"```(?:python|json)?\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


def score_exact(r):
    if not r["ok"]: return 0, "HTTP fail"
    c = r["content"].strip().strip("\"'` ")
    if c == "MAGICPIN_RULES_2026": return 15, "perfect"
    if "MAGICPIN_RULES_2026" in c: return 10, "contains extra text"
    return 0, "wrong: " + c[:60]


def score_math(r):
    if not r["ok"]: return 0, "HTTP fail"
    c = r["content"]
    if re.search(r"\b440\b", c): return 20, "correct (440)"
    return 0, "wrong: " + c.replace("\n", " ")[:60]


def score_json(r):
    if not r["ok"]: return 0, "HTTP fail"
    c = strip_fences(r["content"])
    s, e = c.find("{"), c.rfind("}")
    if s == -1 or e == -1: return 0, "no JSON found"
    try:
        obj = json.loads(c[s:e+1])
    except Exception as ex:
        return 0, "unparseable: " + str(ex)[:50]
    if isinstance(obj, dict):
        keys = {"name", "offer_text", "discount_percent", "city"}
        if keys.issubset(obj.keys()): return 25, "valid + all keys"
        return 15, "valid JSON, missing keys: " + str(keys - set(obj.keys()))
    return 0, "not an object"


def score_code(r):
    if not r["ok"]: return 0, "HTTP fail"
    c = strip_fences(r["content"])
    if "def second_largest" not in c: return 0, "no function found"
    used_sort = bool(re.search(r"\.sort\(|\bsorted\(", c))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(c + "\nassert second_largest([4,1,7,3]) == 4\n"
                   "assert second_largest([10,3,5]) == 5\n"
                   "assert second_largest([2,9,2,8]) == 8\nprint('PASS')\n")
        path = f.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=15)
        passed = p.returncode == 0 and "PASS" in p.stdout
    except Exception:
        passed = False
    finally:
        os.unlink(path)
    if passed and not used_sort: return 15, "passes tests, no sort"
    if passed: return 10, "passes but used sort"
    return 7, "function present, tests fail"


def score_hindi(r):
    if not r["ok"]: return 0, "HTTP fail"
    c = r["content"].strip()
    low = c.lower()
    has_offer = "50" in c
    has_brand = "chai" in low
    words = len(c.split())
    if has_offer and has_brand and words <= 45: return 10, "good (%d words)" % words
    if has_offer and has_brand: return 7, "too long (%d words)" % words
    return 3, "weak: " + c.replace("\n", " ")[:60]


SCORERS = {"exact": score_exact, "math": score_math, "json": score_json,
           "code": score_code, "hindi": score_hindi}


if __name__ == "__main__":
    print("Running benchmark SEQUENTIALLY (pacing %.1fs, backoff on 429)..." % PACE, flush=True)
    results = []
    for model in MODELS:
        res = {"model": model, "tests": {}, "times": {}}
        print(model, flush=True)
        for tname, prompt in TESTS.items():
            r = call_with_retry(model, prompt)
            s, note = SCORERS[tname](r)
            res["tests"][tname] = {"score": s, "note": note, "time": round(r["time"], 2),
                                   "ok": r["ok"], "finish": r.get("finish")}
            res["times"][tname] = r["time"]
            with open(os.path.join(OUTDIR, "%s_%s.txt" % (model.replace("/", "_"), tname)), "w", encoding="utf-8") as f:
                f.write((r.get("content") or r.get("error", "")))
            print("  %-6s %6.2fs  %2d/-%2d  %s" % (tname, r["time"], s, WEIGHTS[tname], note), flush=True)
            time.sleep(PACE)
        avg = sum(res["times"].values()) / len(res["times"])
        res["avg_time"] = round(avg, 2)
        res["latency_score"] = 15 if avg < 2 else 12 if avg < 4 else 9 if avg < 7 else 6 if avg < 12 else 3
        res["total"] = sum(t["score"] for t in res["tests"].values()) + res["latency_score"]
        results.append(res)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    results.sort(key=lambda r: -r["total"])
    print("\n" + "=" * 80)
    print("%-30s %7s %7s %7s %7s %7s %7s %8s" % ("MODEL", "EXACT", "MATH", "JSON", "CODE", "HINDI", "SPEED", "TOTAL"))
    print("-" * 80)
    for r in results:
        t = r["tests"]
        print("%-30s %5d/15 %5d/20 %5d/25 %5d/15 %5d/10 %5d/15 %6d/100"
              % (r["model"], t["exact"]["score"], t["math"]["score"], t["json"]["score"],
                 t["code"]["score"], t["hindi"]["score"], r["latency_score"], r["total"]))
    print("=" * 80)
    print("\nAvg response time per call:")
    for r in results:
        print("  %-30s %.2fs" % (r["model"], r["avg_time"]))
