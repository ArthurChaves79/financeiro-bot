# financeiro_bot.py
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from transformers import pipeline
import pandas as pd
import matplotlib.pyplot as plt
import os
import psycopg2
from datetime import datetime
from flask_talisman import Talisman

app = Flask(__name__)
Talisman(app)  # Força HTTPS e headers de segurança

# Configurações do Banco de Dados (Render PostgreSQL)
DATABASE_URL = os.environ.get('DATABASE_URL')

# Configuração Twilio
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

# Modelo de NLP para classificação
nlp = pipeline('text-classification', model='neuralmind/bert-base-portuguese-cased')

# ==============================================
# Funções do Banco de Dados
# ==============================================
def criar_tabelas():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        telefone VARCHAR(20) UNIQUE,
        saldo NUMERIC DEFAULT 0
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transacoes (
        id SERIAL PRIMARY KEY,
        usuario VARCHAR(20),
        valor NUMERIC,
        categoria VARCHAR(50),
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orcamentos (
        categoria VARCHAR(50) PRIMARY KEY,
        limite NUMERIC
    )''')

    conn.commit()
    conn.close()

# ==============================================
# Funções do Bot
# ==============================================
def processar_mensagem(texto, telefone):
    try:
        # Classificação com NLP
        classe = nlp(texto)[0]['label']
        
        if 'saldo' in texto:
            return consultar_saldo(telefone)
        elif 'adicionar' in texto:
            return registrar_transacao(texto, telefone)
        elif 'relatório' in texto:
            return gerar_relatorio(telefone)
        elif 'orçamento' in texto:
            return definir_orcamento(texto)
        elif 'investir' in texto:
            return sugerir_investimento(telefone)
        else:
            return "Comando não reconhecido. Tente: saldo, adicionar, relatório, orçamento"
            
    except Exception as e:
        return f"Erro: {str(e)}"

def consultar_saldo(telefone):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    cursor.execute('SELECT saldo FROM usuarios WHERE telefone = %s', (telefone,))
    saldo = cursor.fetchone()[0] or 0
    conn.close()
    return f"Seu saldo atual é: R$ {saldo:.2f}"

def registrar_transacao(texto, telefone):
    partes = texto.split()
    valor = float(partes[1])
    categoria = partes[2] if len(partes) > 2 else 'Outros'
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    
    # Atualiza saldo
    cursor.execute('''
        INSERT INTO usuarios (telefone, saldo)
        VALUES (%s, %s)
        ON CONFLICT (telefone) DO UPDATE
        SET saldo = usuarios.saldo + EXCLUDED.saldo
    ''', (telefone, valor))
    
    # Registra transação
    cursor.execute('''
        INSERT INTO transacoes (usuario, valor, categoria)
        VALUES (%s, %s, %s)
    ''', (telefone, valor, categoria))
    
    conn.commit()
    conn.close()
    return "Transação registrada com sucesso!"

def gerar_relatorio(telefone):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    df = pd.read_sql_query('''
        SELECT categoria, SUM(valor) as total 
        FROM transacoes 
        WHERE usuario = %s
        GROUP BY categoria
    ''', conn, params=(telefone,))
    
    plt.figure(figsize=(8,8))
    plt.pie(df['total'], labels=df['categoria'], autopct='%1.1f%%')
    plt.title('Gastos por Categoria')
    img_path = f'relatorio_{telefone}.png'
    plt.savefig(img_path)
    plt.close()
    
    return img_path

def definir_orcamento(texto):
    partes = texto.split()
    categoria = partes[1]
    limite = float(partes[2])
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orcamentos (categoria, limite)
        VALUES (%s, %s)
        ON CONFLICT (categoria) DO UPDATE
        SET limite = EXCLUDED.limite
    ''', (categoria, limite))
    
    conn.commit()
    conn.close()
    return f"Orçamento para {categoria} definido em R$ {limite:.2f}"

def sugerir_investimento(telefone):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(valor) FROM transacoes
        WHERE usuario = %s AND valor > 0
    ''', (telefone,))
    renda = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT saldo FROM usuarios WHERE telefone = %s', (telefone,))
    saldo = cursor.fetchone()[0] or 0
    
    if saldo > renda * 0.3:  # Se economizou mais de 30%
        return "Sugestão: Invista R$ {:.2f} em CDB 100% DI!".format(saldo * 0.5)
    else:
        return "Foque em reduzir dívidas antes de investir."

# ==============================================
# Rotas do Flask
# ==============================================
@app.route('/webhook', methods=['POST'])
def webhook():
    telefone = request.values.get('From', '').replace('whatsapp:', '')
    texto = request.values.get('Body', '').lower()
    
    resposta = processar_mensagem(texto, telefone)
    
    # Se a resposta for uma imagem
    if isinstance(resposta, str) and resposta.endswith('.png'):
        resp = MessagingResponse()
        msg = resp.message()
        msg.body('Seu relatório:')
        msg.media(f'https://{request.host}/{resposta}')
        return str(resp)
    else:
        resp = MessagingResponse()
        resp.message(resposta)
        return str(resp)

@app.route('/')
def health_check():
    return jsonify(status='OK', time=datetime.now().isoformat())

# ==============================================
# Inicialização
# ==============================================
if __name__ == '__main__':
    criar_tabelas()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)