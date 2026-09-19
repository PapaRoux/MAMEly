import subprocess, time
p = subprocess.Popen(["flatpak", "run", "com.snes9x.Snes9x"])
time.sleep(2)
p.terminate()
time.sleep(1)
