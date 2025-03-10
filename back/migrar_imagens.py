from PIL import Image
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import gridfs
import os
import io

from App import db, fs  # Importando MongoDB e GridFS já configurados

# Caminho da pasta de cache
IMAGE_CACHE_DIR = "cached_images"

# Função para recortar imagem
def recortar_imagem(imagem, tamanho=(400, 400)):
    img = Image.open(imagem)

    # Determinar o menor lado para recorte quadrado
    min_dimensao = min(img.size)
    img_cortada = img.crop((
        (img.width - min_dimensao) // 2,
        (img.height - min_dimensao) // 2,
        (img.width + min_dimensao) // 2,
        (img.height + min_dimensao) // 2
    ))

    img_cortada = img_cortada.resize(tamanho, Image.LANCZOS)

    img_bytes = io.BytesIO()
    img_cortada.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

# Função para atualizar imagens antigas
def atualizar_imagens_antigas():
    print("🔄 Iniciando a atualização das imagens antigas...")

    # Buscar todas as imagens já existentes
    usuarios = db["LoqedBirths"].find()

    for user in usuarios:
        if "image_id" in user:
            img_id = user["image_id"]

            # Recuperar imagem do GridFS
            try:
                imagem_original = fs.get(ObjectId(img_id))
                imagem_recortada = recortar_imagem(imagem_original)

                # Atualizar no GridFS
                fs.delete(ObjectId(img_id))  # Exclui a imagem antiga
                new_img_id = fs.put(imagem_recortada, filename=user["imagem"], content_type='image/jpeg')

                # Atualizar ID da nova imagem no banco
                db["LoqedBirths"].update_one({"_id": user["_id"]}, {"$set": {"image_id": str(new_img_id)}})

                # Atualizar imagem no cache
                cache_path = os.path.join(IMAGE_CACHE_DIR, user["imagem"])
                with open(cache_path, "wb") as f:
                    f.write(imagem_recortada.getvalue())

                print(f"✅ Imagem de {user['nome']} atualizada com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao atualizar imagem de {user['nome']}: {e}")

    print("✅ Atualização concluída com sucesso!")

if __name__ == "__main__":
    atualizar_imagens_antigas()
