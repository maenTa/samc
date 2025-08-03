import time
import copy
from flask import Flask, render_template, request, jsonify
from threading import Lock, Thread
from datetime import datetime
# from flask_httpauth import HTTPBasicAuth


app = Flask(__name__)
# auth = HTTPBasicAuth()

# driver_names = {
#     1: "Lewis Hamilton", 2: "Max Verstappen", 3: "Charles Leclerc", 4: "Sergio Perez",
#     5: "George Russell", 6: "Carlos Sainz", 7: "Lando Norris", 8: "Oscar Piastri",
#     9: "Fernando Alonso", 10: "Pierre Gasly", 11: "Esteban Ocon", 12: "Yuki Tsunoda",
#     13: "Valtteri Bottas", 14: "Zhou Guanyu", 15: "Kevin Magnussen", 16: "Nico Hulkenberg",
#     17: "Alex Albon", 18: "Logan Sargeant", 19: "Lance Stroll", 20: "Daniel Ricciardo"
# }

users = {
    "admin": "admin",
    "user": "admin"
}

driver_names  = {
    1: {
        "name": 'Giselle Hennessey',
        'logo': 'corsa.png',
        'team': 47,
        'color': 'yellow'
    },
    2: {
        "name": 'Cassandra Marcelli',
        'logo': 'sonnard.png',
        'team': 77,
        'color': 'red'
    },
    3: {
        "name": 'Aaron Cranston',
        'logo': 'sonnard.png',
        'team': 33,
        'color': 'red'
    },
    4: {
        "name": 'Jouji Nakahara',
        'logo': 'harmony.png',
        'team': 96,
        'color': 'purple'
    },
    5: {
        "name": 'Sezoku Kurosaki',
        'logo': 'zero.png',
        'team': 7,
        'color': 'cyan'
    },
    6: {
        "name": 'Tatsuji Kinomiya',
        'logo': 'harmony.png',
        'team': 69,
        'color': 'purple'
    },
    7: {
        "name": 'Sonia Lovely',
        'logo': 'corsa.png',
        'team': 29,
        'color': 'yellow'
    },
    8: {
        "name": 'Viktoriya Anastasia',
        'logo': 'agro.png',
        'team': 16,
        'color': 'green'
    },
    9: {
        "name": 'Frank Cooper',
        'logo': 'autojuice.png',
        'team': 75,
        'color': 'black'
    },
    10: {
        "name": 'John Doe',
        'logo': 'autojuice.png',
        'team': 65,
        'color': 'orange'
    },

}

# Struktur data untuk menyimpan status balapan
race_data = {
    "start_time": None,
    "drivers": {},
    "last_update": time.time(),
    "flags": {
        "safety_car": False,
        "red_flag": False,
        "yellow_flag": False
    },
    "flag_events": {
        "safety_car_end_time": 0,
        "green_flag_end_time": 0
    },
    "total_laps": 70,
    "current_lap": 0,
    "red_flag_snapshot": None,
    "safety_car_active": False,
    "yellow_flag_active": False,
    "paused": {
        'start': 0,
        'duration': 0,
        'is_paused': False
    }
}

lock = Lock()

# Inisialisasi data pembalap
for i in range(1, len(driver_names)+1):
    race_data["drivers"][i] = {
        "number": i,
        "name": driver_names[i].get('name'),
        'logo': driver_names[i].get('logo'),
        'team': driver_names[i].get('team'),
        'color': driver_names[i].get('color'),
        "laps": 0,
        "last_lap_time": 0,
        "last_lap_duration": 0,
        "position": 0,
        "lap_times": [],
        "gap": 0,
        "last_input": 0,
        'spam_counter': 0
    }

def update_positions():
    """Update posisi berdasarkan lap dan waktu terakhir"""
    drivers = race_data["drivers"].values()
    sorted_drivers = sorted(
        drivers,
        key=lambda x: (-x['laps'], x['last_lap_time'])
    )
    
    for position, driver in enumerate(sorted_drivers, 1):
        race_data["drivers"][driver['number']]['position'] = position
        
