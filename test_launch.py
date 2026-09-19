import subprocess
cmd = ['stella', '/mnt/nfs/8TB/platforms/atari2600/roms/Adventure.bin']
result = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
