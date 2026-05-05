import os
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

print("INICIANDO SCRIPT...")

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

np.random.seed()
data_hoje = datetime.now().date()

# =============================
# LOJAS
# =============================
lojas = pd.DataFrame({
    "loja_id": range(1, 6),
    "loja_nome": [f"Loja_{i}" for i in range(1, 6)],
    "cidade": np.random.choice(["Salvador", "Feira", "Camaçari"], 5),
    "estado": "BA",
    "tipo_loja": np.random.choice(["Atacado", "Varejo"], 5)
})

supabase.table("lojas").upsert(lojas.to_dict("records"), on_conflict="loja_id").execute()

# =============================
# FORNECEDORES
# =============================
fornecedores = pd.DataFrame({
    "fornecedor_id": range(1, 21),
    "fornecedor_nome": [f"Fornecedor_{i}" for i in range(1, 21)],
    "categoria_fornecedor": np.random.choice(["Indústria", "Distribuidor"], 20),
    "prazo_medio_entrega_dias": np.random.randint(2, 15, 20),
    "estado": "BA"
})

supabase.table("fornecedores").upsert(fornecedores.to_dict("records"), on_conflict="fornecedor_id").execute()

# =============================
# PRODUTOS
# =============================
produtos = pd.DataFrame({
    "produto_id": range(1, 201),
    "produto_nome": [f"Produto_{i}" for i in range(1, 201)],
    "categoria": np.random.choice(["Alimentos", "Bebidas", "Higiene"], 200),
    "custo_unitario": np.random.uniform(1, 30, 200),
    "preco_base": np.random.uniform(5, 60, 200)
})

supabase.table("produtos").upsert(produtos.to_dict("records"), on_conflict="produto_id").execute()

# =============================
# VENDAS
# =============================
vendas = pd.DataFrame({
    "venda_id": [str(uuid.uuid4()) for _ in range(300)],
    "data_venda": [str(data_hoje)] * 300,
    "cliente_id": np.random.randint(1, 500, 300),
    "loja_id": np.random.choice(lojas["loja_id"], 300),
    "tipo_cliente": np.random.choice(["Atacado", "Varejo"], 300),
    "produto_id": np.random.choice(produtos["produto_id"], 300),
    "quantidade": np.random.randint(1, 50, 300),
    "desconto": np.random.uniform(0, 0.3, 300),
    "dias_desde_ultima_compra": np.random.randint(1, 60, 300),
    "inadimplente": np.random.choice([0, 1], 300)
})

vendas["preco_unitario"] = vendas["desconto"] * 10
vendas["valor_total"] = vendas["quantidade"] * vendas["preco_unitario"]
vendas["churn"] = (vendas["inadimplente"] == 1).astype(int)

supabase.table("fato_vendas").insert(vendas.to_dict("records")).execute()

# =============================
# ESTOQUE
# =============================
estoque = pd.DataFrame({
    "estoque_id": [str(uuid.uuid4()) for _ in range(500)],
    "data_estoque": [str(data_hoje)] * 500,
    "produto_id": np.random.choice(produtos["produto_id"], 500),
    "loja_id": np.random.choice(lojas["loja_id"], 500),
    "quantidade_estoque": np.random.randint(0, 300, 500),
    "estoque_minimo": np.random.randint(20, 80, 500),
    "estoque_maximo": np.random.randint(150, 500, 500),
})

estoque["custo_estoque"] = estoque["quantidade_estoque"] * 10
estoque["status_ruptura"] = (estoque["quantidade_estoque"] <= estoque["estoque_minimo"]).astype(int)

supabase.table("estoque_produtos").insert(estoque.to_dict("records")).execute()

# =============================
# QUEBRA
# =============================
quebra = pd.DataFrame({
    "quebra_id": [str(uuid.uuid4()) for _ in range(80)],
    "data_quebra": [str(data_hoje)] * 80,
    "produto_id": np.random.choice(produtos["produto_id"], 80),
    "loja_id": np.random.choice(lojas["loja_id"], 80),
    "quantidade_quebra": np.random.randint(1, 20, 80),
    "motivo_quebra": np.random.choice(["Avaria", "Vencimento"], 80)
})

quebra["valor_quebra"] = quebra["quantidade_quebra"] * 10

supabase.table("quebra_produtos").insert(quebra.to_dict("records")).execute()

# =============================
# PEDIDOS
# =============================
pedido = pd.DataFrame({
    "pedido_id": [str(uuid.uuid4()) for _ in range(120)],
    "data_pedido": [str(data_hoje)] * 120,
    "produto_id": np.random.choice(produtos["produto_id"], 120),
    "fornecedor_id": np.random.choice(fornecedores["fornecedor_id"], 120),
    "prazo_entrega_dias": np.random.randint(2, 15, 120),
    "quantidade_pedida": np.random.randint(50, 500, 120),
    "status_pedido": np.random.choice(["Aberto", "Recebido"], 120)
})

pedido["quantidade_recebida"] = pedido["quantidade_pedida"]
pedido["data_prevista_entrega"] = pedido["prazo_entrega_dias"].apply(lambda x: str(data_hoje + timedelta(days=x)))

supabase.table("pedido_produtos").insert(pedido.to_dict("records")).execute()

print("FINALIZOU 🚀")