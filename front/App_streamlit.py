import streamlit as st
import requests
from PIL import Image
import os
from datetime import datetime
import pytz
from langchain.llms import LlamaCpp
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import json

# Definir URL da API Flask
API_URL = "http://localhost:5000"

st.title("Interface para CRUD de Usuários")

# Criar aba de navegação
aba = st.sidebar.radio("Menu", ["Listar Usuários", "Cadastrar Usuário", "Ver Imagens do Banco", "Oráculo"])

# Criar pasta para armazenar imagens temporárias
if not os.path.exists("temp_images"):
    os.makedirs("temp_images")

# Função para formatar data
def formatar_data(data_str):
    try:
        # Converte a string para um objeto datetime (UTC)
        data_obj = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        
        # Define o fuso horário UTC
        utc = pytz.UTC
        data_obj = utc.localize(data_obj)
        
        # Converte para o fuso horário de São Paulo
        fuso_sp = pytz.timezone('America/Sao_Paulo')
        data_local = data_obj.astimezone(fuso_sp)
        
        # Retorna no formato brasileiro (dd/mm/yyyy HH:mm:ss)
        return data_local.strftime("%d/%m/%Y %H:%M:%S")
    except Exception as e:
        print(f"Erro ao formatar data: {str(e)}")  # Log para debug
        return "Data inválida"

# Configuração do modelo Llama
@st.cache_resource
def load_llm():
    llm = LlamaCpp(
        model_path="models/llama-2-7b-chat.gguf",  # Ajuste o caminho do seu modelo
        temperature=0.1,
        max_tokens=2000,
        top_p=1,
        verbose=True,
        n_ctx=2048
    )
    return llm

# Template para análise de dados
ANALYSIS_TEMPLATE = """
Você é um assistente especializado em análise de dados de usuários.
Analise os dados fornecidos e responda à pergunta do usuário.

Dados dos usuários:
{users_data}

Pergunta do usuário:
{question}

Forneça uma resposta clara e concisa baseada apenas nos dados fornecidos.
Se não for possível responder com os dados disponíveis, explique educadamente.

Resposta:"""

if aba == "Listar Usuários":
    st.header("Lista de Usuários")

    response = requests.get(f"{API_URL}/get_users")

    if response.status_code == 200:
        users = response.json()
        for user in users:
            with st.expander(f"👤 {user['nome']}", expanded=True):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Informações do usuário
                    st.write(f"📅 Data de Nascimento: {user['data_nascimento']}")
                    
                    # Formatando a data de criação e atualização
                    created_at = formatar_data(user["created_at"]["$date"]) if isinstance(user["created_at"], dict) else user["created_at"]
                    updated_at = formatar_data(user["updated_at"]["$date"]) if isinstance(user["updated_at"], dict) else user["updated_at"]
                    
                    st.write(f"🕒 Criado em: {created_at}")
                    st.write(f"🕒 Atualizado em: {updated_at}")

                    # Baixar a imagem do GridFS
                    if 'image_id' in user:
                        try:
                            download_response = requests.get(
                                f"{API_URL}/download_image/{user['image_id']}", 
                                headers={'Accept': 'image/*'}
                            )
                            
                            if download_response.status_code == 200:
                                st.image(download_response.content, width=150)
                            else:
                                st.error(f"Erro ao baixar a imagem: {download_response.status_code}")
                        except Exception as e:
                            st.error(f"Erro ao exibir a imagem: {str(e)}")
                    else:
                        st.warning("Usuário não possui imagem")

                with col2:
                    # Botões de ação
                    if st.button("✏️ Editar", key=f"edit_{user['id']}"):
                        st.session_state.editing_user = user['id']
                        st.session_state.editing_name = user['nome']
                        st.session_state.editing_birth = user['data_nascimento']

                    if st.button("🗑️ Deletar", key=f"delete_{user['id']}"):
                        if requests.delete(f"{API_URL}/delete_user/{user['id']}").status_code == 200:
                            st.success(f"Usuário {user['nome']} deletado com sucesso!")
                            st.rerun()
                        else:
                            st.error(f"Erro ao deletar o usuário {user['nome']}")

                # Formulário de edição (aparece quando o botão Editar é clicado)
                if hasattr(st.session_state, 'editing_user') and st.session_state.editing_user == user['id']:
                    st.markdown("### ✏️ Editar Usuário")
                    
                    novo_nome = st.text_input("Nome", value=st.session_state.editing_name)
                    nova_data = st.date_input("Data de Nascimento", 
                                            value=datetime.strptime(st.session_state.editing_birth, "%Y-%m-%d").date())
                    nova_imagem = st.file_uploader("Nova Imagem (opcional)", 
                                                 type=["jpg", "png", "jpeg"], 
                                                 key=f"image_{user['id']}")

                    col3, col4 = st.columns([1, 2])
                    with col3:
                        if st.button("💾 Salvar", key=f"save_{user['id']}"):
                            files = {"imagem": nova_imagem} if nova_imagem else None
                            data = {
                                "nome": novo_nome,
                                "data_nascimento": str(nova_data)
                            }
                            
                            response = requests.put(
                                f"{API_URL}/update_user/{user['id']}", 
                                files=files, 
                                data=data
                            )

                            if response.status_code == 200:
                                st.success("Usuário atualizado com sucesso!")
                                del st.session_state.editing_user
                                st.rerun()
                            else:
                                st.error("Erro ao atualizar usuário.")
                    
                    with col4:
                        if st.button("❌ Cancelar", key=f"cancel_{user['id']}"):
                            del st.session_state.editing_user
                            st.rerun()

            st.markdown("---")  # Separador entre usuários
    else:
        st.error("Erro ao buscar usuários do banco de dados")

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

