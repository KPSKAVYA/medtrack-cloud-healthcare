from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
import uuid
import logging

app = Flask(__name__)
app.secret_key = "medtrack_secret_key"

# ----------------------------
# Logging Setup
# ----------------------------
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------
# AWS Configuration
# ----------------------------
REGION = "ap-south-1"  # Change if needed
SNS_TOPIC_ARN = "arn:aws:sns:ap-south-1:339713112656:Medtrack"

client = MongoClient("mongodb://localhost:27017/")

db = client["medtrack"]

users_table = db["users"]
appointments_table = db["appointments"]

# sns = boto3.client('sns', region_name=REGION)

# ----------------------------
# Home
# ----------------------------
@app.route("/")
def home():
    return render_template("index.html")

# ----------------------------
# Register
# ----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        users_table.insert_one({
            "email": request.form["email"],
            "name": request.form["name"],
            "password": request.form["password"],
            "role": request.form["role"],
            "login_count": 0
        })
        logging.info("New user registered")
        return redirect("/login")

    return render_template("register.html")

# ----------------------------
# Login
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_table.find_one({"email": email})

        if user and user["password"] == password:
            session["user"] = email
            session["role"] = user["role"]

            users_table.update_one(
                {"email": email},
                {"$inc": {"login_count": 1}}
            )

            logging.info(f"{email} logged in")

            if user["role"] == "doctor":
                return redirect("/doctor_dashboard")
            else:
                return redirect("/patient_dashboard")

        return "Invalid Credentials"

    return render_template("login.html")

# ----------------------------
# Logout
# ----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ----------------------------
# Dashboards
# ----------------------------
@app.route("/doctor_dashboard")
def doctor_dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("doctor_dashboard.html")

@app.route("/patient_dashboard")
def patient_dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("patient_dashboard.html")

# ----------------------------
# Book Appointment
# ----------------------------
@app.route("/book_appointment", methods=["GET", "POST"])
def book_appointment():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        appointment_id = str(uuid.uuid4())

        appointments_table.insert_one(
            {
                "appointment_id": appointment_id,
                "patient_email": session["user"],
                "doctor_email": request.form["doctor_email"],
                "date": request.form["date"],
                "time": request.form["time"],
                "status": "Scheduled"
            }
        )

        # sns.publish(
        #     TopicArn=SNS_TOPIC_ARN,
        #     Message=f"New appointment booked on {request.form['date']} at {request.form['time']}",
        #     Subject="New Appointment"
        # )

        logging.info("Appointment booked")

        return redirect("/view_appointment_patient")

    return render_template("book_appointment.html")

# ----------------------------
# View Doctor Appointments
# ----------------------------
@app.route("/view_appointment_doctor")
def view_appointment_doctor():
    if "user" not in session:
        return redirect("/login")

    doctor_email = session["user"]

    appointments = list(
        appointments_table.find({"doctor_email": doctor_email})
    )

    return render_template("view_appointment_doctor.html", appointments=appointments)

# ----------------------------
# View Patient Appointments
# ----------------------------
@app.route("/view_appointment_patient")
def view_appointment_patient():
    if "user" not in session:
        return redirect("/login")

    patient_email = session["user"]

    appointments = list(
        appointments_table.find({"patient_email": patient_email})
    )

    return render_template("view_appointment_patient.html", appointments=appointments)

# ----------------------------
# Submit Diagnosis
# ----------------------------
from datetime import datetime

@app.route("/submit_diagnosis", methods=["GET", "POST"])
def submit_diagnosis():
    if "user" not in session:
        return redirect("/login")

    # ---------------- POST (when doctor clicks submit) ----------------
    if request.method == "POST":

        appointment_id = request.form.get("appointment_id")
        diagnosis = request.form.get("diagnosis")

        appointment = appointments_table.find_one({
            "appointment_id": appointment_id
        })

        if not appointment:
            return redirect("/view_appointment_doctor")

        # check appointment time
        appointment_datetime = datetime.strptime(
            appointment["date"] + " " + appointment["time"],
            "%Y-%m-%d %H:%M"
        )

        if datetime.now() < appointment_datetime:
            return render_template(
                "submit_diagnosis.html",
                appointment=appointment,
                error="Appointment has not started yet. Diagnosis can be submitted after the consultation time."
            )

        appointments_table.update_one(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "diagnosis": diagnosis,
                    "status": "Completed"
                }
            }
        )

        logging.info("Diagnosis submitted")

        return redirect("/view_appointment_doctor")

    # ---------------- GET (when doctor clicks Add Diagnosis) ----------------
    appointment_id = request.args.get("appointment_id")

    if not appointment_id:
        return redirect("/view_appointment_doctor")

    appointment = appointments_table.find_one({
        "appointment_id": appointment_id
    })

    return render_template("submit_diagnosis.html", appointment=appointment)
# ----------------------------
# Search Appointment
# ----------------------------
@app.route("/search", methods=["POST"])
def search():
    search_date = request.form["date"]

    results = list(
        appointments_table.find({"date": search_date})
    )

    return render_template("search_results.html", appointments=results)

# ----------------------------
# Health Check
# ----------------------------
@app.route("/health")
def health():
    return {"status": "Application Running"}, 200

# ----------------------------
# Run App
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
