
import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import pywhatkit
import streamlit as st

# ================================================
# CONFIGURAÇÃO DA PÁGINA E ESTILO VISUAL
# ================================================
st.set_page_config(
    page_title="Gestor de Vagas & Candidaturas", page_icon="💼", layout="wide"
)

# CSS para estilizar a interface
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
    unsafe_allow_html=True,  # <--- Altere aqui (remova o '_text_')
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
                "whatsapp_contato": "+5511999999999",
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
                "whatsapp_contato": "+5511988888888",
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
                "whatsapp_contato": "+5521977777777",
                "telefone": "(21) 2222-3333",
            },
        ]
    )


# Inicializa histórico de envios na sessão
if "historico_envios" not in st.session_state:
    st.session_state.historico_envios = []


# ================================================
# FUNÇÕES DE ENVIO
# ================================================
def enviar_email_gmail(
    email_destino, nome_vaga, caminho_curriculo, gmail_user, gmail_password
):
    """Envia o e-mail via servidor SMTP do Gmail com o currículo em anexo."""
    try:
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = email_destino
        msg["Subject"] = f"Candidatura - Vaga {nome_vaga}"

        corpo_email = f"Olá, estou enviando o currículo para consulta, referente a vaga {nome_vaga}, atenciosamente."
        msg.attach(MIMEText(corpo_email, "plain"))

        if caminho_curriculo and os.path.exists(caminho_curriculo):
            with open(caminho_curriculo, "rb") as f:
                anexo = MIMEApplication(f.read(), Name=os.path.basename(caminho_curriculo))
                anexo[
                    "Content-Disposition"
                ] = f'attachment; filename="{os.path.basename(caminho_curriculo)}"'
                msg.attach(anexo)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {str(e)}"


def enviar_whatsapp_web(numero_whats, nome_vaga):
    """Abre o WhatsApp Web para envio da mensagem pré-formatada."""
    try:
        mensagem = f"Olá, estou enviando o currículo para consulta, referente a vaga {nome_vaga}, atenciosamente."
        # Abre o navegador e agenda o envio
        pywhatkit.sendwhatmsg_instantly(
            phone_no=numero_whats, message=mensagem, wait_time=15, tab_close=True
        )
        return (
            True,
            "WhatsApp Web aberto. Anexe o arquivo manualmente no chat aberto.",
        )
    except Exception as e:
        return False, f"Erro ao abrir WhatsApp: {str(e)}"


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

# Painel de Filtros
st.subheader("🔍 Filtros de Busca")
col1, col2, col3 = st.columns(3)

with col1:
    filtro_nome = st.text_input("Nome da Vaga / Cargo")
    filtro_senioridade = st.selectbox(
        "Senioridade", ["Todas", "Júnior", "Pleno", "Sênior"]
    )

with col2:
    filtro_cidade = st.text_input("Cidade")
    filtro_bairro = st.text_input("Bairro")

with col3:
    filtro_salario_min = st.number_input("Salário Mínimo (R$)", value=0.0, step=500.0)

# Processar Filtros
df_vagas = carregar_vagas()

if filtro_nome:
    df_vagas = df_vagas[
        df_vagas["nome"].str.contains(filtro_nome, case=False, na=False)
    ]
if filtro_senioridade != "Todas":
    df_vagas = df_vagas[df_vagas["senioridade"] == filtro_senioridade]
if filtro_cidade:
    df_vagas = df_vagas[
        df_vagas["cidade"].str.contains(filtro_cidade, case=False, na=False)
    ]
if filtro_bairro:
    df_vagas = df_vagas[
        df_vagas["bairro"].str.contains(filtro_bairro, case=False, na=False)
    ]
if filtro_salario_min > 0:
    df_vagas = df_vagas[df_vagas["salario"] >= filtro_salario_min]

st.markdown("---")
st.subheader(f"📋 Vagas Encontradas ({len(df_vagas)})")

# Listagem de Vagas
for idx, vaga in df_vagas.iterrows():
    with st.container():
        st.markdown(
            f"""
            <div class="vaga-card">
                <h3>{vaga['nome']}</h3>
                <p><b>Senioridade:</b> {vaga['senioridade']} | <b>Salário:</b> R$ {vaga['salario']:.2f}</p>
                <p><b>Localização:</b> {vaga['cidade']} - {vaga['bairro']}</p>
                <p><b>Contatos:</b> E-mail: {vaga['email_contato']} | WhatsApp: {vaga['whatsapp_contato']} | Tel: {vaga['telefone']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button(f"📧 Enviar por E-mail", key=f"email_{vaga['id']}"):
                if not gmail_user or not gmail_password:
                    st.error(
                        "Por favor, preencha as credenciais do Gmail na barra lateral."
                    )
                elif not caminho_temp_curriculo:
                    st.error(
                        "Por favor, faça o upload do seu currículo na barra lateral."
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
                                "Data/Hora": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "Vaga": vaga["nome"],
                                "Canal": "E-mail",
                                "Destinatário": vaga["email_contato"],
                                "Status": "Enviado",
                            }
                        )
                    else:
                        st.error(msg)

        with c2:
            if st.button(f"💬 Enviar por WhatsApp", key=f"whats_{vaga['id']}"):
                sucesso, msg = enviar_whatsapp_web(
                    vaga["whatsapp_contato"], vaga["nome"]
                )
                if sucesso:
                    st.warning(msg)
                    st.session_state.historico_envios.append(
                        {
                            "Data/Hora": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "Vaga": vaga["nome"],
                            "Canal": "WhatsApp",
                            "Destinatário": vaga["whatsapp_contato"],
                            "Status": "Iniciado (WhatsApp Web)",
                        }
                    )
                else:
                    st.error(msg)

# ================================================
# RELATÓRIO DE APLICAÇÕES E ENVIOS
# ================================================
st.markdown("---")
st.subheader("📊 Relatório de Envios")

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