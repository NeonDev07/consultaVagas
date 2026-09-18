import datetime
import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

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
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Sistema inicializado. Pronto para buscas reais na web via Scraping."
    ]


def log_console(mensagem):
    """Regista mensagens no console de saída do Streamlit."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.console_logs.append(f"[{timestamp}] {mensagem}")


# ================================================
# BUSCA DE VAGAS NA INTERNET (WEB SCRAPING SEM API)
# ================================================
def buscar_vagas_internet(
    cargo="", senioridade="", cidade="", bairro="", salario_min=0, API_KEY=""
):
    """Realiza Web Scraping em portais públicos para buscar vagas sem depender de APIs pagas."""
    
    # Agrupa os termos de busca para montar a URL
    termos = [p for p in [cargo, senioridade, cidade, bairro] if p and p.strip()]
    termo_busca = "-".join(termos).replace(" ", "-").lower() if termos else "vagas"

    # Utilizando o portal Vagas.com.br como alvo da raspagem
    url = f"https://www.vagas.com.br/vagas-de-{termo_busca}"

    log_console(f"WEB SCRAPING: A extrair dados da URL: {url}")

    # O User-Agent disfarça o nosso código, simulando que é um navegador real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            vagas_processadas = []

            # O portal Vagas.com.br costuma armazenar cada vaga dentro de uma <li> com a classe "vaga"
            cards_vagas = soup.find_all("li", class_="vaga")
            
            log_console(f"SCRAPING CONCLUÍDO: {len(cards_vagas)} vagas extraídas do HTML.")

            for idx, card in enumerate(cards_vagas):
                # 1. Extração do Título
                titulo_elem = card.find("h2", class_="cargo")
                titulo = titulo_elem.text.strip() if titulo_elem else "Cargo não especificado"

                # 2. Extração da Empresa
                empresa_elem = card.find("span", class_="emprVaga")
                empresa = empresa_elem.text.strip() if empresa_elem else "Empresa Confidencial"

                # 3. Extração da Localização
                local_elem = card.find("span", class_="vaga-local")
                local_vaga = local_elem.text.strip() if local_elem else cidade

                # 4. Extração da Descrição/Resumo
                desc_elem = card.find("div", class_="detalhes")
                descricao = desc_elem.text.strip() if desc_elem else "Ver detalhes no link."

                # 5. Extração do Link da Vaga
                link_elem = card.find("a", href=True)
                link_completo = f"https://www.vagas.com.br{link_elem['href']}" if link_elem else "#"

                vagas_processadas.append(
                    {
                        "id": idx + 1,
                        "nome": titulo,
                        "empresa": empresa,
                        "cidade": local_vaga,
                        "salario": "A combinar / Consultar no portal" if salario_min == 0 else f"Filtro tentado: > R${salario_min}",
                        "descricao": descricao[:250] + "...",
                        "link_vaga": link_completo,
                        "email_contato": f"rh@{empresa.lower().replace(' ', '').replace('-', '')}.com.br",
                    }
                )

            return vagas_processadas
        
        else:
            log_console(f"ERROR HTTP {response.status_code}: O site bloqueou o acesso ou está indisponível.")
            return []
            
    except Exception as e:
        log_console(f"EXCEPTION: Falha durante o scraping - {str(e)}")
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
    st.header("🔑 API Key")
    api_jooble = st.text_input(
        "Chave API Jooble", help="A versão atual utiliza web scraping gratuito. Este campo não é mais obrigatório."
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
                "Nome da Vaga / Cargo", placeholder="Ex: Analista, Python, Vendas"
            )
            filtro_senioridade = st.selectbox(
                "Senioridade", ["", "Estágio", "Júnior", "Pleno", "Sênior", "Especialista"]
            )

        with col2:
            filtro_cidade = st.text_input(
                "Cidade", placeholder="Ex: São Paulo, Rio de Janeiro"
            )
            filtro_bairro = st.text_input(
                "Bairro / Região", placeholder="Ex: Jabaquara, Centro"
            )

        with col3:
            filtro_salario = st.number_input(
                "Valor Min de Salário (R$)", min_value=0, step=500, value=0, help="Deixe 0 para ignorar"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_buscar = st.form_submit_button(
                "🌐 Buscar Vagas na Internet", use_container_width=True
            )

    if btn_buscar:
        with st.spinner("A extrair vagas da web..."):
            vagas = buscar_vagas_internet(
                cargo=filtro_nome,
                senioridade=filtro_senioridade,
                cidade=filtro_cidade,
                bairro=filtro_bairro,
                salario_min=filtro_salario,
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