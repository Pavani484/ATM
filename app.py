from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ✅ DB PATH FIX
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "atm.db")

conn = sqlite3.connect(db_path, check_same_thread=False)
cursor = conn.cursor()

# ✅ CREATE TABLES
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    pin INTEGER,
    balance INTEGER,
    attempts INTEGER DEFAULT 0,
    locked INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    username TEXT,
    action TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()


# 🔐 LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]

        try:
            pin = int(request.form["pin"])
        except:
            return "PIN must be a number"

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if not user:
            return "User not found"

        if user[4] == 1:
            return "Account is locked"

        if pin == user[1]:
            otp = random.randint(1000, 9999)

            session["otp"] = otp
            session["temp_user"] = username

            print("OTP:", otp)  # ✅ check in Render logs

            cursor.execute("UPDATE users SET attempts=0 WHERE username=?", (username,))
            conn.commit()

            return redirect("/verify")

        else:
            attempts = user[3] + 1
            cursor.execute("UPDATE users SET attempts=? WHERE username=?", (attempts, username))

            if attempts >= 3:
                cursor.execute("UPDATE users SET locked=1 WHERE username=?", (username,))
                conn.commit()
                return "Account locked"

            conn.commit()
            return "Incorrect PIN"

    return render_template("login.html")


# 🔐 VERIFY OTP
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":

        # ✅ SESSION CHECK (VERY IMPORTANT)
        if "otp" not in session or "temp_user" not in session:
            return "Session expired. Please login again."

        try:
            user_otp = int(request.form["otp"])
        except:
            return "Invalid OTP format"

        print("Session OTP:", session.get("otp"))
        print("User OTP:", user_otp)

        if user_otp == session.get("otp"):
            session["user"] = session.get("temp_user")
            return redirect("/dashboard")
        else:
            return "Invalid OTP"

    return render_template("verify.html")


# 🆕 REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]

        try:
            pin = int(request.form["pin"])
            balance = int(request.form["balance"])
        except:
            return "PIN and Balance must be numbers"

        if balance < 0:
            return "Balance cannot be negative"

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        if cursor.fetchone():
            return "User already exists"

        cursor.execute(
            "INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)",
            (username, pin, balance)
        )
        conn.commit()

        return redirect("/")

    return render_template("register.html")


# 💳 DASHBOARD
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/")

    username = session["user"]

    if request.method == "POST":
        action = request.form["action"]

        try:
            amount = int(request.form.get("amount", 0))
        except:
            return "Invalid amount"

        if action == "deposit":
            if amount > 0:
                cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE username=?",
                    (amount, username)
                )
                cursor.execute(
                    "INSERT INTO history (username, action) VALUES (?, ?)",
                    (username, f"Deposited {amount}")
                )
            else:
                return "Invalid amount"

        elif action == "withdraw":
            cursor.execute("SELECT balance FROM users WHERE username=?", (username,))
            result = cursor.fetchone()

            if not result:
                return "User not found"

            bal = result[0]

            if amount <= 0:
                return "Invalid amount"
            elif amount > 5000:
                return "Max withdrawal is 5000"
            elif amount > bal:
                return "Insufficient balance"
            else:
                cursor.execute(
                    "UPDATE users SET balance = balance - ? WHERE username=?",
                    (amount, username)
                )
                cursor.execute(
                    "INSERT INTO history (username, action) VALUES (?, ?)",
                    (username, f"Withdrew {amount}")
                )

        conn.commit()

    cursor.execute("SELECT balance FROM users WHERE username=?", (username,))
    result = cursor.fetchone()

    if not result:
        return "User not found"

    balance = result[0]

    cursor.execute("SELECT action, time FROM history WHERE username=?", (username,))
    history = cursor.fetchall()

    return render_template("dashboard.html", balance=balance, history=history)


# 🔓 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ▶️ RUN
if __name__ == "__main__":
    app.run()