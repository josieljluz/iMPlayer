import os
import shutil
import requests
import logging
from hashlib import md5
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações globais
HEADERS = {"User-Agent": "Mozilla/5.0"}
OUTPUT_DIR = Path.cwd() / "iMPlayer"
TIMEOUT = 10  # Tempo limite para requisição
RETRIES = 3  # Número de tentativas de download

# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def download_file(url, save_path, retries=RETRIES):
    """
    Baixa um arquivo da URL fornecida e salva com o nome original.
    Retorna True se o download for bem-sucedido, senão False.
    """
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Tentativa {attempt}/{retries}: Baixando {url}")
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            if response.status_code == 200:
                save_path.parent.mkdir(parents=True, exist_ok=True)  # Garante que o diretório exista
                with save_path.open("wb") as file:
                    file.write(response.content)

                # Verifica se o arquivo foi salvo corretamente
                if save_path.stat().st_size > 0:
                    logger.info(f"Download concluído: {save_path.name}")

                    # Calcula o hash MD5 do arquivo para verificar integridade
                    file_hash = md5(save_path.read_bytes()).hexdigest()
                    logger.info(f"MD5: {file_hash}")

                    return True
                else:
                    logger.error(f"Erro: Arquivo vazio {save_path.name}")
            else:
                logger.error(f"Erro {response.status_code} ao baixar {url}")

        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao baixar {url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Problema de conexão ao baixar {url}")
        except Exception as e:
            logger.error(f"Erro inesperado ao baixar {url}: {e}")

    logger.error(f"Falha ao baixar {url} após {retries} tentativas.")
    return False

def main():
    """Gerencia a limpeza do diretório e o download dos arquivos."""
    logger.info("Limpando diretório...")
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Lista de arquivos para download
    files_to_download = {
        "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7": "epgbrasil.m3u",
        "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5": "epgportugal.m3u",
        "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp": "epgbrasilportugal.m3u",
        "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u": "PiauiTV.m3u",
        "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u": "m3u@proton.me.m3u",
        "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7": "epgbrasil.xml.gz",
        "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5": "epgportugal.xml.gz",
        "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp": "epgbrasilportugal.xml.gz"
    }

    logger.info("Iniciando downloads...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(download_file, url, OUTPUT_DIR / filename): filename
            for url, filename in files_to_download.items()
        }

        for future in as_completed(futures):
            if not future.result():
                logger.error(f"Falha ao baixar {futures[future]}")

    logger.info("Todos os downloads concluídos!")

if __name__ == "__main__":
    main()
