# expapp_fixed.py
# ---------------- Flask & Utilities ----------------
from flask import (
    Flask, request, redirect, render_template, session, url_for,
    send_from_directory, flash, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ---------------- Database ----------------
from supabase import create_client, Client

# ---------------- Environment ----------------
import os
from dotenv import load_dotenv

# ---------------- Python Utilities ----------------
import io
import csv
import re
import uuid
from datetime import datetime, timedelta

# ---------------- PDF Generation ----------------
from flask import make_response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
# ---------------- Custom Utilities ----------------
from utils import extract_amount



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


# ------------------ Helper: login_required decorator ------------------
def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# ------------------ Auto categorizer (unchanged) ------------------
def ai_auto_categorize(text):
    if not text:
        return ("Other", "General")
    s = text.lower()
    s = s.replace("₹", " ").replace("rs.", " ").replace("rs", " ")
    def has(*words):
        return any(re.search(r'\b' + re.escape(w) + r'\b', s) for w in words)
    text = text.lower()

    if any(w in text for w in ["kfc", "dominos", "pizza", "cafe", "restaurant", "burger", "lunch", "dinner"]):
        return ("Food", "Restaurant")
    if any(w in text for w in ["grocery", "supermarket", "milk", "rice", "vegetable"]):
        return ("Food", "Grocery")
    if any(w in text for w in ["uber", "ola", "bus", "train", "flight", "auto"]):
        return ("Travel", "Transport")
    if "petrol" in text or "diesel" in text:
        return ("Travel", "Fuel")
    if any(w in text for w in ["amazon", "flipkart", "myntra", "shopping", "clothes"]):
        return ("Shopping", "Online")
    if any(w in text for w in ["movie", "netflix", "hotstar", "spotify"]):
        return ("Entertainment", "Subscription")
    if any(w in text for w in ["electricity", "water bill", "gas bill", "recharge", "mobile bill"]):
        return ("Bills", "Utility")
    return ("Other", "General")


# ------------------ Ensure upload folders exist ------------------
SUPPORT_UPLOAD_FOLDER = os.path.join("static", "support_uploads")
os.makedirs(SUPPORT_UPLOAD_FOLDER, exist_ok=True)

PROFILE_UPLOAD_FOLDER = os.path.join("static", "profile")
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)


