import os
import shutil
import requests
from hashlib import md5
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

# Configurações globais
HEADERS = {"User-Agent": "Mozilla/5.0"}
DIRETORIO_SAIDA = Path("iMPlayer")
TIMEOUT = 10  # Timeout configurável
TENTATIVAS = 3  # Número de tentativas de download
ARQUIVOS_PARA_DOWNLOAD = {
    "m3u": [
        ("http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7", "epgbrasil.m3u"),
        ("http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5", "epgportugal.m3u"),
        ("http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp", "epgbrasilportugal.m3u"),
        ("https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u", "PiauiTV.m3u"),
        ("https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u", "m3u@proton.me.m3u")
    ],
    "xml.gz": [
        ("http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7", "epgbrasil.xml.gz"),
        ("http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5", "epgportugal.xml.gz"),
        ("http://m3u4u.com/epg/782dyqdrqkh1xegen4zp", "epgbrasilportugal.xml.gz")
    ]
}

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def validar_url(url):
    """Verifica se a URL é válida."""
    try:
        resultado = urlparse(url)
        return all([resultado.scheme, resultado.netloc])
    except ValueError:
        return False


def baixar_arquivo(url, caminho_saida, tentativas=TENTATIVAS):
    """
    Baixa um arquivo da URL fornecida e salva no caminho especificado.
    Retorna True se o download for bem-sucedido, False caso contrário.
    """
    if not validar_url(url):
        logger.error(f"URL inválida: {url}")
        return False

    for tentativa in range(tentativas):
        try:
            logger.info(f"Tentativa {tentativa + 1} de {tentativas}: Baixando {url}")
            resposta = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

            if resposta.status_code == 200:
                # Garante que o diretório de destino exista
                caminho_saida.parent.mkdir(parents=True, exist_ok=True)

                # Salva o conteúdo do arquivo
                with open(caminho_saida, 'wb') as arquivo:
                    arquivo.write(resposta.content)

                # Verifica se o arquivo foi salvo corretamente
                if caminho_saida.stat().st_size > 0:
                    logger.info(f"Arquivo salvo com sucesso: {caminho_saida}")

                    # Calcula o hash MD5 do arquivo
                    with open(caminho_saida, 'rb') as arquivo:
                        hash_md5 = md5(arquivo.read()).hexdigest()
                    logger.info(f"Hash MD5 do arquivo: {hash_md5}")
                    return True
                else:
                    logger.error(f"Erro: Arquivo vazio ou corrompido: {caminho_saida}")
            else:
                logger.error(f"Falha ao baixar {url}. Código: {resposta.status_code}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao baixar {url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Problema de conexão ao baixar {url}")
        except Exception as erro:
            logger.error(f"Erro inesperado ao baixar {url}: {erro}")

    logger.error(f"Falha ao baixar {url} após {tentativas} tentativas.")
    return False


def limpar_diretorio(diretorio):
    """Remove o diretório e recria-o."""
    if diretorio.exists():
        logger.info(f"Limpando diretório: {diretorio}")
        shutil.rmtree(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)


def main():
    """Função principal para executar o processo de download."""
    limpar_diretorio(DIRETORIO_SAIDA)

    logger.info("Iniciando download dos arquivos...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for extensao, arquivos in ARQUIVOS_PARA_DOWNLOAD.items():
            for indice, (url, nome_arquivo) in enumerate(arquivos, start=1):
                caminho_saida = DIRETORIO_SAIDA / f"iMPlayer_{indice}.{extensao}"
                futures.append(executor.submit(baixar_arquivo, url, caminho_saida))

        for future in as_completed(futures):
            if not future.result():
                logger.error("Erro durante o download de um arquivo.")

    logger.info("Download concluído.")


if __name__ == "__main__":
    main()
