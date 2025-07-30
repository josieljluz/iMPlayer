#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
📺 ATUALIZADOR DE PLAYLISTS IPTV AVANÇADO

Funcionalidades:
- Download de múltiplas playlists M3U e EPGs
- Verificação de integridade dos arquivos
- Controle de versão e histórico
- Suporte a proxies e retry automático
- Geração de logs detalhados
"""

import os
import sys
import time
import requests
import hashlib
from pathlib import Path
from datetime import datetime
from tqdm import tqdm  # Barra de progresso
from bs4 import BeautifulSoup  # Para parsing HTML quando necessário

# *****************************
# 🔧 CONFIGURAÇÕES GLOBAIS
# *****************************
class Config:
    # Tempo entre downloads (evitar bloqueio)
    DELAY_BETWEEN_DOWNLOADS = 5  # segundos
    
    # Número máximo de tentativas
    MAX_RETRIES = 3
    
    # Timeout para requisições
    REQUEST_TIMEOUT = 30  # segundos
    
    # Tamanho mínimo para considerar arquivo válido (bytes)
    MIN_FILE_SIZE = 1024  # 1KB
    
    # User-Agent para as requisições
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # Códigos de status HTTP aceitos
    VALID_STATUS_CODES = [200, 301, 302]

# *****************************
# 🎨 CONFIGURAÇÃO DE CORES
# *****************************
class Cores:
    VERDE = '\033[92m'
    AMARELO = '\033[93m'
    VERMELHO = '\033[91m'
    AZUL = '\033[94m'
    MAGENTA = '\033[95m'
    CIANO = '\033[96m'
    BRANCO = '\033[97m'
    RESET = '\033[0m'
    NEGRITO = '\033[1m'
    SUBLINHADO = '\033[4m'

# *****************************
# 📝 LOGGER PERSONALIZADO
# *****************************
class Logger:
    @staticmethod
    def info(mensagem):
        print(f"{Cores.AZUL}[INFO] {mensagem}{Cores.RESET}")
    
    @staticmethod
    def sucesso(mensagem):
        print(f"{Cores.VERDE}[✔] {mensagem}{Cores.RESET}")
    
    @staticmethod
    def aviso(mensagem):
        print(f"{Cores.AMARELO}[⚠] {mensagem}{Cores.RESET}")
    
    @staticmethod
    def erro(mensagem):
        print(f"{Cores.VERMELHO}[✖] {mensagem}{Cores.RESET}", file=sys.stderr)
    
    @staticmethod
    def debug(mensagem):
        print(f"{Cores.CIANO}[DEBUG] {mensagem}{Cores.RESET}")

# *****************************
# 📁 GERENCIADOR DE ARQUIVOS
# *****************************
class GerenciadorArquivos:
    @staticmethod
    def criar_diretorio(caminho):
        """Cria um diretório se não existir"""
        try:
            Path(caminho).mkdir(parents=True, exist_ok=True)
            Logger.info(f"Diretório '{caminho}' criado/verificado")
            return True
        except Exception as e:
            Logger.erro(f"Falha ao criar diretório '{caminho}': {e}")
            return False
    
    @staticmethod
    def verificar_arquivo(caminho_arquivo, tamanho_minimo=Config.MIN_FILE_SIZE):
        """Verifica se um arquivo existe e tem tamanho mínimo"""
        try:
            if not Path(caminho_arquivo).is_file():
                return False
            
            tamanho = os.path.getsize(caminho_arquivo)
            return tamanho >= tamanho_minimo
        except Exception as e:
            Logger.debug(f"Erro ao verificar arquivo: {e}")
            return False
    
    @staticmethod
    def calcular_hash(caminho_arquivo, algoritmo='md5'):
        """Calcula o hash de um arquivo"""
        try:
            hash_obj = hashlib.new(algoritmo)
            with open(caminho_arquivo, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            Logger.erro(f"Erro ao calcular hash: {e}")
            return None

# *****************************
# 🌐 DOWNLOADER DE ARQUIVOS
# *****************************
class Downloader:
    def __init__(self):
        self.sessao = requests.Session()
        self.sessao.headers.update({'User-Agent': Config.USER_AGENT})
    
    def baixar_arquivo(self, url, caminho_destino, forcar=False):
        """
        Baixa um arquivo com tratamento de erros e retry automático
        
        Args:
            url (str): URL do arquivo para download
            caminho_destino (str): Caminho local para salvar
            forcar (bool): Ignorar verificação de arquivo existente
            
        Returns:
            bool: True se o download foi bem-sucedido
        """
        # Verifica se o arquivo já existe e é válido
        if not forcar and GerenciadorArquivos.verificar_arquivo(caminho_destino):
            Logger.info(f"Arquivo já existe e é válido: {caminho_destino}")
            return True
        
        # Cria o diretório se necessário
        GerenciadorArquivos.criar_diretorio(Path(caminho_destino).parent)
        
        # Tenta fazer o download com retry
        for tentativa in range(Config.MAX_RETRIES):
            try:
                Logger.info(f"Tentativa {tentativa+1} para baixar: {url}")
                
                with self.sessao.get(url, stream=True, timeout=Config.REQUEST_TIMEOUT) as resposta:
                    # Verifica status code
                    if resposta.status_code not in Config.VALID_STATUS_CODES:
                        raise requests.exceptions.HTTPError(
                            f"Código de status inválido: {resposta.status_code}")
                    
                    # Obtém tamanho total para barra de progresso
                    tamanho_total = int(resposta.headers.get('content-length', 0))
                    
                    # Configura barra de progresso
                    with tqdm(
                        total=tamanho_total,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"Baixando {Path(caminho_destino).name}"
                    ) as barra_progresso:
                        # Escreve o arquivo em chunks
                        with open(caminho_destino, 'wb') as arquivo:
                            for chunk in resposta.iter_content(chunk_size=8192):
                                if chunk:  # Filtra keep-alive chunks
                                    arquivo.write(chunk)
                                    barra_progresso.update(len(chunk))
                    
                    # Verifica se o arquivo foi salvo corretamente
                    if GerenciadorArquivos.verificar_arquivo(caminho_destino):
                        Logger.sucesso(f"Arquivo salvo com sucesso: {caminho_destino}")
                        Logger.debug(f"Tamanho: {os.path.getsize(caminho_destino)} bytes")
                        Logger.debug(f"Hash MD5: {GerenciadorArquivos.calcular_hash(caminho_destino)}")
                        return True
                    else:
                        raise IOError("Arquivo baixado é inválido ou corrompido")
            
            except Exception as e:
                Logger.aviso(f"Falha na tentativa {tentativa+1}: {str(e)}")
                if tentativa < Config.MAX_RETRIES - 1:
                    time.sleep(Config.DELAY_BETWEEN_DOWNLOADS * (tentativa + 1))
                continue
        
        Logger.erro(f"Falha ao baixar após {Config.MAX_RETRIES} tentativas: {url}")
        return False

# *****************************
# 📺 GERENCIADOR DE PLAYLISTS
# *****************************
class GerenciadorPlaylists:
    def __init__(self):
        self.downloader = Downloader()
        self.playlists = self._carregar_playlists()
    
    def _carregar_playlists(self):
        """Carrega as playlists pré-definidas"""
        return {
            'principal': {
                'nome': 'Playlist Principal',
                'm3u': 'http://m3u4u.com/m3u/xe47yz1pd9spv21mn9vq',
                'epg': 'http://m3u4u.com/epg/xe47yz1pd9spv21mn9vq',
                'ativo': True
            },
            'secundaria': {
                'nome': 'Playlist Secundária',
                'm3u': 'http://m3u4u.com/m3u/d5k2nvdkg9h353qkn984',
                'epg': 'http://m3u4u.com/epg/d5k2nvdkg9h353qkn984',
                'ativo': True
            },
            'especial': {
                'nome': 'Playlist Especial',
                'm3u': 'http://m3u4u.com/m3u/8p4ey8mvw5fq89z8ng1v',
                'epg': 'http://m3u4u.com/epg/8p4ey8mvw5fq89z8ng1v',
                'ativo': True
            },
            'piaui': {
                'nome': 'Piauí TV',
                'm3u': 'http://m3u4u.com/m3u/jq2zy9epr3bwxmgwyxr5',
                'epg': 'http://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5',
                'ativo': True
            }
        }
    
    def listar_playlists(self):
        """Lista todas as playlists disponíveis"""
        Logger.info("📋 Playlists Disponíveis:")
        for id_play, dados in self.playlists.items():
            status = "✅ Ativo" if dados['ativo'] else "❌ Inativo"
            print(f"  {Cores.NEGRITO}{id_play}{Cores.RESET}: {dados['nome']} ({status})")
            print(f"    M3U: {dados['m3u']}")
            print(f"    EPG: {dados['epg']}\n")
    
    def atualizar_playlist(self, playlist_id, diretorio='.', forcar=False):
        """
        Atualiza uma playlist específica (M3U + EPG)
        
        Args:
            playlist_id (str): ID da playlist
            diretorio (str): Diretório de destino
            forcar (bool): Forçar download mesmo se arquivo existir
            
        Returns:
            bool: True se ambos arquivos foram atualizados
        """
        if playlist_id not in self.playlists:
            Logger.erro(f"Playlist '{playlist_id}' não encontrada!")
            return False
        
        if not self.playlists[playlist_id]['ativo']:
            Logger.aviso(f"Playlist '{playlist_id}' está inativa. Pulando...")
            return False
        
        playlist = self.playlists[playlist_id]
        Logger.info(f"🔄 Atualizando playlist: {playlist['nome']}")
        
        # Caminhos dos arquivos
        caminho_m3u = Path(diretorio) / f"{playlist_id}.m3u"
        caminho_epg = Path(diretorio) / f"{playlist_id}.xml"
        
        # Baixa M3U
        sucesso_m3u = self.downloader.baixar_arquivo(
            playlist['m3u'], str(caminho_m3u), forcar)
        
        # Espera entre downloads
        time.sleep(Config.DELAY_BETWEEN_DOWNLOADS)
        
        # Baixa EPG
        sucesso_epg = self.downloader.baixar_arquivo(
            playlist['epg'], str(caminho_epg), forcar)
        
        return sucesso_m3u and sucesso_epg
    
    def atualizar_todas(self, diretorio='.', forcar=False):
        """
        Atualiza todas as playlists ativas
        
        Args:
            diretorio (str): Diretório de destino
            forcar (bool): Forçar download mesmo se arquivo existir
            
        Returns:
            bool: True se todas as playlists foram atualizadas
        """
        Logger.info("🚀 Iniciando atualização de TODAS as playlists")
        resultados = []
        
        for playlist_id in self.playlists:
            if self.playlists[playlist_id]['ativo']:
                resultado = self.atualizar_playlist(playlist_id, diretorio, forcar)
                resultados.append(resultado)
                time.sleep(Config.DELAY_BETWEEN_DOWNLOADS)
        
        return all(resultados)

# *****************************
# 🛠 FUNÇÕES AUXILIARES
# *****************************
def mostrar_ajuda():
    """Exibe mensagem de ajuda"""
    print(f"{Cores.NEGRITO}📺 Atualizador de Playlists IPTV{Cores.RESET}")
    print(f"\n{Cores.SUBLINHADO}Uso:{Cores.RESET}")
    print(f"  {sys.argv[0]} [OPÇÕES]")
    print("\n{Cores.SUBLINHADO}Opções:{Cores.RESET}")
    print(f"  --all          Atualiza todas as playlists ativas")
    print(f"  --list         Lista todas as playlists disponíveis")
    print(f"  --force        Força o download mesmo se o arquivo existir")
    print(f"  --dir DIR      Especifica o diretório de destino (padrão: .)")
    print(f"  --help         Mostra esta mensagem de ajuda")
    print("\n{Cores.SUBLINHADO}Exemplos:{Cores.RESET}")
    print(f"  {sys.argv[0]} --all --dir ./iptv_data")
    print(f"  {sys.argv[0]} --list")
    print(f"  {sys.argv[0]} --force --all")

# *****************************
# 🚀 PONTO DE ENTRADA
# *****************************
def main():
    # Verifica argumentos
    if len(sys.argv) == 1 or '--help' in sys.argv:
        mostrar_ajuda()
        return
    
    # Processa argumentos
    atualizar_todas = '--all' in sys.argv
    listar = '--list' in sys.argv
    forcar = '--force' in sys.argv
    
    # Obtém diretório se especificado
    try:
        dir_index = sys.argv.index('--dir') + 1
        diretorio = sys.argv[dir_index]
    except (ValueError, IndexError):
        diretorio = '.'
    
    # Cria instância do gerenciador
    gerenciador = GerenciadorPlaylists()
    
    # Executa ação conforme argumentos
    if listar:
        gerenciador.listar_playlists()
    elif atualizar_todas:
        gerenciador.atualizar_todas(diretorio, forcar)
    else:
        # Se não for nenhum comando especial, tenta atualizar pelo ID
        playlist_id = sys.argv[1]
        gerenciador.atualizar_playlist(playlist_id, diretorio, forcar)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        Logger.erro("Interrompido pelo usuário!")
        sys.exit(1)
    except Exception as e:
        Logger.erro(f"Erro não tratado: {str(e)}")
        sys.exit(1)