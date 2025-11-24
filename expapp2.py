#https://expense-tracker-12-349v.onrender.com
#https://expense-tracker-12-349v.onrender.com/login
from flask import Flask, request, redirect, render_template, session, url_for
from supabase import create_client, Client
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Secret key for session (change this in real projects)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_this_secret_key")

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --------------- HELPER: LOGIN REQUIRED DECORATOR (OPTIONAL SIMPLE CHECK) ---------------
def login_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


# ------------------------------- SIGNUP -------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("signup.html", error="Email and password are required")

        # Check if user already exists
        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return render_template("signup.html", error="Email already registered")

        hashed_pass = generate_password_hash(password)

        supabase.table("users").insert({
            "email": email,
            "password": hashed_pass
        }).execute()

        return redirect(url_for("login"))

    return render_template("signup.html")


# ------------------------------- LOGIN -------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Email and password are required")

        user = supabase.table("users").select("*").eq("email", email).execute()

        if not user.data:
            return render_template("login.html", error="User not found")

        user_row = user.data[0]
        stored_hash = user_row["password"]

        if not check_password_hash(stored_hash, password):
            return render_template("login.html", error="Incorrect password")

        # Store in session
        session["user_id"] = user_row["id"]
        session["email"] = user_row["email"]

        return redirect(url_for("exptracker"))

    return render_template("login.html")


# ------------------------------- LOGOUT -------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------- MAIN EXPENSE PAGE -------------------------------
@app.route("/", methods=["GET", "POST"])
@login_required
def exptracker():
    user_id = session["user_id"]

    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        note = request.form.get("note", "")

        if not amount or not category:
            # simple validation, reload page with error if needed
            response = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
            expense = response.data
            total = sum(float(item["amount"]) for item in expense) if expense else 0
            return render_template(
                "exptracker.html",
                expense=expense,
                total=total,
                error="Amount and category are required"
            )

        next_date = datetime.now().strftime("%Y-%m-%d")

        supabase.table("expenses").insert({
            "next_date": next_date,
            "amount": amount,
            "category": category,
            "note": note,
            "user_id": user_id
        }).execute()

        return redirect(url_for("exptracker"))

    # GET: fetch current user's expenses
    response = supabase.table("expenses").select("*").eq("user_id", user_id).order("next_date").execute()
    expense = response.data or []

    total = sum(float(item["amount"]) for item in expense) if expense else 0

    return render_template("exptracker.html", expense=expense, total=total)


# ------------------------------- DELETE EXPENSE -------------------------------
@app.route("/delete/<int:id>")
@login_required
def delete_row(id):
    user_id = session["user_id"]

    # Only delete if the row belongs to this user
    supabase.table("expenses").delete().eq("id", id).eq("user_id", user_id).execute()

    return redirect(url_for("exptracker"))
# ----------------------------- PROFILE & SETTINGS ------------------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("profile.html")

@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("settings.html")

# ------------------------------- RUN APP -------------------------------
if __name__ == "__main__":
    # debug=True for local dev, turn off in production
    app.run(host="0.0.0.0", port=5000, debug=True)
