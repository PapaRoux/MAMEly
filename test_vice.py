import subprocess, time
p = subprocess.Popen(["flatpak", "run", "--file-forwarding", "net.sf.VICE", "-VICIIfull", "+confirmonexit", "-autostart", "/mnt/nfs/8TB/platforms/c64/roms/0 And x.zip"])
time.sleep(3)
p.terminate()
time.sleep(1)