# ------------------ Signup / Login / Logout ------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        name = request.form.get("name","").strip()
        phone_number = request.form.get("phone_number","").strip()
        address = request.form.get("address","").strip()

        if not email or not password or not name or not phone_number or not address:
            return render_template("signup.html", error="All field are required")

        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return render_template("signup.html", error="Email already registered")

        hashed_pass = generate_password_hash(password)
        result = supabase.table("users").insert({
            "email": email,
            "password": hashed_pass,
            "name": name,
            "phone_number": phone_number,
            "address": address
        }).execute()

        user = result.data[0]
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        session["phone_number"] = user.get("phone_number", "")
        session["address"] = user.get("address", "")

        return redirect(url_for("profile"))

    return render_template("signup.html")


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

        session["user_id"] = user_row["id"]
        session["email"] = user_row["email"]
        session["name"] = user_row["name"]
        session["phone_number"] = user_row.get("phone_number", "")
        session["address"] = user_row.get("address", "")

        return redirect(url_for("exptracker3"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------ Main page and expenses (kept as-is) ------------------
'''
@app.route("/", methods=["GET"])
@login_required
def exptracker3():
    user_id = session["user_id"]

    # PAGE NUMBER
    page = int(request.args.get("page", 1))
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page - 1

    # DATE FILTER
    specific_date = request.args.get("date")
    query = supabase.table("expenses").select("*").eq("user_id", user_id)

    if specific_date:
        query = query.gte("next_date", specific_date + " 00:00:00") \
                     .lte("next_date", specific_date + " 23:59:59")

    # FETCH ONLY 10 EXPENSES FOR THIS PAGE (use the filtered query)
    result = query.order("next_date", desc=True).range(start, end).execute()
    expenses = result.data or []

    # TOTAL EXPENSE
    total_result = supabase.table("expenses").select("amount").eq("user_id", user_id).execute()
    all_expenses = total_result.data or []
    total = sum(float(e["amount"]) for e in all_expenses)

    # TOTAL PAGES
    count_result = supabase.table("expenses").select("id", count="exact").eq("user_id", user_id).execute()
    total_expenses = count_result.count
    total_pages = (total_expenses + per_page - 1) // per_page

    return render_template(
        "exptracker3.html",
        expense=expenses,
        total=total,
        total_pages=total_pages,
        current_page=page,
        specific_date=specific_date
    )
'''
@app.route("/", methods=["GET"])
@login_required
def exptracker3():
    user_id = session["user_id"]

    # Pagination
    page = int(request.args.get("page", 1))
    per_page = 10
    start = (page - 1) * per_page
    end = start + per_page - 1

    # Filters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    category = request.args.get("category")

    query = supabase.table("expenses").select("*").eq("user_id", user_id)

    if from_date:
        query = query.gte("next_date", f"{from_date} 00:00:00")

    if to_date:
        query = query.lte("next_date", f"{to_date} 23:59:59")

    if category:
        query = query.eq("category", category)

    query = query.order("next_date", desc=True)

    # Fetch paginated expenses
    result = query.range(start, end).execute()
    expenses = result.data or []

    # ---------- TOTAL ----------
    total_query = supabase.table("expenses").select("amount").eq("user_id", user_id)

    if from_date:
        total_query = total_query.gte("next_date", f"{from_date} 00:00:00")
    if to_date:
        total_query = total_query.lte("next_date", f"{to_date} 23:59:59")
    if category:
        total_query = total_query.eq("category", category)

    total_result = total_query.execute()
    total = sum(float(e["amount"]) for e in (total_result.data or []))

    # ---------- COUNT ----------
    count_query = supabase.table("expenses").select("id", count="exact").eq("user_id", user_id)

    if from_date:
        count_query = count_query.gte("next_date", f"{from_date} 00:00:00")
    if to_date:
        count_query = count_query.lte("next_date", f"{to_date} 23:59:59")
    if category:
        count_query = count_query.eq("category", category)

    count_result = count_query.execute()
    total_pages = (count_result.count or 0 + per_page - 1) // per_page

    return render_template(
        "exptracker3.html",
        expense=expenses,
        total=total,
        total_pages=total_pages,
        current_page=page
    )

# ------------------ Add / Modify / Delete expenses (kept) ------------------
@app.route("/add_expense", methods=["GET", "POST"])
@login_required
def add_expense():
    user_id = session["user_id"]

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        subcategory = request.form.get("subcategory", "").strip()
        note = request.form.get("note", "").strip()

        if not amount:
            extracted = extract_amount(note)
            if extracted is None:
                return render_template(
                    "add_expense.html",
                    error="Amount is required (or include amount like ₹1,200 / 2.5k in note)"
                )
            amount = extracted

        if not category or category.lower() == "auto" or not subcategory:
            auto_cat, auto_subcat = ai_auto_categorize(note)
            if not category or category.lower() == "auto":
                category = auto_cat
            if not subcategory:
                subcategory = auto_subcat

        try:
            amount_float = float(amount)
        except (TypeError, ValueError):
            return render_template("add_expense.html", error="Invalid amount format")

        next_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        attachment = request.files.get("attachment")
        attachment_url = None

        if attachment and attachment.filename and allowed_file(attachment.filename):
            filename = secure_filename(attachment.filename)
            unique_path = f"{user_id}/{uuid.uuid4()}_{filename}"

            supabase.storage.from_("expense-attachments").upload(
                unique_path,
                attachment.read(),
                {"content-type": attachment.content_type}
            )

            attachment_url = supabase.storage.from_("expense-attachments").get_public_url(unique_path)

        supabase.table("expenses").insert({
            "user_id": user_id,
            "category": category,
            "subcategory": subcategory,
            "amount": amount_float,
            "note": note,
            "attachment_url": attachment_url,
            "next_date": next_date
        }).execute()

        return redirect(url_for("exptracker3"))

    return render_template("add_expense.html")


@app.route("/delete/<int:id>")
@login_required
def delete_row(id):
    user_id = session["user_id"]
    supabase.table("expenses").delete().eq("id", id).eq("user_id", user_id).execute()
    return redirect(url_for("exptracker3"))


@app.route("/modify/<int:id>", methods=["GET", "POST"])
@login_required
def modify_expense(id):
    user_id = session["user_id"]
    # Fetch the expense
    result = (
        supabase.table("expenses")
        .select("*")
        .eq("id", id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        flash("Expense not found.", "warning")
        return redirect(url_for("exptracker3"))
    expense = result.data[0]
    attachment_url = expense.get("attachment_url")

    if request.method == "POST":
        # --- Form data ---
        new_category = request.form.get("category")
        new_subcategory = request.form.get("subcategory")
        new_note = request.form.get("note")
        remove_attachment = request.form.get("remove_attachment")
        new_attachment = request.files.get("attachment")

        # --- FIX 1: validate amount before touching storage or DB ---
        raw_amount = request.form.get("amount")
        try:
            new_amount = float(raw_amount)
        except (TypeError, ValueError):
            flash("Amount must be a valid number.", "warning")
            return redirect(request.url)

        # --- FIX 2: reject disallowed file types instead of failing silently ---
        if new_attachment and new_attachment.filename:
            if not allowed_file(new_attachment.filename):
                flash("That file type isn't supported.", "warning")
                return redirect(request.url)

        uploaded_path = None     # tracks newly-uploaded file, for rollback on DB failure
        old_attachment_url = attachment_url
        final_attachment_url = attachment_url

        try:
            # --- Upload new attachment (old one is NOT deleted yet) ---
            if new_attachment and new_attachment.filename:
                filename = secure_filename(new_attachment.filename)
                uploaded_path = f"{user_id}/{uuid.uuid4()}_{filename}"
                supabase.storage.from_("expense-attachments").upload(
                    uploaded_path,
                    new_attachment.read(),
                    {"content-type": new_attachment.content_type or "application/octet-stream"}
                )
                final_attachment_url = supabase.storage.from_("expense-attachments").get_public_url(uploaded_path)

            # --- Or mark for removal (old one is NOT deleted yet) ---
            elif remove_attachment:
                final_attachment_url = None

            # --- Update expense row first ---
            supabase.table("expenses").update({
                "category": new_category,
                "subcategory": new_subcategory,
                "amount": new_amount,
                "note": new_note,
                "attachment_url": final_attachment_url
            }).eq("id", id).eq("user_id", user_id).execute()

            # --- FIX 4: only delete the OLD attachment after the DB update succeeds ---
            # (new file replaced it, or it was explicitly removed)
            if old_attachment_url and (uploaded_path or remove_attachment):
                try:
                    old_path = old_attachment_url.split("/storage/v1/object/public/expense-attachments/")[-1]
                    supabase.storage.from_("expense-attachments").remove([old_path])
                except Exception as e:
                    print(f"Failed to delete old attachment: {e}")

            flash("Expense updated successfully!", "success")
            return redirect(url_for("exptracker3"))

        except Exception as e:
            # --- FIX 4 (rollback): DB update failed after a new file was uploaded —
            # delete the orphaned upload so storage doesn't accumulate unreferenced files ---
            if uploaded_path:
                try:
                    supabase.storage.from_("expense-attachments").remove([uploaded_path])
                except Exception as cleanup_err:
                    print(f"Failed to clean up orphaned upload: {cleanup_err}")

            import traceback
            print(traceback.format_exc())
            flash(f"Failed to update expense: {e}", "danger")
            return redirect(request.url)

    return render_template("modify.html", expense=expense)
'''
def modify_expense(id):
    user_id = session["user_id"]

    # Fetch the expense
    result = (
        supabase.table("expenses")
        .select("*")
        .eq("id", id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        flash("Expense not found.", "warning")
        return redirect(url_for("exptracker3"))

    expense = result.data[0]
    attachment_url = expense.get("attachment_url")

    if request.method == "POST":
        try:
            # --- Form data ---
            new_category = request.form.get("category")
            new_subcategory = request.form.get("subcategory")
            new_amount = request.form.get("amount")
            new_note = request.form.get("note")
            remove_attachment = request.form.get("remove_attachment")
            new_attachment = request.files.get("attachment")

            # --- Replace attachment if new file uploaded ---
            if new_attachment and new_attachment.filename and allowed_file(new_attachment.filename):
                # Remove old attachment
                if attachment_url:
                    try:
                        old_path = attachment_url.split("/storage/v1/object/public/expense-attachments/")[-1]
                        supabase.storage.from_("expense-attachments").remove([old_path])
                    except Exception as e:
                        print(f"Failed to delete old attachment: {e}")

                filename = secure_filename(new_attachment.filename)
                unique_path = f"{user_id}/{uuid.uuid4()}_{filename}"
                supabase.storage.from_("expense-attachments").upload(
                    unique_path,
                    new_attachment.read(),
                    {"content-type": new_attachment.content_type or "application/octet-stream"}
                )
                attachment_url = supabase.storage.from_("expense-attachments").get_public_url(unique_path)

            # --- Remove attachment if checkbox checked ---
            elif remove_attachment:
                if attachment_url:
                    try:
                        old_path = attachment_url.split("/storage/v1/object/public/expense-attachments/")[-1]
                        supabase.storage.from_("expense-attachments").remove([old_path])
                    except Exception as e:
                        print(f"Failed to delete attachment: {e}")
                attachment_url = None

            # --- Update expense ---
            supabase.table("expenses").update({
                "category": new_category,
                "subcategory": new_subcategory,
                "amount": new_amount,
                "note": new_note,
                "attachment_url": attachment_url
            }).eq("id", id).eq("user_id", user_id).execute()

            flash("Expense updated successfully!", "success")
            return redirect(url_for("exptracker3"))

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            flash(f"Failed to update expense: {e}", "danger")
            return redirect(request.url)

    return render_template("modify.html", expense=expense)
 '''   
# ------------------ Reports route (fixed single copy) ------------------
@app.route('/report', methods=["GET", "POST"])
def report(): 

    if request.method == "POST": 
        name = request.form.get("name") 
        email = request.form.get("email") 
        issue_type = request.form.get("issue_type") 
        message = request.form.get("message") 
        screenshot = request.files.get("screenshot") 
        
        if screenshot and screenshot.filename:                   
            os.makedirs("uploads", exist_ok=True)                
            filename = secure_filename(screenshot.filename)      
            screenshot.save(os.path.join("uploads", filename))   
    
        return redirect(url_for("support_success")) 
        
    return render_template("report.html")
#----------------------------------------------------------------------    
@app.route("/support_success") 
def support_success(): 
    return render_template("support_success.html")
'''
# ------------------ Support success page ------------------
@app.route("/support_success")
def support_success():
    template_path = "templates/support_success.html"
    if os.path.exists(template_path):
        return render_template("support_success.html")
    else:
        return "Report submitted successfully! We will contact you soon."
'''
# ------------------ Dashboard & other UI routes ------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    result = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
    expenses = result.data or []
    total_expense = sum(float(e["amount"]) for e in expenses) if expenses else 0

    current_month = datetime.now().strftime("%Y-%m")
    monthly_total = sum(float(e["amount"]) for e in expenses if e["next_date"].startswith(current_month))

    # category_map etc.
    category_map = {}
    for e in expenses:
        category_map[e["category"]] = category_map.get(e["category"], 0) + float(e["amount"])
    category_labels = list(category_map.keys())
    category_values = list(category_map.values())

    today = datetime.now()
    week_labels = []
    week_values = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        date_only = day.strftime("%Y-%m-%d")
        total_for_day = sum(float(e["amount"]) for e in expenses if e["next_date"][:10] == date_only)
        week_labels.append(day.strftime("%d %b"))
        week_values.append(total_for_day)

    recent = sorted(expenses, key=lambda x: x["next_date"], reverse=True)[:5]
    top_category = max(category_map, key=category_map.get) if category_map else "None"

    return render_template("dashboard.html",
                           total_expense=total_expense,
                           monthly_total=monthly_total,
                           top_category=top_category,
                           category_labels=category_labels,
                           category_values=category_values,
                           week_labels=week_labels,
                           week_values=week_values,
                           recent=recent,
                           category_map=category_map)
    
# ------------------ service-worker and favicon ------------------
@app.route('/static/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static/icons', 'exptracker_app_icon1.png')
# ----------------------------- Profile & Settings -------------------------
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
#-----------------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
#------------------------- Download Expense -----------------------------------------
@app.route("/download", methods=["GET"])
@login_required
def download_page():
    return render_template("download.html")
#---------------------------- Core Part For Download --------------------------------
@app.route("/download-expenses", methods=["POST"])
@login_required
def download_expenses():
    user_id = session["user_id"]

    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    file_type = request.form.get("file_type", "pdf")

    if not start_date or not end_date:
        flash("Please select both dates", "warning")
        return redirect(url_for("download_page"))

    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"

    result = (
        supabase.table("expenses")
        .select("*")
        .eq("user_id", user_id)
        .gte("next_date", start_dt)
        .lte("next_date", end_dt)
        .order("next_date")
        .execute()
    )

    expenses = result.data or []

    if not expenses:
        flash("No expenses found for selected date range", "info")
        return redirect(url_for("download_page"))

    # ---------- CSV ----------
    if file_type == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Category", "Subcategory", "Amount", "Note"])
        for e in expenses:
            writer.writerow([
                e["next_date"],
                e["category"],
                e["subcategory"],
                e["amount"],
                e.get("note", "")
            ])
        output.seek(0)
        filename = f"expenses_{start_date}_to_{end_date}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # ---------- PDF using ReportLab ----------
    elif file_type == "pdf":
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        pdf.setTitle(f"Expenses {start_date} to {end_date}")
    
        # Title
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(width / 2, height - 50, f"Expenses Report ({start_date} to {end_date})")
    
        # Table headers
        pdf.setFont("Helvetica-Bold", 12)
        y = height - 100
        x_list = [50, 150, 270, 370, 470]  # adjust column positions for better spacing
        headers = ["Date", "Category", "Subcategory", "Amount", "Note"]
        for i, header in enumerate(headers):
            pdf.drawString(x_list[i], y, header)
    
        # Table rows
        pdf.setFont("Helvetica", 12)
        y -= 20
        for e in expenses:
            row = [
                str(e.get("next_date", "")),
                str(e.get("category", "")),
                str(e.get("subcategory", "")),
                str(e.get("amount", "")),
                str(e.get("note", ""))
            ]
            for i, cell in enumerate(row):
                # Align amount to the right
                if headers[i] == "Amount":
                    pdf.drawRightString(x_list[i] + 50, y, cell)  # +50 adjusts to column width
                else:
                    pdf.drawString(x_list[i], y, cell)
            y -= 20
            if y < 50:
                pdf.showPage()
                pdf.setFont("Helvetica", 12)
                y = height - 50
    
        pdf.save()
        buffer.seek(0)
    
        filename = f"expenses_{start_date}_to_{end_date}.pdf"
        response = make_response(buffer.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        return response
# ------------------ Run App ------------------
if __name__ == "__main__":
    # debug True for local dev. Turn off in production.
    app.run(host="0.0.0.0", port=5000, debug=True)
