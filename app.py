from datetime import datetime
import json
import os
from flask import Flask, redirect, render_template, request, session, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

ADMIN_PASSWORD = 'admin123'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def init_db():
  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()

  cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            imagem TEXT
        )
    ''')

  cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            itens TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            data_hora TEXT NOT NULL,
            data_dia TEXT NOT NULL
        )
    ''')
  conn.commit()
  conn.close()


def allowed_file(filename):
  return (
      '.' in filename
      and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
  )

@app.route('/admin/pedido/deletar/<int:pedido_id>', methods=['POST'])
def deletar_pedido(pedido_id):
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()
  cursor.execute('DELETE FROM pedidos WHERE id = ?', (pedido_id,))
  conn.commit()
  conn.close()

  return redirect(url_for('admin'))

@app.route('/')
def index():
  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT * FROM produtos ORDER BY categoria, nome')
  produtos_raw = cursor.fetchall()
  conn.close()

  categorias = {
      'Salgados': [],
      'Doces': [],
      'Bebidas': [],
      'Outros': [],
  }

  for prod in produtos_raw:
    cat = prod['categoria']
    if cat in categorias:
      categorias[cat].append(prod)
    else:
      categorias['Outros'].append(prod)

  return render_template('index.html', categorias=categorias)


@app.route('/fazer_pedido', methods=['POST'])
def fazer_pedido():
  data = request.json
  cliente_nome = data.get('nome')
  mesa = data.get('mesa')
  itens_lista = data.get('itens')
  itens = json.dumps(itens_lista)
  total = data.get('total')

  agora = datetime.now()
  data_hora = agora.strftime('%d/%m/%Y %H:%M:%S')
  data_dia = agora.strftime('%Y-%m-%d')

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()
  cursor.execute(
      'INSERT INTO pedidos (cliente_nome, mesa, itens, total, status,'
      ' data_hora, data_dia) VALUES (?, ?, ?, ?, ?, ?, ?)',
      (
          cliente_nome,
          mesa,
          itens,
          total,
          'pendente',
          data_hora,
          data_dia,
      ),
  )
  conn.commit()
  conn.close()

  return {'status': 'sucesso', 'mensagem': 'Pedido realizado com sucesso!'}

@app.route('/login', methods=['GET', 'POST'])
def login():
  erro = None
  if request.method == 'POST':
    senha = request.form.get('senha')
    if senha == ADMIN_PASSWORD:
      session['admin_logado'] = True
      return redirect(url_for('admin'))
    else:
      erro = 'Senha incorreta. Tente novamente.'
  return render_template('login.html', erro=erro)


@app.route('/logout')
def logout():
  session.pop('admin_logado', None)
  return redirect(url_for('login'))


@app.route('/admin')
def admin():
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  data_selecionada = request.args.get('data')
  if not data_selecionada:
    data_selecionada = datetime.now().strftime('%Y-%m-%d')

  conn = sqlite3.connect('database.db')
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  cursor.execute('SELECT * FROM produtos')
  produtos = cursor.fetchall()

  cursor.execute(
      "SELECT * FROM pedidos WHERE status = 'pendente' ORDER BY id DESC"
  )
  pedidos_pendentes = cursor.fetchall()


  cursor.execute(
      "SELECT * FROM pedidos WHERE status = 'atendido' AND data_dia = ? ORDER BY"
      ' id DESC',
      (data_selecionada,),
  )
  pedidos_atendidos = cursor.fetchall()

  cursor.execute(
      'SELECT data_dia, COUNT(id) as total_pedidos, SUM(total) as'
      ' faturamento_total FROM pedidos WHERE data_dia = ? GROUP BY data_dia',
      (data_selecionada,),
  )
  historico_vendas = cursor.fetchall()

  conn.close()
  return render_template(
      'admin.html',
      produtos=produtos,
      pedidos_pendentes=pedidos_pendentes,
      pedidos_atendidos=pedidos_atendidos,
      historico_vendas=historico_vendas,
      data_selecionada=data_selecionada,
  )


@app.route('/admin/produto/novo', methods=['POST'])
def cadastrar_produto():
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  nome = request.form.get('nome')
  categoria = request.form.get('categoria')
  descricao = request.form.get('descricao')
  preco = float(request.form.get('preco'))

  imagem_url = request.form.get('imagem_url')
  image_file = request.files.get('imagem_arquivo')

  caminho_imagem = ''
  if image_file and allowed_file(image_file.filename):
    filename = image_file.filename
    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    caminho_imagem = url_for('static', filename=f'uploads/{filename}')
  elif imagem_url:
    caminho_imagem = imagem_url
  else:
    caminho_imagem = 'https://via.placeholder.com/300x200?text=Sem+Foto'

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()
  cursor.execute(
      'INSERT INTO produtos (nome, categoria, descricao, preco, imagem)'
      ' VALUES (?, ?, ?, ?, ?)',
      (nome, categoria, descricao, preco, caminho_imagem),
  )
  conn.commit()
  conn.close()

  return redirect(url_for('admin'))


@app.route('/admin/produto/editar/<int:prod_id>', methods=['POST'])
def editar_produto(prod_id):
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  nome = request.form.get('nome')
  categoria = request.form.get('categoria')
  descricao = request.form.get('descricao')
  preco = float(request.form.get('preco'))

  imagem_url = request.form.get('imagem_url')
  image_file = request.files.get('imagem_arquivo')

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()

  if image_file and allowed_file(image_file.filename):
    filename = image_file.filename
    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    caminho_imagem = url_for('static', filename=f'uploads/{filename}')
    cursor.execute(
        'UPDATE produtos SET nome = ?, categoria = ?, descricao = ?, preco ='
        ' ?, imagem = ? WHERE id = ?',
        (nome, categoria, descricao, preco, caminho_imagem, prod_id),
    )
  elif imagem_url:
    cursor.execute(
        'UPDATE produtos SET nome = ?, categoria = ?, descricao = ?, preco ='
        ' ?, imagem = ? WHERE id = ?',
        (nome, categoria, descricao, preco, imagem_url, prod_id),
    )
  else:
    cursor.execute(
        'UPDATE produtos SET nome = ?, categoria = ?, descricao = ?, preco = ?'
        ' WHERE id = ?',
        (nome, categoria, descricao, preco, prod_id),
    )

  conn.commit()
  conn.close()

  return redirect(url_for('admin'))

@app.route('/admin/produto/deletar/<int:prod_id>', methods=['POST'])
def deletar_produto(prod_id):
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()
  cursor.execute('DELETE FROM produtos WHERE id = ?', (prod_id,))
  conn.commit()
  conn.close()
  return redirect(url_for('admin'))


@app.route('/admin/pedido/atender/<int:pedido_id>', methods=['POST'])
def atender_pedido(pedido_id):
  if not session.get('admin_logado'):
    return redirect(url_for('login'))

  conn = sqlite3.connect('database.db')
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE pedidos SET status = 'atendido' WHERE id = ?", (pedido_id,)
  )
  conn.commit()
  conn.close()
  return redirect(url_for('admin'))


if __name__ == '__main__':
  init_db()
  app.run(debug=True, port=5000)