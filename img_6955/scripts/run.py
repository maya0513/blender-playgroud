"""Project entry point. Fixed logs, exit codes and a single-process lock."""
import argparse
import fcntl
import subprocess
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from project import ROOT, SCENE, LOGS, CAMERAS, ensure_directories

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('action', choices=['build', 'validate', 'preview', 'final'])
p.add_argument('--threads', type=int, default=16)
p.add_argument('--views', nargs='+', choices=list(CAMERAS))
a = p.parse_args()
if a.threads < 1 or (a.views and a.action != 'preview'):
    p.error('Use positive --threads; --views is only valid for preview')
ensure_directories()
# Stable lock inode is intentionally kept; concurrent runs never share outputs.
with (LOGS / '.pipeline.lock').open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        p.exit(2, 'Another project operation is running.\n')
    if a.action == 'final':
        # Refuse final rendering when current-scene photographic detail is absent.
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_appearance.py'), '--stage', 'preview'])
        if result.returncode:
            p.exit(result.returncode, 'Appearance preflight failed; inspect and regenerate the photo preview.\n')
    script = {'build': 'build_scene.py', 'validate': 'validate_scene.py',
              'preview': 'render_scene.py', 'final': 'render_scene.py'}[a.action]
    command = ['blender', '-b']
    if a.action != 'build':
        command.append(str(SCENE))
    command += ['-t', str(a.threads), '--python-exit-code', '1', '--python', str(ROOT / 'scripts' / script)]
    if a.action in ['preview', 'final']:
        command += ['--', '--mode', a.action, '--threads', str(a.threads)]
        if a.views:
            command += ['--views', *a.views]
    log_path = LOGS / (a.action + '.log')
    print(f'{a.action}: {log_path}', flush=True)
    with log_path.open('w') as log:
        log.write('Command: ' + repr(command) + '\n')
        log.flush()
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    print(f'{a.action}: {"complete" if result.returncode == 0 else "FAILED"}; see {log_path}', flush=True)
    sys.exit(result.returncode)
