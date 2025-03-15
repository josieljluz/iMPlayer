import os
import shutil
import requests
from hashlib import md5
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações globais
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT_DIR = os.path.join(os.getcwd(), "iMPlayer")
TIMEOUT = 10
RETRIES = 3

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("execution_logs.txt")
    ]
)
logger = logging.getLogger(__name__)

def is_url_accessible(url):
    """
    Verifica se o URL está acessível.
    """
    try:
        response = requests.head(url, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"URL inacessível: {url}. Detalhes: {e}")
        return False

def download_file(url, save_path, retries=RETRIES):
    """
    Baixa um arquivo da URL fornecida e sobrescreve se já existir.
    """
    if os.path.exists(save_path):
        logger.info(f"Arquivo já existe, pulando: {save_path}")
        return True

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Tentativa {attempt}/{retries} baixando: {url}")
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as file:
                    file.write(response.content)

                file_size = os.path.getsize(save_path)
                if file_size > 0:
                    logger.info(f"Download concluído: {save_path} ({file_size} bytes)")
                    return True
                else:
                    logger.error(f"Erro: Arquivo vazio ou corrompido: {save_path}")
            else:
                logger.warning(f"Erro HTTP {response.status_code}: {url}")

        except requests.exceptions.Timeout:
            logger.error(f"Timeout para: {url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Erro de conexão: {url}")
        except Exception as ex:
            logger.error(f"Erro inesperado: {url}. Detalhes: {ex}")

    logger.error(f"Falhou após {RETRIES} tentativas: {url}")
    return False

def main():
    # Limpar diretório anterior
    logger.info("Limpando diretório anterior...")
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Lista de arquivos para download
    files_to_download = [
        {"url": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7", "name": "epgbrasil.m3u"},
        {"url": "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5", "name": "epgportugal.m3u"},
        {"url": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp", "name": "epgbrasilportugal.m3u"},
        {"url": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u", "name": "PiauiTV.m3u"},
        {"url": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u", "name": "m3u@proton.me.m3u"},
        {"url": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7", "name": "epgbrasil.xml.gz"},
        {"url": "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5", "name": "epgportugal.xml.gz"},
        {"url": "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp", "name": "epgbrasilportugal.xml.gz"}
    ]

    # Baixar arquivos em paralelo
    logger.info("Iniciando downloads...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for file in files_to_download:
            save_path = os.path.join(OUTPUT_DIR, file["name"])
            if is_url_accessible(file["url"]):
                futures.append(executor.submit(download_file, file["url"], save_path))

        for future in as_completed(futures):
            if not future.result():
                logger.error("Erro ao baixar algum arquivo.")

    logger.info("Downloads concluídos com sucesso.")

if __name__ == "__main__":
    main()
