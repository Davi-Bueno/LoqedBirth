import re  
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from PIL import Image
from datetime import datetime
import gridfs
import os
import io
import json
import requests
import pytz
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 🔹 Configuração do MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/Loqed"
mongo = PyMongo(app)
db = mongo.cx["Loqed"]
#var pra gravura da img no banco
fs = gridfs.GridFS(db)


# 🔹 Configuração da API DeepSeek
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-48f83f80c7ea485fad3b3d0ae1a82515")  # Defina sua chave

# 🔹 Diretório para cache de imagens
IMAGE_CACHE_DIR = "cached_images"
# Criar diretório de cache se não existir
if not os.path.exists(IMAGE_CACHE_DIR):
    os.makedirs(IMAGE_CACHE_DIR)

    # 🔹 Gerar e validar tokens seguros
SECRET_KEY = "DaviKey"
serializer = URLSafeTimedSerializer(SECRET_KEY)

# 🔹 Gerar token temporário seguro
def gerar_token(image_id, validade=60):
    """Gera um token válido por 5 minutos (300 segundos)"""
    return serializer.dumps(image_id, salt="image_salt")

# 🔹 Validar token seguro
def validar_token(token, validade=300):
    """Valida o token e retorna o ID da imagem se for válido"""
    try:
        return serializer.loads(token, salt="image_salt", max_age=validade)
    except (SignatureExpired, BadSignature):
        return None

# 🔹 Função para recortar e centralizar imagem
def recortar_imagem(imagem, tamanho=(400, 400)):
    """Recorta e redimensiona uma imagem para manter o conteúdo centralizado."""
    img = Image.open(imagem)

    # Determinar o menor lado para recorte quadrado
    min_dimensao = min(img.size)
    img_cortada = img.crop((
        (img.width - min_dimensao) // 2,
        (img.height - min_dimensao) // 2,
        (img.width + min_dimensao) // 2,
        (img.height + min_dimensao) // 2
    ))

    # Redimensionar para o tamanho desejado
    img_cortada = img_cortada.resize(tamanho, Image.LANCZOS)

    # Converter imagem para bytes
    img_bytes = io.BytesIO()
    img_cortada.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


