import os
import streamlit as st
import mysql.connector
from mysql.connector import Error
from contextlib import closing

# ------------------- PAGE CONFIG -------------------
st.set_page_config(page_title="Lost & Found Portal", page_icon="🔎", layout="wide")

# ------------------- DB CONFIG ---------------------
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = os.getenv("DB_PASS", "Vishnu1234!")
DB_NAME = "lost_found_portal"

@st.cache_resource(show_spinner=False)
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

# ---------- Small Helpers ----------
def run_query(sql, params=None, dict_rows=True):
    conn = get_connection()
    with closing(conn.cursor(dictionary=dict_rows)) as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()

def run_exec(sql, params=None):
    conn = get_connection()
    with closing(conn.cursor()) as cur:
        cur.execute(sql, params or ())
        conn.commit()

def success(msg): st.toast(msg, icon="✅")
def fail(msg): st.toast(f"❌ {msg}")

# ---------- Loaders ----------
def load_categories():
    return run_query("SELECT category_id, category_name FROM category ORDER BY category_name")

def load_users():
    return run_query("SELECT user_id, full_name, role FROM user ORDER BY full_name")

def load_locations():
    return run_query("SELECT location_id, name FROM location ORDER BY name")

def load_items(filters=None):
    q = """
        SELECT i.item_id, i.title, i.description, c.category_name, i.status,
               u.full_name AS owner, i.date_reported
        FROM items i
        LEFT JOIN category c ON i.category_id = c.category_id
        LEFT JOIN user u ON i.owner_user_id = u.user_id
        WHERE 1=1
    """
    params = []
    if filters:
        if filters.get("search"):
            q += " AND i.title LIKE %s"
            params.append(f"%{filters['search']}%")
        if filters.get("category_ids"):
            q += " AND i.category_id IN (" + ",".join(["%s"] * len(filters["category_ids"])) + ")"
            params.extend(filters["category_ids"])
        if filters.get("statuses"):
            q += " AND i.status IN (" + ",".join(["%s"] * len(filters["statuses"])) + ")"
            params.extend(filters["statuses"])
    q += " ORDER BY i.item_id DESC"
    return run_query(q, params)


# ---------------- LOGIN PAGE ----------------
def login_page():
    st.title("🔐 Login Page")

    st.write("Select your account to proceed.")
    users = load_users()

    selected = st.selectbox(
        "Select User",
        [f"{u['user_id']} — {u['full_name']} ({u['role']})" for u in users]
    )

    if st.button("Login"):
        uid = int(selected.split(" — ")[0])
        user_data = run_query("SELECT * FROM user WHERE user_id=%s", (uid,))[0]
        st.session_state['logged_in'] = True
        st.session_state['user'] = user_data
        st.success(f"Logged in as {user_data['full_name']}")
        st.rerun()


# =================== PAGES ===================

def page_home():
    st.title("📊 Dashboard")
    col1, col2, col3, col4 = st.columns(4)

    total_items = run_query("SELECT COUNT(*) AS n FROM items")[0]["n"]
    total_lost = run_query("SELECT COUNT(*) AS n FROM items WHERE status='Lost'")[0]["n"]
    total_found = run_query("SELECT COUNT(*) AS n FROM items WHERE status='Found'")[0]["n"]

    try:
        pending = run_query("SELECT total_pending_claims() AS n")[0]["n"]
    except:
        pending = run_query("SELECT COUNT(*) AS n FROM claim WHERE claim_status='Pending'")[0]["n"]

    col1.metric("Total Items", total_items)
    col2.metric("Lost", total_lost)
    col3.metric("Found", total_found)
    col4.metric("Pending Claims", pending)

    st.divider()
    st.subheader("Items by Category")
    rows = run_query("""
        SELECT c.category_name, COUNT(i.item_id) AS total_items
        FROM category c
        LEFT JOIN items i ON c.category_id = i.category_id
        GROUP BY c.category_name
        ORDER BY total_items DESC
    """)
    st.bar_chart({r["category_name"]: r["total_items"] for r in rows})


