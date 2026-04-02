from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import smtplib

app = Flask(__name__)
app.secret_key = "secret123"

# 🔹 SQLite Connection
conn = sqlite3.connect("atm.db", check_same_thread=False)
cursor = conn.cursor()

# 🔹 Create Tables
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
    action TEXT
)
""")

conn.commit()


# 🔹 Send OTP Email
def send_otp_email(receiver_email, otp):
    sender_email = "pavani10072005gmail@gmail.com"
    app_password = "ptpvgduinbkurkxc"   # 🔐 paste here (no spaces)

    message = f"Subject: OTP Verification\n\nYour OTP is: {otp}"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, app_password)
    server.sendmail(sender_email, receiver_email, message)
    server.quit()


# 🔐 LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        pin = int(request.form["pin"])

        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if not user:
            return "User not found"

        if user[4] == 1:
            return "Account locked"

        if pin == user[1]:
            otp = random.randint(1000, 9999)
            session["otp"] = otp
            session["temp_user"] = username

            send_otp_email(username, otp)  # 📧 send OTP

            return redirect("/verify")

        else:
            attempts = user[3] + 1
            cursor.execute("UPDATE users SET attempts=? WHERE username=?", (attempts, username))

            if attempts >= 3:
                cursor.execute("UPDATE users SET locked=1 WHERE username=?", (username,))
                conn.commit()
                return "Account locked due to 3 failed attempts"

            conn.commit()
            return "Incorrect PIN"

    return render_template("login.html")


# 🔐 VERIFY OTP
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        user_otp = int(request.form["otp"])

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
        pin = int(request.form["pin"])
        balance = int(request.form["balance"])

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
        amount = int(request.form.get("amount", 0))

        if action == "deposit":
            if amount > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE username=?", (amount, username))
                cursor.execute("INSERT INTO history VALUES (?, ?)", (username, f"Deposited {amount}"))
            else:
                return "Invalid amount"

        elif action == "withdraw":
            cursor.execute("SELECT balance FROM users WHERE username=?", (username,))
            bal = cursor.fetchone()[0]

            if amount <= 0:
                return "Invalid amount"
            elif amount > 5000:
                return "Max withdrawal is 5000"
            elif amount > bal:
                return "Insufficient balance"
            else:
                cursor.execute("UPDATE users SET balance = balance - ? WHERE username=?", (amount, username))
                cursor.execute("INSERT INTO history VALUES (?, ?)", (username, f"Withdrew {amount}"))

        conn.commit()

    cursor.execute("SELECT balance FROM users WHERE username=?", (username,))
    balance = cursor.fetchone()[0]

    cursor.execute("SELECT action FROM history WHERE username=?", (username,))
    history = cursor.fetchall()

    return render_template("dashboard.html", balance=balance, history=history)


# 🔓 LOGOUT
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


# ▶️ RUN
if __name__ == "__main__":
    app.run(debug=True)