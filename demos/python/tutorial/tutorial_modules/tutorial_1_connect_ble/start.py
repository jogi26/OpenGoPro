import tkinter as tk
from tkinter import ttk
import requests
import ipaddress
import concurrent.futures

# ---------------------------------------------
# GoPro Discovery Logic
# ---------------------------------------------
def is_gopro(ip):
    try:
        r = requests.get(f"http://{ip}/gp/gpControl/status", timeout=0.5)
        if r.status_code == 200 and "status" in r.json():
            return ip
    except:
        return None
    return None

def discover_gopros_on_network(subnet="192.168.1.0/24"):
    found = {}
    net = ipaddress.ip_network(subnet, strict=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(is_gopro, str(ip)): ip for ip in net.hosts()}
        for future in concurrent.futures.as_completed(futures):
            ip = future.result()
            if ip:
                try:
                    r = requests.get(f"http://{ip}/gp/gpControl/info", timeout=0.5)
                    model = r.json().get("model_name", "GoPro")
                except:
                    model = "GoPro"
                found[model + " @ " + ip] = f"http://{ip}"
    return found

# ---------------------------------------------
# GoPro Command Sender
# ---------------------------------------------
def send_gopro_command(base_url, command):
    try:
        r = requests.get(f"{base_url}/gp/gpControl/command/{command}", timeout=1)
        return r.status_code == 200
    except:
        return False

# ---------------------------------------------
# GUI Application
# ---------------------------------------------
def run_gui():
    root = tk.Tk()
    root.title("GoPro Control Center")
    root.geometry("300x250")

    label = ttk.Label(root, text="Discovering cameras...")
    label.pack(pady=10)

    cameras = discover_gopros_on_network("192.168.1.0/24")
    if not cameras:
        cameras = {"No cameras found": "http://0.0.0.0"}

    selected_camera = tk.StringVar(value=list(cameras.keys())[0])
    camera_menu = ttk.Combobox(root, textvariable=selected_camera, values=list(cameras.keys()))
    camera_menu.pack(pady=10)

    def start_recording():
        base_url = cameras[selected_camera.get()]
        if send_gopro_command(base_url, "shutter?p=1"):
            status_label.config(text="Recording started")
        else:
            status_label.config(text="Failed to start")

    def stop_recording():
        base_url = cameras[selected_camera.get()]
        if send_gopro_command(base_url, "shutter?p=0"):
            status_label.config(text="Recording stopped")
        else:
            status_label.config(text="Failed to stop")

    ttk.Button(root, text="Start Recording", command=start_recording).pack(pady=5)
    ttk.Button(root, text="Stop Recording", command=stop_recording).pack(pady=5)

    status_label = ttk.Label(root, text="")
    status_label.pack(pady=10)

    root.mainloop()

# ---------------------------------------------
# Run the GUI
# ---------------------------------------------
if __name__ == '__main__':
    run_gui()
