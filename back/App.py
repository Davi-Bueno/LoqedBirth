from flask import Flask, request, jsonify, send_from_directory
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime
import gridfs
import os

app = Flask(__name__)

# Configuração do MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/Loqed"
mongo = PyMongo(app)

# Obtendo o banco de dados correto
db = mongo.cx["Loqed"]
fs = gridfs.GridFS(db)

# Pasta para salvar imagens
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route('/add_user', methods=['POST'])
def add_user():
    """Adiciona um novo usuário ao MongoDB"""
    nome = request.form.get('nome')
    data_nascimento = request.form.get('data_nascimento')
    imagem = request.files.get('imagem')

    if not nome or not data_nascimento or not imagem:
        return jsonify({"erro": "Campos obrigatórios: nome, data de nascimento e imagem"}), 400

    # Armazenando a imagem em GridFS
    imagem_id = fs.put(imagem, filename=imagem.filename)
    
    # Salvando a imagem no servidor
    filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, filename)
    imagem.save(image_path)

    # Criando o documento no MongoDB
    user = {
        "nome": nome,
        "data_nascimento": data_nascimento,
        "imagem": filename,
        "imagem_id": str(imagem_id),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = db["LoqedBirths"].insert_one(user)

    return jsonify({"mensagem": "Usuário cadastrado!", "id": str(result.inserted_id)}), 201


@app.route('/get_users', methods=['GET'])
def get_users():
    """Retorna todos os usuários cadastrados"""
    users = []
    for user in db["LoqedBirths"].find():
        users.append({
            "id": str(user["_id"]),
            "nome": user["nome"],
            "data_nascimento": user["data_nascimento"],
            "imagem": user["imagem"],
            "created_at": user["created_at"],
            "updated_at": user["updated_at"]
        })
    return jsonify(users)


@app.route('/update_user/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Atualiza um usuário no MongoDB"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    nome = request.form.get('nome')
    data_nascimento = request.form.get('data_nascimento')
    imagem = request.files.get('imagem')

    update_data = {"updated_at": datetime.utcnow()}

    if nome:
        update_data["nome"] = nome
    if data_nascimento:
        update_data["data_nascimento"] = data_nascimento
    if imagem:
        filename = f"{nome.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        imagem.save(image_path)
        update_data["imagem"] = filename

    db["LoqedBirths"].update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return jsonify({"mensagem": "Usuário atualizado!"})


@app.route('/delete_user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deleta um usuário e a sua imagem do MongoDB"""
    user = db["LoqedBirths"].find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    # Deletando o arquivo da imagem
    image_path = os.path.join(UPLOAD_FOLDER, user["imagem"])
    if os.path.exists(image_path):
        os.remove(image_path)

    # Deletando o usuário no MongoDB
    db["LoqedBirths"].delete_one({"_id": ObjectId(user_id)})

    return jsonify({"mensagem": "Usuário deletado com sucesso!"})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve as imagens armazenadas na pasta 'uploads'"""
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == '__main__':
    app.run(debug=False, port=5000)
