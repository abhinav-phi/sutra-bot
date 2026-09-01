import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_bench
from run_bench import (call, score_code, score_hindi, OUTDIR)

jobs = [(m, "code") for m in ["deepseek-v4-flash", "deepseek-v4-flash-vision-exp",
                               "hy3", "mimo-v2.5", "glm-5.3-flash"]] + [("hy3", "hindi")]

prompts = {
    "code": "Write a Python function def second_largest(nums): that returns the second largest number in a list without sorting the list. Reply with ONLY the code, no markdown fences, no explanation.",
    "hindi": "Ek WhatsApp offer message likho max 30 words mein: Chai Point Bangalore mein masala chai pe 50% off. Sirf message do, koi explanation nahi.",
}


def call_retry(model, prompt, max_tokens):
    for attempt, wait in enumerate([0, 10, 25, 45]):
        if wait: time.sleep(wait)
        r = call(model, prompt, max_tokens)
        if r["ok"]: return r
        print("      (retry %d: %s)" % (attempt + 1, r["error"][:90]), flush=True)
    return r

results = {}
for i, (model, tname) in enumerate(jobs):
    if i:
        time.sleep(6)
    r = call_retry(model, prompts[tname], 2000)
    scorer = score_code if tname == "code" else score_hindi
    s, note = scorer(r)
    results["%s_%s" % (model, tname)] = {"score": s, "note": note, "time": round(r["time"], 2), "ok": r["ok"]}
    with open(os.path.join(OUTDIR, "%s_%s.txt" % (model, tname)), "w", encoding="utf-8") as f:
        f.write(r.get("content") or r.get("error", ""))
    print("%-32s %-6s %6.2fs  %2d  %s" % (model, tname, r["time"], s, note), flush=True)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rerun_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
