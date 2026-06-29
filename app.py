from services.ia_service import classificar_risco_zona
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import json

app = Flask(__name__)

# =========================================================
# CONFIGURAÇÃO
# =========================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DB_DIR, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

db = SQLAlchemy(app)

# =========================================================
# MODELOS
# =========================================================

class Reporte(db.Model):
    __tablename__ = "reportes"

    id = db.Column(db.Integer, primary_key=True)

    # =========================
    # IDENTIFICAÇÃO
    # =========================
    nome = db.Column(db.String(120), nullable=False)
    bairro = db.Column(db.String(120), nullable=False)

    # =========================
    # PROBLEMA
    # =========================
    tipo_problema = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text, nullable=False)

    # =========================
    # GEOLOCALIZAÇÃO
    # =========================
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # =========================
    # INTELIGÊNCIA ARTIFICIAL
    # =========================
    alerta_ia = db.Column(db.String(255))

    nivel = db.Column(db.String(20), default="baixo")  # baixo | medio | alto
    score_ia = db.Column(db.Float, default=0)  # 0 a 100

    prob_risco = db.Column(db.Float, default=0)  # probabilidade de risco

    prioridade = db.Column(db.String(50), default="media")

    # =========================
    # CLASSIFICAÇÃO URBANA AVANÇADA
    # =========================
    nivel_risco = db.Column(db.String(100))
    setor_responsavel = db.Column(db.String(150))
    acao_recomendada = db.Column(db.Text)

    # =========================
    # ESTADO DO SISTEMA
    # =========================
    estado = db.Column(db.String(50), default="Aberto")

    resolvido = db.Column(db.Boolean, default=False)

    # =========================
    # MULTIMÍDIA
    # =========================
    foto = db.Column(db.String(255))

    # =========================
    # TEMPO
    # =========================
    data = db.Column(db.String(50))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    # =========================
    # IA AUTOMÁTICA (FUNÇÃO SIMPLES)
    # =========================
    def calcular_risco(self):
        """
        Lógica simples de IA (podes evoluir depois)
        """

        score = 0

        # tipo de problema
        if self.tipo_problema in ["crime", "violencia", "assalto"]:
            score += 70
        elif self.tipo_problema in ["buraco", "estrada", "infraestrutura"]:
            score += 40
        else:
            score += 20

        # estado
        if self.estado == "Aberto":
            score += 20

        # converte para risco
        self.score_ia = score

        if score >= 70:
            self.nivel = "alto"
        elif score >= 40:
            self.nivel = "medio"
        else:
            self.nivel = "baixo"

        self.prob_risco = score / 100

        return self.nivel

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default="cidadao")


