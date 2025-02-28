import streamlit as st
import requests
from PIL import Image
import os
from datetime import datetime

# Definir URL da API Flask
API_URL = "http://localhost:5000"

st.title("Interface para CRUD de Usuários")

# Criar aba de navegação
aba = st.sidebar.radio("Menu", ["Listar Usuários", "Cadastrar Usuário", "Atualizar Usuário"])

# Criar pasta para armazenar imagens temporárias
if not os.path.exists("temp_images"):
    os.makedirs("temp_images")

# Função para formatar data
def formatar_data(data_str):
    try:
        # Converte a string para um objeto datetime
        data_obj = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        # Retorna no formato brasileiro (dd/mm/yyyy HH:mm:ss)
        return data_obj.strftime("%d/%m/%Y %H:%M:%S")
    except Exception as e:
        return "Data inválida"

if aba == "Listar Usuários":
    st.header("Lista de Usuários")

    response = requests.get(f"{API_URL}/get_users")

    if response.status_code == 200:
        users = response.json()
        for user in users:
            st.subheader(user["nome"])
            st.write(f"📅 Data de Nascimento: {user['data_nascimento']}")
            
            # Formatando a data de criação e atualização
            created_at = formatar_data(user["created_at"]["$date"]) if isinstance(user["created_at"], dict) else user["created_at"]
            updated_at = formatar_data(user["updated_at"]["$date"]) if isinstance(user["updated_at"], dict) else user["updated_at"]
            
            st.write(f"🕒 Criado em: {created_at}")
            st.write(f"🕒 Atualizado em: {updated_at}")

            # Baixar a imagem do usuário e exibir
            image_url = f"{API_URL}/uploads/{user['imagem']}"
            response = requests.get(image_url)

            if response.status_code == 200:
                # Salva a imagem na pasta temp_images para exibir no Streamlit
                with open(f"temp_images/{user['imagem']}", "wb") as f:
                    f.write(response.content)
                st.image(f"temp_images/{user['imagem']}", width=150)
            else:
                st.error("Erro ao carregar a imagem!")

            # Botão para deletar o usuário
            if st.button(f"Deletar {user['nome']}", key=f"delete_{user.get('id')}"):
                user_id = user.get("id")  # Garantir que _id exista
                if user_id:
                    delete_response = requests.delete(f"{API_URL}/delete_user/{user_id}")
                    if delete_response.status_code == 200:
                        st.success(f"Usuário {user['nome']} deletado com sucesso!")
                        st.experimental_rerun()  # Recarrega a página para refletir a mudança
                    else:
                        st.error(f"Erro ao deletar o usuário {user['nome']}")
                else:
                    st.error("ID do usuário não encontrado.")
elif aba == "Cadastrar Usuário":
    st.header("Cadastro de Usuário")
           
    nome = st.text_input("Nome")
    data_nascimento = st.date_input("Data de Nascimento")
    imagem = st.file_uploader("Selecione uma imagem", type=["jpg", "png", "jpeg"])

    if st.button("Cadastrar"):
        if nome and data_nascimento and imagem:
            files = {"imagem": imagem}
            data = {"nome": nome, "data_nascimento": str(data_nascimento)}
            response = requests.post(f"{API_URL}/add_user", files=files, data=data)

            if response.status_code == 201:
                st.success("Usuário cadastrado com sucesso!")
            else:
                st.error("Erro ao cadastrar usuário.")
        else:
            st.error("Preencha todos os campos!")

elif aba == "Atualizar Usuário":
    st.header("Atualização de Usuário")
    user_id = st.text_input("ID do Usuário")
    nome = st.text_input("Novo Nome (opcional)")
    data_nascimento = st.date_input("Nova Data de Nascimento (opcional)")
    imagem = st.file_uploader("Nova Imagem (opcional)", type=["jpg", "png", "jpeg"])

    if st.button("Atualizar"):
        if user_id:
            files = {"imagem": imagem} if imagem else None
            data = {"nome": nome, "data_nascimento": str(data_nascimento)}
            response = requests.put(f"{API_URL}/update_user/{user_id}", files=files, data=data)

            if response.status_code == 200:
                st.success("Usuário atualizado com sucesso!")
            else:
                st.error("Erro ao atualizar usuário.")
        else:
            st.error("Informe um ID válido!")