def update_gaps():
    """Update the time interval to the driver directly ahead (not the leader)"""
    drivers = list(race_data["drivers"].values())
    sorted_drivers = sorted(drivers, key=lambda x: (-x['laps'], x['last_lap_time']))

    previous_driver = None
    for driver in sorted_drivers:
        if previous_driver is None:
            driver["gap"] = 0.0  # Leader has no gap
        else:
            # If laps are different, consider full lap(s) behind
            if driver['laps'] < previous_driver['laps']:
                lap_diff = previous_driver['laps'] - driver['laps']
                avg_lap = (
                    sum(driver['lap_times']) / len(driver['lap_times'])
                    if driver['lap_times'] else 0
                )
                gap = lap_diff * avg_lap
            else:
                # Same lap, use timestamp difference
                gap = driver['last_lap_time'] - previous_driver['last_lap_time']
            driver["gap"] = round(gap, 3)
        previous_driver = driver

def update_current_lap():
    """Update current lap berdasarkan pembalap dengan lap tertinggi"""
    max_lap = max(driver['laps'] for driver in race_data["drivers"].values())
    race_data["current_lap"] = max_lap

def handle_safety_car_end():
    """Menangani akhir periode safety car"""
    with lock:
        race_data["flags"]["safety_car"] = False
        race_data["flag_events"]["green_flag_end_time"] = time.time() + 10  # Green flag selama 10 detik
        race_data["last_update"] = time.time()

def handle_yellow_flag_end():
    """Menangani akhir periode yellow flag"""
    with lock:
        race_data["flags"]["yellow_flag"] = False
        race_data["flag_events"]["green_flag_end_time"] = time.time() + 10  # Green flag selama 10 detik
        race_data["last_update"] = time.time()

def monitor_flag_events():
    """Thread untuk memonitor event flag dan mengupdate status"""
    while True:
        time.sleep(0.5)
        current_time = time.time()
        
        with lock:
            # Safety car ending sequence
            if race_data["flags"]["safety_car"] and race_data["flag_events"]["safety_car_end_time"] > 0:
                if current_time > race_data["flag_events"]["safety_car_end_time"]:
                    handle_safety_car_end()
            
            # Green flag sequence
            if race_data["flag_events"]["green_flag_end_time"] > 0:
                if current_time > race_data["flag_events"]["green_flag_end_time"]:
                    race_data["flag_events"]["green_flag_end_time"] = 0
                    race_data["last_update"] = time.time()

# Mulai thread untuk memonitor event flag
flag_monitor_thread = Thread(target=monitor_flag_events)
flag_monitor_thread.daemon = True
flag_monitor_thread.start()

# @auth.get_password
# def get_pw(username):
#     return users.get(username)

@app.route('/')
def leaderboard():
    return render_template('leaderboard.html')


# @auth.login_required
@app.route('/control/<operator_id>')
def control_panel(operator_id):
    try:
        op_id = int(operator_id)
        if op_id < 1 or op_id > 5:
            return "Operator ID tidak valid", 400
        return render_template('control.html', operator_id=operator_id)
    except ValueError:
        return "Operator ID harus angka", 400

@app.route('/start_race', methods=['POST'])
def start_race():
    with lock:
        if race_data["start_time"] is not None:
            return jsonify({"error": "Race already started!"}), 400
            
        start_time = time.time()
        race_data["start_time"] = start_time
        race_data["last_update"] = start_time
        
        # Reset semua flag
        race_data["flags"]["safety_car"] = False
        race_data["flags"]["red_flag"] = False
        race_data["flags"]["yellow_flag"] = False
        race_data["flag_events"] = {
            "safety_car_end_time": 0,
            "green_flag_end_time": 0
        }
        
        # Set start time untuk semua driver
        for driver in race_data["drivers"].values():
            driver["laps"] = 0
            driver["lap_times"] = []
            driver["last_lap_duration"] = 0
            driver["last_lap_time"] = 0
            driver["position"] = 0
            driver["start_time"] = start_time
            
        return jsonify({"status": "Race started!"})