# 🔹 Função para formatar datas para "DD/MM/AAAA HH:MM:SS"
def formatar_data(data):
    fuso_brasilia = pytz.timezone('America/Sao_Paulo')

    if isinstance(data, datetime):
        # Adicione o fuso horário explicitamente caso esteja faltando
        if data.tzinfo is None:
            data = data.replace(tzinfo=pytz.utc)
        return data.astimezone(fuso_brasilia).strftime("%d/%m/%Y %H:%M:%S")
    
    elif isinstance(data, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
            try:
                data = datetime.strptime(data, fmt)
                data = data.replace(tzinfo=pytz.utc).astimezone(fuso_brasilia)
                return data.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                continue
                
    return "Data inválida"

# 🔹 Função para validar nome
def validar_nome(nome):
    """Verifica se o nome contém apenas letras e espaços"""
    return re.match(r"^[a-zA-ZÀ-ÿ\s]+$", nome) is not None

# 🔹 Função para validar data de nascimento
def validar_data_nascimento(data_str):
    """Verifica se a data de nascimento é válida e não está no futuro"""
    try:
        data_nascimento = datetime.strptime(data_str, "%Y-%m-%d")
        data_atual = datetime.now()

        # Restrições:
        if data_nascimento >= data_atual:
            return False
        if data_nascimento.year < 1900:  # Evita datas muito antigas
            return False

        return True
    except ValueError:
        return False

# 🔹 Obtém todos os usuários cadastrados e ordena corretamente
def get_users(order_by="data_nascimento"):
    users = []
    for user in db["LoqedBirths"].find():
        try:
            data_nascimento = user["data_nascimento"]
            updated_at = user["updated_at"]

            # Convertendo para datetime se necessário
            if isinstance(data_nascimento, str):
                data_nascimento = datetime.strptime(data_nascimento, "%Y-%m-%dT%H:%M:%S") \
                    if "T" in data_nascimento else datetime.strptime(data_nascimento, "%Y-%m-%d")

            if isinstance(updated_at, str):
                updated_at = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%f")
            # Aplicar a conversão de fuso horário para Brasília
            fuso_brasilia = pytz.timezone('America/Sao_Paulo')
            data_nascimento = data_nascimento.replace(tzinfo=pytz.utc).astimezone(fuso_brasilia)
            updated_at = updated_at.replace(tzinfo=pytz.utc).astimezone(fuso_brasilia)
        except Exception as e:
            print(f"Erro ao processar datas: {e}")
            continue  # Ignorar usuários com data inválida

        users.append({
            "id": str(user["_id"]),
            "nome": user["nome"],
            "data_nascimento": formatar_data(user["data_nascimento"]),
            "imagem": user["imagem"],
            "image_id": user["image_id"],
            "created_at": formatar_data(user.get("created_at", datetime.utcnow())),
            "updated_at": formatar_data(user.get("updated_at", datetime.utcnow())),
            "data_nascimento_obj": data_nascimento,
            "updated_at_obj": updated_at
        })

    # 🔹 Ordenação dinâmica corrigida
    if order_by == "data_nascimento":
        users = sorted(users, key=lambda x: x["data_nascimento_obj"])
    elif order_by == "updated_at":
        users = sorted(users, key=lambda x: x["updated_at_obj"], reverse=True)

    for user in users:
        del user["data_nascimento_obj"]
        del user["updated_at_obj"]

    return users

# 🔹 Armazenar o estado temporário (última versão dos dados)
def salvar_estado_temporario(users):
    """Salva o estado anterior dos usuários para futura comparação"""
    db["LoqedBirths_History"].delete_many({})  # Remove o estado temporário anterior
    db["LoqedBirths_History"].insert_one({"estado_anterior": users})

@app.route('/get_secure_image/<image_id>', methods=['GET'])
def get_secure_image(image_id):
    """Gera uma URL temporária segura para exibir imagens"""
    token = gerar_token(image_id)
    secure_url = f"{request.host_url}secure_image/{token}"
    return jsonify({"secure_url": secure_url})

@app.route('/secure_image/<token>', methods=['GET'])
def secure_image(token):
    """Valida token e carrega a imagem apenas se válido"""
    image_id = validar_token(token)
    if not image_id:
        return jsonify({"erro": "Token inválido ou expirado"}), 403

    # Buscar imagem via GridFS ou cache
    cache_path = os.path.join(IMAGE_CACHE_DIR, f"{image_id}.jpg")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as image_file:
            return send_file(io.BytesIO(image_file.read()), mimetype='image/jpeg')

    try:
        image_file = fs.get(ObjectId(image_id))
        with open(cache_path, "wb") as f:
            f.write(image_file.read())
        return send_file(io.BytesIO(image_file.read()), mimetype='image/jpeg')

    except gridfs.errors.NoFile:
        return jsonify({"erro": "Imagem não encontrada"}), 404


# 🔹 Criar usuário
@app.route('/add_user', methods=['POST'])
def add_user():
    """Adiciona um novo usuário ao MongoDB"""
    nome = request.form.get('nome')
    data_nascimento = request.form.get('data_nascimento')
    imagem = request.files.get('imagem')

    if not nome or not data_nascimento or not imagem:
        return jsonify({"erro": "Campos obrigatórios: nome, data de nascimento e imagem"}), 400
    
    if not validar_nome(nome):
        return jsonify({"erro": "Nome inválido! Use apenas letras e espaços."}), 400
    
    if not validar_data_nascimento(data_nascimento):
        return jsonify({"erro": "Data de nascimento inválida! A data deve ser coerente."}), 400
    
    # 🔹 Verificar se o nome já existe
    if db["LoqedBirths"].find_one({"nome": nome}):
        return jsonify({"erro": "Nome já cadastrado!"}), 400
    
    imagem_recortada = recortar_imagem(imagem)
    filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

    try:
        img_id = fs.put(imagem_recortada, filename=filename, content_type=imagem.content_type or 'image/jpeg')
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar imagem: {str(e)}"}), 500
    cache_path = os.path.join(IMAGE_CACHE_DIR, filename)
    with open(cache_path, "wb") as f:
        f.write(imagem_recortada.getvalue())
    user = {
        "nome": nome,
        "data_nascimento": data_nascimento,
        "imagem": filename,
        "image_id": str(img_id),
        "created_at": datetime.utcnow().replace(tzinfo=pytz.utc),
        "updated_at": datetime.utcnow().replace(tzinfo=pytz.utc)
    }

    result = db["LoqedBirths"].insert_one(user)
    return jsonify({"mensagem": "Usuário cadastrado!", "id": str(result.inserted_id), "imagem": filename}), 201

# 🔹 Listar usuários
@app.route('/get_users', methods=['GET'])
def get_users_route():
    return jsonify(get_users())

# 🔹 Atualizar usuário
@app.route('/update_user/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Atualiza um usuário no MongoDB"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    nome = request.form.get('nome', user["nome"])
    data_nascimento = request.form.get('data_nascimento', user["data_nascimento"])
    imagem = request.files.get('imagem')

    users = get_users()
    salvar_estado_temporario(users)
    
    # 🔸 Validação dos dados 🔸
    if not validar_nome(nome):
        return jsonify({"erro": "Nome inválido! Use apenas letras e espaços."}), 400

    if not validar_data_nascimento(data_nascimento):
        return jsonify({"erro": "Data de nascimento inválida! A data deve ser coerente."}), 400

    # 🔹 Verificar se o novo nome já existe (exceto se for o próprio usuário)
    if nome != user["nome"] and db["LoqedBirths"].find_one({"nome": nome}):
        return jsonify({"erro": "Nome já cadastrado!"}), 400
    
   

    update_data = {
        "updated_at": datetime.utcnow().replace(tzinfo=pytz.utc),
        "nome": nome,
        "data_nascimento": data_nascimento
    }

    if imagem:
        filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        try:
            new_img_id = fs.put(imagem, filename=filename, content_type=imagem.content_type)
            if "image_id" in user:
                fs.delete(ObjectId(user["image_id"]))
            update_data["imagem"] = filename
            update_data["image_id"] = str(new_img_id)
        except Exception as e:
            return jsonify({"erro": f"Erro ao salvar nova imagem: {str(e)}"}), 500

    db["LoqedBirths"].update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return jsonify({"mensagem": "Usuário atualizado!"})

# 🔹 Deletar usuário
@app.route('/delete_user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Remove um usuário do MongoDB e sua imagem associada"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

     # 🔹 Verificar e remover imagem do cache
    if "imagem" in user:
        cache_path = os.path.join(IMAGE_CACHE_DIR, user["imagem"])
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except Exception as e:
                return jsonify({"erro": f"Erro ao remover imagem do cache: {str(e)}"}), 500

    # 🔹 Verificar e remover imagem do banco (GridFS)
    if "image_id" in user:
        try:
            fs.delete(ObjectId(user["image_id"]))
        except gridfs.errors.NoFile:
            pass  # Se não existir no GridFS, ignora sem erro
        except Exception as e:
            return jsonify({"erro": f"Erro ao remover imagem do banco: {str(e)}"}), 500

    # 🔹 Remover o usuário do banco
    db["LoqedBirths"].delete_one({"_id": ObjectId(user_id)})
    return jsonify({"mensagem": "Usuário e imagem deletados com sucesso!"}), 200

# # 🔹 Servir imagens do cache
# @app.route('/get_cached_image/<image_id>', methods=['GET'])
# def get_cached_image(image_id):
#     """Verifica se a imagem está no cache, se não, baixa do GridFS e armazena"""
#     try:
#         cache_path = os.path.join(IMAGE_CACHE_DIR, f"{image_id}.jpg")

#         # 🔹 Se a imagem já está no cache, retorna diretamente com cabeçalhos HTTP de cache
#         if os.path.exists(cache_path):
#             response = make_response(send_from_directory(IMAGE_CACHE_DIR, f"{image_id}.jpg"))
#             response.headers["Cache-Control"] = "public, max-age=31536000"  # Cache por 1 ano
#             return response

#         # 🔹 Caso contrário, busca no banco e salva no cache
#         image_file = fs.get(ObjectId(image_id))
#         with open(cache_path, "wb") as f:
#             f.write(image_file.read())

#         # Retorna a imagem já com cache ativado
#         response = make_response(send_from_directory(IMAGE_CACHE_DIR, f"{image_id}.jpg"))
#         response.headers["Cache-Control"] = "public, max-age=31536000"
#         return response

#     except gridfs.errors.NoFile:
#         return jsonify({"erro": "Imagem não encontrada"}), 404
#     except Exception as e:
#         return jsonify({"erro": f"Erro ao buscar imagem: {str(e)}"}), 500

@app.route('/load_image/<image_id>', methods=['GET'])
def load_image(image_id):
    """Envia a imagem diretamente via bytes"""
    try:
        # Tenta localizar a imagem no cache local
        cache_path = os.path.join(IMAGE_CACHE_DIR, f"{image_id}.jpg")
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as image_file:
                return send_file(io.BytesIO(image_file.read()), mimetype='image/jpeg')

        # Se não estiver no cache, buscar do banco e armazenar no cache
        image_file = fs.get(ObjectId(image_id))
        with open(cache_path, "wb") as f:
            f.write(image_file.read())

        # Enviar a imagem diretamente ao frontend
        return send_file(io.BytesIO(image_file.read()), mimetype='image/jpeg')

    except gridfs.errors.NoFile:
        return jsonify({"erro": "Imagem não encontrada"}), 404
    except Exception as e:
        return jsonify({"erro": f"Erro ao buscar imagem: {str(e)}"}), 500



# 🔹 Oráculo (IA responde com base nos usuários)
@app.route('/oracle', methods=['POST'])
def oracle():
    data = request.json
    question = data.get("question", "").strip().lower()

    if not question:
        return jsonify({"erro": "A pergunta não pode estar vazia"}), 400

    order_by = "updated_at" if "atualização" in question else "data_nascimento"
    users = get_users(order_by)

# 🔹 Buscar o estado anterior (estado temporário)
    estado_anterior = db["LoqedBirths_History"].find_one()
    estado_anterior = estado_anterior.get("estado_anterior", [])

    prompt = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Você é um assistente de análise de dados. Use resposta na linguagem tradicional/comum. Nunca mostre qualquer id nas respostas nome da campos ou qualquer informação sensível."},
            {"role": "user", "content": f"Usuários antes da atualização:\n\n{json.dumps(estado_anterior, indent=2, ensure_ascii=False)}\n\n"},
            {"role": "user", "content": f"Usuários atuais:\n\n{json.dumps(users, indent=2, ensure_ascii=False)}\n\n{question}"}
        ],
        "max_tokens": 1000,
        "temperature": 0.2
    }

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=prompt)

        # Se a resposta estiver vazia, registrar o erro
        if response.status_code != 200:
            return jsonify({"erro": f"Erro na API DeepSeek: {response.status_code} - {response.text}"}), 500
        
        # Capturar resposta JSON corretamente
        try:
            resposta_json = response.json()
            resposta_texto = resposta_json.get("choices", [{}])[0].get("message", {}).get("content", "Erro ao processar resposta.")
        except json.JSONDecodeError:
            return jsonify({"erro": "A resposta da API não contém um JSON válido", "resposta_bruta": response.text}), 500

        return jsonify({"resposta": resposta_texto.strip(), "dados_utilizados": users})
    
    except requests.RequestException as e:
        return jsonify({"erro": f"Erro de conexão com a API DeepSeek: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=8080)