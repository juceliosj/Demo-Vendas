import os
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

print("INICIANDO SCRIPT...")

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

np.random.seed()

data_hoje = datetime.now().date()

# =============================
# CONFIG
# =============================
TABELA_PRODUTOS = "produtos"
TABELA_VENDAS = "fato_vendas"
TABELA_ESTOQUE = "estoque_produtos"
TABELA_QUEBRA = "quebra_produtos"
TABELA_PEDIDO = "pedido_produtos"

lojas = range(1, 6)

# =============================
# PRODUTOS (DIMENSÃO)
# =============================
qtd_produtos = 200

categorias = ["Alimentos", "Bebidas", "Higiene", "Limpeza"]

produtos = pd.DataFrame({
    "produto_id": range(1, qtd_produtos + 1),
    "produto_nome": [f"Produto_{i}" for i in range(1, qtd_produtos + 1)],
    "categoria": np.random.choice(categorias, qtd_produtos),
    "custo_unitario": np.round(np.random.uniform(1, 30, qtd_produtos), 2),
    "preco_base": np.round(np.random.uniform(5, 60, qtd_produtos), 2)
})

print("Inserindo produtos...")
supabase.table(TABELA_PRODUTOS).upsert(
    produtos.to_dict(orient="records"),
    on_conflict="produto_id"
).execute()

# =============================
# VENDAS (FATO)
# =============================
qtd_registros = 300

vendas = pd.DataFrame({
    "venda_id": [str(uuid.uuid4()) for _ in range(qtd_registros)],
    "data_venda": [str(data_hoje)] * qtd_registros,
    "cliente_id": np.random.randint(1, 500, qtd_registros),
    "tipo_cliente": np.random.choice(["Atacado", "Varejo"], qtd_registros, p=[0.3, 0.7]),
    "produto_id": np.random.choice(produtos["produto_id"], qtd_registros),
    "quantidade": np.random.randint(1, 50, qtd_registros),
    "desconto": np.round(np.random.uniform(0, 0.3, qtd_registros), 2),
    "dias_desde_ultima_compra": np.random.randint(1, 60, qtd_registros),
    "inadimplente": np.random.choice([0, 1], qtd_registros, p=[0.85, 0.15])
})

vendas = vendas.merge(produtos, on="produto_id", how="left")

vendas["preco_unitario"] = np.round(vendas["preco_base"] * (1 - vendas["desconto"]), 2)
vendas["valor_total"] = np.round(vendas["quantidade"] * vendas["preco_unitario"], 2)

vendas["churn"] = np.where(
    (vendas["dias_desde_ultima_compra"] > 30) |
    (vendas["inadimplente"] == 1),
    1,
    0
)

fato_vendas = vendas[[
    "venda_id",
    "data_venda",
    "cliente_id",
    "tipo_cliente",
    "produto_id",
    "quantidade",
    "desconto",
    "preco_unitario",
    "valor_total",
    "dias_desde_ultima_compra",
    "inadimplente",
    "churn"
]]

print("Inserindo vendas...")
supabase.table(TABELA_VENDAS).insert(
    fato_vendas.to_dict(orient="records")
).execute()

# =============================
# ESTOQUE
# =============================
qtd_estoque = 500

estoque = pd.DataFrame({
    "estoque_id": [str(uuid.uuid4()) for _ in range(qtd_estoque)],
    "data_estoque": [str(data_hoje)] * qtd_estoque,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_estoque),
    "loja_id": np.random.choice(lojas, qtd_estoque),
    "quantidade_estoque": np.random.randint(0, 300, qtd_estoque),
    "estoque_minimo": np.random.randint(20, 80, qtd_estoque),
    "estoque_maximo": np.random.randint(150, 500, qtd_estoque),
})

estoque = estoque.merge(produtos[["produto_id", "custo_unitario"]], on="produto_id", how="left")

