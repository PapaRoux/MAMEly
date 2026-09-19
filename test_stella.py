import subprocess
try:
    result = subprocess.run(['stella', '/mnt/nfs/8TB/platforms/atari2600/roms/Adventure.bin'], capture_output=True, text=True, timeout=2)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
except subprocess.TimeoutExpired as e:
    print("Timeout! Stella is running fine and didn't crash.")
    print("STDOUT so far:", e.stdout)
    print("STDERR so far:", e.stderr)
