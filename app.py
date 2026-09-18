import datetime
import os
import smtplib
import time
import urllib.parse
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import streamlit as st

# ================================================
# CONFIGURAÇÃO DA PÁGINA E ESTILO VISUAL
# ================================================
st.set_page_config(
    page_title="Gestor de Vagas & Candidaturas", page_icon="💼", layout="wide"
)

st.markdown(
    """
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        background-color: #0d6efd;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    .vaga-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
        border-left: 5px solid #0d6efd;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ================================================
# BASE DE DADOS SIMULADA (MOCK) DE VAGAS
# ================================================
@st.cache_data
def carregar_vagas():
    return pd.DataFrame(
        [
            {
                "id": 1,
                "nome": "Desenvolvedor Python Full Stack",
                "salario": 8000.00,
                "senioridade": "Pleno",
                "cidade": "São Paulo",
                "bairro": "Pinheiros",
                "email_contato": "recrutamento@techcorp.com",
                "whatsapp_contato": "5511999999999",
                "telefone": "(11) 3333-4444",
            },
            {
                "id": 2,
                "nome": "Engenheiro de Dados",
                "salario": 12000.00,
                "senioridade": "Sênior",
                "cidade": "São Paulo",
                "bairro": "Itaim Bibi",
                "email_contato": "vagas@datafirm.com",
                "whatsapp_contato": "5511988888888",
                "telefone": "(11) 3333-5555",
            },
            {
                "id": 3,
                "nome": "Desenvolvedor Python Junior",
                "salario": 4500.00,
                "senioridade": "Júnior",
                "cidade": "Rio de Janeiro",
                "bairro": "Botafogo",
                "email_contato": "hr@rhsolutions.com",
                "whatsapp_contato": "5521977777777",
                "telefone": "(21) 2222-3333",
            },
        ]
    )


# Inicialização de estados na sessão
if "historico_envios" not in st.session_state:
    st.session_state.historico_envios = []

if "busca_executada" not in st.session_state:
    st.session_state.busca_executada = False

if "vagas_filtradas" not in st.session_state:
    st.session_state.vagas_filtradas = pd.DataFrame()

if "console_logs" not in st.session_state:
    st.session_state.console_logs = [
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Console inicializado com sucesso."
    ]


def log_console(mensagem):
    """Registra eventos no console de saída da aplicação."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state.console_logs.append(f"[{timestamp}] {mensagem}")


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

        corpo_email = f"Olá, estou enviando o currículo para consulta, referente a vaga {nome_vaga}, atenciosamente."
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
            f"SUCCESS: E-mail enviado para {email_destino} referente à vaga '{nome_vaga}'."
        )
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        log_console(
            f"ERROR: Falha ao enviar e-mail para {email_destino}. Motivo: {str(e)}"
        )
        return False, f"Erro ao enviar e-mail: {str(e)}"


# ================================================
# INTERFACE DO USUÁRIO
# ================================================
st.title("💼 Buscador de Vagas & Envio de Candidaturas")

# Sidebar - Credenciais e Arquivos
with st.sidebar:
    st.header("⚙️ Configurações de Envio")
    gmail_user = st.text_input("Seu E-mail Gmail")
    gmail_password = st.text_input(
        "Senha de App do Gmail",
        type="password",
        help="Crie uma Senha de App no painel de segurança da sua Conta Google.",
    )

    st.markdown("---")
    st.header("📄 Seu Currículo")
    arquivo_curriculo = st.file_uploader(
        "Upload do Currículo (PDF/DOCX)", type=["pdf", "docx"]
    )

    caminho_temp_curriculo = None
    if arquivo_curriculo:
        caminho_temp_curriculo = os.path.join("temp_" + arquivo_curriculo.name)
        with open(caminho_temp_curriculo, "wb") as f:
            f.write(arquivo_curriculo.getbuffer())
        st.success("Currículo carregado com sucesso!")

# Navegação por Abas
tab_busca, tab_relatorios, tab_console = st.tabs(
    ["🔍 Buscar Vagas", "📊 Relatório de Envios", "💻 Console de Saída"]
)

