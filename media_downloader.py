#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script unificado para download de playlists M3U e arquivos EPG (XMLTV)
Autor: [josielluz]
Data: [30/07/2025 - 16:35:38]
Versão: 1.1

Descrição:
Este script combina funcionalidades para:
1. Baixar múltiplas playlists M3U de diversas fontes
2. Baixar arquivos EPG (guia de programação) em formato XML comprimido
3. Gerenciar downloads paralelos com verificação de integridade
4. Manter logs detalhados de todas as operações
5. Salvar arquivos em diferentes estruturas de diretórios

Melhorias da versão 1.1:
- Adicionado salvamento na pasta raiz do repositório
- Comentários detalhados linha por linha
- Melhor tratamento de erros
- Verificação de tamanho de arquivo mais robusta
"""

# ==============================================
# BIBLIOTECAS NECESSÁRIAS
# ==============================================

import os           # Operações com arquivos e diretórios
import shutil       # Operações avançadas com arquivos
import requests     # Requisições HTTP
from hashlib import md5  # Geração de hash MD5 para verificação
import logging      # Sistema de logs
from concurrent.futures import ThreadPoolExecutor, as_completed  # Downloads paralelos

# ==============================================
# CONFIGURAÇÕES GLOBAIS
# ==============================================

# Cabeçalho HTTP para simular navegador e evitar bloqueios
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Diretórios de saída para diferentes tipos de conteúdo
OUTPUT_DIRS = {
    "playlists": os.path.join(os.getcwd(), "playlists"),  # Arquivos M3U padrão
    "epg": os.path.join(os.getcwd(), "epg"),            # Arquivos EPG
    "implayer": os.path.join(os.getcwd(), "iMPlayer"),  # Versão iMPlayer
    "root": os.getcwd()                                # Pasta raiz do repositório
}

# Configurações de rede e desempenho
TIMEOUT = 15          # Tempo limite em segundos para requisições
RETRIES = 3           # Número de tentativas para cada download
MAX_WORKERS = 5       # Número máximo de downloads paralelos
MIN_FILE_SIZE = 100   # Tamanho mínimo em bytes para considerar válido (100 bytes)
MAX_FILE_SIZE_MB = 50 # Tamanho máximo em MB (50MB) para evitar downloads muito grandes

# ==============================================
# CONFIGURAÇÃO DO SISTEMA DE LOGGING
# ==============================================

logging.basicConfig(
    level=logging.INFO,  # Nível de log (INFO, WARNING, ERROR, DEBUG)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato da mensagem
    handlers=[
        logging.FileHandler("media_downloader.log"),  # Log em arquivo
        logging.StreamHandler()                       # Log no console
    ]
)
logger = logging.getLogger(__name__)  # Cria o objeto logger

# ==============================================
# FUNÇÕES AUXILIARES
# ==============================================

def validate_url(url):
    """
    Valida se a URL é válida e segura para download.
    
    Parâmetros:
        url (str): URL a ser validada
        
    Retorna:
        bool: True se a URL é válida, False caso contrário
    """
    if not isinstance(url, str):  # Verifica se é uma string
        logger.error(f"URL inválida (não é string): {url}")
        return False
        
    url = url.strip()  # Remove espaços em branco
    if not url:  # Verifica se está vazia
        logger.error("URL vazia")
        return False
        
    # Verifica se começa com http:// ou https://
    if not url.startswith(("http://", "https://")):
        logger.error(f"URL deve começar com http:// ou https://: {url}")
        return False
        
    return True  # URL válida

def create_directory(dir_path):
    """
    Cria um diretório se ele não existir, limpando-o se já existir.
    
    Parâmetros:
        dir_path (str): Caminho do diretório a ser criado/limpo
        
    Retorna:
        bool: True se o diretório está pronto para uso, False em caso de erro
    """
    try:
        # Remove o diretório existente se houver (limpeza)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)  # Remove recursivamente
            logger.info(f"Diretório limpo: {dir_path}")
            
        # Cria o novo diretório
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Diretório criado: {dir_path}")
        return True
        
    except Exception as e:  # Captura qualquer exceção
        logger.error(f"Falha ao preparar diretório {dir_path}: {str(e)}")
        return False

def calculate_file_hash(file_path, hash_type='md5'):
    """
    Calcula o hash de um arquivo para verificação de integridade.
    
    Parâmetros:
        file_path (str): Caminho do arquivo
        hash_type (str): Tipo de hash (md5, sha1, etc)
        
    Retorna:
        str: Hash calculado ou None em caso de erro
    """
    if not os.path.exists(file_path):  # Verifica se o arquivo existe
        logger.error(f"Arquivo não encontrado para cálculo de hash: {file_path}")
        return None
        
    try:
        # Cria o objeto hash conforme o tipo solicitado
        if hash_type == 'md5':
            hash_obj = md5()
        else:
            logger.error(f"Tipo de hash não suportado: {hash_type}")
            return None
            
        # Lê o arquivo em chunks para economizar memória
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):  # Lê em pedaços de 8KB
                hash_obj.update(chunk)  # Atualiza o hash com o chunk atual
                
        return hash_obj.hexdigest()  # Retorna o hash em formato hexadecimal
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash para {file_path}: {str(e)}")
        return None

def is_valid_file_size(file_path):
    """
    Verifica se o tamanho do arquivo está dentro dos limites aceitáveis.
    
    Parâmetros:
        file_path (str): Caminho do arquivo
        
    Retorna:
        bool: True se o tamanho for válido, False caso contrário
    """
    try:
        file_size = os.path.getsize(file_path)  # Obtém tamanho em bytes
        
        # Converte MB para bytes (1 MB = 1024 * 1024 bytes)
        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        
        # Verifica se está dentro dos limites
        if file_size < MIN_FILE_SIZE:
            logger.error(f"Arquivo muito pequeno ({file_size} bytes < {MIN_FILE_SIZE} bytes)")
            return False
        elif file_size > max_size_bytes:
            logger.error(f"Arquivo muito grande ({file_size/1024/1024:.2f} MB > {MAX_FILE_SIZE_MB} MB)")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Erro ao verificar tamanho do arquivo {file_path}: {str(e)}")
        return False

# ==============================================
# FUNÇÃO PRINCIPAL DE DOWNLOAD
# ==============================================

def download_file(url, save_path, retries=RETRIES, timeout=TIMEOUT):
    """
    Faz o download de um arquivo com tratamento de erros e múltiplas tentativas.
    
    Parâmetros:
        url (str): URL do arquivo a ser baixado
        save_path (str): Caminho local para salvar o arquivo
        retries (int): Número de tentativas em caso de falha
        timeout (int): Tempo limite em segundos para a requisição
        
    Retorna:
        bool: True se o download foi bem-sucedido, False caso contrário
    """
    # Validação inicial da URL
    if not validate_url(url):
        return False
        
    # Garante que o diretório de destino existe
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    # Tentativas de download
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Tentativa {attempt}/{retries}: Baixando {url}")
            
            # Faz a requisição HTTP com stream para arquivos grandes
            with requests.get(url, headers=HEADERS, timeout=timeout, stream=True) as response:
                response.raise_for_status()  # Levanta exceção para códigos 4xx/5xx
                
                # Salva o conteúdo no arquivo local
                with open(save_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # Filtra chunks keep-alive
                            file.write(chunk)
                            
                # Verificação pós-download
                if not os.path.exists(save_path):
                    logger.error(f"Arquivo não foi criado: {save_path}")
                    continue
                    
                # Verifica o tamanho do arquivo
                if not is_valid_file_size(save_path):
                    os.remove(save_path)  # Remove arquivo inválido
                    continue
                    
                # Calcula e registra o hash do arquivo
                file_hash = calculate_file_hash(save_path)
                if file_hash:
                    file_size = os.path.getsize(save_path)
                    logger.info(f"Download concluído: {save_path} ({file_size} bytes) | Hash: {file_hash}")
                    return True
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na tentativa {attempt}: {type(e).__name__} - {str(e)}")
        except Exception as e:
            logger.error(f"Erro inesperado na tentativa {attempt}: {type(e).__name__} - {str(e)}")
            
    logger.error(f"Falha ao baixar após {retries} tentativas: {url}")
    return False

# ==============================================
# LISTAS DE DOWNLOAD
# ==============================================

def get_download_lists():
    """
    Retorna dicionários com os arquivos a serem baixados, organizados por tipo.
    
    Retorna:
        tuple: (playlists, epg_files, implayer_files)
    """
    # Playlists M3U padrão (serão salvas na pasta playlists e na raiz)
    playlists = {
        "epgbrasil.m3u": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7",
        "epgbrasilportugal.m3u": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp",
        "epgportugal.m3u": "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5",
        "PiauiTV.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u",
        "m3u@proton.me.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u",
        "playlist.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/playlist.m3u",
        "playlists.m3u": "https://gitlab.com/josielluz/playlists/-/raw/main/playlists.m3u",
        "pornstars.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/pornstars.m3u"
    }
    
    # Arquivos EPG (XMLTV) - serão salvos na pasta epg
    epg_files = {
        "epgbrasil.xml.gz": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7",
        "epgbrasilportugal.xml.gz": "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp",
        "epgportugal.xml.gz": "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5"
    }
    
    # Versão para iMPlayer (nomes padronizados) - pasta iMPlayer
    implayer_files = {
        "iMPlayer_1.m3u": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7",
        "iMPlayer_2.m3u": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp",
        "iMPlayer_3.m3u": "http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5",
        "iMPlayer_1.xml.gz": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7",
        "iMPlayer_2.xml.gz": "http://m3u4u.com/epg/782dyqdrqkh1xegen4zp",
        "iMPlayer_3.xml.gz": "http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5",
        "iMPlayer_4.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u",
        "iMPlayer_5.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u",
        "iMPlayer_6.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/playlist.m3u",
        "iMPlayer_7.m3u": "https://gitlab.com/josielluz/playlists/-/raw/main/playlists.m3u",
        "iMPlayer_8.m3u": "https://gitlab.com/josieljefferson12/playlists/-/raw/main/pornstars.m3u"
    }
    
    # Arquivos para a pasta raiz (algumas playlists selecionadas)
    root_files = {
        "main_playlist.m3u": "http://m3u4u.com/m3u/3wk1y24kx7uzdevxygz7",
        "backup_playlist.m3u": "http://m3u4u.com/m3u/782dyqdrqkh1xegen4zp",
        "guide.xml.gz": "http://m3u4u.com/epg/3wk1y24kx7uzdevxygz7"
    }
    
    return playlists, epg_files, implayer_files, root_files

# ==============================================
# FUNÇÃO PRINCIPAL
# ==============================================

def main():
    """
    Função principal que orquestra todo o processo de download.
    """
    logger.info("Iniciando script de download de playlists e EPGs")
    
    # 1. Preparação dos diretórios
    logger.info("Preparando diretórios de saída...")
    for dir_name, dir_path in OUTPUT_DIRS.items():
        if dir_name != "root":  # Não limpa a pasta raiz para não afetar outros arquivos
            if not create_directory(dir_path):
                logger.error(f"Não foi possível preparar o diretório {dir_name}. Abortando.")
                return
        else:
            # Para a pasta raiz, apenas cria se não existir
            os.makedirs(dir_path, exist_ok=True)
            
    # 2. Obter listas de download
    playlists, epg_files, implayer_files, root_files = get_download_lists()
    
    # 3. Configurar tarefas de download
    download_tasks = [
        (playlists, OUTPUT_DIRS["playlists"]),  # Playlists para pasta playlists
        (playlists, OUTPUT_DIRS["root"]),       # Mesmas playlists para pasta raiz
        (epg_files, OUTPUT_DIRS["epg"]),       # EPGs para pasta epg
        (implayer_files, OUTPUT_DIRS["implayer"]),  # Versão iMPlayer
        (root_files, OUTPUT_DIRS["root"])       # Arquivos específicos para raiz
    ]
    
    # 4. Executar downloads em paralelo
    logger.info("Iniciando downloads paralelos...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []  # Lista para armazenar as tarefas futuras
        
        # Para cada conjunto de arquivos e diretório de destino
        for files_dict, output_dir in download_tasks:
            # Para cada arquivo no dicionário
            for filename, url in files_dict.items():
                save_path = os.path.join(output_dir, filename)
                # Submete a tarefa de download ao executor
                futures.append(executor.submit(download_file, url, save_path))
                
        # Monitorar progresso e resultados
        success_count = 0
        fail_count = 0
        
        # Para cada tarefa concluída
        for future in as_completed(futures):
            if future.result():  # Se o download foi bem-sucedido
                success_count += 1
            else:
                fail_count += 1
                
    # 5. Relatório final
    logger.info(f"Downloads concluídos. Sucessos: {success_count}, Falhas: {fail_count}")
    
    if fail_count > 0:
        logger.warning("Alguns downloads falharam. Verifique os logs para detalhes.")
        
    logger.info("Processo finalizado.")

# Ponto de entrada do script
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Script interrompido pelo usuário.")
    except Exception as e:
        logger.error(f"Erro não tratado: {str(e)}", exc_info=True)
