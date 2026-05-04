import os
import uuid
import pandas as pd
import numpy as np
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
print("INICIANDO SCRIPT...")
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

np.random.seed()

qtd_produtos = 200

categorias = ["Alimentos", "Bebidas", "Higiene", "Limpeza"]

produtos = pd.DataFrame({
    "produto_id": range(1, qtd_produtos + 1),
    "produto_nome": [f"Produto_{i}" for i in range(1, qtd_produtos + 1)],
    "categoria": np.random.choice(categorias, qtd_produtos),
    "custo_unitario": np.round(np.random.uniform(1, 30, qtd_produtos), 2),
    "preco_base": np.round(np.random.uniform(5, 60, qtd_produtos), 2)
})

supabase.table("dim_produtos").upsert(
    produtos.to_dict(orient="records"),
    on_conflict="produto_id"
).execute()

qtd_registros = 300
data_hoje = datetime.now().date()

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

supabase.table("fato_vendas").insert(
    fato_vendas.to_dict(orient="records")
).execute()
print("INICIANDO SCRIPT...")
print(f"{qtd_registros} vendas inseridas no Supabase em {data_hoje}")