class Zona(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(150), nullable=False)
    crescimento_populacional = db.Column(db.Float, default=0)
    novas_construcoes = db.Column(db.Float, default=0)
    infraestruturas = db.Column(db.Float, default=0)
    ocupacao_solo = db.Column(db.Float, default=0)

    poligono = db.Column(db.Text, nullable=True)

    indice_crescimento = db.Column(db.Float, default=0)
    classe_crescimento = db.Column(db.String(50))
    estado_crescimento = db.Column(db.String(100))
    alerta_urbano = db.Column(db.String(255))
    nivel_crescimento = db.Column(db.String(50))
    cor_mapa = db.Column(db.String(20))

    acao_recomendada_zona = db.Column(db.String(255))

    indice_manual = db.Column(db.Float, default=0)
    ajuste_ia = db.Column(db.Float, default=0)
    indice_final = db.Column(db.Float, default=0)

    pressao_reportes = db.Column(db.String(255))
    previsao_risco = db.Column(db.String(255))
    fonte_analise = db.Column(db.String(255))

    sinal_satelite = db.Column(db.String(100))
    sinal_sensor = db.Column(db.String(100))

    # ==========================================================
    # NOVOS CAMPOS DA FASE 10.5 — ÍNDICE INTELIGENTE
    # ==========================================================

    # índice calculado só pelos 4 indicadores do formulário
    indice_manual = db.Column(db.Float, default=0)

    # ajuste automático vindo de reportes / sinais urbanos
    ajuste_ia = db.Column(db.Float, default=0)

    # índice final = índice_manual + ajuste_ia
    indice_final = db.Column(db.Float, default=0)

    # resumo textual da pressão de reportes na zona
    pressao_reportes = db.Column(db.String(255), nullable=True)

    # previsão de risco futuro
    previsao_risco = db.Column(db.String(255), nullable=True)

    # de onde vieram os sinais usados na análise
    fonte_analise = db.Column(db.String(255), nullable=True)

    # sinal simulado de satélite
    sinal_satelite = db.Column(db.String(100), nullable=True)

    # sinal simulado de sensor urbano
    sinal_sensor = db.Column(db.String(100), nullable=True)

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def analisar_alerta_urbano(descricao, tipo_problema):
    texto = f"{tipo_problema or ''} {descricao or ''}".lower()

    # 1) INUNDAÇÃO / DRENAGEM
    if (
        "inund" in texto or
        "água" in texto or
        "agua" in texto or
        "drenagem" in texto or
        "vala" in texto or
        "escoamento" in texto or
        "alag" in texto
    ):
        return {
            "alerta_ia": "Risco de inundação",
            "prioridade": "Alta",
            "nivel_risco": "Muito Alto",
            "setor_responsavel": "Infraestruturas, Saneamento e Proteção Civil",
            "acao_recomendada": "Realizar inspeção urgente, limpeza de drenagem, abertura de canais de escoamento e avaliação de risco às habitações próximas."
        }

    # 2) CONSTRUÇÃO ILEGAL / OCUPAÇÃO IRREGULAR
    if (
        "ilegal" in texto or
        "ocupação irregular" in texto or
        "ocupacao irregular" in texto or
        "construção ilegal" in texto or
        "construcao ilegal" in texto or
        "obra irregular" in texto or
        "sem licença" in texto or
        "sem licenca" in texto
    ):
        return {
            "alerta_ia": "Possível construção ilegal",
            "prioridade": "Alta",
            "nivel_risco": "Alto",
            "setor_responsavel": "Fiscalização Municipal e Planeamento Urbano",
            "acao_recomendada": "Verificar licença da obra, validar ocupação do terreno, analisar conformidade urbanística e notificar os responsáveis se houver irregularidade."
        }

    # 3) LIXO / SANEAMENTO / ESGOTO / INFRAESTRUTURA
    if (
        "lixo" in texto or
        "saneamento" in texto or
        "esgoto" in texto or
        "infraestrutura" in texto or
        "infraestruturas" in texto or
        "valeta" in texto or
        "resíduos" in texto or
        "residuos" in texto
    ):
        return {
            "alerta_ia": "Falta de infraestrutura urbana",
            "prioridade": "Média",
            "nivel_risco": "Médio",
            "setor_responsavel": "Serviços Urbanos, Saneamento e Obras Municipais",
            "acao_recomendada": "Programar intervenção técnica, reforçar limpeza urbana, melhorar saneamento local e avaliar necessidade de infraestrutura complementar."
        }

    # 4) CONFLITO DE USO DO SOLO / OCUPAÇÃO
    if (
        "uso do solo" in texto or
        "solo" in texto or
        "ocupação" in texto or
        "ocupacao" in texto or
        "terreno" in texto or
        "loteamento irregular" in texto
    ):
        return {
            "alerta_ia": "Conflito de uso do solo",
            "prioridade": "Média",
            "nivel_risco": "Médio",
            "setor_responsavel": "Planeamento Urbano e Cadastro Municipal",
            "acao_recomendada": "Analisar o uso atual do terreno, comparar com o plano urbano da zona e verificar necessidade de reordenamento ou fiscalização."
        }

    # 5) ESTRADAS / BURACOS / ACESSO
    if (
        "buraco" in texto or
        "estrada" in texto or
        "via" in texto or
        "acesso" in texto or
        "ponte" in texto
    ):
        return {
            "alerta_ia": "Problema de mobilidade e acesso urbano",
            "prioridade": "Média",
            "nivel_risco": "Médio",
            "setor_responsavel": "Obras Públicas e Mobilidade Urbana",
            "acao_recomendada": "Realizar vistoria técnica, avaliar condições da via e programar manutenção ou reabilitação do acesso."
        }

    # 6) CASO GERAL
    return {
        "alerta_ia": "Situação urbana reportada",
        "prioridade": "Baixa",
        "nivel_risco": "Baixo",
        "setor_responsavel": "Atendimento Municipal",
        "acao_recomendada": "Avaliar o reporte manualmente e encaminhar ao setor competente para análise."
    }


def calcular_indice_zona(crescimento, construcoes, infra, ocupacao):
    crescimento = crescimento or 0
    construcoes = construcoes or 0
    infra = infra or 0
    ocupacao = ocupacao or 0

    # cálculo do índice 0–100
    indice = round(
        (crescimento * 0.30) +
        (construcoes * 0.30) +
        (infra * 0.20) +
        (ocupacao * 0.20), 1
    )

    # garantir que o valor fica entre 0 e 100
    if indice < 0:
        indice = 0
    if indice > 100:
        indice = 100

    # interpretação inteligente
    if indice >= 85:
        classe = "Crescimento Crítico"
        estado = "Expansão Urbana Crítica"
        alerta = "Zona sob forte pressão urbana"
        nivel = "Crítico"
        cor_mapa = "red"
        acao = (
            "Priorizar urgentemente drenagem, saneamento, abertura e reabilitação de vias, "
            "controlo de ocupação do solo, expansão de escolas, postos de saúde e fiscalização urbanística."
        )

    elif indice >= 70:
        classe = "Crescimento Alto"
        estado = "Crescimento Acelerado"
        alerta = "Reforçar infraestruturas"
        nivel = "Alto"
        cor_mapa = "orange"
        acao = (
            "Reforçar infraestruturas urbanas, melhorar mobilidade, saneamento, drenagem "
            "e monitorar novas construções para evitar crescimento desordenado."
        )

    elif indice >= 40:
        classe = "Crescimento Médio"
        estado = "Zona em Expansão"
        alerta = "Monitorar evolução"
        nivel = "Médio"
        cor_mapa = "yellow"
        acao = (
            "Acompanhar o crescimento da zona, planear novas infraestruturas, "
            "melhorar serviços básicos e prevenir ocupação irregular."
        )

    else:
        classe = "Crescimento Baixo"
        estado = "Estável"
        alerta = "Sem pressão urbana significativa"
        nivel = "Baixo"
        cor_mapa = "green"
        acao = (
            "Manter monitoramento urbano, preservar o ordenamento da zona "
            "e planear crescimento futuro de forma preventiva."
        )

    return indice, classe, estado, alerta, nivel, cor_mapa, acao


