import requests
import json
import pandas as pd
import time
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

# --- CONFIGURATION ---
DB_NAME = "trading_data.db"
URL = "https://scanner.tradingview.com/options/scan2?label-product=options-builder"
INTERVAL = 5

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Create table for PCR history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pcr_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            pcr REAL,
            pcr_change REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(pcr, pcr_change):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO pcr_history (timestamp, pcr, pcr_change)
        VALUES (?, ?, ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), pcr, pcr_change))
    conn.commit()
    conn.close()

# --- PCR LOGIC ---
PAYLOAD = {
    "filter": [], 
    "columns": ["option-type", "open_interest", "strike"],
    "sort": {"sort_by": "strike", "ascending": True}
}

def calculate_pcr(data_list):
    # Using Open Interest for PCR as per standard practice
    puts_oi = sum(item.get('open_interest', 0) or 0 for item in data_list if item.get('option-type') == 'put')
    calls_oi = sum(item.get('open_interest', 0) or 0 for item in data_list if item.get('option-type') == 'call')
    return round(puts_oi / calls_oi, 4) if calls_oi > 0 else 0

# --- INITIALIZATION ---
init_db()
history = pd.DataFrame(columns=["timestamp", "pcr", "pcr_change"])
plt.ion()

print(f"Logging started. Saving to {DB_NAME}...")

try:
    while True:
        try:
            response = requests.post(URL, json=PAYLOAD, timeout=10)
            if response.status_code == 200:
                data = response.json()
                fields = data.get("fields", [])
                symbols_data = data.get("symbols", [])
                
                extracted_list = [dict(zip(fields, item["f"])) for item in symbols_data]
                
                # Calculations
                current_pcr = calculate_pcr(extracted_list)
                prev_pcr = history["pcr"].iloc[-1] if not history.empty else current_pcr
                pcr_change = round(current_pcr - prev_pcr, 4)
                current_time = datetime.now().strftime('%H:%M:%S')

                # 1. Save to SQLite
                save_to_db(current_pcr, pcr_change)

                # 2. Update Local DataFrame for Plotting
                new_row = {"timestamp": current_time, "pcr": current_pcr, "pcr_change": pcr_change}
                history = pd.concat([history, pd.DataFrame([new_row])], ignore_index=True)

                # 3. Live Plotting
                plt.clf()
                fig, ax1 = plt.subplots(num=1, figsize=(10, 5))
                ax1.plot(history["timestamp"], history["pcr"], color='blue', label="Total PCR")
                ax2 = ax1.twinx()
                ax2.bar(history["timestamp"], history["pcr_change"], color='red', alpha=0.3, label="Change")
                plt.title(f"Live PCR Tracker (Last Update: {current_time})")
                plt.xticks(rotation=45)
                plt.pause(0.05)

                print(f"Logged to DB: {current_time} | PCR: {current_pcr}")

        except Exception as e:
            print(f"Loop Error: {e}")

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print("Stopping and saving...")