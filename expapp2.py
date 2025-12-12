from flask import Flask, request, redirect, render_template, session, url_for
from supabase import create_client, Client
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv   
from flask import send_from_directory

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
        name = request.form.get("name","").strip()
        phone_number = request.form.get("phone_number","").strip()
        address = request.form.get("address","").strip()

        if not email or not password or not name or not phone_number or not address :
            return render_template("signup.html", error="All field are required")

        # Check if user already exists
        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return render_template("signup.html", error="Email already registered")

        hashed_pass = generate_password_hash(password)
        
        result = supabase.table("users").insert({
            "email": email,
            "password": hashed_pass,
            "name": name,
            "phone_number":phone_number,
            "address":address
        }).execute()
        
        user = result.data[0]
        
        # Store in session IMMEDIATELY
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["phone_number"] = user.get("phone_number", "")
        session["address"] = user.get("address", "")

        return redirect(url_for("profile"))
        
    return render_template("signup.html")

# ------------------------------- LOGIN -------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Email and password are required")

        result = supabase.table("users").select("*").eq("email", email).execute()

        if not result.data:
            return render_template("login.html", error="User not found")

        user_row = result.data[0]
        stored_hash = user_row["password"]

        if not check_password_hash(stored_hash, password):
            return render_template("login.html", error="Incorrect password")

        # Store in session
        session["user_id"] = user_row["id"]
        session["email"] = user_row["email"]
        session["name"]=user_row["name"]
        session["phone_number"] = user_row.get("phone_number", "")
        session["address"] = user_row.get("address", "")

        return redirect(url_for("exptracker3"))

    return render_template("login.html")


# ------------------------------- LOGOUT -------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------- MAIN EXPENSE PAGE (Dashboard) -------------------------------
@app.route("/", methods=["GET"])
@login_required
def exptracker3():
    user_id = session["user_id"]

    # PAGE NUMBER
    page = int(request.args.get("page", 1))
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page - 1

    # FETCH ONLY 10 EXPENSES FOR THIS PAGE
    result = (
        supabase.table("expenses")
        .select("*")
        .eq("user_id", user_id)
        .order("next_date", desc=True)
        .range(start, end)
        .execute()
    )

    expenses = result.data or []

    # ---------- TOTAL EXPENSES FROM ALL ROWS ----------
    total_result = (
        supabase.table("expenses")
        .select("amount")
        .eq("user_id", user_id)
        .execute()
    )
    all_expenses = total_result.data or []
    total = sum(float(e["amount"]) for e in all_expenses)

    # ---------- TOTAL PAGES ----------
    count_result = (
        supabase.table("expenses")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    total_expenses = count_result.count
    total_pages = (total_expenses + per_page - 1) // per_page

    return render_template(
        "exptracker3.html",
        expense=expenses,
        total=total,
        total_pages=total_pages,
        current_page=page
    )

# ------------------------------- DELETE EXPENSE -------------------------------
@app.route("/delete/<int:id>")
@login_required
def delete_row(id):
    print("Deleting ID:", id)
    user_id = session["user_id"]
    print("User ID:", user_id)
    result = supabase.table("expenses").delete().eq("id", id).eq("user_id", user_id).execute()
    print(result.data)
    return redirect(url_for("exptracker3"))

# ----------------------------- Add Expense ---------------------------------
@app.route("/add_expense",methods=["GET","POST"])
@login_required
def add_expense():
    user_id = session["user_id"]
    
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        subcategory = request.form.get("subcategory")
        note = request.form.get("note", "")
        
        if not amount or not category  or not subcategory :
            # simple validation, reload page with error if needed
            return render_template("add_expense.html", error="All fields required")

        # store full datetime
        next_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        supabase.table("expenses").insert({
            "next_date": next_date,
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
            "note": note,
            "user_id": user_id
        }).execute()

        return redirect(url_for("exptracker3"))

    # GET → Show form only
    return render_template("add_expense.html")
'''
#------------------------ Reports ---------------------------------
@app.route("/reports")
def reports():
    return render_template("reports.html")
'''
# ----------------------------- PROFILE & SETTINGS ------------------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    return render_template(
        "profile.html",
        user_id=session.get("user_id"),
        name=session.get("name"),
        email=session.get("email"),
        phone_number=session.get("phone_number"),
        address=session.get("address")
    )

@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("settings.html")