# Adicionar a nova seção para ver imagens do banco
elif aba == "Ver Imagens do Banco":
    st.header("Imagens Armazenadas no Banco")
    
    # Buscar todos os usuários para obter os IDs das imagens
    response = requests.get(f"{API_URL}/get_users")
    
    if response.status_code == 200:
        users = response.json()
        
        for user in users:
            st.write(f"👤 Nome: {user['nome']}")
            st.write(f"📅 Data de Nascimento: {user['data_nascimento']}")
            
            if 'image_id' in user:
                try:
                    # Versão alternativa usando download_image
                    download_response = requests.get(
                        f"{API_URL}/download_image/{user['image_id']}", 
                        headers={'Accept': 'image/*'}  # Indica que esperamos uma imagem
                    )
                    
                    if download_response.status_code == 200:
                        # Exibir a imagem diretamente dos bytes recebidos
                        st.image(download_response.content, width=150)
                        st.write(f"📝 Nome do arquivo: {user['imagem']}")
                        st.write(f"🔍 ID no GridFS: {user['image_id']}")
                    else:
                        st.error(f"Erro ao baixar a imagem: {download_response.status_code}")
                        st.write(f"Resposta do servidor: {download_response.text}")
                except Exception as e:
                    st.error(f"Erro ao processar a imagem: {str(e)}")
                    print(f"[ERRO] Detalhes: {str(e)}")  # Log para debug
            else:
                st.warning("Usuário não possui imagem no banco")
            
            st.markdown("---")  # Separador entre usuários
    else:
        st.error("Erro ao buscar usuários do banco de dados")

elif aba == "Oráculo":
    st.header("🔮 Oráculo - Consulta Inteligente")
    st.write("Faça perguntas sobre os dados dos usuários cadastrados")
    
    try:
        llm = load_llm()
        prompt = PromptTemplate(
            template=ANALYSIS_TEMPLATE,
            input_variables=["users_data", "question"]
        )
        chain = LLMChain(llm=llm, prompt=prompt)
    except Exception as e:
        st.error(f"Erro ao carregar o modelo de IA: {str(e)}")
        st.stop()
    
    response = requests.get(f"{API_URL}/get_users")
    
    if response.status_code == 200:
        users_data = response.json()
        
        # Mostrar estatísticas básicas
        with st.expander("📊 Estatísticas Gerais", expanded=True):
            st.write(f"Total de usuários: {len(users_data)}")
            st.write(f"Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Campo para pergunta
        user_question = st.text_input(
            "💭 Faça sua pergunta ao oráculo:",
            placeholder="Ex: Qual o usuário mais antigo? Quantos usuários nasceram em 2000?"
        )
        
        if st.button("🔮 Consultar"):
            if user_question:
                with st.spinner("Analisando dados..."):
                    try:
                        # Preparar dados para a IA
                        formatted_data = json.dumps(users_data, indent=2, ensure_ascii=False)
                        
                        # Obter resposta da IA
                        response = chain.run({
                            "users_data": formatted_data,
                            "question": user_question
                        })
                        
                        # Mostrar resposta
                        st.success(response)
                        
                        # Mostrar dados analisados
                        with st.expander("🔍 Dados analisados"):
                            st.json(users_data)
                    
                    except Exception as e:
                        st.error(f"Erro na análise: {str(e)}")
            else:
                st.warning("Por favor, faça uma pergunta!")
    
    else:
        st.error("Não foi possível conectar ao banco de dados. Tente novamente mais tarde.")
    
    # Dicas de uso
    with st.expander("💡 Dicas de perguntas"):
        st.markdown("""
        Você pode perguntar sobre:
        - Informações sobre usuários específicos
        - Estatísticas sobre datas de nascimento
        - Padrões nos dados de cadastro
        - Análises temporais
        - Comparações entre usuários
        - E muito mais! A IA tentará responder qualquer pergunta sobre os dados disponíveis
        """)