from flask import Flask, jsonify, request
from flask_cors import CORS
import serial
import threading
import re
import time
import sqlite3

# ============================================================
# FLASK SERVER
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# ESP32 SERIAL SETTINGS
# ============================================================

SERIAL_PORT = "COM7"
BAUD_RATE = 115200


# ============================================================
# DATABASE SETTINGS
# ============================================================

DATABASE_PATH = r"D:\KrishiSetu\database\krishi_setu.db"


def get_db_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10
    )
    connection.row_factory = sqlite3.Row
    return connection


def save_sensor_history(farmer_id, reading):
    if farmer_id is None:
        return False

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            '''
            INSERT INTO sensor_history (
                farmer_id,
                soil_raw,
                soil_moisture,
                soil_condition,
                water_raw,
                water_level,
                water_condition,
                pump_status,
                pump_reason,
                pump_decision,
                rain_status,
                temperature,
                humidity,
                dht_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                farmer_id,
                reading.get("soil_raw"),
                reading.get("soil_moisture"),
                reading.get("soil_condition"),
                reading.get("water_raw"),
                reading.get("water_level"),
                reading.get("water_condition"),
                reading.get("pump_status"),
                reading.get("pump_reason"),
                reading.get("pump_decision"),
                reading.get("rain_status"),
                reading.get("temperature"),
                reading.get("humidity"),
                reading.get("dht_status")
            )
        )

        connection.commit()
        return True

    except Exception as error:
        print("Database history save error:", error)
        return False

    finally:
        if connection is not None:
            connection.close()


def get_sensor_history(farmer_id, limit=100):
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            '''
            SELECT
                id,
                farmer_id,
                soil_raw,
                soil_moisture,
                soil_condition,
                water_raw,
                water_level,
                water_condition,
                pump_status,
                pump_reason,
                pump_decision,
                rain_status,
                temperature,
                humidity,
                dht_status,
                recorded_at
            FROM sensor_history
            WHERE farmer_id = ?
            ORDER BY id DESC
            LIMIT ?
            ''',
            (farmer_id, limit)
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    finally:
        if connection is not None:
            connection.close()




# ============================================================
# CURRENT SENSOR DATA
#
# IMPORTANT:
# The API only receives a COMPLETE sensor cycle at once.
# This prevents the website from seeing half-updated values.
# ============================================================

sensor_data = {
    "soil_raw": 0,
    "soil_moisture": 0,
    "soil_condition": "UNKNOWN",

    "water_raw": 0,
    "water_level": 0,
    "water_condition": "UNKNOWN",

    "pump_status": "UNKNOWN",
    "pump_reason": "UNKNOWN",
    "pump_decision": "UNKNOWN",

    "rain_status": "UNKNOWN",

    "temperature": 0,
    "humidity": 0,
    "dht_status": "UNKNOWN",

    "last_update": ""
}


# Lock protects sensor_data while the API reads it
data_lock = threading.Lock()


# ============================================================
# SERIAL CONNECTION
# ============================================================

ser = None


def connect_serial():

    global ser

    while True:

        try:

            if ser is None or not ser.is_open:

                print(
                    f"Connecting to ESP32 on {SERIAL_PORT}..."
                )

                ser = serial.Serial(
                    SERIAL_PORT,
                    BAUD_RATE,
                    timeout=1
                )

                print(
                    "ESP32 connected successfully."
                )

            return

        except Exception as e:

            print(
                "ESP32 connection failed."
            )

            print(
                "Error:",
                e
            )

            print(
                "Retrying in 3 seconds..."
            )

            time.sleep(3)


# ============================================================
# CONVERT A COMPLETE SERIAL BLOCK INTO ONE READING
# ============================================================

def create_empty_reading():

    return {

        "soil_raw": None,
        "soil_moisture": None,
        "soil_condition": None,

        "water_raw": None,
        "water_level": None,
        "water_condition": None,

        "pump_status": None,
        "pump_reason": None,
        "pump_decision": None,

        "rain_status": None,

        "temperature": None,
        "humidity": None,
        "dht_status": None
    }


def publish_complete_reading(reading):

    global sensor_data

    # Do not publish until the important sensor sections
    # have actually been received.
    required_values = [
        reading["soil_moisture"],
        reading["water_level"],
        reading["pump_status"],
        reading["rain_status"]
    ]

    if any(value is None for value in required_values):

        return False

    with data_lock:

        # Keep the previous valid DHT values if the current
        # DHT11 cycle reports SENSOR ERROR.
        new_data = dict(sensor_data)

        # ----------------------------------------------------
        # SOIL
        # ----------------------------------------------------

        if reading["soil_raw"] is not None:
            new_data["soil_raw"] = reading["soil_raw"]

        if reading["soil_moisture"] is not None:
            new_data["soil_moisture"] = reading["soil_moisture"]

        if reading["soil_condition"] is not None:
            new_data["soil_condition"] = (
                reading["soil_condition"]
            )


        # ----------------------------------------------------
        # WATER LEVEL
        # ----------------------------------------------------

        if reading["water_raw"] is not None:
            new_data["water_raw"] = reading["water_raw"]

        if reading["water_level"] is not None:
            new_data["water_level"] = reading["water_level"]

        if reading["water_condition"] is not None:
            new_data["water_condition"] = (
                reading["water_condition"]
            )


        # ----------------------------------------------------
        # WATER PUMP
        # ----------------------------------------------------

        if reading["pump_status"] is not None:
            new_data["pump_status"] = (
                reading["pump_status"]
            )

        if reading["pump_reason"] is not None:
            new_data["pump_reason"] = (
                reading["pump_reason"]
            )

        if reading["pump_decision"] is not None:
            new_data["pump_decision"] = (
                reading["pump_decision"]
            )


        # ----------------------------------------------------
        # RAIN
        # ----------------------------------------------------

        if reading["rain_status"] is not None:
            new_data["rain_status"] = (
                reading["rain_status"]
            )


        # ----------------------------------------------------
        # DHT11
        # ----------------------------------------------------

        if reading["dht_status"] is not None:

            new_data["dht_status"] = (
                reading["dht_status"]
            )

        if (
            reading["dht_status"] == "OK"
            and reading["temperature"] is not None
            and reading["humidity"] is not None
        ):

            new_data["temperature"] = (
                reading["temperature"]
            )

            new_data["humidity"] = (
                reading["humidity"]
            )


        # ----------------------------------------------------
        # ONE TIMESTAMP FOR THE WHOLE READING
        # ----------------------------------------------------

        new_data["last_update"] = (
            time.strftime("%Y-%m-%d %H:%M:%S")
        )

        # Atomic replacement:
        # the API sees either the old complete reading
        # or the new complete reading, never a mixture.
        sensor_data = new_data

    return True


# ============================================================
# SERIAL DATA READER
# ============================================================

def read_serial_data():

    global ser

    connect_serial()

    current_section = ""

    # Holds one complete ESP32 sensor cycle
    pending = create_empty_reading()

    while True:

        try:

            if ser is None or not ser.is_open:

                connect_serial()

                current_section = ""
                pending = create_empty_reading()


            line = ser.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()


            if not line:
                continue


            print("ESP32:", line)


            upper_line = line.upper()


            # =================================================
            # START OF A NEW SENSOR CYCLE
            # =================================================
            #
            # Some ESP32 programs do not print a final
            # "SENSOR READING COMPLETED" line. Instead, they
            # immediately start the next cycle with "SOIL SENSOR".
            # Therefore publish the previous complete cycle here.
            # =================================================

            if re.fullmatch(r"SOIL SENSOR", upper_line.strip()):

                if publish_complete_reading(pending):

                    print(
                        ">>> COMPLETE SENSOR READING PUBLISHED <<<"
                    )

                current_section = "soil"
                pending = create_empty_reading()

                continue


            # =================================================
            # END OF SENSOR CYCLE
            # =================================================

            if (
                "SENSOR READING COMPLETED" in upper_line
                or "WAITING FOR NEXT READING" in upper_line
            ):

                if publish_complete_reading(pending):

                    print(
                        ">>> COMPLETE SENSOR READING PUBLISHED <<<"
                    )

                current_section = ""
                pending = create_empty_reading()

                continue


            # =================================================
            # SECTION DETECTION
            # =================================================
            #
            # IMPORTANT:
            # Do NOT use "WATER LEVEL" in upper_line here.
            # A data line such as:
            #     Water Level : 35%
            # also contains "WATER LEVEL".
            # The old code therefore skipped the actual value.
            # =================================================

            if re.fullmatch(r"WATER LEVEL", upper_line.strip()):

                current_section = "water"

                continue


            if re.fullmatch(r"WATER PUMP", upper_line.strip()):

                current_section = "pump"

                continue


            if re.fullmatch(r"RAIN SENSOR", upper_line.strip()):

                current_section = "rain"

                continue


            if re.fullmatch(r"DHT11 SENSOR", upper_line.strip()):

                current_section = "dht"

                continue


            # =================================================
            # SOIL SENSOR
            # =================================================

            if current_section == "soil":

                match = re.search(
                    r"Raw Value\s*:\s*(\d+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["soil_raw"] = int(
                        match.group(1)
                    )


                match = re.search(
                    r"Moisture\s*:\s*(\d+)\s*%",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["soil_moisture"] = int(
                        match.group(1)
                    )


                match = re.search(
                    r"Condition\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["soil_condition"] = (
                        match.group(1).strip()
                    )


            # =================================================
            # WATER LEVEL
            # =================================================

            elif current_section == "water":

                match = re.search(
                    r"Raw Value\s*:\s*(\d+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["water_raw"] = int(
                        match.group(1)
                    )


                match = re.search(
                    r"Water Level\s*:\s*(\d+)\s*%",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["water_level"] = int(
                        match.group(1)
                    )


                match = re.search(
                    r"Condition\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["water_condition"] = (
                        match.group(1).strip()
                    )


            # =================================================
            # WATER PUMP
            # =================================================

            elif current_section == "pump":

                match = re.search(
                    r"Status\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["pump_status"] = (
                        match.group(1).strip()
                    )


                match = re.search(
                    r"Reason\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["pump_reason"] = (
                        match.group(1).strip()
                    )


                match = re.search(
                    r"Decision\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["pump_decision"] = (
                        match.group(1).strip()
                    )


            # =================================================
            # RAIN SENSOR
            # =================================================

            elif current_section == "rain":

                match = re.search(
                    r"Rain Status\s*:\s*(.+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["rain_status"] = (
                        match.group(1).strip()
                    )


            # =================================================
            # DHT11 SENSOR
            # =================================================

            elif current_section == "dht":

                if "SENSOR ERROR" in upper_line:

                    pending["dht_status"] = (
                        "SENSOR ERROR"
                    )

                    continue


                match = re.search(
                    r"Temperature\s*:\s*([0-9.]+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["temperature"] = float(
                        match.group(1)
                    )


                match = re.search(
                    r"Humidity\s*:\s*([0-9.]+)",
                    line,
                    re.IGNORECASE
                )

                if match:

                    pending["humidity"] = float(
                        match.group(1)
                    )


                # Only call DHT valid after both values
                # have been received.
                if (
                    pending["temperature"] is not None
                    and pending["humidity"] is not None
                ):

                    pending["dht_status"] = "OK"


        except Exception as e:

            print(
                "Serial reading error:",
                e
            )


            try:

                if ser is not None:

                    ser.close()

            except Exception:
                pass


            ser = None

            current_section = ""

            pending = create_empty_reading()

            time.sleep(2)


# ============================================================
# API ROUTE
# ============================================================

@app.route("/api/data")
def get_data():

    # Return a consistent snapshot.
    with data_lock:

        return jsonify(
            dict(sensor_data)
        )


# ============================================================
# SENSOR HISTORY API
# ============================================================

@app.route("/api/history/<int:farmer_id>", methods=["GET"])
def history(farmer_id):
    try:
        limit = request.args.get("limit", 100, type=int)
        limit = max(1, min(limit, 500))

        rows = get_sensor_history(farmer_id, limit)

        return jsonify({
            "success": True,
            "farmer_id": farmer_id,
            "count": len(rows),
            "history": rows
        })

    except Exception as error:
        print("History fetch error:", error)

        return jsonify({
            "success": False,
            "message": "Could not retrieve sensor history."
        }), 500


@app.route("/api/history/save", methods=["POST"])
def history_save():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "No history data received."
            }), 400

        farmer_id = data.get("farmer_id")

        if farmer_id is None:
            return jsonify({
                "success": False,
                "message": "farmer_id is required."
            }), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM farmers WHERE id = ?",
            (farmer_id,)
        )

        farmer = cursor.fetchone()
        connection.close()

        if farmer is None:
            return jsonify({
                "success": False,
                "message": "Farmer not found."
            }), 404

        reading = data.get("reading", data)

        if save_sensor_history(farmer_id, reading):
            return jsonify({
                "success": True,
                "message": "Sensor reading saved successfully."
            })

        return jsonify({
            "success": False,
            "message": "Could not save sensor reading."
        }), 500

    except Exception as error:
        print("History save API error:", error)

        return jsonify({
            "success": False,
            "message": "Could not save sensor history."
        }), 500


@app.route("/api/history/test", methods=["GET"])
def history_database_test():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM sensor_history"
        )

        result = cursor.fetchone()
        connection.close()

        return jsonify({
            "success": True,
            "database": "connected",
            "sensor_history_count": result["total"]
        })

    except Exception as error:
        print("Sensor history database test error:", error)

        return jsonify({
            "success": False,
            "database": "connection failed",
            "error": str(error)
        }), 500


# ============================================================
# TEST ROUTE
# ============================================================

@app.route("/")
def home():

    return """
    <h1>Krishi Setu Backend</h1>
    <p>ESP32 backend is running.</p>
    <p>Sensor API: /api/data</p>
    """


# ============================================================
# START SERIAL THREAD
# ============================================================

serial_thread = threading.Thread(
    target=read_serial_data,
    daemon=True
)

serial_thread.start()


# ============================================================
# START FLASK SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "       KRISHI SETU BACKEND"
    )

    print(
        "========================================"
    )

    print(
        "ESP32 Port :",
        SERIAL_PORT
    )

    print(
        "Baud Rate  :",
        BAUD_RATE
    )

    print(
        "API        : http://127.0.0.1:5000/api/data"
    )

    print(
        "========================================"
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