def reporte_to_feature(r):
    if r.latitude is None or r.longitude is None:
        return None

    return {
        "type": "Feature",
        "properties": {
            "id": r.id,
            "nome": r.nome,
            "bairro": r.bairro,
            "tipo_problema": r.tipo_problema,
            "descricao": r.descricao,
            "alerta_ia": r.alerta_ia,
            "prioridade": r.prioridade,
            "estado": r.estado,
            "data": r.data
        },
        "geometry": {
            "type": "Point",
            "coordinates": [r.longitude, r.latitude]
        }
    }


def zona_to_feature(z):
    # =========================================================
    # 1. VALIDAR SE EXISTE POLÍGONO
    # =========================================================
    if not z.poligono:
        return None

    # =========================================================
    # 2. TENTAR CONVERTER JSON
    # =========================================================
    try:
        coords = json.loads(z.poligono)
    except Exception:
        return None

    # =========================================================
    # 3. VALIDAR ESTRUTURA
    # =========================================================
    if not isinstance(coords, list) or len(coords) < 3:
        return None

    # =========================================================
    # 4. CONVERTER PARA FORMATO GEOJSON (lon, lat)
    # =========================================================
    ring = []

    for ponto in coords:
        if (
            isinstance(ponto, list)
            and len(ponto) == 2
        ):
            lat = ponto[0]
            lon = ponto[1]
            ring.append([lon, lat])

    # =========================================================
    # 5. GARANTIR QUE TEM POLÍGONO VÁLIDO
    # =========================================================
    if len(ring) < 3:
        return None

    # fechar polígono
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    # =========================================================
    # 6. RETORNO GEOJSON FINAL
    # =========================================================
    return {
        "type": "Feature",
        "properties": {
            "id": z.id,
            "nome": z.nome,

            "crescimento_populacional": z.crescimento_populacional,
            "novas_construcoes": z.novas_construcoes,
            "infraestruturas": z.infraestruturas,
            "ocupacao_solo": z.ocupacao_solo,

            "indice_final": z.indice_final,
            "classe": z.classe_crescimento,
            "estado": z.estado_crescimento,
            "alerta": z.alerta_urbano,
            "nivel": z.nivel_crescimento,
            "cor": z.cor_mapa,
            "acao": z.acao_recomendada_zona,

            "pressao_reportes": z.pressao_reportes,
            "previsao_risco": z.previsao_risco,
            "fonte_analise": z.fonte_analise,
            "sinal_satelite": z.sinal_satelite,
            "sinal_sensor": z.sinal_sensor
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring]
        }
    }

# =========================================================
# ROTAS
# =========================================================
@app.route("/")
def home():
    return render_template(
        "index.html",
        total_reportes=Reporte.query.count(),
        total_zonas=Zona.query.count()
    )


@app.route("/reportar", methods=["GET", "POST"])
def reportar():
    if request.method == "POST":
        nome = request.form.get("nome")
        bairro = request.form.get("bairro")
        tipo = request.form.get("tipo_problema")
        desc = request.form.get("descricao")

        lat = request.form.get("latitude")
        lon = request.form.get("longitude")

        lat = float(lat) if lat else None
        lon = float(lon) if lon else None

        ia = analisar_alerta_urbano(desc, tipo)

        r = Reporte(
            nome=nome,
            bairro=bairro,
            tipo_problema=tipo,
            descricao=desc,
            latitude=lat,
            longitude=lon,
            alerta_ia=ia["alerta_ia"],
            prioridade=ia["prioridade"],
            nivel_risco=ia["nivel_risco"],
            setor_responsavel=ia["setor_responsavel"],
            acao_recomendada=ia["acao_recomendada"],
            data=datetime.now().strftime("%d/%m/%Y %H:%M")
        )

        db.session.add(r)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("reportar.html")

@app.route("/reporte/<int:reporte_id>")
def detalhe_reporte(reporte_id):
    reporte = Reporte.query.get_or_404(reporte_id)
    return render_template("detalhe_reporte.html", reporte=reporte)


# ==========================================================
# FUNÇÕES DO ÍNDICE DE CRESCIMENTO INTELIGENTE
# ==========================================================

def normalizar_bairro(texto):
    if not texto:
        return ""
    return str(texto).strip().lower()


def classificar_indice_final(indice):
    """
    Classifica o índice final da zona e gera os textos de apoio.
    """
    if indice >= 85:
        return {
            "classe": "Crescimento Crítico",
            "estado": "Zona em pressão urbana extrema",
            "alerta": "Alerta urbano máximo: expansão crítica da zona",
            "nivel": "Crítico",
            "acao": "Priorizar intervenção urbana imediata, controlo territorial e reforço de infraestruturas."
        }
    elif indice >= 70:
        return {
            "classe": "Crescimento Alto",
            "estado": "Zona em forte expansão urbana",
            "alerta": "Alerta urbano elevado: zona sob pressão de crescimento",
            "nivel": "Alto",
            "acao": "Monitorar a expansão, reforçar planeamento urbano e prevenir ocupação desordenada."
        }
    elif indice >= 50:
        return {
            "classe": "Crescimento Moderado",
            "estado": "Zona em evolução urbana controlada",
            "alerta": "Atenção: crescimento urbano moderado",
            "nivel": "Médio",
            "acao": "Acompanhar a evolução da zona e planear melhorias graduais."
        }
    else:
        return {
            "classe": "Crescimento Baixo",
            "estado": "Zona com baixa pressão de crescimento",
            "alerta": "Sem alerta crítico de crescimento urbano",
            "nivel": "Baixo",
            "acao": "Manter monitorização periódica e gestão preventiva da zona."
        }


