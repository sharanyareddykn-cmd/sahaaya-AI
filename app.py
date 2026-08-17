import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# SAHAAYA AI - FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = "SAHAAYA_AI_SECRET_KEY_CHANGE_LATER"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "sahaaya.db")


# =========================================================
# CONSTANTS
# =========================================================

CATEGORIES = [
    "Water",
    "Sanitation",
    "Healthcare",
    "Education",
    "Roads & Infrastructure",
    "Electricity",
    "Other"
]

STATUSES = [
    "Submitted",
    "AI Analyzed",
    "Verified",
    "Assigned",
    "In Progress",
    "Resolved",
    "Closed"
]

ROLES = [
    "citizen",
    "ngo",
    "admin"
]


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def current_time():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def generate_id(prefix, number):

    return (
        f"SAH-{prefix}-"
        f"{datetime.now().year}-"
        f"{number:05d}"
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def initialize_database():

    connection = get_db()

    connection.executescript("""

        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            citizen_id TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            phone TEXT,

            ward TEXT,

            password_hash TEXT NOT NULL,

            role TEXT NOT NULL DEFAULT 'citizen',

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS complaints (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE NOT NULL,

            citizen_id TEXT NOT NULL,

            title TEXT NOT NULL,

            description TEXT NOT NULL,

            category TEXT,

            ward TEXT,

            latitude REAL,

            longitude REAL,

            duration_days INTEGER DEFAULT 0,

            affected_people INTEGER DEFAULT 0,

            status TEXT DEFAULT 'Submitted',

            ai_category TEXT,

            ai_severity TEXT,

            ai_urgency TEXT,

            ai_priority TEXT,

            ai_sdg TEXT,

            ai_reason TEXT,

            ai_confidence REAL,

            human_priority TEXT,

            admin_note TEXT,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS complaint_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT NOT NULL,

            old_status TEXT,

            new_status TEXT NOT NULL,

            changed_by TEXT NOT NULL,

            note TEXT,

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS feedback (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT NOT NULL,

            citizen_id TEXT NOT NULL,

            rating INTEGER NOT NULL,

            comment TEXT,

            created_at TEXT NOT NULL
        );

    """)


    # =====================================================
    # DEMO ADMIN ACCOUNT
    # =====================================================

    admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        ("admin@sahaaya.local",)
    ).fetchone()


    if not admin:

        connection.execute(
            """
            INSERT INTO users
            (
                citizen_id,
                name,
                email,
                phone,
                ward,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SAH-ADMIN-001",
                "System Administrator",
                "admin@sahaaya.local",
                "9999999999",
                "All",
                generate_password_hash("Admin@123"),
                "admin",
                current_time()
            )
        )


    # =====================================================
    # DEMO NGO ACCOUNT
    # =====================================================

    ngo = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        ("ngo@sahaaya.local",)
    ).fetchone()


    if not ngo:

        connection.execute(
            """
            INSERT INTO users
            (
                citizen_id,
                name,
                email,
                phone,
                ward,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SAH-NGO-001",
                "NGO Officer",
                "ngo@sahaaya.local",
                "9999999998",
                "All",
                generate_password_hash("Ngo@123"),
                "ngo",
                current_time()
            )
        )


    connection.commit()

    connection.close()


# =========================================================
# AI ANALYSIS
# =========================================================

