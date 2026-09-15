# ============================================================
#                    KRISHI SETU
#              FARMER AUTHENTICATION BACKEND
# ============================================================

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

import sqlite3
import os
import sys


# ============================================================
# PATH CONFIGURATION
# ============================================================

# Get the KrishiSetu project folder
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

# Database location
DATABASE_PATH = os.path.join(
    BASE_DIR,
    "database",
    "krishi_setu.db"
)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

# Secret key used for login sessions
# We will change this to an environment variable
# before AWS deployment.
app.secret_key = "krishi-setu-development-secret-key"


# Allow frontend to communicate with backend
CORS(
    app,
    supports_credentials=True
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# HOME / TEST ROUTE
# ============================================================

@app.route("/")
def home():

    return jsonify({
        "status": "success",
        "message": "Krishi Setu Authentication Backend is running"
    })


# ============================================================
# FARMER REGISTRATION
# ============================================================

@app.route(
    "/api/auth/register",
    methods=["POST"]
)
def register():

    try:

        # ----------------------------------------------------
        # GET JSON DATA
        # ----------------------------------------------------

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No registration data received."
            }), 400


        # ----------------------------------------------------
        # GET VALUES
        # ----------------------------------------------------

        name = data.get(
            "name",
            ""
        ).strip()

        email = data.get(
            "email",
            ""
        ).strip().lower()

        password = data.get(
            "password",
            ""
        )


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not name:

            return jsonify({
                "success": False,
                "message": "Please enter your name."
            }), 400


        if not email:

            return jsonify({
                "success": False,
                "message": "Please enter your email."
            }), 400


        if not password:

            return jsonify({
                "success": False,
                "message": "Please enter your password."
            }), 400


        if len(password) < 6:

            return jsonify({
                "success": False,
                "message": "Password must contain at least 6 characters."
            }), 400


        # ----------------------------------------------------
        # CHECK EMAIL FORMAT
        # ----------------------------------------------------

        if "@" not in email or "." not in email:

            return jsonify({
                "success": False,
                "message": "Please enter a valid email address."
            }), 400


        # ----------------------------------------------------
        # CONNECT DATABASE
        # ----------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor()


        # ----------------------------------------------------
        # CHECK WHETHER FARMER ALREADY EXISTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM farmers
            WHERE email = ?
            """,
            (email,)
        )

        existing_farmer = cursor.fetchone()


        if existing_farmer:

            connection.close()

            return jsonify({
                "success": False,
                "message": "An account with this email already exists."
            }), 409


        # ----------------------------------------------------
        # HASH PASSWORD
        # ----------------------------------------------------

        password_hash = generate_password_hash(
            password
        )


        # ----------------------------------------------------
        # CREATE FARMER
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO farmers
            (
                name,
                email,
                password_hash
            )
            VALUES
            (
                ?,
                ?,
                ?
            )
            """,
            (
                name,
                email,
                password_hash
            )
        )


        # Get newly created farmer ID
        farmer_id = cursor.lastrowid


        # Save database changes
        connection.commit()

        connection.close()


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "message": "Farmer account created successfully.",

            "farmer": {
                "id": farmer_id,
                "name": name,
                "email": email
            }

        }), 201


    except Exception as error:

        print(
            "Registration error:",
            error
        )

        return jsonify({

            "success": False,

            "message": "Registration failed. Please try again."

        }), 500


# ============================================================
# FARMER LOGIN
# ============================================================