def calcular_indice_inteligente(nome_zona, crescimento_populacional, novas_construcoes, infraestruturas, ocupacao_solo):
    """
    Calcula o índice inteligente da zona com base em:
    1) índice manual
    2) ajuste por reportes
    3) pressão de reportes
    4) previsão de risco
    5) fonte da análise
    """

    # ------------------------------------------------------
    # 1) ÍNDICE MANUAL
    # ------------------------------------------------------
    try:
        crescimento_populacional = float(crescimento_populacional or 0)
        novas_construcoes = float(novas_construcoes or 0)
        infraestruturas = float(infraestruturas or 0)
        ocupacao_solo = float(ocupacao_solo or 0)
    except:
        crescimento_populacional = 0
        novas_construcoes = 0
        infraestruturas = 0
        ocupacao_solo = 0

    # pesos do índice manual
    indice_manual = (
        crescimento_populacional * 0.30 +
        novas_construcoes * 0.30 +
        infraestruturas * 0.15 +
        ocupacao_solo * 0.25
    )

    # ------------------------------------------------------
    # 2) PROCURAR REPORTES DA ZONA
    # ------------------------------------------------------
    nome_zona_norm = normalizar_bairro(nome_zona)

    todos_reportes = Reporte.query.all()
    reportes_zona = []

    for r in todos_reportes:
        bairro_r = normalizar_bairro(r.bairro)
        if bairro_r == nome_zona_norm:
            reportes_zona.append(r)

    total_reportes = len(reportes_zona)

    # ------------------------------------------------------
    # 3) AJUSTE POR REPORTES
    # ------------------------------------------------------
    ajuste_ia = 0
    qtd_alta = 0
    qtd_inundacao = 0
    qtd_lixo = 0
    qtd_erosao = 0
    qtd_drenagem = 0
    qtd_ocupacao = 0

    for r in reportes_zona:
        prioridade = (r.prioridade or "").strip().lower()
        problema = (r.tipo_problema or "").strip().lower()
        descricao = (r.descricao or "").strip().lower()

        # prioridade alta
        if prioridade == "alta":
            qtd_alta += 1
            ajuste_ia += 2

        # inundação
        if "inunda" in problema or "inunda" in descricao:
            qtd_inundacao += 1
            ajuste_ia += 2

        # lixo
        if "lixo" in problema or "lixo" in descricao:
            qtd_lixo += 1
            ajuste_ia += 1

        # erosão
        if "eros" in problema or "eros" in descricao:
            qtd_erosao += 1
            ajuste_ia += 2

        # drenagem
        if "dren" in problema or "dren" in descricao:
            qtd_drenagem += 1
            ajuste_ia += 1.5

        # ocupação / construção irregular
        if (
            "ocup" in problema or "ocup" in descricao or
            "constru" in problema or "constru" in descricao or
            "irregular" in problema or "irregular" in descricao
        ):
            qtd_ocupacao += 1
            ajuste_ia += 2

    # bónus pela quantidade total de reportes
    if total_reportes >= 8:
        ajuste_ia += 6
    elif total_reportes >= 5:
        ajuste_ia += 4
    elif total_reportes >= 3:
        ajuste_ia += 2

    # limite de segurança do ajuste
    if ajuste_ia > 25:
        ajuste_ia = 25

    # ------------------------------------------------------
    # 4) PRESSÃO DE REPORTES
    # ------------------------------------------------------
    if total_reportes == 0:
        pressao_reportes = "Sem pressão relevante de reportes"
    elif total_reportes <= 2:
        pressao_reportes = "Baixa pressão urbana por reportes"
    elif total_reportes <= 4:
        pressao_reportes = "Pressão urbana moderada por reportes"
    elif total_reportes <= 7:
        pressao_reportes = "Alta pressão urbana por reportes"
    else:
        pressao_reportes = "Zona sob forte pressão de ocorrências urbanas"

    # ------------------------------------------------------
    # 5) SINAIS SIMULADOS DE SATÉLITE E SENSOR
    # ------------------------------------------------------
    sinal_satelite = "Sem sinal satelital relevante"
    sinal_sensor = "Sem sinal urbano monitorado"

    if ocupacao_solo >= 75 and novas_construcoes >= 70:
        sinal_satelite = "Possível expansão urbana acelerada observável por satélite"

    if qtd_inundacao >= 2 or qtd_drenagem >= 2:
        sinal_sensor = "Sinal urbano de risco hídrico / drenagem"

    # ------------------------------------------------------
    # 6) PREVISÃO DE RISCO
    # ------------------------------------------------------
    if indice_manual >= 75 and total_reportes >= 4:
        previsao_risco = "Zona com risco elevado de tornar-se crítica nos próximos ciclos urbanos"
    elif indice_manual >= 60 and total_reportes >= 2:
        previsao_risco = "Zona com tendência de pressão urbana crescente"
    elif total_reportes >= 3:
        previsao_risco = "Zona em atenção devido ao aumento de ocorrências urbanas"
    else:
        previsao_risco = "Zona relativamente estável no cenário atual"

    # ------------------------------------------------------
    # 7) FONTE DA ANÁLISE
    # ------------------------------------------------------
    fontes = ["Indicadores manuais"]
    if total_reportes > 0:
        fontes.append("Reportes urbanos")
    if sinal_satelite != "Sem sinal satelital relevante":
        fontes.append("Sinal satelital simulado")
    if sinal_sensor != "Sem sinal urbano monitorado":
        fontes.append("Sinal urbano monitorado")

    fonte_analise = " + ".join(fontes)

    # ------------------------------------------------------
    # 8) ÍNDICE FINAL
    # ------------------------------------------------------
    indice_final = indice_manual + ajuste_ia

    if indice_final > 100:
        indice_final = 100

    classificacao = classificar_indice_final(indice_final)

    return {
        "indice_manual": round(indice_manual, 2),
        "ajuste_ia": round(ajuste_ia, 2),
        "indice_final": round(indice_final, 2),
        "pressao_reportes": pressao_reportes,
        "previsao_risco": previsao_risco,
        "fonte_analise": fonte_analise,
        "sinal_satelite": sinal_satelite,
        "sinal_sensor": sinal_sensor,
        "classe": classificacao["classe"],
        "estado": classificacao["estado"],
        "alerta": classificacao["alerta"],
        "nivel": classificacao["nivel"],
        "acao": classificacao["acao"]
    }