# -------------------------------Modify----------------------------------
@app.route("/modify/<int:id>",methods=["GET","POST"])
@login_required
def modify_expense(id):
    user_id = session["user_id"]
    result = (
        supabase.table("expenses")
        .select("*")
        .eq("id", id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        return redirect(url_for("exptracker3"))

    expense = result.data[0]
    if request.method == "POST":
        new_category = request.form.get("category")
        new_subcategory=request.form.get("subcategory")
        new_amount = request.form.get("amount")
        new_note = request.form.get("note")

        supabase.table("expenses").update({
            "category": new_category,
            "subcategory":new_subcategory,
            "amount": new_amount,
            "note": new_note,
        }).eq("id", id).eq("user_id", user_id).execute()

        return redirect(url_for("exptracker3"))

    return render_template("modify.html", expense=expense)

# ------------------------------- History Check / FILTER -------------------------
@app.route('/exptracker_filter', methods=['POST'])
@login_required
def filter_expenses():
    user_id = session["user_id"]

    specific_date = request.form.get("specific_date")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    query = supabase.table("expenses").select("*").eq("user_id", user_id)

    # 1. Filter by specific date
    if specific_date:
        query = query.gte("next_date", specific_date + " 00:00:00") \
                     .lte("next_date", specific_date + " 23:59:59")

    # 2. Filter by range
    elif start_date and end_date:
        query = query.gte("next_date", start_date) \
                     .lte("next_date", end_date + " 23:59:59")

    elif start_date and not end_date:
        query = query.gte("next_date", start_date)

    elif end_date and not start_date:
        query = query.lte("next_date", end_date + " 23:59:59")

    # Execute
    result = query.order("next_date", desc=False).execute()
    expenses = result.data or []

    total = sum(float(item["amount"]) for item in expenses) if expenses else 0

    return render_template(
        "exptracker3.html",
        expense=expenses,
        total=total,
        specific_date=specific_date,
        start_date=start_date,
        end_date=end_date,
        current_page=1,
        total_pages=1   
    )

# --------------------------- Dashboard ------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    # Fetch expenses for logged-in user
    result = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
    expenses = result.data or []

    # ----- TOTAL SPENT -----
    total_expense = sum(float(e["amount"]) for e in expenses)

    # ----- MONTHLY TOTAL -----
    current_month = datetime.now().strftime("%Y-%m")
    monthly_total = sum(
        float(e["amount"])
        for e in expenses
        if e["next_date"].startswith(current_month)
    )

    # ----- CATEGORY BREAKDOWN -----
    category_map = {}
    for e in expenses:
        category_map[e["category"]] = category_map.get(e["category"], 0) + float(e["amount"])

    category_labels = list(category_map.keys())
    category_values = list(category_map.values())

    # ----- WEEKLY SPENDING (LAST 7 DAYS) -----
    today = datetime.now()
    week_labels = []
    week_values = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        date_only = day.strftime("%Y-%m-%d")

        # Extract only date from stored timestamp
        total_for_day = sum(
            float(e["amount"])
            for e in expenses
            if e["next_date"][:10] == date_only
        )

        week_labels.append(day.strftime("%d %b"))
        week_values.append(total_for_day)

    # ----- RECENT EXPENSES -----
    recent = sorted(expenses, key=lambda x: x["next_date"], reverse=True)[:5]

    # ----- TOP CATEGORY -----
    top_category = max(category_map, key=category_map.get) if category_map else "None"
    
    return render_template(
        "dashboard.html",
        total_expense=total_expense,
        monthly_total=monthly_total,
        top_category=top_category,
        category_labels=category_labels,
        category_values=category_values,
        week_labels=week_labels,
        week_values=week_values,
        recent=recent
    )
# ------------------------------- service worker ------------------------
@app.route('/static/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')
# ------------------------------ expense page ---------------------------
@app.route("/expenses_page/<int:page>")
@login_required
def expenses_page(page):
    user_id = session["user_id"]

    LIMIT = 10
    OFFSET = (page - 1) * LIMIT

    result = (
        supabase.table("expenses")
        .select("*")
        .eq("user_id", user_id)
        .order("next_date", desc=True)
        .range(OFFSET, OFFSET + LIMIT - 1)
        .execute()
    )

    expenses = result.data or []

    count_result = (
        supabase.table("expenses")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    total_expenses = count_result.count
    total_pages = (total_expenses + 9) // 10

    total = sum(float(e["amount"]) for e in expenses)

    return render_template(
        "exptracker3.html",
        expense=expenses,
        total=total,
        total_pages=total_pages,
        current_page=page
    )
# ---------------------------- History ---------------------------------
@app.route("/expense_history")
def history():
    selected_date = request.args.get("date")

    conn = get_db_connection()
    cursor = conn.cursor()

    if selected_date:
        cursor.execute("""
            SELECT * FROM expenses 
            WHERE DATE(date) = ?
            ORDER BY date DESC
        """, (selected_date,))
    else:
        cursor.execute("""
            SELECT * FROM expenses
            ORDER BY date DESC
        """)

    expenses = cursor.fetchall()
    conn.close()

    return render_template("exptracker3.html", expenses=expenses)


# ----------------------------- icon ------------------------------------
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static/icons', 'exptracker_app_icon1.png')

from flask import request, redirect, url_for
import os

UPLOAD_FOLDER = "static/profile"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------------------- RUN APP -------------------------------
if __name__ == "__main__":
    # debug=True for local dev, turn off in production
    app.run(host="0.0.0.0", port=5000, debug=True)


'''
#https://expense-tracker-20.onrender.com
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
        name = request.form.get("name","").strip()
        phone_number = request.form.get("phone_number","").strip()

        if not email or not password or not name or not phone_number :
            return render_template("signup.html", error="All field are required")

        # Check if user already exists
        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return render_template("signup.html", error="Email already registered")

        hashed_pass = generate_password_hash(password)
        
        result = supabase.table("users").insert({
            "email": email,
            "password": hashed_pass,
            "name": name,
            "phone_number":phone_number
        }).execute()
        
        user = result.data[0]
        
        # Store in session IMMEDIATELY
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["phone_number"] = user["phone_number"]

        return redirect(url_for("profile"))
        
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
        session["name"]=user_row["name"]

        return redirect(url_for("exptracker3"))

    return render_template("login.html")


# ------------------------------- LOGOUT -------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------- MAIN EXPENSE PAGE -------------------------------
@app.route("/", methods=["GET", "POST"])
@login_required
def exptracker3():
    user_id = session["user_id"]
    
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        subcategory=request.form.get("subcategory")
        note = request.form.get("note", "")
        
        if not amount or not category or not subcategory :
            #simple validation, reload page with error if needed
            response = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
            expense = response.data
            total = sum(float(item["amount"]) for item in expense) if expense else 0
            return render_template(
                "exptracker3.html",
                expense=expense,
                total=total,
                error="Amount and category are required"
            )
        if not amount or not category or not subcategory :
            # simple validation, reload page with error if needed
            response = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
            expense = response.data
            total = sum(float(item["amount"]) for item in expense) if expense else 0
            return render_template(
                "exptracker2.html",
                expense=expense,
                total=total,
                error="Amount and category are required"
            )
        next_date = datetime.now().strftime("%Y-%m-%d")

        supabase.table("expenses").insert({
            "next_date": next_date,
            "amount": amount,
            "category": category,
            "subcategory":subcategory,
            "note": note,
            "user_id": user_id
        }).execute()

        return redirect(url_for("exptracker3"))
        #return redirect(url_for("add_expense"))
        
    # GET: fetch current user's expenses
    response = supabase.table("expenses").select("*").eq("user_id", user_id).order("next_date").execute()
    expense = response.data or []

    total = sum(float(item["amount"]) for item in expense) if expense else 0

    return render_template("exptracker3.html", expense=expense, total=total)


# ------------------------------- DELETE EXPENSE -------------------------------
@app.route("/delete/<int:id>")
@login_required
def delete_row(id):
    user_id = session["user_id"]

    # Only delete if the row belongs to this user
    supabase.table("expenses").delete().eq("id", id).eq("user_id", user_id).execute()

    return redirect(url_for("exptracker3"))
    #return redirect(url_for("expense_history"))
# ----------------------------- Add Expense ---------------------------------
@app.route("/add_expense",methods=["GET","POST"])
@login_required
def add_expense():
    user_id = session["user_id"]
    
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        subcategory = request.form.get("subcategory")
        note = request.form.get("note", "")
        
        if not amount or not category  or not subcategory :
            # simple validation, reload page with error if needed
            return render_template("add_expense.html", error="All fields required")

        next_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        supabase.table("expenses").insert({
            "next_date": next_date,
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
            "note": note,
            "user_id": user_id
        }).execute()

        return redirect(url_for("exptracker3"))

    # GET → Show form only
    return render_template("add_expense.html")
#------------------------- Expense history -------------------------
@app.route("/expense_history")
def history():
    return render_template("expense_history.html")
#------------------------ Reports ---------------------------------
@app.route("/reports")
def reports():
    return render_template("reports.html")
# ----------------------------- PROFILE & SETTINGS ------------------------------
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("login")
    return render_template("profile.html")

@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("settings.html")
# -------------------------------Modify----------------------------------
@app.route("/modify/<int:id>",methods=["GET","POST"])
@login_required
def modify_expense(id):
    user_id = session["user_id"]
    result = (
        supabase.table("expenses")
        .select("*")
        .eq("id", id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        return redirect(url_for("exptracker3"))

    expense = result.data[0]
    if request.method == "POST":
        new_category = request.form.get("category")
        new_subcategory=request.form.get("subcategory")
        new_amount = request.form.get("amount")
        new_note = request.form.get("note")

        supabase.table("expenses").update({
            "category": new_category,
            "subcategory":new_subcategory,
            "amount": new_amount,
            "note": new_note,
        }).eq("id", id).eq("user_id", user_id).execute()

        return redirect(url_for("exptracker3"))

    return render_template("modify.html", expense=expense)
# ------------------------------- History Check / FILTER -------------------------
@app.route('/exptracker_filter', methods=['POST'])
@login_required
def filter_expenses():
    user_id = session["user_id"]

    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    query = supabase.table("expenses").select("*").eq("user_id", user_id)

    if start_date and end_date:
        query = query.gte("next_date", start_date).lte("next_date", end_date)

    result = query.order("next_date", desc=False).execute()
    expenses = result.data

    return render_template("exptracker3.html", expenses=expenses)

# ------------------------------- RUN APP -------------------------------
if __name__ == "__main__":
    # debug=True for local dev, turn off in production
    app.run(host="0.0.0.0", port=5000, debug=True)
'''

