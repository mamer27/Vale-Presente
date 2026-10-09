"""Gerador de Vale Presente — Núcleo de Incentivos (web).

Variáveis de ambiente:
  APP_PASSWORD  senha compartilhada do Núcleo (obrigatória em produção)
  SECRET_KEY    chave da sessão (o Render gera sozinho)
"""
import hmac
import os
import shutil
import tempfile
import threading
import time
import uuid
from functools import wraps

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import vale_core as core

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB por envio
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

SENHA = os.environ.get("APP_PASSWORD", "")
RAIZ = os.path.join(tempfile.gettempdir(), "vale_presente_jobs")
os.makedirs(RAIZ, exist_ok=True)
VALIDADE_SEG = 2 * 3600

JOBS = {}
LOCK = threading.Lock()


def agora():
    return time.time()


def login_necessario(f):
    @wraps(f)
    def w(*a, **k):
        if SENHA and not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        if SENHA and hmac.compare_digest(request.form.get("senha", ""), SENHA):
            session["ok"] = True
            return redirect(url_for("index"))
        erro = "Senha incorreta."
        time.sleep(1)
    return render_template("login.html", erro=erro)


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_necessario
def index():
    limpar_antigos()
    return render_template("index.html", aviso_sem_senha=not SENHA)


def limpar_antigos():
    with LOCK:
        velhos = [j for j, d in JOBS.items() if agora() - d["criado"] > VALIDADE_SEG]
        for j in velhos:
            shutil.rmtree(os.path.join(RAIZ, j), ignore_errors=True)
            JOBS.pop(j, None)


def rodar_job(job_id):
    job = JOBS[job_id]
    pasta = os.path.join(RAIZ, job_id)
    saida = os.path.join(pasta, "saida")
    os.makedirs(saida, exist_ok=True)
    base = job["base_path"]
    try:
        job["msg"] = "Lendo a base de cadastro..."
        dic = core.ler_base(base)
        job["msg"] = f"Base lida: {len(dic)} cadastros."
        resultados = []
        total = len(job["apuracoes"])
        for i, (caminho, nome) in enumerate(job["apuracoes"], start=1):
            job["msg"] = f"Processando {i}/{total}: {nome}"
            try:
                r = core.processar_apuracao(caminho, nome, dic, base, saida)
            except Exception as e:  # um arquivo ruim não derruba os outros
                r = {"arquivo": nome, "ok": False, "erro": str(e)}
            finally:
                try:
                    os.remove(caminho)  # apuração tem dado pessoal: apaga logo
                except OSError:
                    pass
            if r.get("saida"):
                r["saida_nome"] = os.path.basename(r.pop("saida"))
            resultados.append(r)
            job["resultados"] = list(resultados)
        try:
            os.remove(base)
        except OSError:
            pass
        n_sem = core.consolidar_sem_cadastro(resultados, os.path.join(saida, "SEM_CADASTRO_consolidado.xlsx"))
        job["n_sem"] = n_sem
        job["status"] = "pronto"
        job["msg"] = "Concluído."
    except Exception as e:
        job["status"] = "erro"
        job["msg"] = str(e)


@app.route("/novo", methods=["POST"])
@login_necessario
def novo():
    job_id = uuid.uuid4().hex[:12]
    os.makedirs(os.path.join(RAIZ, job_id, "entrada"), exist_ok=True)
    with LOCK:
        JOBS[job_id] = {"status": "enviando", "msg": "Recebendo arquivos...", "criado": agora(),
                        "base_path": None, "apuracoes": [], "resultados": []}
    return jsonify(job=job_id)


@app.route("/arquivo/<job_id>", methods=["POST"])
@login_necessario
def arquivo(job_id):
    """Recebe UM arquivo por requisição (evita limite de tamanho do envio total)."""
    job = JOBS.get(job_id)
    if not job or job["status"] != "enviando":
        return jsonify(erro="Envio inválido ou já iniciado."), 400
    f = request.files.get("arquivo")
    tipo = request.form.get("tipo")
    if not f or not f.filename:
        return jsonify(erro="Arquivo ausente."), 400
    if not f.filename.lower().endswith(".xlsx"):
        return jsonify(erro=f"'{f.filename}' não é .xlsx."), 400
    entrada = os.path.join(RAIZ, job_id, "entrada")
    if tipo == "base":
        job["base_path"] = os.path.join(entrada, "base.xlsx")
        f.save(job["base_path"])
    elif tipo == "apuracao":
        p = os.path.join(entrada, f"apuracao_{len(job['apuracoes'])}.xlsx")
        f.save(p)
        job["apuracoes"].append((p, f.filename))
    else:
        return jsonify(erro="Tipo inválido."), 400
    return jsonify(ok=True)


@app.route("/iniciar/<job_id>", methods=["POST"])
@login_necessario
def iniciar(job_id):
    job = JOBS.get(job_id)
    if not job or job["status"] != "enviando":
        return jsonify(erro="Envio inválido ou já iniciado."), 400
    if not job["base_path"]:
        return jsonify(erro="Falta a BASE COMPLETA."), 400
    if not job["apuracoes"]:
        return jsonify(erro="Falta ao menos uma apuração."), 400
    job["status"] = "rodando"
    job["msg"] = "Na fila..."
    threading.Thread(target=rodar_job, args=(job_id,), daemon=True).start()
    return jsonify(ok=True)


@app.route("/status/<job_id>")
@login_necessario
def status(job_id):
    j = JOBS.get(job_id)
    if not j:
        abort(404)
    return jsonify(status=j["status"], msg=j["msg"], resultados=j["resultados"], n_sem=j.get("n_sem", 0))


@app.route("/baixar/<job_id>/<path:nome>")
@login_necessario
def baixar(job_id, nome):
    if job_id not in JOBS:
        abort(404)
    pasta = os.path.join(RAIZ, job_id)
    nome = os.path.basename(nome)
    caminho = os.path.join(pasta, "saida", nome)
    if not os.path.isfile(caminho):
        abort(404)
    return send_file(caminho, as_attachment=True, download_name=os.path.basename(caminho))


@app.route("/saude")
def saude():
    return "ok"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