@app.route("/adicionar_zona", methods=["GET", "POST"])
def adicionar_zona():
    if request.method == "POST":
        try:
            nome = request.form.get("nome", "").strip()
            crescimento_populacional = float(request.form.get("crescimento_populacional", 0) or 0)
            novas_construcoes = float(request.form.get("novas_construcoes", 0) or 0)
            infraestruturas = float(request.form.get("infraestruturas", 0) or 0)
            ocupacao_solo = float(request.form.get("ocupacao_solo", 0) or 0)
            poligono = request.form.get("poligono", "").strip()

            # ------------------------------------------------------
            # CALCULAR ÍNDICE INTELIGENTE
            # ------------------------------------------------------
            resultado = calcular_indice_inteligente(
                nome_zona=nome,
                crescimento_populacional=crescimento_populacional,
                novas_construcoes=novas_construcoes,
                infraestruturas=infraestruturas,
                ocupacao_solo=ocupacao_solo
            )

            # ------------------------------------------------------
            # CRIAR ZONA COM TODOS OS CAMPOS
            # ------------------------------------------------------
            zona = Zona(
                nome=nome,
                crescimento_populacional=crescimento_populacional,
                novas_construcoes=novas_construcoes,
                infraestruturas=infraestruturas,
                ocupacao_solo=ocupacao_solo,
                poligono=poligono,

                # manter compatibilidade com o sistema antigo
                indice_crescimento=resultado["indice_final"],
                classe_crescimento=resultado["classe"],
                estado_crescimento=resultado["estado"],
                alerta_urbano=resultado["alerta"],
                nivel_crescimento=resultado["nivel"],
                acao_recomendada_zona=resultado["acao"],

                # novos campos inteligentes
                indice_manual=resultado["indice_manual"],
                ajuste_ia=resultado["ajuste_ia"],
                indice_final=resultado["indice_final"],
                pressao_reportes=resultado["pressao_reportes"],
                previsao_risco=resultado["previsao_risco"],
                fonte_analise=resultado["fonte_analise"],
                sinal_satelite=resultado["sinal_satelite"],
                sinal_sensor=resultado["sinal_sensor"]
            )

            db.session.add(zona)
            db.session.commit()

            return redirect(url_for("dashboard"))

        except Exception as e:
            db.session.rollback()
            return f"Erro ao adicionar zona: {str(e)}"

    return render_template("adicionar_zona.html")

# ==========================================================
# FASE 10.6A — MOTOR DE ALERTAS URBANOS INTELIGENTES
# ==========================================================