def analyze_complaint(
    description,
    duration,
    affected_people,
    selected_category
):

    description = description or ""

    text = description.lower()


    try:
        duration = int(duration or 0)
    except (TypeError, ValueError):
        duration = 0


    try:
        affected_people = int(affected_people or 0)
    except (TypeError, ValueError):
        affected_people = 0


    # =====================================================
    # CATEGORY DETECTION
    # =====================================================

    if (
        selected_category in CATEGORIES
        and selected_category != "Other"
    ):

        category = selected_category


    elif any(
        word in text
        for word in [
            "water",
            "pipe",
            "tap",
            "drinking",
            "leak",
            "pipeline"
        ]
    ):

        category = "Water"


    elif any(
        word in text
        for word in [
            "toilet",
            "drain",
            "garbage",
            "sewage",
            "waste",
            "sanitation"
        ]
    ):

        category = "Sanitation"


    elif any(
        word in text
        for word in [
            "hospital",
            "medicine",
            "health",
            "clinic",
            "ambulance",
            "doctor"
        ]
    ):

        category = "Healthcare"


    elif any(
        word in text
        for word in [
            "school",
            "teacher",
            "student",
            "education",
            "classroom"
        ]
    ):

        category = "Education"


    elif any(
        word in text
        for word in [
            "road",
            "pothole",
            "bridge",
            "street",
            "footpath"
        ]
    ):

        category = "Roads & Infrastructure"


    elif any(
        word in text
        for word in [
            "electricity",
            "power",
            "transformer",
            "streetlight",
            "current"
        ]
    ):

        category = "Electricity"


    else:

        category = "Other"


    # =====================================================
    # PRIORITY SCORE
    # =====================================================

    score = 0.0

    score += min(duration, 30) * 0.5

    score += min(
        affected_people,
        1000
    ) / 100


    if category in [
        "Water",
        "Healthcare",
        "Sanitation"
    ]:

        score += 4


    emergency_words = [
        "emergency",
        "danger",
        "unsafe",
        "outbreak",
        "contaminated",
        "accident",
        "critical",
        "urgent"
    ]


    if any(
        word in text
        for word in emergency_words
    ):

        score += 6


    # =====================================================
    # PRIORITY CLASSIFICATION
    # =====================================================

    if score >= 12:

        priority = "HIGH"
        severity = "High"
        urgency = "High"


    elif score >= 6:

        priority = "MEDIUM"
        severity = "Medium"
        urgency = "Medium"


    else:

        priority = "LOW"
        severity = "Low"
        urgency = "Low"


    # =====================================================
    # SDG MAPPING
    # =====================================================

    sdg_mapping = {

        "Water":
            "SDG 6 – Clean Water and Sanitation",

        "Sanitation":
            "SDG 6 – Clean Water and Sanitation",

        "Healthcare":
            "SDG 3 – Good Health and Well-being",

        "Education":
            "SDG 4 – Quality Education",

        "Roads & Infrastructure":
            "SDG 9 – Industry, Innovation and Infrastructure",

        "Electricity":
            "SDG 7 – Affordable and Clean Energy",

        "Other":
            "SDG 11 – Sustainable Cities and Communities"
    }


    # =====================================================
    # EXPLANATION
    # =====================================================

    reason = (
        f"The system detected a "
        f"{category.lower()} issue. "
        f"The complaint has been active for "
        f"{duration} day(s), and approximately "
        f"{affected_people} people are affected. "
        f"These factors contributed to the "
        f"{priority.lower()} priority."
    )


    return {

        "category": category,

        "severity": severity,

        "urgency": urgency,

        "priority": priority,

        "sdg": sdg_mapping.get(
            category,
            sdg_mapping["Other"]
        ),

        "reason": reason,

        "confidence": 0.82
    }


# =========================================================
# LOGIN DECORATORS
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("user_id"):

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return wrapper


def role_required(*roles):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if not session.get("user_id"):

                return redirect(
                    url_for("login")
                )


            if session.get("role") not in roles:

                flash(
                    "You do not have permission.",
                    "danger"
                )

                return redirect(
                    url_for("dashboard")
                )


            return function(*args, **kwargs)

        return wrapper

    return decorator


# =========================================================
# COMPLAINT HISTORY
# =========================================================

