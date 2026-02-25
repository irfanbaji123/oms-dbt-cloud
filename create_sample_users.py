import bcrypt
import snowflake.connector

SNOWFLAKE_CONFIG = {
    "user": "BASHA2975",
    "password": "Irf@nb@ji29752975",
    "account": "NRRMYSH-GH03951",
    "warehouse": "COMPUTE_WH",
    "database": "MY_EMPLOYEE",
    "schema": "EMPLOYEE_TICKET"
}

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
cur = conn.cursor()

users = [
    ("EMP001", "John Smith", "john.smith@company.com", "employee"),
    ("EMP002", "Priya Kumar", "priya.kumar@company.com", "employee"),
    ("EMP003", "David Lee", "david.lee@company.com", "employee"),
    ("MGR001", "Sarah Johnson", "sarah.johnson@company.com", "manager"),
]

for emp_id, name, email, role in users:
    password_hash = hash_password("Password@123")
    cur.execute("""
        INSERT INTO employees (employee_id, name, email, password_hash, role)
        VALUES (%s, %s, %s, %s, %s)
    """, (emp_id, name, email, password_hash, role))

conn.commit()
print("Sample users inserted successfully.")
