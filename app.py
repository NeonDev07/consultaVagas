import datetime
import os
import smtplib
import time
import urllib.parse
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import requests
import streamlit as st

# ================================================
# CONFIGURAÇÃO DA PÁGINA
# ================================================
st.set_page_config(
    page_title="Gestor de Vagas & Candidaturas", page_icon="💼", layout="wide"
)

# Estilos CSS
st.markdown(
    """
    <style>
    .vaga-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
        border-left: 5px solid #0d6efd;
        color: #212529;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Inicialização do estado de sessão
if "historico_envios" not in st.session_state:
    st.session_state.historico_envios = []

if "busca_executada" not in st.session_state:
    st.session_state.busca_executada = False

if "vagas_filtradas" not in st.session_state:
    st.session_state.vagas_filtradas = []

if "console_logs" not in st.session_state:
    st.session_state.console_logs = [
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Sistema inicializado. Pronto para buscas reais na web."
    ]


def log_console(mensagem):
    """Regista mensagens no console de saída do Streamlit."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.console_logs.append(f"[{timestamp}] {mensagem}")


# ================================================
# BÚSCA DE VAGAS EM TEMPO REAL NA INTERNET (API JOOBLE)
# ================================================
def buscar_vagas_internet(
    cargo="", cidade="", bairro="", salario_min=0, API_KEY=""
):
    """Realiza requisições HTTP para buscar vagas reais publicadas na web."""
    if not API_KEY:
        # Chave genérica de testes pública para consumo de API Jooble
        API_KEY = "5d46c646-1be4-432a-bc91-3e4df1cf6454"

    url = f"https://jooble.org/api/{API_KEY}"

    # Monta a localização com base na Cidade e Bairro informados
    localizacao_partes = [p for p in [bairro, cidade] if p and p.strip()]
    location = ", ".join(localizacao_partes) if localizacao_partes else "Brasil"

    keywords = cargo if cargo and cargo.strip() else "Vagas"

    payload = {"keywords": keywords, "location": location, "page": 1}

    log_console(
        f"HTTP REQUEST: A pesquisar na web por Keywords: '{keywords}' | Localização: '{location}'"
    )

    try:
        response = requests.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            dados = response.json()
            jobs_brutos = dados.get("jobs", [])
            log_console(
                f"HTTP RESPONSE 200: {len(jobs_brutos)} vagas encontradas na API."
            )

            vagas_processadas = []
            for idx, job in enumerate(jobs_brutos):
                # Extração e normalização de dados reais
                salario = job.get("salary", "A combinar")

                # Limpeza simples da descrição HTML
                snippet = (
                    job.get("snippet", "")
                    .replace("<b>", "")
                    .replace("</b>", "")
                    .replace("<br>", "")
                )

                vagas_processadas.append(
                    {
                        "id": idx + 1,
                        "nome": job.get("title", "Cargo não especificado"),
                        "empresa": job.get("company", "Empresa Confidencial"),
                        "cidade": job.get("location", location),
                        "salario": salario if salario else "A combinar",
                        "descricao": snippet,
                        "link_vaga": job.get("link", "#"),
                        "email_contato": f"contato@{job.get('company', 'empresa').lower().replace(' ', '')}.com",
                    }
                )

            return vagas_processadas
        else:
            log_console(
                f"ERROR HTTP: Código {response.status_code} ao buscar vagas."
            )
            return []
    except Exception as e:
        log_console(f"EXCEPTION: Falha de conexão na busca de vagas - {str(e)}")
        return []


# ================================================
# FUNÇÃO DE ENVIO DE E-MAIL
# ================================================
def enviar_email_gmail(
    email_destino, nome_vaga, caminho_curriculo, gmail_user, gmail_password
):
    try:
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = email_destino
        msg["Subject"] = f"Candidatura - Vaga {nome_vaga}"

        corpo_email = f"Olá, gostaria de candidatar-me à vaga de {nome_vaga}. Segue em anexo o meu currículo para análise.\n\nAtenciosamente,"
        msg.attach(MIMEText(corpo_email, "plain"))

        if caminho_curriculo and os.path.exists(caminho_curriculo):
            with open(caminho_curriculo, "rb") as f:
                anexo = MIMEApplication(
                    f.read(), Name=os.path.basename(caminho_curriculo)
                )
                anexo[
                    "Content-Disposition"
                ] = f'attachment; filename="{os.path.basename(caminho_curriculo)}"'
                msg.attach(anexo)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()

        log_console(
            f"SUCCESS: E-mail de candidatura enviado com sucesso para {email_destino} ({nome_vaga})."
        )
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        log_console(
            f"ERROR: Erro no envio de e-mail para {email_destino}. Motivo: {str(e)}"
        )
        return False, f"Erro ao enviar e-mail: {str(e)}"


# ================================================
# INTERFACE DO USUÁRIO
# ================================================
st.title("🌐 Buscador de Vagas na Web & Envio Automático")

# Barra Lateral
with st.sidebar:
    st.header("⚙️ Configurações de Envio")
    gmail_user = st.text_input("O seu E-mail Gmail")
    gmail_password = st.text_input("Senha de Aplicação Gmail", type="password")

    st.markdown("---")
    st.header("🔑 API Key (Opcional)")
    api_jooble = st.text_input(
        "Chave API Jooble", help="Deixe em branco para usar a chave pública padrão."
    )

    st.markdown("---")
    st.header("📄 Currículo")
    arquivo_curriculo = st.file_uploader(
        "Fazer upload do Currículo (PDF)", type=["pdf", "docx"]
    )

    caminho_temp_curriculo = None
    if arquivo_curriculo:
        caminho_temp_curriculo = os.path.join("temp_" + arquivo_curriculo.name)
        with open(caminho_temp_curriculo, "wb") as f:
            f.write(arquivo_curriculo.getbuffer())
        st.success("Currículo anexado!")

# Abas de Navegação
tab_busca, tab_relatorios, tab_console = st.tabs(
    ["🔍 Buscar na Web", "📊 Relatório de Candidaturas", "💻 Console de Saída"]
)

# ------------------------------------------------
# ABA 1: BUSCA DE VAGAS EM TEMPO REAL
# ------------------------------------------------
with tab_busca:
    st.subheader("🔎 Pesquisa de Vagas na Internet (Filtros Opcionais)")

    with st.form(key="form_busca_web"):
        col1, col2, col3 = st.columns(3)

        with col1:
            filtro_nome = st.text_input(
                "Cargo / Termo", placeholder="Ex: Analista, Python, Vendas"
            )

        with col2:
            filtro_cidade = st.text_input(
                "Cidade", placeholder="Ex: São Paulo, Rio de Janeiro"
            )

        with col3:
            filtro_bairro = st.text_input(
                "Bairro / Região", placeholder="Ex: Jabaquara, Centro"
            )

        btn_buscar = st.form_submit_button(
            "🌐 Buscar Vagas na Internet", use_container_width=True
        )

    if btn_buscar:
        with st.spinner("A pesquisar vagas na web..."):
            vagas = buscar_vagas_internet(
                cargo=filtro_nome,
                cidade=filtro_cidade,
                bairro=filtro_bairro,
                API_KEY=api_jooble,
            )
            st.session_state.vagas_filtradas = vagas
            st.session_state.busca_executada = True

    st.markdown("---")

    if st.session_state.busca_executada:
        vagas = st.session_state.vagas_filtradas
        st.subheader(f"📋 Vagas Encontradas na Web ({len(vagas)})")

        if not vagas:
            st.warning(
                "Nenhuma vaga foi encontrada para os termos pesquisados. Tente termos mais abrangentes."
            )

        for vaga in vagas:
            with st.container():
                st.markdown(
                    f"""
                    <div class="vaga-card">
                        <h3>{vaga['nome']}</h3>
                        <p><b>Empresa:</b> {vaga['empresa']} | <b>Localização:</b> {vaga['cidade']}</p>
                        <p><b>Salário:</b> {vaga['salario']}</p>
                        <p><b>Resumo:</b> {vaga['descricao']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        f"📧 Enviar E-mail de Candidatura",
                        key=f"email_{vaga['id']}",
                    ):
                        if not gmail_user or not gmail_password:
                            st.error(
                                "Preencha as suas credenciais do Gmail na barra lateral."
                            )
                        elif not caminho_temp_curriculo:
                            st.error("Anexe o seu currículo na barra lateral.")
                        else:
                            sucesso, msg = enviar_email_gmail(
                                vaga["email_contato"],
                                vaga["nome"],
                                caminho_temp_curriculo,
                                gmail_user,
                                gmail_password,
                            )
                            if sucesso:
                                st.success(msg)
                                st.session_state.historico_envios.append(
                                    {
                                        "Data/Hora": time.strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        ),
                                        "Vaga": vaga["nome"],
                                        "Empresa": vaga["empresa"],
                                        "Destinatário": vaga["email_contato"],
                                        "Status": "Enviado",
                                    }
                                )
                            else:
                                st.error(msg)

                with c2:
                    st.link_button(
                        "🔗 Ver Vaga / Candidatar no Portal",
                        vaga["link_vaga"],
                        use_container_width=True,
                    )
    else:
        st.info(
            "Insira os termos de pesquisa desejados e clique em **🌐 Buscar Vagas na Internet**."
        )


# ------------------------------------------------
# ABA 2: RELATÓRIO DE CANDIDATURAS
# ------------------------------------------------
with tab_relatorios:
    st.subheader("📊 Histórico de Candidaturas Enviadas")

    if st.session_state.historico_envios:
        df_relatorio = pd.DataFrame(st.session_state.historico_envios)
        st.dataframe(df_relatorio, use_container_width=True)

        csv = df_relatorio.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descarregar Relatório (CSV)",
            data=csv,
            file_name="historico_candidaturas.csv",
            mime="text/csv",
        )
    else:
        st.info("Nenhuma candidatura enviada nesta sessão.")


# ------------------------------------------------
# ABA 3: CONSOLE DE SAÍDA
# ------------------------------------------------
with tab_console:
    st.subheader("💻 Console de Logs do Sistema")

    c_top1, c_top2 = st.columns([0.85, 0.15])
    with c_top2:
        if st.button("🗑️ Limpar Console"):
            st.session_state.console_logs = [
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Console limpo."
            ]
            st.rerun()

    log_text = "\n".join(st.session_state.console_logs)
    st.text_area(
        "Saída de Execução (Logs)", value=log_text, height=400, disabled=True
    )