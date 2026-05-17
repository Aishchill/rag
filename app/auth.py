import bcrypt
from functools import wraps
from flask import session, redirect, url_for, flash


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


def login_user(user):
    session["user_id"] = user["id"]
    session["username"] = user["username"]


def logout_user():
    session.clear()