def add_history(
    complaint_id,
    old_status,
    new_status,
    changed_by,
    note=""
):

    connection = get_db()

    connection.execute(
        """
        INSERT INTO complaint_history
        (
            complaint_id,
            old_status,
            new_status,
            changed_by,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            old_status,
            new_status,
            changed_by,
            note,
            current_time()
        )
    )

    connection.commit()

    connection.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        ward = request.form.get(
            "ward",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        if (
            not name
            or not email
            or not password
        ):

            flash(
                "Name, email and password are required.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        connection = get_db()


        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()


        if existing:

            connection.close()

            flash(
                "This email is already registered.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()["total"] + 1


        citizen_id = generate_id(
            "CIT",
            count
        )


        connection.execute(
            """
            INSERT INTO users
            (
                citizen_id,
                name,
                email,
                phone,
                ward,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citizen_id,
                name,
                email,
                phone,
                ward,
                generate_password_hash(password),
                "citizen",
                current_time()
            )
        )


        connection.commit()

        connection.close()


        flash(
            f"Registration successful! "
            f"Your Citizen ID is {citizen_id}",
            "success"
        )


        return redirect(
            url_for("login")
        )


    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        connection = get_db()


        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()


        connection.close()


        if (
            user
            and check_password_hash(
                user["password_hash"],
                password
            )
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["citizen_id"] = user["citizen_id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["email"] = user["email"]
            session["ward"] = user["ward"]


            return redirect(
                url_for("dashboard")
            )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    connection = get_db()


    if session.get("role") == "citizen":

        complaints = connection.execute(
            """
            SELECT *
            FROM complaints
            WHERE citizen_id = ?
            ORDER BY id DESC
            """,
            (session["citizen_id"],)
        ).fetchall()


    else:

        complaints = connection.execute(
            """
            SELECT
                c.*,
                u.name AS citizen_name,
                u.phone AS citizen_phone
            FROM complaints c
            LEFT JOIN users u
                ON c.citizen_id = u.citizen_id
            ORDER BY c.id DESC
            """
        ).fetchall()


    total = len(complaints)


    high = sum(
        1
        for complaint in complaints
        if (
            complaint["human_priority"]
            or complaint["ai_priority"]
        ) == "HIGH"
    )


    pending = sum(
        1
        for complaint in complaints
        if complaint["status"]
        not in ["Resolved", "Closed"]
    )


    resolved = sum(
        1
        for complaint in complaints
        if complaint["status"]
        in ["Resolved", "Closed"]
    )


    category_counts = {}

    status_counts = {}


    for complaint in complaints:

        category = (
            complaint["ai_category"]
            or complaint["category"]
            or "Other"
        )


        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )


        status = (
            complaint["status"]
            or "Submitted"
        )


        status_counts[status] = (
            status_counts.get(status, 0) + 1
        )


    connection.close()


    return render_template(
        "dashboard.html",

        complaints=complaints,

        total=total,

        high=high,

        pending=pending,

        resolved=resolved,

        category_counts=category_counts,

        status_counts=status_counts
    )


# =========================================================
# NEW COMPLAINT
# =========================================================

@app.route(
    "/complaint/new",
    methods=["GET", "POST"]
)
@role_required("citizen")
def new_complaint():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()


        description = request.form.get(
            "description",
            ""
        ).strip()


        category = request.form.get(
            "category",
            "Other"
        ).strip()


        ward = request.form.get(
            "ward",
            ""
        ).strip()


        duration_value = (
            request.form.get("duration_days")
            or request.form.get("duration")
            or "0"
        )


        affected_value = (
            request.form.get("affected_people")
            or request.form.get("people_affected")
            or "0"
        )


        try:

            duration = int(
                duration_value
            )

        except (
            ValueError,
            TypeError
        ):

            duration = 0


        try:

            affected = int(
                affected_value
            )

        except (
            ValueError,
            TypeError
        ):

            affected = 0


        latitude = (
            request.form.get("latitude")
            or None
        )


        longitude = (
            request.form.get("longitude")
            or None
        )


        if not title:

            flash(
                "Complaint title is required.",
                "danger"
            )

            return redirect(
                url_for("new_complaint")
            )


        if not description:

            flash(
                "Complaint description is required.",
                "danger"
            )

            return redirect(
                url_for("new_complaint")
            )


        if duration < 0:

            duration = 0


        if affected < 0:

            affected = 0


        if category not in CATEGORIES:

            category = "Other"


        connection = get_db()


        number = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM complaints
            """
        ).fetchone()["total"] + 1


        complaint_id = generate_id(
            "CMP",
            number
        )


        result = analyze_complaint(
            description,
            duration,
            affected,
            category
        )


        timestamp = current_time()


        connection.execute(
            """
            INSERT INTO complaints
            (
                complaint_id,
                citizen_id,
                title,
                description,
                category,
                ward,
                latitude,
                longitude,
                duration_days,
                affected_people,
                status,
                ai_category,
                ai_severity,
                ai_urgency,
                ai_priority,
                ai_sdg,
                ai_reason,
                ai_confidence,
                created_at,
                updated_at
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                complaint_id,
                session["citizen_id"],
                title,
                description,
                category,
                ward,
                latitude,
                longitude,
                duration,
                affected,
                "AI Analyzed",
                result["category"],
                result["severity"],
                result["urgency"],
                result["priority"],
                result["sdg"],
                result["reason"],
                result["confidence"],
                timestamp,
                timestamp
            )
        )


        connection.commit()

        connection.close()


        add_history(
            complaint_id,
            "Submitted",
            "AI Analyzed",
            session["citizen_id"],
            "AI analysis completed."
        )


        flash(
            f"Complaint {complaint_id} submitted successfully. "
            f"AI Priority: {result['priority']}",
            "success"
        )


        return redirect(
            url_for(
                "complaint_detail",
                complaint_id=complaint_id
            )
        )


    return render_template(
        "new_complaint.html",
        categories=CATEGORIES
    )


