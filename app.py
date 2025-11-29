from flask import Flask, render_template, request, redirect, url_for, session, flash
from mysql.connector import connection
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ifonias_chave_super_secreta"

# ===========================
# CONFIGURAÇÃO DO BANCO
# ===========================
def conectar():
    return connection.MySQLConnection(
        host="127.0.0.1",
        user="root",
        password="sy68p014",
        database="ifonias_db"
    )

# ===========================
# CONFIGURAÇÕES DE UPLOAD
# ===========================
UPLOAD_FOLDER = "static/audios"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"mp3", "wav", "mpeg"}

def arquivo_permitido(nome):
    return "." in nome and nome.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===========================
# LOGIN
# ===========================
@app.route("/", methods=["GET", "POST"])
def login():
    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
    total = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    if total == 0:
        return render_template("login.html", sem_usuarios=True)

    if request.method == "POST":
        usuario_login = request.form.get("usuario")
        senha = request.form.get("senha")

        db = conectar()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s AND senha=%s",
                       (usuario_login, senha))
        usuario = cursor.fetchone()
        cursor.close()
        db.close()

        if usuario:
            session["usuario_id"] = usuario["id_usuario"]
            session["nome"] = usuario["nome"]
            return redirect(url_for("timeline"))
        else:
            return render_template("login.html", erro_login=True)

    return render_template("login.html")

# ===========================
# LOGOUT
# ===========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ===========================
# TIMELINE
# ===========================
@app.route("/timeline")
def timeline():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.*, u.nome
        FROM audios a
        JOIN usuarios u ON a.usuario_id = u.id_usuario
        ORDER BY a.criado_em DESC
    """)
    audios = cursor.fetchall()

    cursor.execute("SELECT audio_id FROM curtidas WHERE usuario_id=%s",
                   (session["usuario_id"],))
    curtidos = [c["audio_id"] for c in cursor.fetchall()]

    cursor.close()
    db.close()

    return render_template("timeline.html", audios=audios, curtidos=curtidos)

# ===========================
# PERFIL
# ===========================
@app.route("/perfil")
def perfil():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios WHERE id_usuario=%s",
                   (session["usuario_id"],))
    usuario = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM audios
        WHERE usuario_id=%s
        ORDER BY criado_em DESC
    """, (session["usuario_id"],))
    audios = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("perfil.html", usuario=usuario, audios=audios)

# ===========================
# UPLOAD
# ===========================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        titulo = request.form.get("titulo")
        legenda = request.form.get("legenda")
        arquivo = request.files.get("audio_file")

        if arquivo and arquivo_permitido(arquivo.filename):
            nome_limpo = secure_filename(arquivo.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_limpo)
            arquivo.save(caminho)

            db = conectar()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO audios (usuario_id, titulo, legenda, arquivo_audio)
                VALUES (%s, %s, %s, %s)
            """, (session["usuario_id"], titulo, legenda, nome_limpo))
            db.commit()
            cursor.close()
            db.close()

            return redirect(url_for("timeline"))

    return render_template("upload.html")

# ===========================
# CURTIR / DESCURTIR
# ===========================
@app.route("/curtir/<int:audio_id>")
def curtir(audio_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
                   (session["usuario_id"], audio_id))
    existe = cursor.fetchone()

    if existe:
        cursor.execute("DELETE FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
                       (session["usuario_id"], audio_id))
    else:
        cursor.execute("INSERT INTO curtidas (usuario_id, audio_id) VALUES (%s, %s)",
                       (session["usuario_id"], audio_id))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("timeline"))

# ===========================
# COMENTÁRIO
# ===========================
@app.route("/comentar/<int:audio_id>", methods=["POST"])
def comentar(audio_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    texto = request.form.get("comentario")

    db = conectar()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO comentarios (usuario_id, audio_id, texto)
        VALUES (%s, %s, %s)
    """, (session["usuario_id"], audio_id, texto))

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("timeline"))

# ===========================
# CADASTRO
# ===========================
@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        nome = request.form.get("nome")
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        curso = request.form.get("curso")
        campus = request.form.get("campus")

        db = conectar()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO usuarios (nome, usuario, senha, curso, campus)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, usuario, senha, curso, campus))

        db.commit()
        cursor.close()
        db.close()

        return render_template("login.html", cadastro_ok=True)

    return render_template("cadastro.html")

# ===========================
# RUN
# ===========================
if __name__ == "__main__":
    app.run(debug=True)
