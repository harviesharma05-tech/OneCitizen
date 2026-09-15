"""Flask server: login, role-scoped dashboard, and the JSON API behind it."""
import os

from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for)

from . import pipeline, rbac
from .schemes import match_scheme

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__,
            template_folder=os.path.join(BASE, "web", "templates"),
            static_folder=os.path.join(BASE, "web", "static"))
app.secret_key = "ubdp-prototype-demo-key"

AUDIT_LOG = []


def current_user():
    u = session.get("user")
    return u if u else None


def require_login():
    user = current_user()
    if not user:
        return None
    return user


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = rbac.authenticate(request.form.get("username", ""),
                                 request.form.get("password", ""))
        if user:
            session["user"] = user
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Those credentials didn't match. Try again.",
                               users=rbac.USERS)
    return render_template("login.html", users=rbac.USERS)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    user = require_login()
    if not user:
        return redirect(url_for("login"))
    s = pipeline.state()
    scope = rbac.visible_citizens(s["golden"], user)
    return render_template("dashboard.html", user=user, impact=s["impact"],
                           accuracy=s["accuracy"], scoped_count=len(scope))


# ------------------------------------------------------------------- API
@app.route("/api/citizens")
def api_citizens():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401

    s = pipeline.state()
    scope = rbac.visible_citizens(s["golden"], user)

    q = (request.args.get("q") or "").lower().strip()
    band = request.args.get("risk", "")
    if q:
        scope = [g for g in scope if q in (g["name_raw"] or "").lower()
                 or q in g["citizen_id"].lower()
                 or q in (g["aadhaar"] or "")]
    if band and user["perms"]["can_see_fraud"]:
        scope = [g for g in scope if g["risk"]["band"] == band]

    scope = sorted(scope, key=lambda g: -(g.get("risk", {}).get("score", 0)))
    AUDIT_LOG.append(rbac.audit_line(user, "list_citizens", f"{len(scope)} records"))
    return jsonify([rbac.project(g, user) for g in scope[:120]])


@app.route("/api/citizen/<cid>")
def api_citizen(cid):
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    s = pipeline.state()
    scope = rbac.visible_citizens(s["golden"], user)
    match = next((g for g in scope if g["citizen_id"] == cid), None)
    if not match:
        return jsonify({"error": "not found or outside your department scope"}), 404
    AUDIT_LOG.append(rbac.audit_line(user, "view_citizen", cid))

    payload = rbac.project(match, user)
    payload["all_scheme_checks"] = [match_scheme(match, sc) for sc in s["schemes"]]
    return jsonify(payload)


@app.route("/api/review-queue")
def api_review():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    if not user["perms"]["can_review_merges"]:
        return jsonify({"error": "your role cannot review merges"}), 403
    s = pipeline.state()
    return jsonify([{
        "score": r["score"], "reasons": r["reasons"],
        "left": {k: r["left"][k] for k in ("dept_record_id", "source_dept", "name_raw",
                                           "dob", "address_raw", "aadhaar")},
        "right": {k: r["right"][k] for k in ("dept_record_id", "source_dept", "name_raw",
                                             "dob", "address_raw", "aadhaar")},
    } for r in sorted(s["review_queue"], key=lambda x: -x["score"])[:40]])


@app.route("/api/fraud")
def api_fraud():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    if not user["perms"]["can_see_fraud"]:
        return jsonify({"error": "your role cannot view fraud signals"}), 403
    s = pipeline.state()
    return jsonify({"duplicate_applications": s["duplicate_apps"][:40],
                    "rings": s["rings"][:40]})


@app.route("/api/schemes")
def api_schemes():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    s = pipeline.state()
    return jsonify({"catalogue": s["schemes"], "overlapping": s["dup_schemes"]})


@app.route("/api/audit")
def api_audit():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    return jsonify(AUDIT_LOG[-60:][::-1])


def main():
    print("Warming the pipeline...")
    pipeline.run(verbose=True)
    print("Dashboard ready at http://127.0.0.1:5000  (any demo user, password: demo)")
    app.run(debug=False, port=5000)


if __name__ == "__main__":
    main()
