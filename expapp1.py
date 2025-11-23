from flask import Flask , request,redirect, render_template
from supabase import create_client,Client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SUPABASE_URL= os.getenv("SUPABASE_URL")
SUPABASE_KEY= os.getenv("SUPABASE_KEY")
supabase: Client= create_client (SUPABASE_URL,SUPABASE_KEY)

CSV_FILE= os.path.join("/tmp", "expenses1.csv")

#if not os.path.exists(CSV_FILE):
#    with open (CSV_FILE,"w",newline="")as file:
#        writer = csv.writer(file)
#        writer.writerow(["date","amount","category","note"])
#OPORER GULO PYTHON ER CODE JE GULO HASH(#) ROACHE

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        hashed_pass = generate_password_hash(password)

        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return "Email already registered!"

        supabase.table("users").insert({
            "email": email,
            "password": hashed_pass
        }).execute()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = supabase.table("users").select("*").eq("email", email).execute()

        if not user.data:
            return "User not found!"

        stored_hash = user.data[0]["password"]

        if not check_password_hash(stored_hash, password):
            return "Incorrect password!"

        session["user_id"] = user.data[0]["id"]
        session["email"] = user.data[0]["email"]

        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/",methods=["GET","POST"])
def exptracker():
    if request.method=="POST":
        amount=request.form["amount"]
        category=request.form["category"]
        note=request.form["note"]
        next_date=datetime.now().strftime("%Y-%m-%d")
    
        #with open(CSV_FILE,"a",newline="")as file:
        #    writer=csv.writer(file)
        #    writer.writerow([date,amount,category,note])

        supabase.table("expenses").insert({
            "next_date":next_date,
            "amount":amount,
            "category":category,
            "note":note
            "user_id": session["user_id"]
        }).execute()
        return redirect("/")
    response=supabase.table("expenses").select("*").execute()
    expense=response.data
    total=sum(float(item["amount"])for item in expense)

    #with open(CSV_FILE,"r")as file:
    #    reader=csv.DictReader(file)
    #    for row in reader:
    #        expense.append(row)
    #        total+=float(row["amount"])
    return render_template("exptracker.html",expense=expense, total=total)

@app.route("/delete/<int:id>")
def delete_row(id):
    supabase.table("expenses").delete().eq("id",id).execute()
    
    #rows = []

    #with open(CSV_FILE, "r") as file:
    #    reader = csv.reader(file)
    #    rows = list(reader)

    #if index + 1 < len(rows):
    #    rows.pop(index + 1)

    #with open(CSV_FILE, "w", newline="") as file:
    #    writer = csv.writer(file)
    #    writer.writerows(rows)
    
    return redirect("/") 




if __name__ == "__main__":
    app.run()

    #git config --global user.name "supratikdev04" && git config --global user.email "supratik.dev04@gmail.com"
