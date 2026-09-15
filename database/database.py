import sqlite3
import os

# ============================================================
# KRISHI SETU DATABASE
# ============================================================

# Database will be created inside the database folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "krishi_setu.db")


# ============================================================
# CREATE DATABASE CONNECTION
# ============================================================

def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# CREATE TABLES
# ============================================================

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # ========================================================
    # FARMERS TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farmers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password_hash TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # ========================================================
    # SENSOR HISTORY TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            farmer_id INTEGER NOT NULL,

            soil_raw INTEGER,

            soil_moisture REAL,

            soil_condition TEXT,

            water_raw INTEGER,

            water_level REAL,

            water_condition TEXT,

            pump_status TEXT,

            pump_reason TEXT,

            pump_decision TEXT,

            rain_status TEXT,

            temperature REAL,

            humidity REAL,

            dht_status TEXT,

            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (farmer_id)
                REFERENCES farmers(id)

        )
    """)


    # ========================================================
    # SAVE CHANGES
    # ========================================================

    connection.commit()

    connection.close()

    print("========================================")
    print("       KRISHI SETU DATABASE")
    print("========================================")
    print("Database created successfully!")
    print()
    print("Database file:")
    print(DATABASE_PATH)
    print()
    print("Tables created:")
    print("1. farmers")
    print("2. sensor_history")
    print("========================================")


# ============================================================
# RUN DATABASE INITIALIZATION
# ============================================================

if __name__ == "__main__":

    initialize_database()