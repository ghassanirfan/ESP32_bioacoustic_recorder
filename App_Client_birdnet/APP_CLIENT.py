import socket
import time
import requests
from zeroconf import ServiceBrowser, Zeroconf
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from threading import Thread
import os
import subprocess
import pandas as pd
import sys

is_recording = False
start_time = None
selected_esp = None
esp_list = {}
timer_label = None
timer_running = False
download_progress = None
download_folder_path = None
selected_files = []

class EspListener:
    def __init__(self):
        self.esp32_list = {}

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
            self.esp32_list[name] = ip

    def update_service(self, zeroconf, type, name):
        pass

def scan_esp():
    listener = EspListener()
    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    time.sleep(5)
    zeroconf.close()
    return listener.esp32_list

def reset_esp(esp_ip):
    url = f"http://{esp_ip}/reset"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            messagebox.showinfo("Success", "ESP reset successfully")
        else:
            messagebox.showerror("Error", "Failed to reset ESP")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Request failed: {e}")

def run_analysis_thread():
    # Fungsi untuk menjalankan proses analisis dalam thread terpisah
    input_path = input_file_path.get()
    output_path = output_file_path.get()
    min_confidence = min_confidence_var.get()
    sensitivity = sensitivity_var.get()

    if not input_path:
        messagebox.showerror("Error", "Please select an input file.")
        return
    if not output_path:
        messagebox.showerror("Error", "Please select an output file.")
        return

    # Construct the command with the correct path to analyze.py
    birdnet_analyzer_path = os.path.join("Birdnet-Analyzer", "analyze.py")
    command = [
        "python", birdnet_analyzer_path,
        "--i", input_path,
        "--o", output_path,
        "--rtype", "csv",
        "--lat", "-1",
        "--lon", "-1",
        "--min_conf", str(min_confidence),
        "--sensitivity", str(sensitivity)
    ]

    try:
        subprocess.run(command, check=True)
        messagebox.showinfo("Success", "BirdNET Analyzer completed successfully.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"BirdNET Analyzer failed: {e}")

def run_analysis():
    # Fungsi untuk memulai thread analisis
    analysis_thread = Thread(target=run_analysis_thread)
    analysis_thread.start()

def start_recording(esp32_ip):
    global start_time, timer_running
    url = f"http://{esp32_ip}/start"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            start_time = time.time()
            timer_running = True
            Thread(target=update_timer).start()
            messagebox.showinfo("Success", f"Recording started on {esp32_ip}")
        else:
            messagebox.showerror("Error", f"Failed to start recording on {esp32_ip}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Request failed: {e}")

def stop_recording(esp32_ip):
    global start_time, timer_running
    url = f"http://{esp32_ip}/stop"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            if start_time:
                duration = time.time() - start_time
                start_time = None
                timer_running = False
                timer_label.config(text="Recording Duration: 00:00:00")
                messagebox.showinfo("Success", f"Recording stopped on {esp32_ip}\nDuration: {duration:.2f} seconds")
        else:
            messagebox.showerror("Error", f"Failed to stop recording on {esp32_ip}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Request failed: {e}")

def get_file_list(esp32_ip):
    url = f"http://{esp32_ip}/list"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_list = response.text.split('\n')
            file_details = []
            for file_info in file_list:
                if file_info.strip():
                    parts = file_info.split(' - ')
                    file_name = parts[0].strip()
                    file_size = parts[1].strip() if len(parts) > 1 else 'Unknown size'
                    file_details.append((file_name, file_size))
            return file_details
        else:
            messagebox.showerror("Error", f"Failed to get file list from {esp32_ip}")
            return []
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Request failed: {e}")
        return []

def download_file(esp32_ip, filename=None):
    global download_progress
    url_base = f"http://{esp32_ip}/download"
    if filename:
        url = f"{url_base}?file={filename}"
        Thread(target=download_single_file, args=(url, filename)).start()
    else:
        files = get_file_list(esp32_ip)
        for file in files:
            if file:
                url = f"{url_base}?file={file}"
                Thread(target=download_single_file, args=(url, file)).start()

def merge_csv_files():
    global selected_files
    # Memilih folder yang berisi file-file CSV yang akan digabungkan
    folder_path = filedialog.askdirectory()
    if not folder_path:
        messagebox.showwarning("Warning", "No folder selected")
        return
    
    # Mendapatkan semua file CSV di dalam folder
    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    if not csv_files:
        messagebox.showwarning("Warning", "No CSV files found in the selected folder")
        return
    
    merged_df = pd.DataFrame()
    
    for csv_file in csv_files:
        file_path = os.path.join(folder_path, csv_file)
        df = pd.read_csv(file_path)
        df['Source'] = csv_file  # Menambahkan kolom "Source" yang berisi nama file CSV
        merged_df = pd.concat([merged_df, df], ignore_index=True)
    
    # Memilih folder untuk menyimpan file CSV yang telah digabungkan
    save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if save_path:
        merged_df.to_csv(save_path, index=False)
        messagebox.showinfo("Success", f"CSV files merged and saved to {save_path}")
    else:
        messagebox.showwarning("Warning", "No save location selected")

def select_download_folder():
    global download_folder_path
    download_folder_path = filedialog.askdirectory()
    if download_folder_path:
        messagebox.showinfo("Success", f"Download folder set to: {download_folder_path}")
    else:
        messagebox.showwarning("Warning", "No folder selected for download")

def download_single_file(url, filename):
    global download_progress
    try:
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        total_size_mb = total_size / (1024 * 1024)
        if response.status_code == 200:
            with open(os.path.join(download_folder_path, filename), 'wb') as f:
                downloaded_size = 0
                start_time = time.time()
                for data in response.iter_content(chunk_size=1024):
                    f.write(data)
                    downloaded_size += len(data)
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    download_speed = (downloaded_size / elapsed_time) / 1024 if elapsed_time != 0 else 0
                    downloaded_size_mb = downloaded_size / (1024 * 1024)
                    download_status = f"Progress: {downloaded_size_mb:.2f} / {total_size_mb:.2f} MB | Speed: {download_speed:.2f} KB/s"
                    download_progress.config(text=download_status)
                    root.update_idletasks()
            messagebox.showinfo("Success", f"File {filename} downloaded to {download_folder_path}")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Download failed: {e}")

def sync_time(esp32_ip):
    current_time = int(time.mktime(datetime.now().timetuple()))
    url = f"http://{esp32_ip}/set_time?time={current_time}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            messagebox.showinfo("Success", "Time synchronized successfully")
        else:
            messagebox.showerror("Error", "Failed to synchronize time")
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Request failed: {e}")

def select_esp():
    global selected_esp, esp_list
    esp_list = scan_esp()
    if not esp_list:
        messagebox.showwarning("Warning", "No ESP32 devices found.")
        return

    esp_listbox.delete(0, tk.END)
    for esp32_name, esp32_ip in esp_list.items():
        esp_listbox.insert(tk.END, f"{esp32_name} ({esp32_ip})")

def on_esp_select(event):
    global selected_esp
    selection = esp_listbox.curselection()
    if selection:
        selected_index = selection[0]
        selected_esp_name_ip = esp_listbox.get(selected_index)
        selected_esp = selected_esp_name_ip.split('(')[1][:-1]
        sync_time(selected_esp)

def scan_command():
    select_esp()

def start_command():
    global is_recording
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        is_recording = True
        start_recording(selected_esp)

def stop_command():
    global is_recording
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        stop_recording(selected_esp)
        is_recording = False

def reset_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        reset_esp(selected_esp)

def get_files_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        files = get_file_list(selected_esp)
        files_listbox.delete(0, tk.END)
        for file_name, file_size in files:
            files_listbox.insert(tk.END, f"{file_name} - {file_size}")

def download_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        selection = files_listbox.curselection()
        if selection:
            selected_file = files_listbox.get(selection[0])
            filename = selected_file.split(' - ')[0].strip()  # Extract the file name part
            download_file(selected_esp, filename)
        else:
            messagebox.showwarning("Warning", "No file selected")

def delete_file_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        selection = files_listbox.curselection()
        if selection:
            selected_file = files_listbox.get(selection[0])
            filename = selected_file.split(' - ')[0].strip()  # Extract the file name part
            url = f"http://{selected_esp}/delete?file={filename}"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    messagebox.showinfo("Success", f"File {filename} deleted from {selected_esp}")
                    get_files_command()  # Refresh file list after deletion
                else:
                    messagebox.showerror("Error", f"Failed to delete file {filename}")
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", f"Request failed: {e}")
        else:
            messagebox.showwarning("Warning", "No file selected")

def rename_file_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        selection = files_listbox.curselection()
        if selection:
            selected_file = files_listbox.get(selection[0])
            old_filename = selected_file.split(' - ')[0].strip()  # Extract the file name part

            # Memunculkan dialog sederhana untuk menginput nama baru
            new_filename = simpledialog.askstring("Rename File", f"Enter new name for '{old_filename}':")
            if new_filename:
                url = f"http://{selected_esp}/rename?file={old_filename}&new_name={new_filename}"
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        messagebox.showinfo("Success", f"File {old_filename} renamed to {new_filename}")
                        get_files_command()  # Refresh file list after renaming
                    else:
                        messagebox.showerror("Error", f"Failed to rename file {old_filename}")
                except requests.exceptions.RequestException as e:
                    messagebox.showerror("Error", f"Request failed: {e}")
        else:
            messagebox.showwarning("Warning", "No file selected")

def sync_command():
    if not selected_esp:
        messagebox.showwarning("Warning", "No ESP selected")
    else:
        sync_time(selected_esp)

def update_timer():
    global start_time, timer_label, timer_running
    while timer_running:
        elapsed_time = int(time.time() - start_time)
        timer_label.config(text=f"Recording Duration: {time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}")
        time.sleep(1)

def exit_command():
    root.quit()

# GUI Setup
root = tk.Tk()
root.title("Client APP Recording Devices")
root.geometry('600x650')

# Path to the azure-dark theme file
theme_path = os.path.join(os.path.dirname(__file__), "azure.tcl")

# Apply the azure-dark theme
root.tk.call("source", theme_path)
root.tk.call("set_theme", "dark")
style = ttk.Style(root)
style.theme_use("azure-dark")

# Tabs for ESP32 devices and files
tab_parent = ttk.Notebook(root)
tab_parent.pack(expand=True, fill="both")

# ESP32 Devices tab
esp_tab = ttk.Frame(tab_parent)
tab_parent.add(esp_tab, text="Recording Devices")
esp_tab.columnconfigure(0, weight=1)
esp_tab.rowconfigure(0, weight=1)

esp_frame = ttk.LabelFrame(esp_tab, text="Choose Recording Devices")
esp_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
esp_listbox = tk.Listbox(esp_frame, height=10, width=79)
esp_listbox.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
esp_listbox.bind('<<ListboxSelect>>', on_esp_select)
ttk.Button(esp_frame, text="Scan for Recording Devices", command=scan_command).grid(row=1, column=0, pady=5)

# Files tab
files_tab = ttk.Frame(tab_parent)
tab_parent.add(files_tab, text="Files")
files_tab.columnconfigure(0, weight=1)
files_tab.rowconfigure(0, weight=1)

files_frame = ttk.LabelFrame(files_tab, text="Files")
files_frame.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
files_listbox = tk.Listbox(files_frame, height=10, width=79)
files_listbox.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
ttk.Button(files_frame, text="Get file list", command=get_files_command).grid(row=1, column=0, pady=5)
ttk.Button(files_frame, text="Select Download Folder", command=select_download_folder).grid(row=2, column=0, padx=10, pady=5, sticky="ew")
ttk.Button(files_frame, text="Download file", command=download_command).grid(row=3, column=0, padx=10, pady=5, sticky="ew")
ttk.Button(files_frame, text="Delete file", command=delete_file_command).grid(row=4, column=0, padx=10, pady=5, sticky="ew")


# BirdNET Analyzer tab
analyzer_tab = ttk.Frame(tab_parent)
tab_parent.add(analyzer_tab, text="BirdNET Analyzer")
analyzer_tab.columnconfigure(0, weight=1)
analyzer_tab.rowconfigure(0, weight=1)

analyzer_frame = ttk.LabelFrame(analyzer_tab, text="BirdNET Analyzer Settings (Multiple FIle)")
analyzer_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))

