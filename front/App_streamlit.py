import streamlit as st
import requests
import os
from datetime import datetime
import pytz
import re
import socket


local_ip = socket.gethostbyname(socket.gethostname())

# 🔹 Definir URL da API Flask
API_URL = f"http://{local_ip}:8080" if local_ip != "127.0.0.1" else "http://localhost:8080"

# 🔐 SECRET_KEY para acesso básico
SECRET_KEY = "DaviKey"

# 🔹 Função para exibir alerta inicial
def validar_acesso():
    """Valida se o usuário tem a chave secreta correta."""
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False  # Inicializa como não autenticado

    if not st.session_state.autenticado:
        chave_digitada = st.text_input("🔐 Digite a chave de acesso para continuar:", type="password")
        if st.button("Entrar"):
            if chave_digitada == SECRET_KEY:
                st.session_state.autenticado = True
                st.success("✅ Acesso permitido! Bem-vindo ao sistema.")
                st.rerun()
            else:
                st.error("❌ Chave de acesso incorreta. Tente novamente.")
        st.stop()

# 🔹 Validar acesso antes de qualquer coisa
validar_acesso()

st.title("📌 Painel de Gerenciamento de Usuários")

# Criar menu lateral
aba = st.sidebar.radio("Menu", ["Listar Usuários", "Cadastrar Usuário", "Oráculo"])

# Criar pasta para armazenar imagens temporárias
if not os.path.exists("temp_images"):
    os.makedirs("temp_images")

# 🔹 Função para validar nome
def validar_nome(nome):
    """Verifica se o nome contém apenas letras e espaços"""
    return re.match(r"^[a-zA-ZÀ-ÿ\s]+$", nome) is not None

# 🔹 Função para validar data de nascimento
def validar_data_nascimento(data_nascimento):
    """Verifica se a data de nascimento é coerente"""
    try:
        data_nasc = datetime.strptime(str(data_nascimento), "%Y-%m-%d")
        data_atual = datetime.now()

        if data_nasc >= data_atual:
            return False
        if data_nasc.year < 1900:  # Evita datas muito antigas
            return False
        return True
    except ValueError:
        return False

# 🔹 Função para verificar se o nome já existe
def verificar_nome_existente(nome, id_atual=None):
    """
    Verifica se o nome já existe no banco de dados.
    Se 'id_atual' for fornecido, ele ignora o próprio usuário na verificação.
    """
    response = requests.get(f"{API_URL}/get_users")
    if response.status_code == 200:
        users = response.json()
        for user in users:
            # Ignorar o próprio usuário durante a verificação
            if user['nome'].strip().lower() == nome.strip().lower() and user['id'] != id_atual:
                return True  # Nome duplicado encontrado
    return False




