from flask import Flask, render_template, request, redirect, url_for, session, flash
from mysql.connector import connection
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "ifonias_music"

# Conexão com o banco
def conectar():
    return connection.MySQLConnection(
        host="127.0.0.1",
        user="root",
        password="sy68p014",
        database="ifonias_db"
    )

# Configurações de upload
UPLOAD_FOLDER = "static/audios"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"mp3", "wav", "mpeg"}

AVATAR_FOLDER = "static/avatars"
app.config["AVATAR_FOLDER"] = AVATAR_FOLDER

# Cria pasta para avatares caso não exista
if not os.path.exists(AVATAR_FOLDER):
    os.makedirs(AVATAR_FOLDER)

# Verifica se o arquivo enviado é permitido
def arquivo_permitido(nome):
    return "." in nome and nome.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Página de login
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
        cursor.execute(
            "SELECT * FROM usuarios WHERE usuario=%s AND senha=%s",
            (usuario_login, senha)
        )
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

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Página principal com os áudios
@app.route("/timeline")
def timeline():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.*, u.nome, u.usuario, u.curso, u.campus,
            (SELECT COUNT(*) FROM curtidas c WHERE c.audio_id = a.id_audio) AS total_curtidas
        FROM audios a
        JOIN usuarios u ON a.usuario_id = u.id_usuario
        ORDER BY a.criado_em DESC
    """)
    audios = cursor.fetchall()

    cursor.execute("SELECT audio_id FROM curtidas WHERE usuario_id=%s",
                   (session["usuario_id"],))
    curtidos = [c["audio_id"] for c in cursor.fetchall()]

    cursor.execute("""
        SELECT c.*, u.nome AS nome_usuario
        FROM comentarios c
        JOIN usuarios u ON c.usuario_id = u.id_usuario
        ORDER BY c.criado_em ASC
    """)
    comentarios_brutos = cursor.fetchall()
    comentarios = {}
    for c in comentarios_brutos:
        comentarios.setdefault(c["audio_id"], []).append(c)

    cursor.execute("""
        SELECT c.audio_id, u.nome
        FROM curtidas c
        JOIN usuarios u ON u.id_usuario = c.usuario_id
    """)
    curtidores_brutos = cursor.fetchall()
    curtidores = {}
    for c in curtidores_brutos:
        curtidores.setdefault(c["audio_id"], []).append(c["nome"])

    cursor.close()
    db.close()

    return render_template(
        "timeline.html",
        audios=audios,
        curtidos=curtidos,
        comentarios=comentarios,
        curtidores=curtidores
    )

# Perfil do usuário logado
@app.route("/perfil")
def perfil():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios WHERE id_usuario=%s",
                   (session["usuario_id"],))
    usuario = cursor.fetchone()

    cursor.execute("SELECT * FROM audios WHERE usuario_id=%s ORDER BY criado_em DESC",
                   (session["usuario_id"],))
    audios = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("perfil.html", usuario=usuario, audios=audios)

# Deletar áudio
@app.route("/deletar_audio/<int:id_audio>")
def deletar_audio(id_audio):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM audios WHERE id_audio=%s AND usuario_id=%s",
        (id_audio, session["usuario_id"])
    )
    audio = cursor.fetchone()

    if not audio:
        cursor.close()
        db.close()
        return redirect(url_for("perfil"))

    cursor.execute("DELETE FROM curtidas WHERE audio_id=%s", (id_audio,))
    cursor.execute("DELETE FROM comentarios WHERE audio_id=%s", (id_audio,))

    caminho = os.path.join(app.config["UPLOAD_FOLDER"], audio["arquivo_audio"])
    if os.path.exists(caminho):
        os.remove(caminho)

    cursor.execute("DELETE FROM audios WHERE id_audio=%s", (id_audio,))
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("perfil"))

# Editar perfil do usuário
@app.route("/editar_perfil", methods=["GET", "POST"])
def editar_perfil():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE id_usuario=%s", (session["usuario_id"],))
    usuario = cursor.fetchone()

    if request.method == "POST":
        nome = request.form.get("nome")
        usuario_login = request.form.get("usuario")
        curso = request.form.get("curso")
        campus = request.form.get("campus")
        avatar_file = request.files.get("avatar")

        avatar_nome = usuario["avatar"]
        if avatar_file and avatar_file.filename != "":
            nome_seguro = secure_filename(avatar_file.filename)
            avatar_caminho = os.path.join(app.config["AVATAR_FOLDER"], nome_seguro)

            if usuario["avatar"]:
                caminho_antigo = os.path.join(app.config["AVATAR_FOLDER"], usuario["avatar"])
                if os.path.exists(caminho_antigo):
                    os.remove(caminho_antigo)

            avatar_file.save(avatar_caminho)
            avatar_nome = nome_seguro

        cursor.execute("""
            UPDATE usuarios
            SET nome=%s, usuario=%s, curso=%s, campus=%s, avatar=%s
            WHERE id_usuario=%s
        """, (nome, usuario_login, curso, campus, avatar_nome, session["usuario_id"]))

        db.commit()
        cursor.close()
        db.close()

        session["nome"] = nome
        return redirect(url_for("perfil"))

    cursor.close()
    db.close()
    return render_template("editar_perfil.html", usuario=usuario)

# Upload de áudio
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        titulo = request.form.get("titulo")
        legenda = request.form.get("legenda")
        tipo_audio = request.form.get("tipo_audio")
        arquivo = request.files.get("audio_file")

        if arquivo and arquivo_permitido(arquivo.filename):
            nome_limpo = secure_filename(arquivo.filename)
            caminho = os.path.join(app.config["UPLOAD_FOLDER"], nome_limpo)
            arquivo.save(caminho)

            db = conectar()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO audios (usuario_id, titulo, legenda, arquivo_audio, tipo_audio)
                VALUES (%s, %s, %s, %s, %s)
            """, (session["usuario_id"], titulo, legenda, nome_limpo, tipo_audio))
            db.commit()
            cursor.close()
            db.close()

            return redirect(url_for("timeline"))

    return render_template("upload.html")

