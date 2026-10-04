"""Independent build, validation, preview, final and verification entry point."""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'scripts/project.json').read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','validate','preview','final','verify','all'])
    parser.add_argument('--threads',type=int,default=16)
    parser.add_argument('--views',nargs='+',choices=CONFIG['views'])
    args = parser.parse_args()
    if args.threads < 1 or (args.views and args.action != 'preview'):
        parser.error('Positive threads required; --views is only available with preview.')
    logs = ROOT/'review/logs'
    logs.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ, ALSOFT_DRIVERS='null', SDL_AUDIODRIVER='dummy')
    with (logs/'.pipeline.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(2,'This project is already running.\n')
        actions = ['build','validate','preview','final','verify'] if args.action == 'all' else [args.action]
        for action in actions:
            if action == 'build' and CONFIG['kind'] == 'flat':
                subprocess.run([sys.executable,str(ROOT/'scripts/vectorize_reference.py')],check=True,env=env)
            if action == 'verify':
                command = [sys.executable,str(ROOT/'scripts/verify_outputs.py')]
            else:
                command = ['blender','-b','-noaudio']
                if action != 'build':
                    command.append(str(ROOT/CONFIG['scene']))
                command += ['-t',str(args.threads),'--python-exit-code','1','--python',str(ROOT/'scripts/scene_tasks.py'),'--',action,'--threads',str(args.threads)]
                if args.views:
                    command += ['--views',*args.views]
            path = logs/(action+'.log')
            print(f'{CONFIG["kind"]}: {action} → {path}',flush=True)
            start = time.monotonic()
            with path.open('w') as log:
                log.write('Command: '+repr(command)+'\n')
                log.flush()
                result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env)
                log.write(f'\nElapsed: {time.monotonic()-start:.3f}s; exit code: {result.returncode}\n')
            if result.returncode:
                parser.exit(result.returncode,f'{action} failed; inspect {path}\n')
            if action == 'preview':
                with path.open('a') as log:
                    subprocess.run([sys.executable,str(ROOT/'scripts/verify_outputs.py'),'--preview-comparison'],
                                   check=True,stdout=log,stderr=subprocess.STDOUT,env=env)
            print(f'{action}: complete ({time.monotonic()-start:.1f}s)',flush=True)


if __name__ == '__main__':
    main()