estoque["custo_estoque"] = np.round(
    estoque["quantidade_estoque"] * estoque["custo_unitario"], 2
)

estoque["status_ruptura"] = np.where(
    estoque["quantidade_estoque"] <= estoque["estoque_minimo"],
    1,
    0
)

estoque = estoque[[
    "estoque_id",
    "data_estoque",
    "produto_id",
    "loja_id",
    "quantidade_estoque",
    "estoque_minimo",
    "estoque_maximo",
    "custo_estoque",
    "status_ruptura"
]]

print("Inserindo estoque...")
supabase.table(TABELA_ESTOQUE).insert(
    estoque.to_dict(orient="records")
).execute()

# =============================
# QUEBRA
# =============================
qtd_quebras = 80

motivos_quebra = ["Avaria", "Vencimento", "Perda operacional", "Produto danificado"]

quebras = pd.DataFrame({
    "quebra_id": [str(uuid.uuid4()) for _ in range(qtd_quebras)],
    "data_quebra": [str(data_hoje)] * qtd_quebras,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_quebras),
    "loja_id": np.random.choice(lojas, qtd_quebras),
    "quantidade_quebra": np.random.randint(1, 20, qtd_quebras),
    "motivo_quebra": np.random.choice(motivos_quebra, qtd_quebras)
})

quebras = quebras.merge(produtos[["produto_id", "custo_unitario"]], on="produto_id", how="left")

quebras["valor_quebra"] = np.round(
    quebras["quantidade_quebra"] * quebras["custo_unitario"], 2
)

quebras = quebras[[
    "quebra_id",
    "data_quebra",
    "produto_id",
    "loja_id",
    "quantidade_quebra",
    "valor_quebra",
    "motivo_quebra"
]]

print("Inserindo quebra...")
supabase.table(TABELA_QUEBRA).insert(
    quebras.to_dict(orient="records")
).execute()

# =============================
# PEDIDOS
# =============================
qtd_pedidos = 120

status_pedido_lista = ["Aberto", "Recebido", "Parcial", "Atrasado"]

pedidos = pd.DataFrame({
    "pedido_id": [str(uuid.uuid4()) for _ in range(qtd_pedidos)],
    "data_pedido": [str(data_hoje)] * qtd_pedidos,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_pedidos),
    "fornecedor_id": np.random.randint(1, 30, qtd_pedidos),
    "prazo_entrega_dias": np.random.randint(2, 15, qtd_pedidos),
    "quantidade_pedida": np.random.randint(50, 500, qtd_pedidos),
    "status_pedido": np.random.choice(status_pedido_lista, qtd_pedidos)
})

pedidos["quantidade_recebida"] = np.where(
    pedidos["status_pedido"] == "Recebido",
    pedidos["quantidade_pedida"],
    np.where(
        pedidos["status_pedido"] == "Parcial",
        np.round(pedidos["quantidade_pedida"] * np.random.uniform(0.3, 0.8, qtd_pedidos)).astype(int),
        0
    )
)

pedidos["data_prevista_entrega"] = pedidos.apply(
    lambda row: str(data_hoje + timedelta(days=int(row["prazo_entrega_dias"]))),
    axis=1
)

pedidos = pedidos[[
    "pedido_id",
    "data_pedido",
    "produto_id",
    "fornecedor_id",
    "prazo_entrega_dias",
    "quantidade_pedida",
    "quantidade_recebida",
    "data_prevista_entrega",
    "status_pedido"
]]

print("Inserindo pedidos...")
supabase.table(TABELA_PEDIDO).insert(
    pedidos.to_dict(orient="records")
).execute()

# =============================
# FINAL
# =============================
print(f"{qtd_registros} vendas inseridas")
print(f"{qtd_estoque} registros de estoque inseridos")
print(f"{qtd_quebras} registros de quebra inseridos")
print(f"{qtd_pedidos} pedidos inseridos")
print("FINALIZOU 🚀")