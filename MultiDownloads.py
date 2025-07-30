#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📺 IPTV DOWNLOADER - Baixador de Playlists M3U do GitHub
🔹 Sistema para download de playlists M3U hospedadas no GitHub
🔹 Recursos:
   - Download paralelo com retry automático
   - Cache inteligente
   - Tratamento de erros robusto
"""

import os
import sys
import time
import requests
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tqdm import tqdm

# 🎨 Configuração de cores para terminal
class TermColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# 📝 Configuração de logging
class CustomFormatter(logging.Formatter):
    """Formata logs com cores e informações detalhadas"""
    FORMATS = {
        logging.DEBUG: TermColors.CYAN + "%(asctime)s [DEBUG] %(message)s" + TermColors.RESET,
        logging.INFO: TermColors.GREEN + "%(asctime)s [INFO] %(message)s" + TermColors.RESET,
        logging.WARNING: TermColors.YELLOW + "%(asctime)s [WARN] %(message)s" + TermColors.RESET,
        logging.ERROR: TermColors.RED + "%(asctime)s [ERROR] %(message)s" + TermColors.RESET,
        logging.CRITICAL: TermColors.RED + TermColors.BOLD + "%(asctime)s [CRITICAL] %(message)s" + TermColors.RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logger(level=logging.INFO):
    """Configura o logger com saída para console e arquivo"""
    logger = logging.getLogger('GitHubDownloader')
    logger.setLevel(level)
    
    # Handler para console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(CustomFormatter())
    
    # Handler para arquivo
    fh = logging.FileHandler('github_downloader.log', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(file_formatter)
    
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

logger = setup_logger()

# 🌐 Configuração de requisições HTTP
class RequestManager:
    """Gerencia requisições HTTP com tratamento avançado de erros"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) GitHub-Downloader/1.0',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        self.timeout = 30
        self.max_retries = 3
        self.retry_delay = 5
        self.cache_dir = Path('.cache')
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_with_retry(self, url: str) -> Optional[requests.Response]:
        """Executa requisição com tentativas automáticas"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Tentativa {attempt + 1}/{self.max_retries} falhou para {url}. Aguardando {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Falha ao acessar {url}: {str(e)}")
                    return None

# 📂 Classe principal do GitHub Downloader
class GitHubDownloader:
    """Sistema para download de arquivos M3U do GitHub"""
    
    def __init__(self):
        self.request_manager = RequestManager()
        self.playlists = self._load_playlists()
        self.stats = {
            'total_downloads': 0,
            'success': 0,
            'failed': 0,
            'bytes_downloaded': 0,
            'cache_hits': 0
        }
    
    def _load_playlists(self) -> Dict[str, Dict]:
        """Carrega as playlists com seus respectivos links"""
        return {
            'piauitv': {
                'name': '📡 Piauí TV',
                'url': 'https://gitlab.com/josieljefferson12/playlists/-/raw/main/PiauiTV.m3u',
                'category': 'regional'
            },
            'proton': {
                'name': '⚛️ M3U Proton',
                'url': 'https://gitlab.com/josieljefferson12/playlists/-/raw/main/m3u4u_proton.me.m3u',
                'category': 'general'
            },
            'playlist': {
                'name': '📻 Playlist Geral',
                'url': 'https://gitlab.com/josieljefferson12/playlists/-/raw/main/playlist.m3u',
                'category': 'general'
            },
            'playlists': {
                'name': '🎬 Playlists Variadas',
                'url': 'https://gitlab.com/josielluz/playlists/-/raw/main/playlists.m3u',
                'category': 'general'
            },
            'pornstars': {
                'name': '🔞 Conteúdo Adulto',
                'url': 'https://gitlab.com/josieljefferson12/playlists/-/raw/main/pornstars.m3u',
                'category': 'adult'
            }
        }
    
    def _get_cache_key(self, url: str) -> str:
        """Gera chave de cache baseada na URL"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[bytes]:
        """Verifica se o conteúdo está em cache"""
        cache_file = self.request_manager.cache_dir / cache_key
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                content = f.read()
            self.stats['cache_hits'] += 1
            return content
        return None
    
    def _save_to_cache(self, cache_key: str, content: bytes):
        """Armazena conteúdo no cache"""
        cache_file = self.request_manager.cache_dir / cache_key
        with open(cache_file, 'wb') as f:
            f.write(content)
    
    def download_file(self, url: str, output_path: Path, use_cache: bool = True) -> bool:
        """Baixa um arquivo com tratamento avançado"""
        try:
            cache_key = self._get_cache_key(url)
            
            # Verifica cache primeiro
            if use_cache and (cached_content := self._check_cache(cache_key)):
                content = cached_content
                logger.info(f"📦 Usando cache para {url}")
            else:
                response = self.request_manager.get_with_retry(url)
                if not response:
                    return False
                
                content = response.content
                self._save_to_cache(cache_key, content)
                self.stats['bytes_downloaded'] += len(content)
            
            # Salva o arquivo
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(content)
            
            self.stats['success'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar {url}: {str(e)}")
            self.stats['failed'] += 1
            return False
        finally:
            self.stats['total_downloads'] += 1
    
    def update_playlist(self, playlist_id: str, output_dir: Path) -> bool:
        """Atualiza uma playlist específica"""
        if playlist_id not in self.playlists:
            logger.error(f"Playlist {playlist_id} não encontrada!")
            return False
        
        playlist = self.playlists[playlist_id]
        m3u_path = output_dir / f"{playlist_id}.m3u"
        
        if self.download_file(playlist['url'], m3u_path):
            logger.info(f"✅ {playlist['name']} baixada com sucesso")
            return True
        else:
            logger.error(f"❌ Falha ao baixar {playlist['name']}")
            return False
    
    def update_all(self, output_dir: Path, max_workers: int = 4) -> bool:
        """Atualiza todas as playlists em paralelo"""
        logger.info(f"🚀 Iniciando atualização de {len(self.playlists)} playlists com {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.update_playlist, pid, output_dir): pid
                for pid in self.playlists
            }
            
            results = []
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processando"):
                pid = futures[future]
                try:
                    results.append(future.result())
                    logger.debug(f"Concluído: {pid}")
                except Exception as e:
                    logger.error(f"Erro em {pid}: {str(e)}")
                    results.append(False)
        
        return all(results)
    
    def show_stats(self):
        """Exibe estatísticas detalhadas"""
        logger.info("\n📊 ESTATÍSTICAS FINAIS")
        logger.info(f"🔹 Total de downloads: {self.stats['total_downloads']}")
        logger.info(f"🔹 Sucessos: {TermColors.GREEN}{self.stats['success']}{TermColors.RESET}")
        logger.info(f"🔹 Falhas: {TermColors.RED}{self.stats['failed']}{TermColors.RESET}")
        logger.info(f"🔹 Cache hits: {self.stats['cache_hits']}")
        
        # Converter bytes para formato legível
        bytes_size = self.stats['bytes_downloaded']
        size = f"{bytes_size/1024/1024:.2f} MB" if bytes_size > 1024*1024 else f"{bytes_size/1024:.2f} KB"
        logger.info(f"🔹 Dados transferidos: {size}")

# 🎯 Ponto de entrada principal
def main():
    """Função principal"""
    try:
        import argparse
        
        parser = argparse.ArgumentParser(description='📥 GitHub M3U Downloader')
        parser.add_argument('--dir', type=str, default='playlists',
                          help='Diretório de saída para as playlists')
        parser.add_argument('--paralelo', type=int, default=4,
                          help='Número de downloads paralelos')
        parser.add_argument('--timeout', type=int, default=30,
                          help='Timeout para requisições (segundos)')
        parser.add_argument('--delay', type=int, default=2,
                          help='Delay entre requisições (segundos)')
        parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                          default='INFO', help='Nível de log')
        
        args = parser.parse_args()
        
        # Configura logger com nível selecionado
        logger.setLevel(getattr(logging, args.log_level))
        
        # Cria diretório de saída
        output_dir = Path(args.dir)
        output_dir.mkdir(exist_ok=True)
        
        # Configura o downloader
        downloader = GitHubDownloader()
        downloader.request_manager.timeout = args.timeout
        downloader.request_manager.retry_delay = args.delay
        
        # Executa a atualização
        start_time = time.time()
        success = downloader.update_all(output_dir, max_workers=args.paralelo)
        elapsed = time.time() - start_time
        
        # Resultado final
        downloader.show_stats()
        logger.info(f"⏱ Tempo total: {elapsed:.2f} segundos")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Execução interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"💥 Erro não tratado: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