def gerar_alertas_urbanos():
    """
    Gera alertas automáticos a partir das zonas e dos reportes.
    Retorna uma lista de dicionários para mostrar no dashboard.
    """

    alertas = []

    zonas = Zona.query.order_by(Zona.id.desc()).all()
    reportes = Reporte.query.order_by(Reporte.id.desc()).all()

    # ------------------------------------------------------
    # 1) ALERTAS BASEADOS NAS ZONAS
    # ------------------------------------------------------
    for z in zonas:
        nome = z.nome or "Zona sem nome"
        indice_final = z.indice_final if z.indice_final is not None else z.indice_crescimento
        nivel = (z.nivel_crescimento or "").strip().lower()
        classe = (z.classe_crescimento or "").strip()
        previsao = (z.previsao_risco or "").strip().lower()
        pressao = (z.pressao_reportes or "").strip().lower()
        acao = (z.acao_recomendada_zona or "").strip().lower()

        # -------------------------------
        # ALERTA 1 — crescimento crítico
        # -------------------------------
        if (indice_final is not None and indice_final >= 85) or nivel in ["crítico", "critico"]:
            alertas.append({
                "tipo": "Crescimento Crítico",
                "zona": nome,
                "nivel": "Crítico",
                "mensagem": f"A zona {nome} apresenta crescimento urbano crítico e requer monitorização reforçada.",
                "acao": z.acao_recomendada_zona or "Priorizar intervenção urbana imediata."
            })

        # -------------------------------
        # ALERTA 2 — crescimento alto
        # -------------------------------
        elif (indice_final is not None and indice_final >= 70) or nivel == "alto":
            alertas.append({
                "tipo": "Crescimento Elevado",
                "zona": nome,
                "nivel": "Alto",
                "mensagem": f"A zona {nome} apresenta crescimento urbano elevado e deve ser acompanhada de perto.",
                "acao": z.acao_recomendada_zona or "Reforçar monitorização e planeamento urbano."
            })

        # -------------------------------
        # ALERTA 3 — risco futuro elevado
        # -------------------------------
        if "risco elevado" in previsao or "tornar-se crítica" in previsao or "tornar-se critica" in previsao:
            alertas.append({
                "tipo": "Risco Urbano Futuro",
                "zona": nome,
                "nivel": "Alto",
                "mensagem": f"A zona {nome} apresenta tendência de agravamento e pode tornar-se crítica.",
                "acao": z.acao_recomendada_zona or "Executar ações preventivas antes do agravamento."
            })

        # -------------------------------
        # ALERTA 4 — forte pressão urbana
        # -------------------------------
        if "forte pressão" in pressao or "forte pressao" in pressao or "alta pressão" in pressao or "alta pressao" in pressao:
            alertas.append({
                "tipo": "Pressão Urbana",
                "zona": nome,
                "nivel": "Alto",
                "mensagem": f"A zona {nome} apresenta forte pressão de ocorrências urbanas.",
                "acao": z.acao_recomendada_zona or "Reforçar resposta municipal e fiscalização territorial."
            })

        # -------------------------------
        # ALERTA 5 — ação prioritária
        # -------------------------------
        if (
            "intervenção imediata" in acao or
            "intervencao imediata" in acao or
            "priorizar" in acao or
            "urgente" in acao
        ):
            alertas.append({
                "tipo": "Intervenção Prioritária",
                "zona": nome,
                "nivel": "Crítico",
                "mensagem": f"A zona {nome} exige intervenção prioritária segundo a análise do sistema.",
                "acao": z.acao_recomendada_zona or "Executar intervenção prioritária."
            })

    # ------------------------------------------------------
    # 2) ALERTAS BASEADOS NOS REPORTES POR BAIRRO
    # ------------------------------------------------------
    contagem_bairros = {}
    contagem_alta = {}

    for r in reportes:
        bairro = (r.bairro or "").strip()
        prioridade = (r.prioridade or "").strip().lower()

        if not bairro:
            continue

        contagem_bairros[bairro] = contagem_bairros.get(bairro, 0) + 1

        if prioridade == "alta":
            contagem_alta[bairro] = contagem_alta.get(bairro, 0) + 1

    # bairros com muitos reportes
    for bairro, total in contagem_bairros.items():
        if total >= 5:
            alertas.append({
                "tipo": "Concentração de Reportes",
                "zona": bairro,
                "nivel": "Alto",
                "mensagem": f"O bairro/zona {bairro} acumulou {total} reportes e deve ser observado com prioridade.",
                "acao": "Verificar causas recorrentes e reforçar resposta municipal."
            })

    # bairros com muitos reportes de prioridade alta
    for bairro, total_alta in contagem_alta.items():
        if total_alta >= 3:
            alertas.append({
                "tipo": "Ocorrências Críticas",
                "zona": bairro,
                "nivel": "Crítico",
                "mensagem": f"O bairro/zona {bairro} registou {total_alta} reportes de prioridade alta.",
                "acao": "Avaliar situação no terreno e atuar com urgência."
            })

    # ------------------------------------------------------
    # 3) REMOVER DUPLICADOS MUITO PARECIDOS
    # ------------------------------------------------------
    vistos = set()
    alertas_filtrados = []

    for a in alertas:
        chave = (a["tipo"], a["zona"], a["mensagem"])
        if chave not in vistos:
            vistos.add(chave)
            alertas_filtrados.append(a)

    # ------------------------------------------------------
    # 4) ORDENAR ALERTAS: críticos primeiro
    # ------------------------------------------------------
    prioridade_alerta = {
        "Crítico": 0,
        "Alto": 1,
        "Médio": 2,
        "Baixo": 3
    }

    alertas_filtrados.sort(key=lambda x: prioridade_alerta.get(x["nivel"], 99))

    return alertas_filtrados

@app.route("/dashboard")
def dashboard():

    # =====================================================
    # 1. BUSCA DE DADOS (EXEMPLO - adapta ao teu projeto)
    # =====================================================
    reportes = Reporte.query.all()
    zonas = Zona.query.all()

    total_reportes = len(reportes)
    total_zonas = len(zonas)

    reportes_alta = Reporte.query.filter_by(nivel="alto").all()
    zonas_criticas = Zona.query.filter(Zona.indice_final >= 80).all()

    media_indice = (
        sum(z.indice_final for z in zonas) / len(zonas)
        if zonas else 0
    )

    # =====================================================
    # 2. ZONA CRÍTICA (SEGURA)
    # =====================================================
    zona_critica = (
        Zona.query.order_by(Zona.indice_final.desc()).first()
        if Zona.query.first()
        else None
    )

    nome_zona_critica = zona_critica.nome if zona_critica else "-"
    indice_zona_critica = zona_critica.indice_final if zona_critica else 0

    # =====================================================
    # 3. OUTROS CÁLCULOS
    # =====================================================
    ranking_zonas = Zona.query.order_by(Zona.indice_final.desc()).all()

    alerta_global = "ALTO RISCO" if media_indice > 70 else "NORMAL"

    score_urbano = (
        sum(r.score for r in reportes) / len(reportes)
        if reportes else 0
    )

    alertas = [
        r for r in reportes
        if getattr(r, "nivel", "") == "alto"
    ]

    # =====================================================
    # 4. RETORNO FINAL
    # =====================================================
    return render_template(
        "dashboard.html",
        reportes=reportes,
        zonas=zonas,
        total_reportes=total_reportes,
        total_zonas=total_zonas,
        reportes_alta=reportes_alta,
        zonas_criticas=zonas_criticas,
        media_indice=media_indice,
        nome_zona_critica=nome_zona_critica,
        indice_zona_critica=indice_zona_critica,
        ranking_zonas=ranking_zonas,
        alerta_global=alerta_global,
        score_urbano=score_urbano,
        alertas=alertas
    )