# Curtir ou descurtir
@app.route("/curtir/<int:audio_id>")
def curtir(audio_id):
    if "usuario_id" not in session:
        return {"erro": "Não logado"}, 401

    user_id = session["usuario_id"]
    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
        (user_id, audio_id)
    )
    existe = cursor.fetchone()

    if existe:
        cursor.execute("DELETE FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
                       (user_id, audio_id))
        status = "descurtido"
    else:
        cursor.execute("INSERT INTO curtidas (usuario_id, audio_id) VALUES (%s, %s)",
                       (user_id, audio_id))
        status = "curtido"

    db.commit()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM curtidas WHERE audio_id=%s",
        (audio_id,)
    )
    total = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return {"status": status, "total": total}, 200

# Adicionar comentário
@app.route("/comentar/<int:audio_id>", methods=["POST"])
def comentar(audio_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    texto = request.form.get("comentario")
    if not texto.strip():
        return redirect(url_for("timeline"))

    db = conectar()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO comentarios (usuario_id, audio_id, texto) VALUES (%s, %s, %s)",
        (session["usuario_id"], audio_id, texto)
    )
    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for("timeline"))

# Cadastro de usuário
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

# Perfil público
@app.route("/perfil/<int:user_id>")
def perfil_publico(user_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id_usuario, nome, usuario, curso, campus, avatar FROM usuarios WHERE id_usuario=%s",
        (user_id,)
    )
    usuario = cursor.fetchone()

    if not usuario:
        cursor.close()
        db.close()
        return redirect(url_for("timeline"))

    cursor.execute(
        "SELECT * FROM audios WHERE usuario_id=%s ORDER BY criado_em DESC",
        (user_id,)
    )
    audios = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("perfil_publico.html", usuario=usuario, audios=audios)

# Deletar conta
@app.route("/deletar_conta")
def deletar_conta():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    user_id = session["usuario_id"]
    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT avatar FROM usuarios WHERE id_usuario=%s", (user_id,))
    usuario = cursor.fetchone()
    if usuario and usuario["avatar"]:
        caminho = os.path.join(app.config["AVATAR_FOLDER"], usuario["avatar"])
        if os.path.exists(caminho):
            os.remove(caminho)

    cursor.execute("DELETE FROM comentarios WHERE usuario_id=%s", (user_id,))
    cursor.execute("DELETE FROM curtidas WHERE usuario_id=%s", (user_id,))

    cursor.execute("SELECT arquivo_audio FROM audios WHERE usuario_id=%s", (user_id,))
    audios = cursor.fetchall()
    for a in audios:
        caminho_audio = os.path.join(app.config["UPLOAD_FOLDER"], a["arquivo_audio"])
        if os.path.exists(caminho_audio):
            os.remove(caminho_audio)

    cursor.execute("DELETE FROM audios WHERE usuario_id=%s", (user_id,))
    cursor.execute("DELETE FROM usuarios WHERE id_usuario=%s", (user_id,))
    db.commit()

    cursor.close()
    db.close()
    session.clear()

    return redirect(url_for("login"))

# Página de áudio individual
@app.route("/audio/<int:audio_id>")
def audio(audio_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.*, u.nome, u.usuario, u.avatar
        FROM audios a
        JOIN usuarios u ON u.id_usuario = a.usuario_id
        WHERE id_audio=%s
    """, (audio_id,))
    audio = cursor.fetchone()

    cursor.close()
    db.close()

    if not audio:
        return redirect(url_for("timeline"))

    db = conectar()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.*, u.nome AS nome_usuario
        FROM comentarios c
        JOIN usuarios u ON c.usuario_id = u.id_usuario
        WHERE c.audio_id=%s
        ORDER BY c.criado_em ASC
    """, (audio_id,))
    comentarios = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("audio.html", audio=audio, comentarios=comentarios)

# Deletar comentário
@app.route("/deletar_comentario/<int:id_comentario>", methods=["POST"])
def deletar_comentario(id_comentario):
    if "usuario_id" not in session:
        return "unauthorized", 403

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM comentarios WHERE id_comentario=%s",
        (id_comentario,)
    )
    comentario = cursor.fetchone()

    if not comentario or comentario["usuario_id"] != session["usuario_id"]:
        cursor.close()
        db.close()
        return "forbidden", 403

    cursor.execute(
        "DELETE FROM comentarios WHERE id_comentario=%s",
        (id_comentario,)
    )
    db.commit()

    cursor.close()
    db.close()
    return "ok", 200

# Endpoint AJAX de curtir
@app.route("/curtir_ajax/<int:audio_id>", methods=["POST"])
def curtir_ajax(audio_id):
    if "usuario_id" not in session:
        return {"erro": "Não logado"}, 401

    user_id = session["usuario_id"]
    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
                   (user_id, audio_id))
    existe = cursor.fetchone()

    if existe:
        cursor.execute("DELETE FROM curtidas WHERE usuario_id=%s AND audio_id=%s",
                       (user_id, audio_id))
        status = "descurtido"
    else:
        cursor.execute("INSERT INTO curtidas (usuario_id, audio_id) VALUES (%s, %s)",
                       (user_id, audio_id))
        status = "curtido"

    db.commit()

    cursor.execute("SELECT COUNT(*) AS total FROM curtidas WHERE audio_id=%s",
                   (audio_id,))
    total = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return {"status": status, "total": total}, 200

# Run
if __name__ == "__main__":
    app.run(debug=True)
