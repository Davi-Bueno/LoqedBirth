from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime
import gridfs
import os
import io
import pytz
import json

app = Flask(__name__)

# Variável global para armazenar histórico de dados
users_history = []

# Configuração do MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/Loqed"
mongo = PyMongo(app)

# Obtendo o banco de dados correto
db = mongo.cx["Loqed"]
fs = gridfs.GridFS(db)

# Pasta para salvar imagens localmente
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Garante que a pasta existe

def get_local_datetime():
    """Retorna a data e hora atual no fuso horário de São Paulo"""
    fuso_sp = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso_sp)

@app.route('/add_user', methods=['POST'])
def add_user():
    """Adiciona um novo usuário ao MongoDB"""
    nome = request.form.get('nome')
    data_nascimento = request.form.get('data_nascimento')
    imagem = request.files.get('imagem')

    if not nome or not data_nascimento or not imagem:
        return jsonify({"erro": "Campos obrigatórios: nome, data de nascimento e imagem"}), 400

    # Criando um nome único para a imagem
    filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

    # 🚀 Log para depuração
    print(f"[LOG] Nome: {nome}")
    print(f"[LOG] Data de Nascimento: {data_nascimento}")
    print(f"[LOG] Arquivo recebido: {imagem.filename}")
    print(f"[LOG] Tipo MIME recebido: {imagem.content_type}")

    try:
        # Salvando diretamente no GridFS
        img_id = fs.put(
            imagem,
            filename=filename,
            content_type=imagem.content_type or 'image/jpeg',
            upload_date=datetime.utcnow()
        )
        print(f"[LOG] Imagem salva no GridFS com ID: {img_id}")

    except Exception as e:
        print(f"[ERRO] Erro ao salvar imagem: {str(e)}")
        return jsonify({"erro": f"Erro ao salvar imagem: {str(e)}"}), 500

    # Criando o documento no MongoDB
    user = {
        "nome": nome,
        "data_nascimento": data_nascimento,
        "imagem": filename,
        "image_id": str(img_id),
        "created_at": get_local_datetime(),
        "updated_at": get_local_datetime()
    }
    result = db["LoqedBirths"].insert_one(user)

    return jsonify({
        "mensagem": "Usuário cadastrado!",
        "id": str(result.inserted_id),
        "imagem": filename
    }), 201


@app.route('/get_users', methods=['GET'])
def get_users():
    """Retorna todos os usuários cadastrados"""
    global users_history
    users = []
    for user in db["LoqedBirths"].find():
        user_data = {
            "id": str(user["_id"]),
            "nome": user["nome"],
            "data_nascimento": user["data_nascimento"],
            "imagem": user["imagem"],
            "image_id": user["image_id"],
            "created_at": str(user["created_at"]),
            "updated_at": str(user["updated_at"])
        }
        users.append(user_data)
    
    # Atualiza o histórico
    users_history = users
    
    # Log formatado para debug
    formatted_json = json.dumps(users, indent=2, ensure_ascii=False)
    print(f"[LOG] Users JSON: {formatted_json}")
    
    # Retorna diretamente a lista de usuários, sem wrapper adicional
    return jsonify(users)

@app.route('/download_image/<image_id>', methods=['GET'])
def download_image(image_id):
    """Baixa a imagem armazenada no GridFS"""
    try:
        print(f"[LOG] Tentando baixar imagem com ID: {image_id}")
        
        # Obtém o arquivo do GridFS
        file = fs.get(ObjectId(image_id))
        if not file:
            print(f"[ERRO] Imagem não encontrada para o ID: {image_id}")
            return jsonify({"erro": "Imagem não encontrada"}), 404

        # Verificar content_type armazenado no GridFS
        content_type = file.content_type if file.content_type else 'image/jpeg'
        
        
        # Lê o conteúdo do arquivo
        file_data = file.read()
        
        # Retorna o arquivo diretamente como resposta
        return send_file(
            io.BytesIO(file_data),
            mimetype=content_type,
            as_attachment=False
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao baixar imagem: {str(e)}")
        return jsonify({"erro": str(e)}), 500



@app.route('/update_user/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Atualiza um usuário no MongoDB"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    nome = request.form.get('nome', user["nome"])
    data_nascimento = request.form.get('data_nascimento', user["data_nascimento"])
    imagem = request.files.get('imagem')

    update_data = {"updated_at": get_local_datetime(), "nome": nome, "data_nascimento": data_nascimento}

    if imagem:
        filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        image_path = os.path.join(UPLOAD_FOLDER, filename)

        try:
            imagem.save(image_path)
            with open(image_path, 'rb') as img_file:
                new_img_id = fs.put(img_file, filename=filename, content_type=imagem.content_type)

            # Removendo a imagem anterior do GridFS
            if "image_id" in user:
                fs.delete(ObjectId(user["image_id"]))

            update_data["imagem"] = filename
            update_data["image_id"] = str(new_img_id)

        except Exception as e:
            return jsonify({"erro": f"Erro ao salvar nova imagem: {str(e)}"}), 500

    db["LoqedBirths"].update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return jsonify({"mensagem": "Usuário atualizado!"})


@app.route('/delete_user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deleta um usuário e a sua imagem do MongoDB"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    # Deletando o arquivo da imagem no GridFS
    if "image_id" in user:
        try:
            fs.delete(ObjectId(user["image_id"]))
        except Exception as e:
            return jsonify({"erro": f"Erro ao excluir imagem do GridFS: {str(e)}"}), 500

    # Deletando o arquivo da imagem local
    image_path = os.path.join(UPLOAD_FOLDER, user["imagem"])
    if os.path.exists(image_path):
        os.remove(image_path)

    # Deletando o usuário no MongoDB
    db["LoqedBirths"].delete_one({"_id": ObjectId(user_id)})

    return jsonify({"mensagem": "Usuário deletado com sucesso!"})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve as imagens armazenadas na pasta 'uploads'"""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(UPLOAD_FOLDER, filename)
    return jsonify({"erro": "Imagem não encontrada"}), 404


@app.route('/test_image/<image_id>', methods=['GET'])
def test_image(image_id):
    """Rota de teste para download direto da imagem"""
    try:
        # Obtém o arquivo do GridFS
        file = fs.get(ObjectId(image_id))
        if not file:
            return jsonify({"erro": "Imagem não encontrada"}), 404

        # Define um content_type padrão se for null
        content_type = file.content_type if file.content_type else 'image/jpeg'
        
        # Lê o conteúdo do arquivo
        file_data = file.read()
        
        # Logs para debug
        print(f"Tamanho do arquivo: {len(file_data)} bytes")
        print(f"Content type: {content_type}")
        print(f"Nome do arquivo: {file.filename}")
        
        # Retorna o arquivo diretamente como resposta
        return send_file(
            io.BytesIO(file_data),
            mimetype=content_type,
            as_attachment=True,
            download_name=file.filename
        )
        
    except Exception as e:
        print(f"Erro ao baixar imagem: {str(e)}")  # Debug log
        return jsonify({"erro": str(e)}), 500

@app.route('/get_oracle_data', methods=['GET'])
def get_oracle_data():
    """Retorna os dados históricos para consulta do oráculo"""
    global users_history
    
    # Formatando os dados para melhor análise
    oracle_data = {
        "total_users": len(users_history),
        "users_details": users_history,
        "last_update": datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return jsonify(oracle_data)

if __name__ == '__main__':
    app.run(debug=False, port=5000)