@app.route("/mapa")
def mapa():

    # ==========================
    # REPORTES
    # ==========================
    reportes_features = []

    for r in Reporte.query.all():
        feature = reporte_to_feature(r)
        if feature:
            reportes_features.append(feature)

    # ==========================
    # ZONAS
    # ==========================
    zonas_features = []

    for z in Zona.query.all():
        feature = zona_to_feature(z)
        if feature:
            zonas_features.append(feature)

    # ==========================
    # GEOJSON
    # ==========================
    reportes_geojson = {
        "type": "FeatureCollection",
        "features": reportes_features
    }

    zonas_geojson = {
        "type": "FeatureCollection",
        "features": zonas_features
    }

    # ==========================
    # TEMPLATE
    # ==========================
    return render_template(
        "mapa.html",
        reportes_geojson=reportes_geojson,
        zonas_geojson=zonas_geojson
    )


@app.route("/exportar_geojson")
def exportar_geojson():
    reportes = Reporte.query.all()

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for r in reportes:
        feature = reporte_to_feature(r)
        if feature:
            geojson["features"].append(feature)

    caminho = os.path.join(BASE_DIR, "reportes.geojson")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=4)

    return send_file(caminho, as_attachment=True)


@app.route("/api/resumo")
def api_resumo():

    reportes = Reporte.query.all()
    zonas = Zona.query.all()

    return jsonify({
        "total_reportes": len(reportes),
        "total_zonas": len(zonas),
        "reportes_alta": len([r for r in reportes if (r.prioridade or "").lower() == "alta"]),
        "zonas_criticas": len([z for z in zonas if (z.nivel_crescimento or "").lower() in ["crítico", "critico", "alto"]])
    })


@app.route("/api/alertas")
def api_alertas():

    zonas = Zona.query.all()

    alertas = []

    for z in zonas:
        if (z.indice_final or 0) >= 80:
            alertas.append({
                "zona": z.nome,
                "nivel": "CRITICO",
                "mensagem": "Zona em risco extremo"
            })

    return jsonify(alertas)


@app.route("/api/ranking")
def api_ranking():

    zonas = Zona.query.order_by(Zona.indice_final.desc()).limit(10).all()

    return jsonify([
        {
            "nome": z.nome,
            "indice": z.indice_final,
            "nivel": z.nivel_crescimento
        }
        for z in zonas
    ])


@app.route("/ia")
def ia_cidade():

    q = request.args.get("q", "").lower()

    reportes = Reporte.query.all()
    zonas = Zona.query.all()

    if "pior zona" in q:
        pior = max(zonas, key=lambda z: z.indice_final or 0)
        return {"resposta": f"A pior zona é {pior.nome} com índice {pior.indice_final}"}

    if "lixo" in q:
        total = len([r for r in reportes if "lixo" in (r.tipo_problema or "").lower()])
        return {"resposta": f"Existem {total} reportes de lixo"}

    if "resumo" in q:
        return {"resposta": f"Temos {len(reportes)} reportes e {len(zonas)} zonas"}

    return {"resposta": "Pergunta não reconhecida"}



    # =========================
    # CASO: lixo
    # =========================
    if "lixo" in pergunta:

        lixo = [
            r for r in reportes
            if "lixo" in (r.tipo_problema or "").lower()
            or "lixo" in (r.descricao or "").lower()
        ]

        return jsonify({
            "resposta": f"Existem {len(lixo)} reportes relacionados com lixo na cidade"
        })

    # =========================
    # CASO: resumo
    # =========================
    if "resumo" in pergunta:

        return jsonify({
            "resposta": f"A cidade tem {len(reportes)} reportes e {len(zonas)} zonas monitoradas"
        })

    # =========================
    # CASO: não reconhecido
    # =========================
    return jsonify({
        "resposta": "Pergunta não reconhecida. Use: pior zona, lixo, resumo"
    })


@app.route("/api/reportes_geojson")
def api_reportes_geojson():
    reportes = Reporte.query.all()
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for r in reportes:
        feature = reporte_to_feature(r)
        if feature:
            geojson["features"].append(feature)

    return jsonify(geojson)


@app.route("/api/zonas_geojson")
def api_zonas_geojson():
    zonas = Zona.query.all()
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for z in zonas:
        feature = zona_to_feature(z)
        if feature:
            geojson["features"].append(feature)

    return jsonify(geojson)


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            return redirect(url_for("dashboard"))

        return "Login inválido"

    return render_template("login.html")