@app.route('/restart_after_red', methods=['POST'])
def restart_after_red():
    with lock:
        if not race_data["flags"]["red_flag"]:
            return jsonify({"error": "Red flag not active!"}), 400
            
        # Nonaktifkan red flag
        race_data["flags"]["red_flag"] = False
        
        # Mulai balapan kembali
        start_time = time.time()
        race_data["start_time"] = start_time
        race_data["last_update"] = time.time()
        
        # Tambahkan 3 lap ke semua pembalap
        for driver in race_data["drivers"].values():
            # Gunakan snapshot saat red flag diaktifkan
            if race_data["red_flag_snapshot"] and driver["number"] in race_data["red_flag_snapshot"]:
                snapshot = race_data["red_flag_snapshot"][driver["number"]]
                driver["laps"] = snapshot["laps"] + 3
                driver["position"] = snapshot["position"]
            
            # Reset start time untuk lap berikutnya
            driver["start_time"] = start_time
        
        # Reset snapshot
        race_data["red_flag_snapshot"] = None
        
        return jsonify({"status": "Race restarted after red flag!"})

@app.route('/driver_input', methods=['POST'])
def driver_input():
    driver_num = int(request.form['driver_num'])
    current_time = time.time()
    
    with lock:
        if time.time() - race_data['drivers'][driver_num]['last_input'] < 30:
            if race_data['drivers'][driver_num]['spam_counter'] > 10:
                return jsonify({'error': 'JANGNAN DISPAM KONT!!!!'}), 400
            race_data['drivers'][driver_num]['spam_counter'] += 1
            return jsonify({'error': 'Someone just input this driver, please wait'}), 400
        
        if not race_data["start_time"]:
            return jsonify({"error": "Race not started!"}), 400
        
        if race_data["flags"]["red_flag"]:
            return jsonify({"error": "Red flag active!"}), 400
        
        race_data["drivers"][driver_num]['last_input'] = time.time()    
        driver = race_data["drivers"][driver_num]
        
        # Hitung durasi lap
        if driver['laps'] == 0:
            # Lap pertama
            lap_duration = current_time - race_data["start_time"]
        else:
            lap_duration = current_time - driver["start_time"]
        
        # Simpan data lap
        driver["lap_times"].append(lap_duration)
        driver["last_lap_duration"] = lap_duration
        driver["last_lap_time"] = current_time
        driver["laps"] += 1
        
        # Reset start time untuk lap berikutnya
        driver["start_time"] = current_time
        
        race_data["last_update"] = current_time
        
        
        
        update_current_lap()
        update_positions()
        update_gaps()
        
        return jsonify({
            "status": f"Driver {driver_num} - Lap {driver['laps']} recorded!",
            "lap_time": f"{lap_duration:.3f}s",
            "driver_number": driver_num,
            "current_lap": driver['laps']
        })

