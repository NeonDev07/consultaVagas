import datetime
import os
import smtplib
import time
import re
import urllib.parse
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

if "historico_envios" not in st.session_state:
    st.session_state.historico_envios = []

if "busca_executada" not in st.session_state:
    st.session_state.busca_executada = False

if "vagas_filtradas" not in st.session_state:
    st.session_state.vagas_filtradas = []

if "console_logs" not in st.session_state:
    st.session_state.console_logs = [
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Sistema inicializado."
    ]

def log_console(mensagem):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.console_logs.append(f"[{timestamp}] {mensagem}")

# ================================================
# BUSCA DIRETA (WEB SCRAPING DE VAGAS ESTRUTURADAS)
# ================================================
def buscar_vagas_internet(
    cargo="", senioridade="", cidade="", bairro="", salario_min=0, portal="LinkedIn"
):
    vagas_processadas = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # ------------------ SCRAPING LINKEDIN ------------------
    if portal == "LinkedIn":
        termo_busca = f"{cargo} {senioridade}".strip() or "vagas"
        local_busca = f"{cidade} {bairro}".strip() or "Brasil"

        url = f"https://br.linkedin.com/jobs/search?keywords={urllib.parse.quote(termo_busca)}&location={urllib.parse.quote(local_busca)}&position=1&pageNum=0"
        log_console(f"SCRAPING {portal}: Procurando '{termo_busca}' em '{local_busca}'")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            cards_vagas = soup.find_all("div", class_="base-search-card")

            for idx, card in enumerate(cards_vagas):
                titulo_elem = card.find("h3", class_="base-search-card__title")
                titulo = titulo_elem.text.strip() if titulo_elem else "Título indisponível"

                empresa_elem = card.find("h4", class_="base-search-card__subtitle")
                empresa = empresa_elem.text.strip() if empresa_elem else "Empresa Confidencial"

                local_elem = card.find("span", class_="job-search-card__location")
                local = local_elem.text.strip() if local_elem else local_busca

                link_elem = card.find("a", class_="base-card__full-link", href=True)
                link = link_elem["href"].split("?")[0] if link_elem else "#"

                email_base = f"rh@{empresa.lower().replace(' ', '').replace('.', '').replace(',', '')}.com"

                vagas_processadas.append({
                    "id": idx + 1,
                    "nome": titulo,
                    "empresa": empresa,
                    "cidade": local,
                    "salario": "A combinar" if salario_min == 0 else f"Alvo: > R${salario_min}",
                    "descricao": "Vaga estruturada via LinkedIn.",
                    "link_vaga": link,
                    "email_contato": email_base,
                    "portal": portal
                })
        except Exception as e:
            log_console(f"Erro no LinkedIn: {str(e)}")

    # ------------------ SCRAPING VAGAS.COM.BR ------------------
    elif portal == "Vagas.com.br":
        termos = [p for p in [cargo, senioridade, cidade, bairro] if p and p.strip()]
        termo_busca = "-".join(termos).replace(" ", "-").lower() if termos else "vagas"
        url = f"https://www.vagas.com.br/vagas-de-{termo_busca}"
        
        log_console(f"SCRAPING {portal}: Acessando URL {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            cards_vagas = soup.find_all("li", class_="vaga")

            for idx, card in enumerate(cards_vagas):
                titulo_elem = card.find("h2", class_="cargo")
                titulo = titulo_elem.text.strip() if titulo_elem else "Cargo não especificado"

                empresa_elem = card.find("span", class_="emprVaga")
                empresa = empresa_elem.text.strip() if empresa_elem else "Empresa Confidencial"

                local_elem = card.find("span", class_="vaga-local")
                local = local_elem.text.strip() if local_elem else cidade

                desc_elem = card.find("div", class_="detalhes")
                descricao = desc_elem.text.strip() if desc_elem else "Ver detalhes no link."

                link_elem = card.find("a", href=True)
                link = f"https://www.vagas.com.br{link_elem['href']}" if link_elem else "#"

                # REGEX: Tenta achar um email real perdido na descrição
                emails_achados = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', descricao)
                email_contato = emails_achados[0] if emails_achados else f"rh@{empresa.lower().replace(' ', '').replace('-', '')}.com.br"

                vagas_processadas.append({
                    "id": len(vagas_processadas) + 1,
                    "nome": titulo,
                    "empresa": empresa,
                    "cidade": local,
                    "salario": "A combinar" if salario_min == 0 else f"Alvo: > R${salario_min}",
                    "descricao": descricao[:200] + "...",
                    "link_vaga": link,
                    "email_contato": email_contato,
                    "portal": portal
                })
        except Exception as e:
            log_console(f"Erro no Vagas.com.br: {str(e)}")

    return vagas_processadas

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

        log_console(f"SUCCESS: E-mail enviado com sucesso para {email_destino}")
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        log_console(f"ERROR: Erro no envio para {email_destino}. Motivo: {str(e)}")
        return False, f"Erro ao enviar e-mail: {str(e)}"

# ================================================
# INTERFACE DO USUÁRIO
# ================================================
st.title("🌐 Automação de Vagas & Candidaturas")

with st.sidebar:
    st.header("⚙️ Configurações de Envio")
    gmail_user = st.text_input("O seu E-mail Gmail")
    gmail_password = st.text_input("Senha de App Gmail", type="password")

    st.markdown("---")
    st.header("📄 Currículo")
    arquivo_curriculo = st.file_uploader("Fazer upload do Currículo (PDF)", type=["pdf", "docx"])

    caminho_temp_curriculo = None
    if arquivo_curriculo:
        caminho_temp_curriculo = os.path.join("temp_" + arquivo_curriculo.name)
        with open(caminho_temp_curriculo, "wb") as f:
            f.write(arquivo_curriculo.getbuffer())
        st.success("Currículo anexado!")

tab_busca, tab_relatorios, tab_console = st.tabs(
    ["🔍 Buscar na Web", "📊 Relatório de Candidaturas", "💻 Console de Saída"]
)

# ------------------------------------------------
# ABA 1: BUSCA DE VAGAS EM TEMPO REAL
# ------------------------------------------------
with tab_busca:
    st.subheader("🔎 Pesquisa de Vagas")

    with st.form(key="form_busca_web"):
        col1, col2, col3 = st.columns(3)

        with col1:
            filtro_nome = st.text_input("Nome da Vaga / Cargo")
            filtro_portal = st.selectbox("Portal de Vagas (Filtro de Site)", ["LinkedIn", "Vagas.com.br"])

        with col2:
            filtro_cidade = st.text_input("Cidade")
            filtro_senioridade = st.selectbox("Senioridade", ["", "Estágio", "Júnior", "Pleno", "Sênior", "Especialista"])

        with col3:
            filtro_bairro = st.text_input("Bairro / Região")
            filtro_salario = st.number_input("Valor Min de Salário (R$)", min_value=0, step=500, value=0)
            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_buscar = st.form_submit_button("🌐 Buscar Vagas", use_container_width=True)

    if btn_buscar:
        with st.spinner(f"Extraindo vagas do {filtro_portal}..."):
            vagas = buscar_vagas_internet(
                cargo=filtro_nome,
                senioridade=filtro_senioridade,
                cidade=filtro_cidade,
                bairro=filtro_bairro,
                salario_min=filtro_salario,
                portal=filtro_portal
            )
            st.session_state.vagas_filtradas = vagas
            st.session_state.busca_executada = True

    st.markdown("---")

    if st.session_state.busca_executada:
        vagas = st.session_state.vagas_filtradas
        st.subheader(f"📋 Encontradas: {len(vagas)} vagas no {filtro_portal if vagas else ''}")

        for vaga in vagas:
            with st.container():
                st.markdown(
                    f"""
                    <div class="vaga-card">
                        <h3>{vaga['nome']}</h3>
                        <p><b>{vaga['empresa']}</b> | <b>Local:</b> {vaga['cidade']} | <b>Portal:</b> {vaga['portal']}</p>
                        <p><b>Resumo:</b> {vaga['descricao']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2 = st.columns(2)
                
                with c1:
                    # NOVIDADE: O e-mail agora é um campo editável pelo utilizador!
                    email_digitado = st.text_input("E-mail de Destino (Edite se necessário):", value=vaga["email_contato"], key=f"input_email_{vaga['id']}")
                    
                    if st.button(f"📧 Enviar Candidatura", key=f"btn_email_{vaga['id']}"):
                        if not gmail_user or not gmail_password:
                            st.error("Preencha as suas credenciais de App do Gmail na barra lateral.")
                        elif not caminho_temp_curriculo:
                            st.error("Anexe o seu currículo na barra lateral.")
                        else:
                            sucesso, msg = enviar_email_gmail(
                                email_digitado,
                                vaga["nome"],
                                caminho_temp_curriculo,
                                gmail_user,
                                gmail_password,
                            )
                            if sucesso:
                                st.success(msg)
                                st.session_state.historico_envios.append(
                                    {
                                        "Data/Hora": time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "Vaga": vaga["nome"],
                                        "Empresa": vaga["empresa"],
                                        "Destinatário": email_digitado,
                                        "Portal": vaga["portal"],
                                        "Status": "Enviado",
                                    }
                                )
                            else:
                                st.error(msg)

                with c2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.link_button("🔗 Abrir Link Oficial da Vaga", vaga["link_vaga"], use_container_width=True)

# ------------------------------------------------
# ABA 2: RELATÓRIO DE CANDIDATURAS
# ------------------------------------------------
with tab_relatorios:
    st.subheader("📊 Histórico de Candidaturas Enviadas")
    if st.session_state.historico_envios:
        df_relatorio = pd.DataFrame(st.session_state.historico_envios)
        st.dataframe(df_relatorio, use_container_width=True)
        csv = df_relatorio.to_csv(index=False).encode("utf-8")
        st.download_button(label="📥 Descarregar Relatório", data=csv, file_name="historico_candidaturas.csv", mime="text/csv")
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
            st.session_state.console_logs = [f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Console limpo."]
            st.rerun()

    log_text = "\n".join(st.session_state.console_logs)
    st.text_area("Saída de Execução (Logs)", value=log_text, height=400, disabled=True)