ttk.Label(analyzer_frame, text="Input Folder:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
input_file_path = tk.StringVar()
ttk.Entry(analyzer_frame, textvariable=input_file_path).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
ttk.Button(analyzer_frame, text="Browse", command=lambda: input_file_path.set(filedialog.askdirectory())).grid(row=0, column=2, padx=5, pady=5)

ttk.Label(analyzer_frame, text="Output Folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
output_file_path = tk.StringVar()
ttk.Entry(analyzer_frame, textvariable=output_file_path).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
ttk.Button(analyzer_frame, text="Browse", command=lambda: output_file_path.set(filedialog.askdirectory())).grid(row=1, column=2, padx=5, pady=5)

ttk.Label(analyzer_frame, text="Min Confidence:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
min_confidence_var = tk.DoubleVar(value=0.5)
ttk.Entry(analyzer_frame, textvariable=min_confidence_var).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

ttk.Label(analyzer_frame, text="Sensitivity:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.E)
sensitivity_var = tk.DoubleVar(value=1.0)
ttk.Entry(analyzer_frame, textvariable=sensitivity_var).grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

ttk.Label(analyzer_frame, text="Latitude:").grid(row=4, column=0, padx=5, pady=5, sticky=tk.E)
latitude_var = tk.DoubleVar(value=-1)
ttk.Entry(analyzer_frame, textvariable=latitude_var).grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

ttk.Label(analyzer_frame, text="Longitude:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.E)
longitude_var = tk.DoubleVar(value=-1)
ttk.Entry(analyzer_frame, textvariable=longitude_var).grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)


ttk.Button(analyzer_frame, text="Run analiyis", command=run_analysis).grid(row=6, column=0, columnspan=3, pady=10)
ttk.Button(analyzer_frame, text="Merge CSV Files", command=merge_csv_files).grid(row=7, column=0, columnspan=3, pady=10)

# About tab
about_tab = ttk.Frame(tab_parent)
tab_parent.add(about_tab, text="About")
about_tab.columnconfigure(0, weight=1)
about_tab.rowconfigure(0, weight=1)

about_text = """
ESP32 Recorder v1.0

This program allows you to control ESP32 recording devices,
download recorded files, and analyze recordings with BirdNET-analyzer.

Authors: Ghassan Irfan

License: -

Project Funding: Departement Of Biology, Sebelas Maret University

For more information, visit github.com/ghassanirfan
or contact me : ghassanirfan@student.uns.ac.id
This Application is not associated BirdNET-Lite, BirdNET-Analyzer and only for educational use
Thanks to BirdNet-Analyzer K.Lisa Yang center for Conservation Bioacoustics
"""

about_label = ttk.Label(about_tab, text=about_text, wraplength=500, justify=tk.LEFT)
about_label.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
# Download progress
progress_frame = ttk.Frame(root)
progress_frame.pack(pady=10)
download_progress = ttk.Label(progress_frame, text="Progress: 0 / 0 MB | Speed: 0 KB/s")
download_progress.pack(fill="x", padx=10, pady=5)

# Actions
action_frame = ttk.LabelFrame(root, text="Actions")
action_frame.pack(padx=10, pady=5, fill="x")
action_frame.columnconfigure(0, weight=1)

ttk.Button(action_frame, text="Start recording", command=start_command).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
ttk.Button(action_frame, text="Stop recording", command=stop_command).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
ttk.Button(action_frame, text="Reset ESP", command=reset_command).grid(row=0, column=2, padx=5, pady=5, sticky="ew")
ttk.Button(action_frame, text="Sync time", command=sync_command).grid(row=0, column=3, padx=5, pady=5, sticky="ew")

# Recording Duration
timer_label = ttk.Label(action_frame, text="Recording Duration: 00:00:00")
timer_label.grid(row=1, column=0, columnspan=4, pady=5)

# Exit button
ttk.Button(root, text="Exit", command=exit_command).pack(pady=10, fill="x")

root.mainloop()