# 🔹 Listar Usuários
if aba == "Listar Usuários":
    st.header("📋 Lista de Usuários")

    response = requests.get(f"{API_URL}/get_users")

    if response.status_code == 200:
        users = response.json()
        for user in users:
            with st.expander(f"👤 {user['nome']}", expanded=True):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"📅 Data de Nascimento: {user['data_nascimento']}")
                    created_at = (user["created_at"])
                    updated_at = (user["updated_at"])
                    st.write(f"🕒 Criado em: {created_at}")
                    st.write(f"🕒 Atualizado em: {updated_at}")

                    if 'image_id' in user:
                        # Requisição à nova rota que gera URLs temporárias seguras
                        response = requests.get(f"{API_URL}/get_secure_image/{user['image_id']}")

                        if response.status_code == 200:
                            secure_url = response.json().get("secure_url", "")
                            st.image(secure_url, width=300, use_container_width=True)
                        else:
                            st.warning("🚫 Imagem não encontrada.")

                with col2:
                    if st.button("✏️ Editar", key=f"edit_{user['id']}"):
                        st.session_state.editing_user = user['id']
                        st.session_state.editing_name = user['nome']
                        st.session_state.editing_birth = user['data_nascimento']

                    if st.button("🗑️ Deletar", key=f"delete_{user['id']}"):
                        if requests.delete(f"{API_URL}/delete_user/{user['id']}").status_code == 200:
                            st.success(f"Usuário {user['nome']} deletado com sucesso!")
                            st.rerun()
                        else:
                            st.error(f"Erro ao deletar {user['nome']}.")

                # 🔹 Edição de Usuário
                if hasattr(st.session_state, 'editing_user') and st.session_state.editing_user == user['id']:
                    st.markdown("### ✏️ Editar Usuário")
                    novo_nome = st.text_input("Nome", value=st.session_state.editing_name)
                    # 🔹 Garante que a string tem apenas a data, sem horas
                    data_nascimento_str = st.session_state.editing_birth.split(" ")[0]  # Remove a parte da hora, se existir

                    # 🔹 Converte para objeto datetime corretamente
                    nova_data = st.date_input("Data de Nascimento", value=datetime.strptime(data_nascimento_str, "%d/%m/%Y").date())
                    nova_imagem = st.file_uploader("Nova Imagem (opcional)", type=["jpg", "png", "jpeg"], key=f"image_{user['id']}")

                    col3, col4 = st.columns([1, 2])
                    with col3:
                         if st.button("💾 Salvar", key=f"save_{user['id']}"):
                            # 🔹 Validação antes de enviar ao backend
                            if not validar_nome(novo_nome):
                                st.error("❌ Nome inválido! Use apenas letras e espaços.")
                            elif verificar_nome_existente(novo_nome, id_atual=user['id']):
                                st.error("❌ Nome já cadastrado!")
                            elif not validar_data_nascimento(nova_data):
                                st.error("❌ Data de nascimento inválida! Escolha uma data coerente.")
                            else:
                                # 🔹 Atualizar usuário
                                files = {"imagem": nova_imagem} if nova_imagem else None
                                data = {"nome": novo_nome, "data_nascimento": str(nova_data)}
                                response = requests.put(f"{API_URL}/update_user/{user['id']}", files=files, data=data)

                                if response.status_code == 200:
                                    st.success("✅ Usuário atualizado com sucesso!")
                                    del st.session_state.editing_user
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao atualizar usuário.")



                    with col4:
                        if st.button("❌ Cancelar", key=f"cancel_{user['id']}"):
                            del st.session_state.editing_user
                            st.rerun()

            st.markdown("---")
    else:
        st.error("Erro ao buscar usuários do banco.")

# 🔹 Cadastrar Usuário
elif aba == "Cadastrar Usuário":
    st.header("➕ Cadastrar Usuário")

    nome = st.text_input("Nome")
    data_nascimento = st.date_input("Data de Nascimento")
    imagem = st.file_uploader("Selecione uma imagem", type=["jpg", "png", "jpeg"])

    if st.button("Cadastrar"):
        # 🔸 Validações 🔸
        if not nome:
            st.error("❌ Nome é obrigatório!")
        elif not validar_nome(nome):
            st.error("❌ Nome inválido! Use apenas letras e espaços.")
        elif verificar_nome_existente(nome):
            st.error("❌ Nome já cadastrado!")
        elif not validar_data_nascimento(data_nascimento):
            st.error("❌ Data de nascimento inválida! Escolha uma data coerente.")
        elif not imagem:
            st.error("❌ É obrigatório anexar uma imagem.")
        else:
            # 🔹 Cadastro no backend
            files = {"imagem": imagem}
            data = {"nome": nome, "data_nascimento": str(data_nascimento)}

            response = requests.post(f"{API_URL}/add_user", files=files, data=data)

            if response.status_code == 201:
                st.success("✅ Usuário cadastrado com sucesso!")
            else:
                st.error(f"❌ Erro ao cadastrar usuário: {response.json().get('erro', 'Erro desconhecido')}")



# 🔹 Oráculo
elif aba == "Oráculo":
    st.header("🔮 Oráculo - Inteligência de Dados")
    st.write("Faça perguntas sobre os usuários cadastrados!")

    user_question = st.text_input(
        "💭 Pergunte ao Oráculo:",
        placeholder="Exemplo: Qual é o usuário mais jovem?"
    )

    if st.button("🔍 Consultar"):
        if user_question:
            with st.spinner("Consultando..."):
                response = requests.post(f"{API_URL}/oracle", json={"question": user_question})

                if response.status_code == 200:
                    data = response.json()
                    resposta = data.get("resposta", "Erro ao obter resposta.")
                    dados_utilizados = data.get("dados_utilizados", [])

                    # Exibir resposta principal
                    st.success(resposta)

                    # Exibir JSON dos dados utilizados logo abaixo
                    with st.expander("📂 Dados utilizados para análise"):
                        st.json(dados_utilizados)
                else:
                    st.error("Erro ao consultar o Oráculo.")
        else:
            st.warning("Digite uma pergunta antes de consultar o Oráculo!")