@app.route(
    "/api/auth/login",
    methods=["POST"]
)
def login():

    try:

        # ----------------------------------------------------
        # GET LOGIN DATA
        # ----------------------------------------------------

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No login data received."
            }), 400


        email = data.get(
            "email",
            ""
        ).strip().lower()

        password = data.get(
            "password",
            ""
        )


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not email or not password:

            return jsonify({

                "success": False,

                "message": "Email and password are required."

            }), 400


        # ----------------------------------------------------
        # FIND FARMER
        # ----------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                password_hash
            FROM farmers
            WHERE email = ?
            """,
            (email,)
        )

        farmer = cursor.fetchone()

        connection.close()


        # ----------------------------------------------------
        # CHECK FARMER EXISTS
        # ----------------------------------------------------

        if farmer is None:

            return jsonify({

                "success": False,

                "message": "Invalid email or password."

            }), 401


        # ----------------------------------------------------
        # CHECK PASSWORD
        # ----------------------------------------------------

        password_correct = check_password_hash(

            farmer["password_hash"],

            password

        )


        if not password_correct:

            return jsonify({

                "success": False,

                "message": "Invalid email or password."

            }), 401


        # ====================================================
        # LOGIN SUCCESSFUL
        # ====================================================

        session["farmer_id"] = farmer["id"]

        session["farmer_name"] = farmer["name"]

        session["farmer_email"] = farmer["email"]


        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "message": "Login successful.",

            "farmer": {

                "id": farmer["id"],

                "name": farmer["name"],

                "email": farmer["email"]

            }

        })


    except Exception as error:

        print(
            "Login error:",
            error
        )

        return jsonify({

            "success": False,

            "message": "Login failed. Please try again."

        }), 500


# ============================================================
# GET CURRENT LOGGED-IN FARMER
# ============================================================

@app.route(
    "/api/auth/me",
    methods=["GET"]
)
def current_farmer():

    # --------------------------------------------------------
    # CHECK SESSION
    # --------------------------------------------------------

    farmer_id = session.get(
        "farmer_id"
    )


    if farmer_id is None:

        return jsonify({

            "success": False,

            "logged_in": False,

            "message": "No farmer is currently logged in."

        }), 401


    # --------------------------------------------------------
    # GET FARMER FROM DATABASE
    # --------------------------------------------------------

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                created_at
            FROM farmers
            WHERE id = ?
            """,
            (farmer_id,)
        )

        farmer = cursor.fetchone()

        connection.close()


        if farmer is None:

            session.clear()

            return jsonify({

                "success": False,

                "logged_in": False,

                "message": "Farmer account not found."

            }), 401


        # ----------------------------------------------------
        # RETURN FARMER
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "logged_in": True,

            "farmer": {

                "id": farmer["id"],

                "name": farmer["name"],

                "email": farmer["email"],

                "created_at": farmer["created_at"]

            }

        })


    except Exception as error:

        print(
            "Current farmer error:",
            error
        )

        return jsonify({

            "success": False,

            "message": "Could not retrieve farmer information."

        }), 500


# ============================================================
# FARMER LOGOUT
# ============================================================

@app.route(
    "/api/auth/logout",
    methods=["POST"]
)
def logout():

    # Remove all login session information
    session.clear()


    return jsonify({

        "success": True,

        "message": "Logged out successfully."

    })


# ============================================================
# TEST DATABASE ROUTE
# ============================================================

@app.route(
    "/api/auth/test",
    methods=["GET"]
)
def test_database():

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) AS total FROM farmers"
        )

        result = cursor.fetchone()

        connection.close()


        return jsonify({

            "success": True,

            "database": "connected",

            "farmers_count": result["total"]

        })


    except Exception as error:

        print(
            "Database test error:",
            error
        )

        return jsonify({

            "success": False,

            "database": "connection failed",

            "error": str(error)

        }), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("       KRISHI SETU AUTHENTICATION")
    print("========================================")
    print()
    print(
        "Database:",
        DATABASE_PATH
    )
    print()
    print(
        "Register API:"
    )
    print(
        "http://127.0.0.1:5001/api/auth/register"
    )
    print()
    print(
        "Login API:"
    )
    print(
        "http://127.0.0.1:5001/api/auth/login"
    )
    print()
    print(
        "Current Farmer API:"
    )
    print(
        "http://127.0.0.1:5001/api/auth/me"
    )
    print()
    print("========================================")

    app.run(

        host="127.0.0.1",

        port=5001,

        debug=False

    )
    