# ------------------------------------------------
# ABA 1: BUSCA DE VAGAS
# ------------------------------------------------
with tab_busca:
    st.subheader("🔍 Parâmetros de Busca (Opções Flexíveis)")

    with st.form(key="form_busca"):
        col1, col2, col3 = st.columns(3)

        with col1:
            filtro_nome = st.text_input(
                "Nome da Vaga / Cargo", placeholder="Ex: Python"
            )
            filtro_senioridade = st.selectbox(
                "Senioridade", ["Todas", "Júnior", "Pleno", "Sênior"]
            )

        with col2:
            filtro_cidade = st.text_input(
                "Cidade", placeholder="Ex: São Paulo"
            )
            filtro_bairro = st.text_input("Bairro", placeholder="Ex: Pinheiros")

        with col3:
            filtro_salario_min = st.number_input(
                "Salário Mínimo (R$)", value=0.0, step=500.0
            )

        btn_buscar = st.form_submit_button(
            "🔎 Buscar Vagas", use_container_width=True
        )

    if btn_buscar:
        df_vagas = carregar_vagas()

        # Aplicando filtros apenas se preenchidos
        if filtro_nome and filtro_nome.strip():
            df_vagas = df_vagas[
                df_vagas["nome"].str.contains(
                    filtro_nome.strip(), case=False, na=False
                )
            ]

        if filtro_senioridade != "Todas":
            df_vagas = df_vagas[df_vagas["senioridade"] == filtro_senioridade]

        if filtro_cidade and filtro_cidade.strip():
            df_vagas = df_vagas[
                df_vagas["cidade"].str.contains(
                    filtro_cidade.strip(), case=False, na=False
                )
            ]

        if filtro_bairro and filtro_bairro.strip():
            df_vagas = df_vagas[
                df_vagas["bairro"].str.contains(
                    filtro_bairro.strip(), case=False, na=False
                )
            ]

        if filtro_salario_min > 0:
            df_vagas = df_vagas[df_vagas["salario"] >= filtro_salario_min]

        st.session_state.vagas_filtradas = df_vagas
        st.session_state.busca_executada = True
        log_console(
            f"QUERY: Consulta realizada. {len(df_vagas)} vaga(s) encontrada(s)."
        )

    st.markdown("---")

    if st.session_state.busca_executada:
        df_vagas = st.session_state.vagas_filtradas
        st.subheader(f"📋 Vagas Encontradas ({len(df_vagas)})")

        if df_vagas.empty:
            st.warning(
                "Nenhuma vaga foi encontrada com os filtros selecionados."
            )

        for idx, vaga in df_vagas.iterrows():
            with st.container():
                st.markdown(
                    f"""
                    <div class="vaga-card">
                        <h3>{vaga['nome']}</h3>
                        <p><b>Senioridade:</b> {vaga['senioridade']} | <b>Salário:</b> R$ {vaga['salario']:.2f}</p>
                        <p><b>Localização:</b> {vaga['cidade']} - {vaga['bairro']}</p>
                        <p><b>Contatos:</b> E-mail: {vaga['email_contato']} | WhatsApp: +{vaga['whatsapp_contato']} | Tel: {vaga['telefone']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        f"📧 Enviar por E-mail", key=f"email_{vaga['id']}"
                    ):
                        if not gmail_user or not gmail_password:
                            st.error(
                                "Preencha as credenciais do Gmail na barra lateral."
                            )
                            log_console(
                                "WARN: Tentativa de envio cancelada por falta de credenciais do Gmail."
                            )
                        elif not caminho_temp_curriculo:
                            st.error(
                                "Faça o upload do seu currículo na barra lateral."
                            )
                            log_console(
                                "WARN: Tentativa de envio cancelada por falta de currículo."
                            )
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
                                        "Canal": "E-mail",
                                        "Destinatário": vaga["email_contato"],
                                        "Status": "Enviado",
                                    }
                                )
                            else:
                                st.error(msg)

                with c2:
                    texto_mensagem = f"Olá, estou enviando o currículo para consulta, referente a vaga {vaga['nome']}, atenciosamente."
                    texto_encoded = urllib.parse.quote(texto_mensagem)
                    url_whatsapp = f"https://wa.me/{vaga['whatsapp_contato']}?text={texto_encoded}"

                    if st.link_button("💬 Abrir no WhatsApp", url_whatsapp):
                        log_console(
                            f"INFO: Link do WhatsApp aberto para a vaga '{vaga['nome']}' ({vaga['whatsapp_contato']})."
                        )
    else:
        st.info(
            "Preencha os filtros desejados e clique em **🔎 Buscar Vagas** para consultar."
        )


# ------------------------------------------------
# ABA 2: RELATÓRIO DE ENVIOS
# ------------------------------------------------
with tab_relatorios:
    st.subheader("📊 Histórico e Relatório de Candidaturas")

    if st.session_state.historico_envios:
        df_relatorio = pd.DataFrame(st.session_state.historico_envios)
        st.dataframe(df_relatorio, use_container_width=True)

        csv = df_relatorio.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Baixar Relatório em CSV",
            data=csv,
            file_name="relatorio_envios_vagas.csv",
            mime="text/csv",
        )
    else:
        st.info("Nenhuma candidatura enviada nesta sessão ainda.")


# ------------------------------------------------
# ABA 3: CONSOLE DE SAÍDA DE SISTEMA
# ------------------------------------------------
with tab_console:
    st.subheader("💻 Console de Logs e Saída do Sistema")

    c_top1, c_top2 = st.columns([0.85, 0.15])
    with c_top2:
        if st.button("🗑️ Limpar Console"):
            st.session_state.console_logs = [
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Console limpo."
            ]
            st.rerun()

    log_text = "\n".join(st.session_state.console_logs)
    st.text_area("Logs de Execução", value=log_text, height=400, disabled=True)