# =========================================================
# INICIALIZAÇÃO DA BASE DE DADOS
# =========================================================
with app.app_context():
    db.create_all()

# ==========================================================
# EXPORTAÇÃO DE DADOS GEOESPACIAIS
# ==========================================================

@app.route("/exportar/reportes_geojson")
def exportar_reportes_geojson():
    reportes = Reporte.query.order_by(Reporte.id.desc()).all()

    features = []
    for r in reportes:
        if r.latitude is not None and r.longitude is not None:
            features.append({
                "type": "Feature",
                "properties": {
                    "id": r.id,
                    "nome": r.nome,
                    "bairro": r.bairro,
                    "tipo_problema": r.tipo_problema,
                    "descricao": r.descricao,
                    "alerta_ia": r.alerta_ia,
                    "prioridade": r.prioridade,
                    "nivel_risco": r.nivel_risco,
                    "setor_responsavel": r.setor_responsavel,
                    "acao_recomendada": r.acao_recomendada,
                    "estado": r.estado,
                    "data": r.data
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [r.longitude, r.latitude]
                }
            })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return Response(
        json.dumps(geojson, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=reportes.geojson"}
    )


@app.route("/exportar/zonas_geojson")
def exportar_zonas_geojson():
    zonas = Zona.query.order_by(Zona.id.desc()).all()

    features = []
    for z in zonas:
        feature = zona_to_feature(z)
        if feature:
            features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return Response(
        json.dumps(geojson, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=zonas.geojson"}
    )


@app.route("/exportar/zonas_kml")
def exportar_zonas_kml():
    zonas = Zona.query.order_by(Zona.id.desc()).all()

    kml = []
    kml.append('<?xml version="1.0" encoding="UTF-8"?>')
    kml.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    kml.append('<Document>')
    kml.append('<name>Zonas GeoAI-CIM Nampula</name>')

    for z in zonas:
        if not z.poligono:
            continue

        try:
            coords = json.loads(z.poligono)
        except Exception:
            continue

        if not isinstance(coords, list) or len(coords) < 3:
            continue

        coordenadas_kml = []
        for ponto in coords:
            if isinstance(ponto, list) and len(ponto) == 2:
                lat = ponto[0]
                lon = ponto[1]
                coordenadas_kml.append(f"{lon},{lat},0")

        if len(coordenadas_kml) < 3:
            continue

        # fechar polígono
        if coordenadas_kml[0] != coordenadas_kml[-1]:
            coordenadas_kml.append(coordenadas_kml[0])

        descricao = f"""
        <![CDATA[
        <b>Zona:</b> {z.nome}<br>
        <b>Índice:</b> {z.indice_crescimento}<br>
        <b>Classe:</b> {z.classe_crescimento}<br>
        <b>Estado:</b> {z.estado_crescimento}<br>
        <b>Alerta:</b> {z.alerta_urbano}<br>
        <b>Nível:</b> {z.nivel_crescimento}<br>
        <b>Ação:</b> {z.acao_recomendada_zona}
        ]]>
        """

        kml.append("<Placemark>")
        kml.append(f"<name>{z.nome}</name>")
        kml.append(f"<description>{descricao}</description>")
        kml.append("<Polygon>")
        kml.append("<outerBoundaryIs><LinearRing><coordinates>")
        kml.append(" ".join(coordenadas_kml))
        kml.append("</coordinates></LinearRing></outerBoundaryIs>")
        kml.append("</Polygon>")
        kml.append("</Placemark>")

    kml.append("</Document>")
    kml.append("</kml>")

    kml_content = "\n".join(kml)

    return Response(
        kml_content,
        mimetype="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": "attachment; filename=zonas.kml"}
    )

# ==========================================================
# UPGRADE DA TABELA ZONA
# ==========================================================

@app.route("/upgrade_zona_105")
def upgrade_zona_105():
    colunas_novas = [
        ("indice_manual", "FLOAT DEFAULT 0"),
        ("ajuste_ia", "FLOAT DEFAULT 0"),
        ("indice_final", "FLOAT DEFAULT 0"),
        ("pressao_reportes", "VARCHAR(255)"),
        ("previsao_risco", "VARCHAR(255)"),
        ("fonte_analise", "VARCHAR(255)"),
        ("sinal_satelite", "VARCHAR(100)"),
        ("sinal_sensor", "VARCHAR(100)")
    ]

    conn = db.engine.raw_connection()
    cursor = conn.cursor()

    try:
        # ver colunas atuais da tabela zona
        cursor.execute("PRAGMA table_info(zona)")
        existentes = [linha[1] for linha in cursor.fetchall()]

        adicionadas = []

        for nome_coluna, tipo_sql in colunas_novas:
            if nome_coluna not in existentes:
                sql = f"ALTER TABLE zona ADD COLUMN {nome_coluna} {tipo_sql}"
                cursor.execute(sql)
                adicionadas.append(nome_coluna)

        conn.commit()

        if adicionadas:
            return (
                "Upgrade 10.5A concluído com sucesso.<br>"
                "Colunas adicionadas: " + ", ".join(adicionadas)
            )
        else:
            return "Upgrade 10.5A já tinha sido aplicado. Nenhuma coluna nova foi adicionada."

    except Exception as e:
        conn.rollback()
        return f"Erro no upgrade 10.5A: {str(e)}"

    finally:
        cursor.close()
        conn.close()

# =========================================================
# EXECUTAR
# =========================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000)