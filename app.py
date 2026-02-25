from flask import Flask, render_template, request, redirect, session
import snowflake.connector
import uuid
import bcrypt
from config import SNOWFLAKE_CONFIG, SECRET_KEY, OPENAI_API_KEY
from openai import OpenAI

app = Flask(__name__)
app.secret_key = SECRET_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

def get_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONFIG)

# ---------------- PASSWORD ----------------
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        emp_id = request.form['employee_id']
        password = request.form['password']

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash, role FROM employees WHERE employee_id=%s", (emp_id,))
        user = cur.fetchone()

        if user and verify_password(password, user[0]):
            session['employee_id'] = emp_id
            session['role'] = user[1]

            if user[1] == "manager":
                return redirect('/manager')
            return redirect('/dashboard')

        return "Invalid Credentials"

    return render_template('login.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'employee_id' not in session:
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT ticket_id, issue_type, status, priority FROM tickets WHERE employee_id=%s",
        (session['employee_id'],)
    )
    tickets = cur.fetchall()

    return render_template('dashboard.html', tickets=tickets)

# ---------------- CREATE TICKET ----------------
@app.route('/create_ticket', methods=['GET', 'POST'])
def create_ticket():
    if request.method == 'POST':
        issue_type = request.form['issue_type']
        description = request.form['description']
        priority = request.form['priority']

        ticket_id = str(uuid.uuid4())[:8]

        conn = get_connection()
        cur = conn.cursor()

        # Check existing resolved tickets
        cur.execute("SELECT description, resolution FROM tickets WHERE resolution IS NOT NULL")
        records = cur.fetchall()

        ai_suggestion = None
        status = "Pending Approval"

        # Check if similar ticket already resolved
        for desc, res in records:
            if description.lower() in desc.lower():
                ai_suggestion = res
                status = "Auto-Resolved"
                break

        # If not found, call AI (safe try/except)
        if not ai_suggestion:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an IT support assistant."},
                        {"role": "user", "content": description}
                    ]
                )
                ai_suggestion = response.choices[0].message.content
            except Exception as e:
                print("AI Error:", e)
                ai_suggestion = "AI service temporarily unavailable. IT team will review your request."

        # Insert ticket into database
        cur.execute("""
            INSERT INTO tickets(ticket_id, employee_id, issue_type,
                                 description, priority, status, ai_suggestion)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (ticket_id, session['employee_id'], issue_type,
              description, priority, status, ai_suggestion))

        conn.commit()
        return redirect('/dashboard')

    return render_template('create_ticket.html')

# ---------------- MANAGER ----------------
@app.route('/manager')
def manager():
    if session.get('role') != 'manager':
        return redirect('/')

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT ticket_id, employee_id, issue_type, priority, status FROM tickets WHERE status='Pending Approval'"
    )
    tickets = cur.fetchall()

    return render_template('manager_dashboard.html', tickets=tickets)

@app.route('/approve/<ticket_id>')
def approve(ticket_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET status='Approved' WHERE ticket_id=%s", (ticket_id,))
    conn.commit()
    return redirect('/manager')

@app.route('/resolve/<ticket_id>', methods=['POST'])
def resolve(ticket_id):
    resolution = request.form['resolution']
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE tickets
        SET status='Resolved', resolution=%s
        WHERE ticket_id=%s
    """, (resolution, ticket_id))
    conn.commit()
    return redirect('/manager')

if __name__ == '__main__':
    app.run(debug=True)