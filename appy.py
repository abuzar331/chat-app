import os
from flask import Flask, render_template, request, session, redirect, jsonify
from flask_migrate import Migrate
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, User, Message
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Photo upload folder
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/chat")
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing = User.query.filter(
            (User.username == request.form["username"]) |
            (User.email == request.form["email"])
        ).first()
        if existing:
            return "Username ya email already registered hai"
        user = User(
            username=request.form["username"],
            email=request.form["email"],
            password_hash=generate_password_hash(request.form["password"])
        )
        db.session.add(user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect("/chat")
        return "Invalid login"
    return render_template("login.html")

@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect("/login")
    users = User.query.filter(User.id != session["user_id"]).all()
    return render_template(
        "chat.html",
        username=session["username"],
        users=users,
        session_user_id=session["user_id"]
    )

@app.route("/messages/<int:user_id>")
@login_required
def messages(user_id):
    if "user_id" not in session:
        return jsonify({"messages": []})
    me = session["user_id"]
    if me == user_id:
        return jsonify({"messages": []})

    msgs = Message.query.filter(
        (
            (Message.sender_id == me) & (Message.receiver_id == user_id)
        ) | (
            (Message.sender_id == user_id) & (Message.receiver_id == me)
        )
    ).filter(
        Message.is_deleted == False
    ).order_by(Message.timestamp).all()

    return jsonify({
        "messages": [
            {
                "id": m.id,
                "from": m.sender_id,
                "text": m.content,
                "image": m.image_path
            }
            for m in msgs
        ]
    })


# ---- PHOTO UPLOAD ----

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    if "photo" not in request.files:
        return jsonify({"error": "no file"}), 400
    file = request.files["photo"]
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Unique naam — timestamp + original name
        unique_name = f"{session['user_id']}_{int(datetime.now().timestamp())}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(filepath)
        image_url = f"/static/uploads/{unique_name}"

        receiver_id = int(request.form.get("receiver_id"))
        msg = Message(
            sender_id=session["user_id"],
            receiver_id=receiver_id,
            content=None,
            image_path=image_url
        )
        db.session.add(msg)
        db.session.commit()

        # Dono sides pe photo bhejo socket se
        socketio.emit("private_message", {
            "from": session["user_id"],
            "message": None,
            "image": image_url,
            "msg_id": msg.id
        }, room=str(receiver_id))

        return jsonify({"image": image_url, "msg_id": msg.id})
    return jsonify({"error": "invalid file"}), 400

# ---- DELETE MESSAGE (BOTH SIDES) ----

@app.route("/delete/message/<int:msg_id>", methods=["DELETE"])
@login_required
def delete_message(msg_id):
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({"error": "not found"}), 404
    # Sirf sender hi delete kar sakta hai
    if msg.sender_id != session["user_id"]:
        return jsonify({"error": "forbidden"}), 403

    msg.is_deleted = True
    db.session.commit()

    # Receiver ko bhi socket se notify karo
    socketio.emit("message_deleted", {
        "msg_id": msg_id
    }, room=str(msg.receiver_id))

    return jsonify({"success": True})





@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---- SOCKET EVENTS ----
@socketio.on("connect")
def on_connect():
    if "user_id" in session:
        join_room(str(session["user_id"]))
        print(f" User {session['user_id']} connected and joined room")

@socketio.on("private_message")
def on_private_message(data):
    if "user_id" not in session:
        return

    sender_id = session["user_id"]
    receiver_id = int(data["to"])
    text = data["message"]

    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=text
    )
    db.session.add(msg)
    db.session.commit()
    print(f"💬 Message from {sender_id} to {receiver_id}: {text}")

    emit("private_message", {
        "from": sender_id,
        "message": text
    }, room=str(receiver_id))

@socketio.on("typing")
def on_typing(data):
    if "user_id" not in session:
        return
    print(f"Typing from {session['user_id']} to {data.get('to')}")
    emit("typing", {
        "from": session["user_id"]
    }, room=str(data["to"]))


@socketio.on("stop_typing")
def on_stop_typing(data):
    if "user_id" not in session:
        return
    print(f" Stop typing from {session['user_id']} to {data.get('to')}")
    emit("stop_typing", {
        "from": session["user_id"]
    }, room=str(data["to"]))

# ---- DELETE FULL CHAT (BOTH SIDES) ----
@app.route("/delete/chat/<int:other_user_id>", methods=["DELETE"])
@login_required
def delete_chat(other_user_id):
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    
    me = session["user_id"]
    
    # Dono users ke beech saare messages delete karo
    Message.query.filter(
        (
            (Message.sender_id == me) & (Message.receiver_id == other_user_id)
        ) | (
            (Message.sender_id == other_user_id) & (Message.receiver_id == me)
        )
    ).update({"is_deleted": True}, synchronize_session=False)
    
    db.session.commit()
    
    # Dusre user ko bhi notify karo socket se
    socketio.emit("chat_cleared", {
        "by_user": me
    }, room=str(other_user_id))
    
    return jsonify({"success": True})



with app.app_context():
    db.create_all()

if __name__ == "__main__":
    socketio.run(app, debug=True)
      