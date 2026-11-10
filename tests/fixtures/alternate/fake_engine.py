"""A stand-in engine for `alternate`'s tests (tests/test_alternate.py).

fake_engine.py SIDE SOURCE LOG RUN: appends SIDE to the order log LOG and
copies SOURCE, a run file, to RUN. FAKE_ENGINE=NAME=MODE changes what the
run named NAME (new-2, say) does instead:
  exit4   writes its file, then exits 4;
  nofile  writes nothing and exits 0;
  wait    writes its file and its process id (to LOG.pid), then sleeps
          until it is stopped;
  killself  kills itself with SIGKILL;
  background  writes its file, starts a child that sleeps and writes the
          child's process id to LOG.pid, then exits 0, leaving it running.
FAKE_ENGINE_SAY=1 makes every run print "engine says hi" on standard output.
"""

import os
import shutil
import signal
import subprocess
import sys
import time

side, source, log, run = sys.argv[1:5]
name = os.path.splitext(os.path.basename(run))[0]
with open(log, "a", encoding="utf-8") as order:
    order.write(side + "\n")
if os.environ.get("FAKE_ENGINE_SAY"):
    print("engine says hi", flush=True)
target, _, mode = os.environ.get("FAKE_ENGINE", "").partition("=")
mode = mode if target == name else ""
if mode == "killself":
    os.kill(os.getpid(), signal.SIGKILL)
if mode != "nofile":
    shutil.copyfile(source, run)
if mode == "background":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(log + ".pid", "w", encoding="utf-8") as pid:
        pid.write(str(child.pid))
if mode == "wait":
    with open(log + ".pid", "w", encoding="utf-8") as pid:
        pid.write(str(os.getpid()))
    time.sleep(60)
sys.exit(4 if mode == "exit4" else 0)
