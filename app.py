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
        password="labinfo",
        database="ifonias_db"
    )

# ===========================
# CONFIGURAÇÕES DE UPLOAD
# ===========================
UPLOAD_FOLDER = "static/audios"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"mp3", "wav", "mpeg"}
AVATAR_FOLDER = "static/avatars"
app.config["AVATAR_FOLDER"] = AVATAR_FOLDER

# Criar pasta se não existir
if not os.path.exists(AVATAR_FOLDER):
    os.makedirs(AVATAR_FOLDER)



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
        SELECT 
            a.*, 
            u.nome,
            u.usuario,
            u.curso,
            u.campus,
            (SELECT COUNT(*) FROM curtidas c WHERE c.audio_id = a.id_audio) AS total_curtidas
        FROM audios a
        JOIN usuarios u ON a.usuario_id = u.id_usuario
        ORDER BY a.criado_em DESC
    """)
    audios = cursor.fetchall()

    # =======================
    # Todos os áudios + total de curtidas
    # =======================
    cursor.execute("""
        SELECT a.*, u.nome,
            (SELECT COUNT(*) FROM curtidas c WHERE c.audio_id = a.id_audio) AS total_curtidas
        FROM audios a
        JOIN usuarios u ON a.usuario_id = u.id_usuario
        ORDER BY a.criado_em DESC
    """)
    audios = cursor.fetchall()

    # =======================
    # Quais áudios o usuário curtiu
    # =======================
    cursor.execute("SELECT audio_id FROM curtidas WHERE usuario_id=%s",
                   (session["usuario_id"],))
    curtidos = [c["audio_id"] for c in cursor.fetchall()]

    # =======================
    # Comentários
    # =======================
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

    # =======================
    # Lista de curtidores por áudio
    # =======================
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
# DELETAR ÁUDIO
# ===========================
@app.route("/deletar_audio/<int:id_audio>")
def deletar_audio(id_audio):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    # Verifica se o áudio pertence ao usuário
    cursor.execute("""
        SELECT * FROM audios WHERE id_audio=%s AND usuario_id=%s
    """, (id_audio, session["usuario_id"]))
    audio = cursor.fetchone()

    if not audio:
        cursor.close()
        db.close()
        return redirect(url_for("perfil"))

    # Deleta curtidas e comentários antes (integridade)
    cursor.execute("DELETE FROM curtidas WHERE audio_id=%s", (id_audio,))
    cursor.execute("DELETE FROM comentarios WHERE audio_id=%s", (id_audio,))

    # Deleta o arquivo de áudio do disco
    caminho = os.path.join(app.config["UPLOAD_FOLDER"], audio["arquivo_audio"])
    if os.path.exists(caminho):
        os.remove(caminho)

    # Deleta o registro
    cursor.execute("DELETE FROM audios WHERE id_audio=%s", (id_audio,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for("perfil"))

# ===========================
# EDITAR PERFIL
# ===========================
@app.route("/editar_perfil", methods=["GET", "POST"])
def editar_perfil():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM usuarios WHERE id_usuario=%s",
                   (session["usuario_id"],))
    usuario = cursor.fetchone()

    if request.method == "POST":
        nome = request.form.get("nome")
        usuario_login = request.form.get("usuario")
        curso = request.form.get("curso")
        campus = request.form.get("campus")

        avatar_file = request.files.get("avatar")

        avatar_nome = usuario["avatar"]  # mantém o antigo se não trocar

        if avatar_file and avatar_file.filename != "":
            nome_seguro = secure_filename(avatar_file.filename)
            avatar_caminho = os.path.join(app.config["AVATAR_FOLDER"], nome_seguro)

            # remove avatar antigo
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
        return {"erro": "Não logado"}, 401

    user_id = session["usuario_id"]
    conn = connection.MySQLConnection(**db_config)
    cursor = conn.cursor(dictionary=True)

    # Verifica se já curtiu
    cursor.execute("""
        SELECT * FROM curtidas WHERE usuario_id = %s AND audio_id = %s
    """, (user_id, audio_id))
    existe = cursor.fetchone()

    if existe:
        # Remove curtida
        cursor.execute("""
            DELETE FROM curtidas WHERE usuario_id = %s AND audio_id = %s
        """, (user_id, audio_id))
        conn.commit()
        curtido = False
    else:
        # Adiciona curtida
        cursor.execute("""
            INSERT INTO curtidas (usuario_id, audio_id) VALUES (%s, %s)
        """, (user_id, audio_id))
        conn.commit()
        curtido = True

    # Conta novamente
    cursor.execute("SELECT COUNT(*) AS total FROM curtidas WHERE audio_id = %s", (audio_id,))
    total = cursor.fetchone()["total"]

    conn.close()

    return {"curtido": curtido, "total": total}


@app.route("/curtir_ajax/<int:audio_id>", methods=["POST"])
def curtir_ajax(audio_id):
    if "usuario_id" not in session:
        return {"erro": "não logado"}, 401

    db = conectar()
    cursor = db.cursor(dictionary=True)

    # Verifica se já curtiu
    cursor.execute("""
        SELECT * FROM curtidas 
        WHERE usuario_id=%s AND audio_id=%s
    """, (session["usuario_id"], audio_id))
    existe = cursor.fetchone()

    if existe:
        cursor.execute("""
            DELETE FROM curtidas 
            WHERE usuario_id=%s AND audio_id=%s
        """, (session["usuario_id"], audio_id))
        status = "descurtido"
    else:
        cursor.execute("""
            INSERT INTO curtidas (usuario_id, audio_id)
            VALUES (%s, %s)
        """, (session["usuario_id"], audio_id))
        status = "curtido"

    db.commit()

    # Contar curtidas atualizadas
    cursor.execute("SELECT COUNT(*) AS total FROM curtidas WHERE audio_id=%s", (audio_id,))
    total = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return {
        "status": status,
        "total": total
    }, 200


# ===========================
# COMENTÁRIO
# ===========================
@app.route("/comentar/<int:audio_id>", methods=["POST"])
def comentar(audio_id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    texto = request.form.get("comentario")

    if not texto.strip():
        return redirect(url_for("timeline"))

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
# PERFIL PÚBLICO (ver perfil de outro usuário)
# ===========================
@app.route("/perfil/<int:user_id>")
def perfil_publico(user_id):
    # se não estiver logado, redireciona ao login (opcional)
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = conectar()
    cursor = db.cursor(dictionary=True)

    # busca dados do usuário solicitado
    cursor.execute("SELECT id_usuario, nome, usuario, curso, campus, avatar FROM usuarios WHERE id_usuario=%s", (user_id,))
    usuario = cursor.fetchone()

    if not usuario:
        cursor.close()
        db.close()
        return redirect(url_for("timeline"))  # usuário não encontrado

    # busca áudios desse usuário
    cursor.execute("""
        SELECT * FROM audios
        WHERE usuario_id=%s
        ORDER BY criado_em DESC
    """, (user_id,))
    audios = cursor.fetchall()

    cursor.close()
    db.close()

    # renderiza uma página de perfil público (sem botões de editar/deletar)
    return render_template("perfil_publico.html", usuario=usuario, audios=audios)

# ===========================
# DELETAR PERFIL
# ===========================
@app.route("/deletar_conta")
def deletar_conta():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    user_id = session["usuario_id"]

    db = conectar()
    cursor = db.cursor(dictionary=True)

    # buscar avatar para deletar do disco
    cursor.execute("SELECT avatar FROM usuarios WHERE id_usuario=%s", (user_id,))
    usuario = cursor.fetchone()

    # deletar avatar do disco
    if usuario and usuario["avatar"]:
        caminho = os.path.join(app.config["AVATAR_FOLDER"], usuario["avatar"])
        if os.path.exists(caminho):
            os.remove(caminho)

    # deletar comentários do usuário
    cursor.execute("DELETE FROM comentarios WHERE usuario_id=%s", (user_id,))

    # deletar curtidas do usuário
    cursor.execute("DELETE FROM curtidas WHERE usuario_id=%s", (user_id,))

    # pegar todos os áudios do usuário
    cursor.execute("SELECT arquivo_audio FROM audios WHERE usuario_id=%s", (user_id,))
    audios = cursor.fetchall()

    # deletar arquivos de áudio
    for a in audios:
        caminho_audio = os.path.join(app.config["UPLOAD_FOLDER"], a["arquivo_audio"])
        if os.path.exists(caminho_audio):
            os.remove(caminho_audio)

    # deletar áudios do banco
    cursor.execute("DELETE FROM audios WHERE usuario_id=%s", (user_id,))

    # deletar conta
    cursor.execute("DELETE FROM usuarios WHERE id_usuario=%s", (user_id,))
    db.commit()

    cursor.close()
    db.close()

    session.clear()

    return redirect(url_for("login"))

# ===========================
# PÁGINA DE ÁUDIO INDIVIDUAL
# ===========================
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

    return render_template("audio.html", audio=audio)


@app.route("/deletar_comentario/<int:id_comentario>", methods=["POST"])
def deletar_comentario(id_comentario):
    if "usuario_id" not in session:
        return "unauthorized", 403

    db = conectar()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM comentarios WHERE id_comentario=%s", (id_comentario,))
    comentario = cursor.fetchone()

    if not comentario or comentario["usuario_id"] != session["usuario_id"]:
        cursor.close()
        db.close()
        return "forbidden", 403

    cursor.execute("DELETE FROM comentarios WHERE id_comentario=%s", (id_comentario,))
    db.commit()

    cursor.close()
    db.close()

    return "ok", 200


# ===========================
# RUN
# ===========================
if __name__ == "__main__":
    app.run(debug=True)
