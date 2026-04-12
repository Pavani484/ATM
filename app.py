from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import os
import smtplib
from email.mime.text import MIMEText
import time
import threading

app = Flask(__name__)
app.secret_key = "secret123"

# ✅ Database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "atm.db")

conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    pin INTEGER,
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

# 📧 EMAIL OTP
def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("EMAIL_USER")
    app_password = os.getenv("EMAIL_PASS")

    if not sender_email or not app_password:
        print("OTP:", otp)
        return

    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "OTP Verification"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)

# 🔐 LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        if not email or not pin:
            return "Email and PIN required"

        try:
            pin = int(pin)
        except:
            return "PIN must be number"

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if not user:
            return "User not found"

        if user[4] == 1:
            return "Account locked"

        if pin == user[1]:
            otp = random.randint(1000, 9999)

            session["otp"] = otp
            session["otp_time"] = time.time()
            session["temp_user"] = email

            cursor.execute("UPDATE users SET attempts=0 WHERE email=?", (email,))
            conn.commit()
            threading.Thread(target=send_otp_email, args=(email, otp)).start()
            # send_otp_email(email, otp)

            return redirect("/verify")

        else:
            attempts = user[3] + 1
            cursor.execute("UPDATE users SET attempts=? WHERE email=?", (attempts, email))

            if attempts >= 3:
                cursor.execute("UPDATE users SET locked=1 WHERE email=?", (email,))
                conn.commit()
                return "Account locked"

            conn.commit()
            return "Incorrect PIN"

    return render_template("login.html")

# 🔐 VERIFY OTP
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":

        if "otp" not in session or "temp_user" not in session:
            return "Session expired"

        try:
            user_otp = int(request.form["otp"])
        except:
            return "Invalid OTP"

        if time.time() - session["otp_time"] > 120:
            return "OTP expired"

        if user_otp == session["otp"]:
            session["user"] = session["temp_user"]
            return redirect("/dashboard")
        else:
            return "Invalid OTP"

    return render_template("verify.html")

# 🆕 REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")
        balance = request.form.get("balance")

        if not email or not pin or not balance:
            return "All fields required"

        try:
            pin = int(pin)
            balance = int(balance)
        except:
            return "Invalid input"

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        if cursor.fetchone():
            return "User already exists"

        cursor.execute("INSERT INTO users (email, pin, balance) VALUES (?, ?, ?)", (email, pin, balance))
        conn.commit()

        return redirect("/")

    return render_template("register.html")

# 💳 DASHBOARD
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/")

    email = session["user"]

    if request.method == "POST":
        action = request.form["action"]

        try:
            amount = int(request.form.get("amount", 0))
        except:
            return "Invalid amount"

        if action == "deposit" and amount > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE email=?", (amount, email))
            cursor.execute("INSERT INTO history (email, action) VALUES (?, ?)", (email, f"Deposited {amount}"))

        elif action == "withdraw":
            cursor.execute("SELECT balance FROM users WHERE email=?", (email,))
            bal = cursor.fetchone()[0]

            if amount > 0 and amount <= bal:
                cursor.execute("UPDATE users SET balance = balance - ? WHERE email=?", (amount, email))
                cursor.execute("INSERT INTO history (email, action) VALUES (?, ?)", (email, f"Withdrew {amount}"))

        conn.commit()

    cursor.execute("SELECT balance FROM users WHERE email=?", (email,))
    balance = cursor.fetchone()[0]

    cursor.execute("SELECT action, time FROM history WHERE email=?", (email,))
    history = cursor.fetchall()

    return render_template("dashboard.html", balance=balance, history=history)

# 🔓 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# 🔑 FORGOT PIN
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email")

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        if not cursor.fetchone():
            return "Email not found"

        otp = random.randint(1000, 9999)

        session["reset_otp"] = otp
        session["reset_user"] = email
        session["reset_time"] = time.time()

        send_otp_email(email, otp)

        return redirect("/reset-verify")

    return render_template("forgot.html")

# 🔑 RESET VERIFY
@app.route("/reset-verify", methods=["GET", "POST"])
def reset_verify():
    if request.method == "POST":

        if "reset_otp" not in session:
            return "Session expired"

        try:
            user_otp = int(request.form["otp"])
        except:
            return "Invalid OTP"

        if time.time() - session["reset_time"] > 120:
            return "OTP expired"

        if user_otp == session["reset_otp"]:
            return redirect("/reset-pin")
        else:
            return "Invalid OTP"

    return render_template("reset_verify.html")

# 🔑 RESET PIN
@app.route("/reset-pin", methods=["GET", "POST"])
def reset_pin():
    if "reset_user" not in session:
        return redirect("/")

    if request.method == "POST":
        try:
            new_pin = int(request.form["pin"])
        except:
            return "Invalid PIN"

        email = session["reset_user"]

        cursor.execute("UPDATE users SET pin=? WHERE email=?", (new_pin, email))
        conn.commit()

        session.clear()
        return "PIN reset successful! <a href='/'>Login</a>"

    return render_template("reset_pin.html")

if __name__ == "__main__":
    app.run()