def page_items():
    st.title("🧾 Items")

    cats = load_categories()
    statuses = ["Lost", "Found"]

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2,2,2,1])
        search = c1.text_input("Search title")
        selected_cats = c2.multiselect("Category", [c["category_name"] for c in cats])
        selected_cat_ids = [c["category_id"] for c in cats if c["category_name"] in selected_cats]
        selected_statuses = c3.multiselect("Status", statuses, default=statuses)
        if c4.button("Clear"):
            st.session_state.clear()
            st.rerun()

    items = load_items({
        "search": search.strip() if search else None,
        "category_ids": selected_cat_ids or None,
        "statuses": selected_statuses or None
    })

    st.dataframe(items, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Quick Actions")
    colA, colB, colC = st.columns(3)
    target_id = colA.number_input("Item ID", min_value=1, step=1)
    new_status = colB.selectbox("Set status", ["Lost", "Found"])
    if colC.button("Apply"):
        run_exec("UPDATE items SET status=%s WHERE item_id=%s", (new_status, target_id))
        success("Status updated.")
        st.rerun()


def page_add_item():
    st.title("➕ Add New Item")
    cats = load_categories()
    users = load_users()

    with st.form("add_item_form", clear_on_submit=True):
        title = st.text_input("Item Title")
        col1, col2 = st.columns(2)
        existing_cat = col1.selectbox("Choose Category", ["-- New --"] + [c["category_name"] for c in cats])
        new_cat = col2.text_input("Or create new category")

        description = st.text_area("Description")
        status = st.selectbox("Status", ["Lost", "Found"])
        owner = st.selectbox("Owner User", [f"{u['user_id']} — {u['full_name']}" for u in users])

        submit = st.form_submit_button("Submit")

    if submit:
        if not title.strip():
            fail("Item title required.")
            return

        if existing_cat != "-- New --":
            cat_id = next(c["category_id"] for c in cats if c["category_name"] == existing_cat)
        else:
            run_exec("INSERT INTO category (category_name) VALUES (%s)", (new_cat.strip(),))
            cat_id = run_query("SELECT LAST_INSERT_ID() AS id")[0]["id"]

        owner_id = int(owner.split(" — ")[0])
        run_exec("""
            INSERT INTO items (title, description, category_id, owner_user_id, status, date_reported)
            VALUES (%s,%s,%s,%s,%s,NOW())
        """, (title, description, cat_id, owner_id, status))

        success("Item added successfully.")
        st.rerun()


def page_reports():
    st.title("📝 Reports (Lost / Found)")
    users = load_users()
    locs = load_locations()
    items_all = run_query("SELECT item_id, title FROM items ORDER BY item_id DESC")

    tab1, tab2 = st.tabs(["Report Lost", "Report Found"])

    # Lost
    with tab1:
        with st.form("lost_form", clear_on_submit=True):
            user_sel = st.selectbox("Reported by", [f"{u['user_id']} — {u['full_name']}" for u in users])
            item_sel = st.selectbox("Item", [f"{i['item_id']} — {i['title']}" for i in items_all])
            loc_sel = st.selectbox("Location", [f"{l['location_id']} — {l['name']}" for l in locs])
            date_lost = st.date_input("Date Lost")
            submit_lost = st.form_submit_button("Create Lost Report")

        if submit_lost:
            uid = int(user_sel.split(" — ")[0])
            iid = int(item_sel.split(" — ")[0])
            lid = int(loc_sel.split(" — ")[0])
            run_exec("""
                INSERT INTO lostreport (user_id, item_id, location_id, date_lost, status, reported_at)
                VALUES (%s,%s,%s,%s,'Open',NOW())
            """, (uid, iid, lid, date_lost))
            success("Lost report filed.")

    # Found
    with tab2:
        with st.form("found_form", clear_on_submit=True):
            rep_sel = st.selectbox("Found by", [f"{u['user_id']} — {u['full_name']}" for u in users])
            item_sel = st.selectbox("Item", [f"{i['item_id']} — {i['title']}" for i in items_all], key="founditem")
            loc_sel = st.selectbox("Location", [f"{l['location_id']} — {l['name']}" for l in locs], key="foundloc")
            date_found = st.date_input("Date Found")
            submit_found = st.form_submit_button("Create Found Report")

        if submit_found:
            uid = int(rep_sel.split(" — ")[0])
            iid = int(item_sel.split(" — ")[0])
            lid = int(loc_sel.split(" — ")[0])
            run_exec("""
                INSERT INTO foundreport (reported_by_user_id, item_id, location_id, date_found, status, reported_at)
                VALUES (%s,%s,%s,%s,'Unclaimed',NOW())
            """, (uid, iid, lid, date_found))
            success("Found report filed.")


def page_claims():
    st.title("✅ Claims")
    items_all = run_query("SELECT item_id, title FROM items ORDER BY item_id DESC")
    users = load_users()

    with st.container(border=True):
        st.subheader("Create Claim")
        c1, c2, c3 = st.columns([3,3,1])
        item_sel = c1.selectbox("Item", [f"{i['item_id']} — {i['title']}" for i in items_all])
        user_sel = c2.selectbox("Claimer", [f"{u['user_id']} — {u['full_name']}" for u in users])

        if c3.button("Create"):
            iid = int(item_sel.split(" — ")[0])
            uid = int(user_sel.split(" — ")[0])
            run_exec("INSERT INTO claim (item_id, claimer_id, claim_status, claimed_at) VALUES (%s,%s,'Pending',NOW())",
                     (iid, uid))
            success("Claim created.")
            st.rerun()

    st.subheader("All Claims")
    claims = run_query("""
        SELECT c.claim_id, c.item_id, i.title AS item_title, u.full_name AS claimer,
               c.claim_status, c.claimed_at
        FROM claim c
        JOIN items i ON c.item_id = i.item_id
        LEFT JOIN user u ON c.claimer_id = u.user_id
        ORDER BY c.claim_id DESC
    """)
    st.dataframe(claims, use_container_width=True, hide_index=True)

    colA, colB = st.columns([2,1])
    cid = colA.number_input("Approve Claim ID", min_value=1, step=1)
    if colB.button("Approve"):
        run_exec("UPDATE claim SET claim_status='Approved' WHERE claim_id=%s", (cid,))
        itm = run_query("SELECT item_id FROM claim WHERE claim_id=%s", (cid,))[0]["item_id"]
        run_exec("UPDATE items SET status='Found' WHERE item_id=%s", (itm,))
        run_exec("UPDATE foundreport SET status='Returned' WHERE item_id=%s", (itm,))
        success("Claim approved.")
        st.rerun()


def page_analytics():
    st.title("📈 Analytics")

    st.subheader("Items by Category")
    rows = run_query("""
        SELECT c.category_name, COUNT(i.item_id) AS total_items
        FROM category c
        LEFT JOIN items i ON c.category_id = i.category_id
        GROUP BY c.category_name
        ORDER BY total_items DESC
    """)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.bar_chart({r["category_name"]: r["total_items"] for r in rows})

    st.divider()
    st.subheader("Claims by Status")
    rows2 = run_query("SELECT claim_status, COUNT(*) AS total FROM claim GROUP BY claim_status")
    st.dataframe(rows2, use_container_width=True, hide_index=True)


# ---------------- PROTECT PAGES ----------------
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    login_page()
    st.stop()


# ---------------- ROUTER ----------------
with st.sidebar:
    st.title("🔎 Lost & Found Portal")
    st.write(f"Logged in as **{st.session_state['user']['full_name']}** ({st.session_state['user']['role']})")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    page = st.radio("Menu", ["Dashboard", "Items", "Add Item", "Reports", "Claims", "Analytics"])

if page == "Dashboard":
    page_home()
elif page == "Items":
    page_items()
elif page == "Add Item":
    page_add_item()
elif page == "Reports":
    page_reports()
elif page == "Claims":
    page_claims()
elif page == "Analytics":
    page_analytics()