# =========================================================
# COMPLAINT DETAIL
# =========================================================

@app.route(
    "/complaint/<complaint_id>"
)
@login_required
def complaint_detail(complaint_id):

    connection = get_db()


    complaint = connection.execute(
        """
        SELECT
            c.*,
            u.name AS citizen_name,
            u.email AS citizen_email,
            u.phone AS citizen_phone
        FROM complaints c
        LEFT JOIN users u
            ON c.citizen_id = u.citizen_id
        WHERE c.complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()


    if not complaint:

        connection.close()

        flash(
            "Complaint not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    if (
        session.get("role") == "citizen"
        and complaint["citizen_id"]
        != session.get("citizen_id")
    ):

        connection.close()

        flash(
            "You do not have permission to view this complaint.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    history = connection.execute(
        """
        SELECT *
        FROM complaint_history
        WHERE complaint_id = ?
        ORDER BY id ASC
        """,
        (complaint_id,)
    ).fetchall()


    feedback = connection.execute(
        """
        SELECT *
        FROM feedback
        WHERE complaint_id = ?
        ORDER BY id DESC
        """,
        (complaint_id,)
    ).fetchall()


    connection.close()


    return render_template(
        "complaint_detail.html",

        complaint=complaint,

        history=history,

        feedback=feedback,

        statuses=STATUSES
    )


# =========================================================
# VERIFY COMPLAINT
# =========================================================
# THIS ROUTE FIXES THE RENDER ERROR:
#
# complaint_detail.html is calling:
#
# url_for("verify_complaint", complaint_id=...)
#
# The old app.py did not have this endpoint.
# =========================================================

@app.route(
    "/complaint/<complaint_id>/verify",
    methods=["GET", "POST"]
)
@role_required("admin", "ngo")
def verify_complaint(complaint_id):

    connection = get_db()


    complaint = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()


    if not complaint:

        connection.close()

        flash(
            "Complaint not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    old_status = complaint["status"]


    # -----------------------------------------------------
    # If already verified, do not create duplicate history
    # -----------------------------------------------------

    if old_status == "Verified":

        connection.close()

        flash(
            "This complaint is already verified.",
            "info"
        )

        return redirect(
            url_for(
                "complaint_detail",
                complaint_id=complaint_id
            )
        )


    # -----------------------------------------------------
    # Update complaint status
    # -----------------------------------------------------

    connection.execute(
        """
        UPDATE complaints
        SET
            status = ?,
            updated_at = ?
        WHERE complaint_id = ?
        """,
        (
            "Verified",
            current_time(),
            complaint_id
        )
    )


    connection.commit()

    connection.close()


    # -----------------------------------------------------
    # Add history entry
    # -----------------------------------------------------

    add_history(
        complaint_id,
        old_status,
        "Verified",
        session.get(
            "citizen_id",
            "STAFF"
        ),
        "Complaint verified by staff."
    )


    flash(
        "Complaint verified successfully.",
        "success"
    )


    return redirect(
        url_for(
            "complaint_detail",
            complaint_id=complaint_id
        )
    )


# =========================================================
# UPDATE COMPLAINT
# =========================================================

@app.route(
    "/complaint/<complaint_id>/update",
    methods=["POST"]
)
@role_required("admin", "ngo")
def update_complaint(complaint_id):

    connection = get_db()


    complaint = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()


    if not complaint:

        connection.close()

        flash(
            "Complaint not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    old_status = complaint["status"]


    new_status = request.form.get(
        "status",
        old_status
    ).strip()


    human_priority = request.form.get(
        "human_priority",
        ""
    ).strip()


    admin_note = request.form.get(
        "admin_note",
        ""
    ).strip()


    if new_status not in STATUSES:

        new_status = old_status


    connection.execute(
        """
        UPDATE complaints
        SET
            status = ?,
            human_priority = ?,
            admin_note = ?,
            updated_at = ?
        WHERE complaint_id = ?
        """,
        (
            new_status,
            human_priority or None,
            admin_note or None,
            current_time(),
            complaint_id
        )
    )


    connection.commit()

    connection.close()


    if new_status != old_status:

        add_history(
            complaint_id,
            old_status,
            new_status,
            session.get(
                "citizen_id",
                "STAFF"
            ),
            admin_note
        )


    flash(
        "Complaint updated successfully.",
        "success"
    )


    return redirect(
        url_for(
            "complaint_detail",
            complaint_id=complaint_id
        )
    )


# =========================================================
# FEEDBACK
# =========================================================

@app.route(
    "/complaint/<complaint_id>/feedback",
    methods=["POST"]
)
@role_required("citizen")
def submit_feedback(complaint_id):

    connection = get_db()


    complaint = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()


    if not complaint:

        connection.close()

        flash(
            "Complaint not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    if complaint["citizen_id"] != session.get(
        "citizen_id"
    ):

        connection.close()

        flash(
            "You cannot provide feedback for this complaint.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )


    try:

        rating = int(
            request.form.get(
                "rating",
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        rating = 0


    comment = request.form.get(
        "comment",
        ""
    ).strip()


    if rating < 1 or rating > 5:

        connection.close()

        flash(
            "Please select a rating from 1 to 5.",
            "danger"
        )

        return redirect(
            url_for(
                "complaint_detail",
                complaint_id=complaint_id
            )
        )


    connection.execute(
        """
        INSERT INTO feedback
        (
            complaint_id,
            citizen_id,
            rating,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            session["citizen_id"],
            rating,
            comment,
            current_time()
        )
    )


    connection.commit()

    connection.close()


    flash(
        "Thank you for your feedback.",
        "success"
    )


    return redirect(
        url_for(
            "complaint_detail",
            complaint_id=complaint_id
        )
    )


# =========================================================
# API
# =========================================================

@app.route(
    "/api/complaint/<complaint_id>"
)
@login_required
def complaint_api(complaint_id):

    connection = get_db()


    complaint = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE complaint_id = ?
        """,
        (complaint_id,)
    ).fetchone()


    if not complaint:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Complaint not found."
        }), 404


    if (
        session.get("role") == "citizen"
        and complaint["citizen_id"]
        != session.get("citizen_id")
    ):

        connection.close()

        return jsonify({
            "success": False,
            "message": "Access denied."
        }), 403


    data = dict(complaint)


    connection.close()


    return jsonify({
        "success": True,
        "complaint": data
    })


# =========================================================
# INITIALIZE DATABASE
# =========================================================

initialize_database()


# =========================================================
# START FLASK SERVER
# =========================================================

if __name__ == "__main__":

    print()

    print("=" * 60)

    print("SAHAAYA AI")

    print("Citizen Grievance Intelligence Platform")

    print("=" * 60)

    print("Database:", DATABASE)

    print("Server: http://127.0.0.1:5000")

    print("=" * 60)

    print()


    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
