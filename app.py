from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "App is working 🚀"



from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import os
import smtplib
from email.mime.text import MIMEText
import time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# ✅ DB Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "atm.db")

# ✅ DB Connection per request
def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ✅ Create Tables
conn = get_db()
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    pin TEXT,
    balance INTEGER,
    attempts INTEGER DEFAULT 0,
    locked INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    email TEXT,
    action TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

# 📧 SEND OTP
def send_otp_email(receiver_email, otp):
    print("OTP:", otp)

# 🔐 LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        if not email or not pin:
            return render_template("login.html", message="All fields required")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if not user:
            return render_template("login.html", message="User not found")

        if user["locked"] == 1:
            return render_template("login.html", message="Account locked")

        if check_password_hash(user["pin"], pin):
            otp = random.randint(1000, 9999)

            session["otp"] = otp
            session["otp_time"] = time.time()
            session["temp_user"] = email

            cursor.execute("UPDATE users SET attempts=0 WHERE email=?", (email,))
            conn.commit()

            send_otp_email(email, otp)

            return redirect("/verify")
        else:
            attempts = user["attempts"] + 1
            cursor.execute("UPDATE users SET attempts=? WHERE email=?", (attempts, email))

            if attempts >= 3:
                cursor.execute("UPDATE users SET locked=1 WHERE email=?", (email,))
                conn.commit()
                return render_template("login.html", message="Account locked")

            conn.commit()
            return render_template("login.html", message="Incorrect PIN")

    return render_template("login.html")

# 🔐 VERIFY OTP
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":

        if "otp" not in session:
            return redirect("/")

        user_otp = request.form.get("otp")

        if not user_otp:
            return render_template("verify.html", message="Enter OTP")

        if time.time() - session["otp_time"] > 120:
            return render_template("verify.html", message="OTP expired")

        if int(user_otp) == session["otp"]:
            session["user"] = session["temp_user"]

            session.pop("otp", None)
            session.pop("otp_time", None)
            session.pop("temp_user", None)

            return redirect("/dashboard")
        else:
            return render_template("verify.html", message="Invalid OTP")

    return render_template("verify.html")

# 🆕 REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")
        balance = request.form.get("balance")

        if not email or not pin or not balance:
            return render_template("register.html", message="All fields required")

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        if cursor.fetchone():
            return render_template("register.html", message="User already exists")

        hashed_pin = generate_password_hash(pin)

        cursor.execute(
            "INSERT INTO users (email, pin, balance) VALUES (?, ?, ?)",
            (email, hashed_pin, int(balance))
        )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("register.html")

# 💳 DASHBOARD
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/")

    email = session["user"]
    conn = get_db()
    cursor = conn.cursor()

    message = None

    if request.method == "POST":
        action = request.form["action"]
        amount = int(request.form.get("amount", 0))

        cursor.execute("SELECT balance FROM users WHERE email=?", (email,))
        bal = cursor.fetchone()["balance"]

        if action == "deposit" and amount > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE email=?", (amount, email))
            cursor.execute("INSERT INTO history (email, action) VALUES (?, ?)", (email, f"Deposited {amount}"))
            message = "Deposit successful"

        elif action == "withdraw":
            if amount > bal:
                message = "Insufficient balance"
            else:
                cursor.execute("UPDATE users SET balance = balance - ? WHERE email=?", (amount, email))
                cursor.execute("INSERT INTO history (email, action) VALUES (?, ?)", (email, f"Withdrew {amount}"))
                message = "Withdrawal successful"

        conn.commit()

    cursor.execute("SELECT balance FROM users WHERE email=?", (email,))
    balance = cursor.fetchone()["balance"]

    cursor.execute("SELECT action, time FROM history WHERE email=?", (email,))
    history = cursor.fetchall()

    return render_template("dashboard.html", balance=balance, history=history, message=message)

# 🔓 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ▶ RUN
if __name__ == "__main__":
    app.run(debug=True)