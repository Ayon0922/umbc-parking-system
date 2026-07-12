"""
UMBC Parking Management System — Streamlit admin console.
CMSC 461 · production-hardened build.

Run:  streamlit run app.py
Config comes from environment variables (see db.py / .env.example).
"""
import os
from datetime import datetime, date, timedelta

import streamlit as st

from db import run_query, run_readonly

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="UMBC Parking Admin",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] {
        height: 42px; padding: 0 18px;
        background: #f0f2f6; border-radius: 8px;
        font-weight: 600; font-size: 0.82rem;
    }
    .stTabs [aria-selected="true"] { background: #c41230 !important; color: white !important; }
    .section-header { font-size: 1.4rem; font-weight: 700; color: #c41230; margin-bottom: 4px; }
    .code-block { background:#1e1e1e; color:#d4d4d4; padding:14px 18px; border-radius:8px;
                  font-family:monospace; font-size:0.8rem; white-space:pre-wrap; margin-top:8px; }
</style>
""", unsafe_allow_html=True)


def metric_card(label, value, color="#1f77b4"):
    st.markdown(
        f"""<div style='background:{color};padding:16px 20px;border-radius:10px;
        text-align:center;color:white;margin-bottom:8px'>
        <div style='font-size:2rem;font-weight:700'>{value}</div>
        <div style='font-size:0.85rem;opacity:0.9'>{label}</div></div>""",
        unsafe_allow_html=True,
    )


# ============================================================
# LOGIN GATE  (simple shared-secret; set APP_ADMIN_PASSWORD in env)
# ============================================================
def require_login():
    if st.session_state.get("authed"):
        return
    st.markdown("<h2 style='color:#c41230'>🐾 UMBC Parking Admin — Sign in</h2>", unsafe_allow_html=True)
    expected = os.getenv("APP_ADMIN_PASSWORD", "admin")
    with st.form("login"):
        pwd = st.text_input("Admin password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            if pwd == expected:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.caption("Default password is `admin` — override it with the APP_ADMIN_PASSWORD environment variable.")
    st.stop()


require_login()

# Fail fast with a friendly message if the DB is unreachable.
try:
    run_query("SELECT 1;")
except Exception as e:
    st.error(f"Cannot reach the database. Is Postgres running / is DB_HOST correct?\n\n{e}")
    st.stop()

# ============================================================
# HEADER
# ============================================================
col_logo, col_title, col_out = st.columns([1, 8, 1])
with col_logo:
    st.markdown("<div style='font-size:3.5rem;margin-top:4px'>🐾</div>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1 style='margin:0;color:#c41230'>UMBC Parking Management System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='margin:0;color:#555;font-size:0.9rem'>CMSC 461 · Database Management Systems · Admin Console</p>", unsafe_allow_html=True)
with col_out:
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")

tab_dash, tab_lots, tab_permits, tab_res, tab_enforce, tab_pay, tab_reports, tab_concur = st.tabs([
    "📊 Dashboard", "🅿️ Lots & Sensors", "🎫 Permits", "📅 Reservations",
    "🚨 Enforcement", "💳 Payments", "📋 SQL Reports", "🔒 Concurrency Demo",
])

# ==============================================================
# TAB 1 — DASHBOARD
# ==============================================================
with tab_dash:
    st.markdown('<div class="section-header">System Dashboard</div>', unsafe_allow_html=True)
    st.caption("Live overview of the UMBC Parking Management System.")
    try:
        total_spots   = run_query("SELECT COUNT(*) AS n FROM Spots;")["n"][0]
        avail_spots   = run_query("SELECT COUNT(*) AS n FROM Spots WHERE is_occupied = FALSE;")["n"][0]
        active_perms  = run_query("SELECT COUNT(*) AS n FROM Permits WHERE expiry_date > CURRENT_DATE;")["n"][0]
        open_tickets  = run_query("SELECT COUNT(*) AS n FROM Tickets WHERE status = 'Issued';")["n"][0]
        total_users   = run_query("SELECT COUNT(*) AS n FROM Users;")["n"][0]
        total_revenue = run_query("SELECT COALESCE(SUM(amount),0) AS n FROM Payments;")["n"][0]
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: metric_card("Total Spots", total_spots, "#2c7bb6")
        with c2: metric_card("Available Spots", avail_spots, "#28a745")
        with c3: metric_card("Active Permits", active_perms, "#6f42c1")
        with c4: metric_card("Open Tickets", open_tickets, "#dc3545")
        with c5: metric_card("Registered Users", total_users, "#17a2b8")
        with c6: metric_card("Revenue Collected $", f"{float(total_revenue):,.2f}", "#fd7e14")
    except Exception as e:
        st.error(f"Could not load metrics: {e}")

    st.markdown("---")
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📍 Real-Time Lot Availability")
        st.caption("Sourced from the `CurrentLotAvailability` view.")
        try:
            st.dataframe(run_query("SELECT * FROM CurrentLotAvailability ORDER BY available_spots DESC;"),
                         use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"View error: {e}")
    with col_r:
        st.subheader("🪪 Active Permits by User")
        st.caption("Sourced from the `ActivePermitUserList` view.")
        try:
            st.dataframe(run_query("SELECT * FROM ActivePermitUserList ORDER BY expiry_date;"),
                         use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"View error: {e}")

    st.markdown("---")
    st.subheader("🕑 Recent Sensor Events")
    try:
        st.dataframe(run_query("""
            SELECT se.event_id, se.event_type, se.event_timestamp,
                   sn.sensor_model, l.lot_name, sp.spot_number
            FROM SensorEvents se
            JOIN Sensors sn ON se.sensor_id = sn.sensor_id
            JOIN Spots sp ON sn.spot_id = sp.spot_id
            JOIN Lots l ON sp.lot_id = l.lot_id
            ORDER BY se.event_timestamp DESC LIMIT 10;
        """), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Query error: {e}")

# ==============================================================
# TAB 2 — LOTS & SENSORS  (sensor-occupancy trigger)
# ==============================================================
with tab_lots:
    st.markdown('<div class="section-header">Parking Lots & Sensor Simulation</div>', unsafe_allow_html=True)
    st.caption("Inserting a SensorEvent fires `trg_sensor_occupancy`, which auto-flips `is_occupied` on the linked spot.")
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("All Spots — Current Occupancy")
        try:
            st.dataframe(run_query("""
                SELECT l.lot_name, sp.spot_number, sp.spot_type,
                       CASE WHEN sp.is_occupied THEN '🔴 Occupied' ELSE '🟢 Available' END AS status,
                       sn.sensor_model
                FROM Spots sp
                JOIN Lots l ON sp.lot_id = l.lot_id
                LEFT JOIN Sensors sn ON sp.spot_id = sn.spot_id
                ORDER BY l.lot_name, sp.spot_number;
            """), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Query error: {e}")
    with col_b:
        st.subheader("🔬 Sensor Simulation")
        try:
            lots_df = run_query("SELECT lot_id, lot_name FROM Lots ORDER BY lot_name;")
            lot_map = dict(zip(lots_df["lot_name"], lots_df["lot_id"]))
            sel_lot = st.selectbox("Choose a Lot", list(lot_map.keys()), key="sim_lot")
            event_type = st.radio("Event Type", ["Arrival", "Departure"], horizontal=True)
            occ = (event_type == "Departure")   # departing spots are currently occupied
            sensors_df = run_query("""
                SELECT sn.sensor_id,
                       CONCAT('Spot ', sp.spot_number, ' (', sp.spot_type, ')') AS label
                FROM Sensors sn
                JOIN Spots sp ON sn.spot_id = sp.spot_id
                WHERE sp.lot_id = %s AND sp.is_occupied = %s;
            """, (lot_map[sel_lot], occ))
            if sensors_df.empty:
                st.warning(f"No {'occupied' if occ else 'available'} sensored spots in {sel_lot}.")
            else:
                sensor_map = dict(zip(sensors_df["label"], sensors_df["sensor_id"]))
                sel_lbl = st.selectbox("Select Sensor / Spot", list(sensor_map.keys()))
                if st.button(f"🚗 Fire {event_type} Event", type="primary"):
                    try:
                        run_query("INSERT INTO SensorEvents (event_type, sensor_id) VALUES (%s, %s);",
                                  (event_type, sensor_map[sel_lbl]), commit=True)
                        st.success(f"Trigger flipped occupancy for {sel_lbl}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Error loading sensor form: {e}")

# ==============================================================
# TAB 3 — PERMITS  (issue_permit function)
# ==============================================================
with tab_permits:
    st.markdown('<div class="section-header">Permit Management</div>', unsafe_allow_html=True)
    st.caption("Calls the `issue_permit(v_id, t_id, start_date)` function; it rejects a second active permit per vehicle.")
    col_form, col_view = st.columns([1, 2])
    with col_form:
        st.subheader("Issue a New Permit")
        try:
            vehicles   = run_query("SELECT vehicle_id, license_plate FROM Vehicles ORDER BY license_plate;")
            perm_types = run_query("SELECT type_id, type_name, cost FROM PermitTypes ORDER BY type_name;")
            v_map = dict(zip(vehicles["license_plate"], vehicles["vehicle_id"]))
            t_map = dict(zip(perm_types.apply(lambda r: f"{r['type_name']} (${r['cost']})", axis=1),
                             perm_types["type_id"]))
            sel_plate = st.selectbox("Vehicle License Plate", list(v_map.keys()), key="perm_plate")
            sel_type  = st.selectbox("Permit Type", list(t_map.keys()), key="perm_type")
            start_dt  = st.date_input("Start Date", value=date.today(), key="perm_start")
            if st.button("✅ Issue Permit", type="primary"):
                try:
                    run_query("SELECT issue_permit(%s, %s, %s);",
                              (v_map[sel_plate], t_map[sel_type], start_dt), commit=True)
                    st.success(f"Permit issued for {sel_plate}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Transaction failed: {e}")
        except Exception as e:
            st.error(f"Error loading form: {e}")

        st.markdown("---")
        st.subheader("Delete a Permit")
        try:
            active_p = run_query("""
                SELECT p.permit_id, v.license_plate, pt.type_name, p.expiry_date
                FROM Permits p
                JOIN Vehicles v ON p.vehicle_id = v.vehicle_id
                JOIN PermitTypes pt ON p.type_id = pt.type_id
                WHERE p.expiry_date > CURRENT_DATE ORDER BY p.permit_id;
            """)
            if not active_p.empty:
                p_map = {f"#{r['permit_id']} — {r['license_plate']} ({r['type_name']})": r['permit_id']
                         for _, r in active_p.iterrows()}
                sel_p = st.selectbox("Select Active Permit", list(p_map.keys()), key="del_permit")
                if st.button("🗑️ Delete Permit"):
                    try:
                        run_query("DELETE FROM Permits WHERE permit_id = %s;", (p_map[sel_p],), commit=True)
                        st.success("Permit deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Error: {e}")

    with col_view:
        st.subheader("All Permits")
        fc1, fc2 = st.columns(2)
        with fc1:
            status_filter = st.radio("Show", ["Active", "Expired", "All"], horizontal=True, key="perm_status")
        with fc2:
            search_plate = st.text_input("Search License Plate", placeholder="e.g. ABC", key="perm_search")
        try:
            clauses, params = [], []
            if status_filter == "Active":
                clauses.append("p.expiry_date > CURRENT_DATE")
            elif status_filter == "Expired":
                clauses.append("p.expiry_date <= CURRENT_DATE")
            if search_plate:
                clauses.append("v.license_plate ILIKE %s")     # parameterised — no injection
                params.append(f"%{search_plate}%")
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            df_all_p = run_query(f"""
                SELECT p.permit_id, v.license_plate, u.name AS owner,
                       pt.type_name, pt.cost, p.issue_date, p.expiry_date,
                       CASE WHEN p.expiry_date > CURRENT_DATE THEN 'Active' ELSE 'Expired' END AS status
                FROM Permits p
                JOIN Vehicles v ON p.vehicle_id = v.vehicle_id
                JOIN PermitTypes pt ON p.type_id = pt.type_id
                LEFT JOIN User_Vehicles uv ON v.vehicle_id = uv.vehicle_id
                LEFT JOIN Users u ON uv.user_id = u.user_id
                {where}
                ORDER BY p.expiry_date DESC;
            """, params or None)
            st.dataframe(df_all_p, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Query error: {e}")

# ==============================================================
# TAB 4 — RESERVATIONS  (double-booking trigger)
# ==============================================================
with tab_res:
    st.markdown('<div class="section-header">Reservations</div>', unsafe_allow_html=True)
    st.caption("`trg_prevent_double_booking` rejects overlapping reservations for the same spot at the DB level.")
    col_form, col_view = st.columns([1, 2])
    with col_form:
        st.subheader("Book a Reservation")
        try:
            users_df = run_query("SELECT user_id, name FROM Users ORDER BY name;")
            spots_df = run_query("""
                SELECT sp.spot_id, CONCAT(l.lot_name,' — Spot ',sp.spot_number,' (',sp.spot_type,')') AS label
                FROM Spots sp JOIN Lots l ON sp.lot_id = l.lot_id
                ORDER BY l.lot_name, sp.spot_number;
            """)
            u_map = dict(zip(users_df["name"], users_df["user_id"]))
            s_map = dict(zip(spots_df["label"], spots_df["spot_id"]))
            sel_user = st.selectbox("User", list(u_map.keys()), key="res_user")
            sel_spot = st.selectbox("Spot", list(s_map.keys()), key="res_spot")
            sc, ec = st.columns(2)
            with sc:
                sd = st.date_input("Start Date", value=date.today(), key="res_sd")
                stime = st.time_input("Start Time", value=datetime.now().replace(minute=0, second=0, microsecond=0).time(), key="res_st")
            with ec:
                ed = st.date_input("End Date", value=date.today(), key="res_ed")
                etime = st.time_input("End Time", value=(datetime.now()+timedelta(hours=2)).replace(minute=0, second=0, microsecond=0).time(), key="res_et")
            res_start = datetime.combine(sd, stime)
            res_end   = datetime.combine(ed, etime)
            if st.button("📅 Create Reservation", type="primary"):
                if res_end <= res_start:
                    st.error("End time must be after start time.")
                else:
                    try:
                        run_query("""INSERT INTO Reservations (start_time, end_time, status, user_id, spot_id)
                                     VALUES (%s, %s, 'Confirmed', %s, %s);""",
                                  (res_start, res_end, u_map[sel_user], s_map[sel_spot]), commit=True)
                        st.success(f"Reservation confirmed for {sel_user}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Database rejected reservation:\n\n`{e}`")
        except Exception as e:
            st.error(f"Form error: {e}")

        st.markdown("---")
        st.subheader("Cancel a Reservation")
        try:
            conf_res = run_query("""
                SELECT r.res_id, u.name, l.lot_name, sp.spot_number
                FROM Reservations r
                JOIN Users u ON r.user_id = u.user_id
                JOIN Spots sp ON r.spot_id = sp.spot_id
                JOIN Lots l ON sp.lot_id = l.lot_id
                WHERE r.status = 'Confirmed' ORDER BY r.start_time;
            """)
            if not conf_res.empty:
                c_map = {f"#{r['res_id']} — {r['name']} @ {r['lot_name']} Spot {r['spot_number']}": r['res_id']
                         for _, r in conf_res.iterrows()}
                sel_c = st.selectbox("Select Reservation", list(c_map.keys()), key="cancel_res")
                if st.button("❌ Cancel Reservation"):
                    try:
                        run_query("UPDATE Reservations SET status='Cancelled' WHERE res_id=%s;",
                                  (c_map[sel_c],), commit=True)
                        st.success("Reservation cancelled.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.info("No confirmed reservations.")
        except Exception as e:
            st.error(f"Error: {e}")

    with col_view:
        st.subheader("All Reservations")
        rf = st.selectbox("Filter by Status", ["All", "Confirmed", "Completed", "Cancelled"], key="res_filter")
        try:
            params = None if rf == "All" else (rf,)
            where = "" if rf == "All" else "WHERE r.status = %s"
            st.dataframe(run_query(f"""
                SELECT r.res_id, u.name AS user, l.lot_name, sp.spot_number,
                       sp.spot_type, r.start_time, r.end_time, r.status
                FROM Reservations r
                JOIN Users u ON r.user_id = u.user_id
                JOIN Spots sp ON r.spot_id = sp.spot_id
                JOIN Lots l ON sp.lot_id = l.lot_id
                {where}
                ORDER BY r.start_time DESC;
            """, params), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Query error: {e}")

# ==============================================================
# TAB 5 — ENFORCEMENT  (auto_generate_tickets procedure)
# ==============================================================
with tab_enforce:
    st.markdown('<div class="section-header">Enforcement & Auto-Ticketing</div>', unsafe_allow_html=True)
    st.caption("`CALL auto_generate_tickets()` fines occupied spots whose current reservation holder has no valid permit.")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("🤖 Auto-Ticketing Protocol")
        if st.button("▶️ Run Auto-Ticketing", type="primary"):
            try:
                run_query("CALL auto_generate_tickets();", commit=True)
                st.success("Auto-ticketing executed.")
                st.rerun()
            except Exception as e:
                st.error(f"Procedure failed: {e}")

        st.markdown("---")
        st.subheader("✍️ Issue Manual Ticket")
        try:
            veh_df  = run_query("SELECT vehicle_id, license_plate FROM Vehicles ORDER BY license_plate;")
            spot_df = run_query("""
                SELECT sp.spot_id, CONCAT(l.lot_name,' — Spot ',sp.spot_number) AS label
                FROM Spots sp JOIN Lots l ON sp.lot_id = l.lot_id ORDER BY l.lot_name, sp.spot_number;
            """)
            mv = dict(zip(veh_df["license_plate"], veh_df["vehicle_id"]))
            ms = dict(zip(spot_df["label"], spot_df["spot_id"]))
            t_plate = st.selectbox("Vehicle", list(mv.keys()), key="tkt_veh")
            t_spot  = st.selectbox("Spot", list(ms.keys()), key="tkt_spot")
            t_fine  = st.number_input("Fine Amount ($)", min_value=10.0, max_value=500.0, value=50.0, step=5.0)
            if st.button("🎟️ Issue Ticket"):
                try:
                    run_query("INSERT INTO Tickets (fine_amount, status, vehicle_id, spot_id) VALUES (%s,'Issued',%s,%s);",
                              (t_fine, mv[t_plate], ms[t_spot]), commit=True)
                    st.success(f"Ticket issued for {t_plate} — ${t_fine:.2f}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Form error: {e}")

    with col2:
        st.subheader("📄 Citation Database")
        tf = st.selectbox("Filter by Status", ["All", "Issued", "Paid", "Appealed", "Voided"], key="tkt_filter")
        try:
            params = None if tf == "All" else (tf,)
            where = "" if tf == "All" else "WHERE t.status = %s"
            st.dataframe(run_query(f"""
                SELECT t.ticket_id, v.license_plate, t.fine_amount, t.status,
                       sp.spot_number, l.lot_name,
                       TO_CHAR(t.issue_timestamp,'YYYY-MM-DD HH24:MI') AS issued_at
                FROM Tickets t
                JOIN Vehicles v ON t.vehicle_id = v.vehicle_id
                JOIN Spots sp ON t.spot_id = sp.spot_id
                JOIN Lots l ON sp.lot_id = l.lot_id
                {where}
                ORDER BY t.issue_timestamp DESC;
            """, params), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Query error: {e}")

        st.markdown("---")
        st.subheader("🔄 Update Ticket Status")
        try:
            open_t = run_query("""
                SELECT t.ticket_id, v.license_plate, t.fine_amount, t.status
                FROM Tickets t JOIN Vehicles v ON t.vehicle_id = v.vehicle_id
                WHERE t.status != 'Paid' ORDER BY t.ticket_id;
            """)
            if not open_t.empty:
                tm = {f"#{r['ticket_id']} — {r['license_plate']} (${r['fine_amount']}) [{r['status']}]": r['ticket_id']
                      for _, r in open_t.iterrows()}
                sel_t = st.selectbox("Select Ticket", list(tm.keys()), key="upd_tkt")
                ns = st.radio("New Status", ["Appealed", "Paid", "Issued", "Voided"], horizontal=True, key="tkt_new_stat")
                if st.button("💾 Update Status"):
                    try:
                        run_query("UPDATE Tickets SET status=%s WHERE ticket_id=%s;", (ns, tm[sel_t]), commit=True)
                        st.success(f"Ticket #{tm[sel_t]} updated to {ns}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        except Exception as e:
            st.error(f"Error: {e}")

# ==============================================================
# TAB 6 — PAYMENTS
# ==============================================================
with tab_pay:
    st.markdown('<div class="section-header">Payment Processing</div>', unsafe_allow_html=True)
    st.caption("Record payments against tickets; a ticket auto-marks Paid once installments cover the fine.")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("💳 Record a Payment")
        try:
            issued_t = run_query("""
                SELECT t.ticket_id, v.license_plate, t.fine_amount,
                       COALESCE(SUM(pay.amount),0) AS paid_so_far
                FROM Tickets t
                JOIN Vehicles v ON t.vehicle_id = v.vehicle_id
                LEFT JOIN Payments pay ON t.ticket_id = pay.ticket_id
                WHERE t.status IN ('Issued','Appealed')
                GROUP BY t.ticket_id, v.license_plate, t.fine_amount ORDER BY t.ticket_id;
            """)
            if issued_t.empty:
                st.success("No outstanding tickets to pay. 🎉")
            else:
                pay_map = {f"#{r['ticket_id']} — {r['license_plate']} | Fine ${r['fine_amount']} | Paid ${r['paid_so_far']}": r['ticket_id']
                           for _, r in issued_t.iterrows()}
                sel = st.selectbox("Select Ticket", list(pay_map.keys()), key="pay_tkt")
                tid = pay_map[sel]
                row = issued_t[issued_t["ticket_id"] == tid].iloc[0]
                remaining = float(row["fine_amount"]) - float(row["paid_so_far"])
                amt = st.number_input("Payment Amount ($)", min_value=0.01,
                                      max_value=max(0.01, remaining),
                                      value=max(0.01, remaining), step=1.0, key="pay_amt")
                st.caption(f"Remaining balance: ${remaining:.2f}")
                if st.button("💰 Submit Payment", type="primary"):
                    try:
                        run_query("INSERT INTO Payments (amount, ticket_id) VALUES (%s, %s);",
                                  (amt, tid), commit=True)
                        if float(row["paid_so_far"]) + amt >= float(row["fine_amount"]):
                            run_query("UPDATE Tickets SET status='Paid' WHERE ticket_id=%s;", (tid,), commit=True)
                            st.success(f"Full payment recorded — ticket #{tid} marked Paid.")
                        else:
                            st.success(f"Partial payment ${amt:.2f} recorded.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Payment failed: {e}")
        except Exception as e:
            st.error(f"Form error: {e}")

    with col2:
        st.subheader("📊 Payment History")
        try:
            st.dataframe(run_query("""
                SELECT pay.payment_id, v.license_plate, t.ticket_id,
                       t.fine_amount AS original_fine, pay.amount AS paid,
                       TO_CHAR(pay.payment_timestamp,'YYYY-MM-DD HH24:MI') AS paid_at, t.status
                FROM Payments pay
                JOIN Tickets t ON pay.ticket_id = t.ticket_id
                JOIN Vehicles v ON t.vehicle_id = v.vehicle_id
                ORDER BY pay.payment_timestamp DESC;
            """), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Query error: {e}")

        st.markdown("---")
        st.subheader("💰 Permit Revenue by Type")
        st.caption("Permits sold × type cost (the corrected revenue query).")
        try:
            st.dataframe(run_query("""
                SELECT pt.type_name, COUNT(pr.permit_id) AS permits_sold, SUM(pt.cost) AS permit_revenue
                FROM PermitTypes pt JOIN Permits pr ON pt.type_id = pr.type_id
                GROUP BY pt.type_name ORDER BY permit_revenue DESC;
            """), use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"No revenue data yet: {e}")

# ==============================================================
# TAB 7 — SQL REPORTS
# ==============================================================
with tab_reports:
    st.markdown('<div class="section-header">SQL Query Reports</div>', unsafe_allow_html=True)
    st.caption("The course-level queries from `queryAll.sql`, runnable live.")
    QUERIES = {
        "1. User Roles (Simple Join)":
            "SELECT u.name, r.role_name FROM Users u JOIN Roles r ON u.role_id=r.role_id ORDER BY u.name;",
        "2. Vehicles per User (Aggregation)":
            "SELECT u.name, COUNT(uv.vehicle_id) AS vehicle_count FROM Users u LEFT JOIN User_Vehicles uv ON u.user_id=uv.user_id GROUP BY u.name ORDER BY vehicle_count DESC;",
        "3. Active Student Permits (Filter + Join)":
            "SELECT v.license_plate, p.expiry_date FROM Permits p JOIN Vehicles v ON p.vehicle_id=v.vehicle_id JOIN User_Vehicles uv ON v.vehicle_id=uv.vehicle_id JOIN Users u ON uv.user_id=u.user_id JOIN Roles r ON u.role_id=r.role_id WHERE r.role_name='Student' AND p.expiry_date>CURRENT_DATE;",
        "4. Lots with No Occupied Spots (Subquery)":
            "SELECT lot_name FROM Lots WHERE lot_id NOT IN (SELECT lot_id FROM Spots WHERE is_occupied=TRUE);",
        "5. Users with Both Permit & Ticket (Set Op)":
            "SELECT DISTINCT u.user_id,u.name FROM Users u JOIN User_Vehicles uv ON u.user_id=uv.user_id JOIN Permits p ON uv.vehicle_id=p.vehicle_id INTERSECT SELECT DISTINCT u.user_id,u.name FROM Users u JOIN User_Vehicles uv ON u.user_id=uv.user_id JOIN Tickets t ON uv.vehicle_id=t.vehicle_id;",
        "6. Sensor History — Lot 4 (Complex Join)":
            "SELECT l.lot_name,s.spot_number,se.event_type,se.event_timestamp FROM Lots l JOIN Spots s ON l.lot_id=s.lot_id JOIN Sensors sn ON s.spot_id=sn.spot_id JOIN SensorEvents se ON sn.sensor_id=se.sensor_id WHERE l.lot_name='Lot 4' ORDER BY se.event_timestamp DESC;",
        "7. Lots with >1 Available Spot (GROUP BY/HAVING)":
            "SELECT l.lot_name,COUNT(s.spot_id) AS available_count FROM Lots l JOIN Spots s ON l.lot_id=s.lot_id WHERE s.is_occupied=FALSE GROUP BY l.lot_name HAVING COUNT(s.spot_id)>1;",
        "8. ⚡ Detailed Ticket Report (Expensive)":
            "SELECT u.name,v.license_plate,t.fine_amount,l.lot_name,t.issue_timestamp FROM Users u JOIN User_Vehicles uv ON u.user_id=uv.user_id JOIN Vehicles v ON uv.vehicle_id=v.vehicle_id JOIN Tickets t ON v.vehicle_id=t.vehicle_id JOIN Spots s ON t.spot_id=s.spot_id JOIN Lots l ON s.lot_id=l.lot_id WHERE t.status='Issued';",
        "9. ⚡ Reservation Overlap Check (Expensive)":
            "SELECT r1.res_id AS res_a,r2.res_id AS res_b,r1.spot_id FROM Reservations r1 JOIN Reservations r2 ON r1.spot_id=r2.spot_id WHERE r1.res_id<r2.res_id AND r1.status='Confirmed' AND r2.status='Confirmed' AND r1.start_time<r2.end_time AND r1.end_time>r2.start_time;",
        "10. ⚡ Permit Revenue per Type (Expensive, corrected)":
            "SELECT pt.type_name,COUNT(pr.permit_id) AS permits_sold,SUM(pt.cost) AS permit_revenue FROM PermitTypes pt JOIN Permits pr ON pt.type_id=pr.type_id GROUP BY pt.type_name ORDER BY permit_revenue DESC;",
    }
    sel_q = st.selectbox("Select a Query", list(QUERIES.keys()), key="report_q")
    sql_text = QUERIES[sel_q]
    st.markdown(f'<div class="code-block">{sql_text}</div>', unsafe_allow_html=True)
    if st.button("▶️ Execute Query", type="primary", key="run_q"):
        try:
            df = run_readonly(sql_text)
            if df is not None and not df.empty:
                st.success(f"Returned {len(df)} row(s).")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Query executed — no rows returned.")
        except Exception as e:
            st.error(f"Error: {e}")
        # Show the planner's view too.
        try:
            plan = run_readonly("EXPLAIN ANALYZE " + sql_text)
            st.caption("EXPLAIN ANALYZE:")
            st.markdown(f'<div class="code-block">{"<br>".join(plan.iloc[:,0].tolist())}</div>', unsafe_allow_html=True)
        except Exception:
            pass

    st.markdown("---")
    st.subheader("🔎 Custom SQL (read-only)")
    st.caption("SELECT-only, executed inside a READ ONLY transaction that is always rolled back.")
    custom = st.text_area("Enter a SELECT query", height=100, placeholder="SELECT * FROM Lots;", key="custom_sql")
    if st.button("▶️ Run Custom SQL"):
        stmt = custom.strip().rstrip(";")
        if not stmt:
            st.warning("Enter a query first.")
        elif not stmt.upper().startswith(("SELECT", "WITH", "EXPLAIN")):
            st.warning("Only SELECT / WITH / EXPLAIN statements are allowed here.")
        elif ";" in stmt:
            st.warning("Single statement only — remove the semicolon-separated statements.")
        else:
            try:
                df = run_readonly(stmt)
                if df is not None:
                    st.success(f"Returned {len(df)} row(s).")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No results.")
            except Exception as e:
                st.error(f"SQL error: {e}")

# ==============================================================
# TAB 8 — CONCURRENCY DEMO
# ==============================================================
with tab_concur:
    st.markdown('<div class="section-header">Concurrency Control Demo</div>', unsafe_allow_html=True)
    st.caption("Two users try to book the same spot for overlapping times. Only one may succeed.")
    st.info("For a true two-session (blocking) demo, run `sql/transaction.sql` in two pgAdmin tabs. "
            "This panel runs the sequence programmatically to show the outcome.")
    try:
        demo = run_query("""
            SELECT r.spot_id, l.lot_name, sp.spot_number
            FROM Reservations r JOIN Spots sp ON r.spot_id=sp.spot_id JOIN Lots l ON sp.lot_id=l.lot_id
            WHERE r.status='Confirmed' ORDER BY r.start_time LIMIT 1;
        """)
        spot_id = int(demo.iloc[0]["spot_id"]) if not demo.empty else 1
        lot     = demo.iloc[0]["lot_name"] if not demo.empty else "Lot 4"
        spot_no = demo.iloc[0]["spot_number"] if not demo.empty else 12
    except Exception:
        spot_id, lot, spot_no = 1, "Lot 4", 12

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🟢 Session A (first booker)")
        st.markdown(f"Target **{lot} — Spot {spot_no}**, `2026-09-01 09:00 → 11:00`, user 1")
        if st.button("▶️ Run Session A (should SUCCEED)", key="sa"):
            try:
                run_query("INSERT INTO Reservations (start_time,end_time,status,user_id,spot_id) VALUES (%s,%s,'Confirmed',1,%s);",
                          ("2026-09-01 09:00:00", "2026-09-01 11:00:00", spot_id), commit=True)
                st.success("Session A committed.")
            except Exception as e:
                st.warning(f"Session A blocked by existing data: {e}")
    with c2:
        st.subheader("🔴 Session B (overlapping)")
        st.markdown(f"Same spot, `2026-09-01 10:00 → 12:00` (overlaps!), user 2")
        if st.button("▶️ Run Session B (should FAIL)", key="sb", type="primary"):
            try:
                run_query("INSERT INTO Reservations (start_time,end_time,status,user_id,spot_id) VALUES (%s,%s,'Confirmed',2,%s);",
                          ("2026-09-01 10:00:00", "2026-09-01 12:00:00", spot_id), commit=True)
                st.warning("Session B succeeded — run Session A first to create the conflict.")
            except Exception as e:
                st.error(f"❌ Session B rejected by trigger:\n\n`{e}`")
                st.success("Concurrency control working as designed.")

    st.markdown("---")
    st.subheader("📊 Current Reservation State")
    try:
        st.dataframe(run_query("""
            SELECT r.res_id, u.name, l.lot_name, sp.spot_number, r.start_time, r.end_time, r.status
            FROM Reservations r JOIN Users u ON r.user_id=u.user_id
            JOIN Spots sp ON r.spot_id=sp.spot_id JOIN Lots l ON sp.lot_id=l.lot_id
            ORDER BY r.start_time DESC LIMIT 20;
        """), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Query error: {e}")

st.markdown("---")
st.markdown("<p style='text-align:center;color:#aaa;font-size:0.8rem'>UMBC Parking Management System · CMSC 461 · Streamlit + PostgreSQL</p>", unsafe_allow_html=True)