@app.route('/set_flag', methods=['POST'])
def set_flag():
    flag_name = request.form['flag']
    value = request.form['value'] == 'true'
    
    print(flag_name, value)
    

    if flag_name not in race_data["flags"]:
        return jsonify({"error": "Invalid flag"}), 400
        
    # Logika untuk flag yang saling eksklusif
    if flag_name == "red_flag" and value:
        # Jika mengaktifkan red flag, matikan flag lainnya
        race_data["flags"]["yellow_flag"] = False
        race_data["flags"]["safety_car"] = False
        race_data["flags"]["red_flag"] = True
        
        race_data['paused']['start'] = time.time()
        race_data['paused']['is_paused'] = True
        
        # Ambil snapshot keadaan saat ini
        race_data["red_flag_snapshot"] = {}
        for num, driver in race_data["drivers"].items():
            race_data["red_flag_snapshot"][num] = {
                "laps": driver["laps"],
                "position": driver["position"],
                "last_lap_time": driver["last_lap_time"],
                "lap_times": copy.deepcopy(driver["lap_times"])
            }
        
        # Hentikan balapan
        # race_data["start_time"] = None
        return jsonify({
            "status": "Red flag activated! Race stopped.",
            "flags": race_data["flags"]
        })
        
    elif flag_name == "yellow_flag" and value:
        # Jika mengaktifkan yellow flag, matikan red flag
        race_data["flags"]["red_flag"] = False
        race_data["flags"]["yellow_flag"] = True
        
        # Jika sebelumnya safety car aktif, nonaktifkan
        if race_data["flags"]["safety_car"]:
            race_data["flags"]["safety_car"] = False
        
        return jsonify({
            "status": "Yellow flag activated!",
            "flags": race_data["flags"]
        })
        
    elif flag_name == "yellow_flag" and not value:
        # Menonaktifkan yellow flag - mulai sequence green flag
        race_data["flags"]["yellow_flag"] = False
        race_data["flag_events"]["green_flag_end_time"] = time.time() + 10
        return jsonify({
            "status": "Yellow flag deactivated. Green flag for 10 seconds!",
            "flags": race_data["flags"]
        })
        
    elif flag_name == "safety_car" and value:
        # Jika mengaktifkan safety car, matikan red flag
        race_data["flags"]["red_flag"] = False
        race_data["flags"]["safety_car"] = True
        
        # Jika sebelumnya yellow flag aktif, nonaktifkan
        if race_data["flags"]["yellow_flag"]:
            race_data["flags"]["yellow_flag"] = False
        
        return jsonify({
            "status": "Safety car activated!",
            "flags": race_data["flags"]
        })
        
    elif flag_name == "safety_car" and not value:
        # Menonaktifkan safety car - mulai sequence ending
        race_data['flags']['safety_car'] = False
        race_data["flag_events"]["safety_car_end_time"] = time.time() + 15
        return jsonify({
            "status": "Safety car ending in 15 seconds!",
            "flags": race_data["flags"]
        })
    
    else:
        # Untuk menonaktifkan flag, langsung set ke false

        if(flag_name == 'red_flag' and not value):
            race_data['paused']['duration'] += time.time() - race_data['paused']['start'] 
            race_data['paused']['start'] = 0
            race_data['paused']['is_paused'] = False
        
        race_data["flags"][flag_name] = value
        return jsonify({
            "status": f"{flag_name} set to {value}",
            "flags": race_data["flags"]
        })

@app.route('/race_data')
def get_race_data():
    with lock:
        is_safety_car_end_time_float = isinstance(race_data['flag_events']['safety_car_end_time'], float)
        if(is_safety_car_end_time_float):
            race_data['flag_events']['safety_car_end_time'] = race_data['flag_events']['safety_car_end_time'] if race_data['flag_events']['safety_car_end_time'] > time.time()  > 0 else None
            
        print(race_data['flag_events']['safety_car_end_time'])
        return jsonify({
            "drivers": list(race_data["drivers"].values()),
            "elapsed_time": time.time() - race_data["start_time"] if race_data["start_time"] else 0,
            "last_update": race_data["last_update"],
            "flags": race_data["flags"],
            "flag_events": race_data["flag_events"],
            "current_lap": race_data["current_lap"],
            "total_laps": race_data["total_laps"],
            "red_flag_snapshot": race_data["red_flag_snapshot"] is not None,
            "start_time": race_data['start_time'],
            'paused': race_data['paused']
        })

@app.route('/director_image')
def get_director_image():
    return jsonify({
        "image_url": "/static/drivers/logo_samc.png"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)