import os
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from supabase import create_client
from dotenv import load_dotenv

print("INICIANDO SCRIPT...")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

np.random.seed()

data_hoje = datetime.now().date()

MODO_CARGA_INICIAL = False

if MODO_CARGA_INICIAL:
    datas = pd.date_range(
        start="2026-01-01",
        end=datetime.now().date(),
        freq="D"
    )
else:
    datas = pd.date_range(
        start=datetime.now().date(),
        end=datetime.now().date(),
        freq="D"
    )

# =============================
# CONFIGURAÇÕES
# =============================
qtd_produtos = 200
qtd_lojas = 5
qtd_fornecedores = 20
qtd_vendas = 300
qtd_estoque = 500
qtd_quebras = 80
qtd_pedidos = 120

# =============================
# LOJAS
# =============================
lojas = pd.DataFrame({
    "loja_id": range(1, qtd_lojas + 1),
    "loja_nome": [f"Loja_{i}" for i in range(1, qtd_lojas + 1)],
    "cidade": np.random.choice(["Salvador", "Feira de Santana", "Camaçari", "Lauro de Freitas"], qtd_lojas),
    "estado": ["BA"] * qtd_lojas,
    "tipo_loja": np.random.choice(["Atacado", "Varejo", "Atacarejo"], qtd_lojas)
})

supabase.table("lojas").upsert(
    lojas.to_dict(orient="records"),
    on_conflict="loja_id"
).execute()

# =============================
# FORNECEDORES
# =============================
fornecedores = pd.DataFrame({
    "fornecedor_id": range(1, qtd_fornecedores + 1),
    "fornecedor_nome": [f"Fornecedor_{i}" for i in range(1, qtd_fornecedores + 1)],
    "categoria_fornecedor": np.random.choice(["Alimentos", "Bebidas", "Higiene", "Limpeza"], qtd_fornecedores),
    "prazo_medio_entrega_dias": np.random.randint(2, 15, qtd_fornecedores),
    "estado": np.random.choice(["BA", "SE", "PE", "SP"], qtd_fornecedores)
})

supabase.table("fornecedores").upsert(
    fornecedores.to_dict(orient="records"),
    on_conflict="fornecedor_id"
).execute()

# =============================
# PRODUTOS
# =============================
produtos = pd.DataFrame({
    "produto_id": range(1, qtd_produtos + 1),
    "produto_nome": [f"Produto_{i}" for i in range(1, qtd_produtos + 1)],
    "categoria": np.random.choice(["Alimentos", "Bebidas", "Higiene", "Limpeza"], qtd_produtos),
    "custo_unitario": np.round(np.random.uniform(1, 30, qtd_produtos), 2),
    "preco_base": np.round(np.random.uniform(5, 60, qtd_produtos), 2)
})

supabase.table("produtos").upsert(
    produtos.to_dict(orient="records"),
    on_conflict="produto_id"
).execute()

# =============================
# VENDAS
# =============================
lista_vendas = []

for data_ref in datas:

    vendas_dia = pd.DataFrame({
        "venda_id": [str(uuid.uuid4()) for _ in range(qtd_vendas)],
        "data_venda": [str(data_ref.date())] * qtd_vendas,
        "cliente_id": np.random.randint(1, 500, qtd_vendas),
        "loja_id": np.random.choice(lojas["loja_id"], qtd_vendas),
        "tipo_cliente": np.random.choice(
            ["Atacado", "Varejo"],
            qtd_vendas,
            p=[0.3, 0.7]
        ),
        "produto_id": np.random.choice(produtos["produto_id"], qtd_vendas),
        "quantidade": np.random.randint(1, 50, qtd_vendas),
        "desconto": np.round(np.random.uniform(0, 0.3, qtd_vendas), 2),
        "dias_desde_ultima_compra": np.random.randint(1, 60, qtd_vendas),
        "inadimplente": np.random.choice(
            [0, 1],
            qtd_vendas,
            p=[0.85, 0.15]
        )
    })

    lista_vendas.append(vendas_dia)

vendas = pd.concat(lista_vendas, ignore_index=True)

vendas = vendas.merge(
    produtos[["produto_id", "preco_base"]],
    on="produto_id",
    how="left"
)

vendas["preco_unitario"] = np.round(
    vendas["preco_base"] * (1 - vendas["desconto"]),
    2
)

vendas["valor_total"] = np.round(
    vendas["quantidade"] * vendas["preco_unitario"],
    2
)

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
    "loja_id",
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

# =============================
# ESTOQUE
# =============================
estoque = pd.DataFrame({
    "estoque_id": [str(uuid.uuid4()) for _ in range(qtd_estoque)],
    "data_estoque": [str(data_hoje)] * qtd_estoque,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_estoque),
    "loja_id": np.random.choice(lojas["loja_id"], qtd_estoque),
    "quantidade_estoque": np.random.randint(0, 300, qtd_estoque),
    "estoque_minimo": np.random.randint(20, 80, qtd_estoque),
    "estoque_maximo": np.random.randint(150, 500, qtd_estoque)
})

estoque = estoque.merge(
    produtos[["produto_id", "custo_unitario"]],
    on="produto_id",
    how="left"
)

estoque["custo_estoque"] = np.round(
    estoque["quantidade_estoque"] * estoque["custo_unitario"],
    2
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

supabase.table("estoque_produtos").insert(
    estoque.to_dict(orient="records")
).execute()

# =============================
# QUEBRA
# =============================
quebra = pd.DataFrame({
    "quebra_id": [str(uuid.uuid4()) for _ in range(qtd_quebras)],
    "data_quebra": [str(data_hoje)] * qtd_quebras,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_quebras),
    "loja_id": np.random.choice(lojas["loja_id"], qtd_quebras),
    "quantidade_quebra": np.random.randint(1, 20, qtd_quebras),
    "motivo_quebra": np.random.choice(
        ["Avaria", "Vencimento", "Perda operacional", "Produto danificado"],
        qtd_quebras
    )
})

quebra = quebra.merge(
    produtos[["produto_id", "custo_unitario"]],
    on="produto_id",
    how="left"
)

quebra["valor_quebra"] = np.round(
    quebra["quantidade_quebra"] * quebra["custo_unitario"],
    2
)

quebra = quebra[[
    "quebra_id",
    "data_quebra",
    "produto_id",
    "loja_id",
    "quantidade_quebra",
    "valor_quebra",
    "motivo_quebra"
]]

supabase.table("quebra_produtos").insert(
    quebra.to_dict(orient="records")
).execute()

# =============================
# PEDIDOS
# =============================
pedido = pd.DataFrame({
    "pedido_id": [str(uuid.uuid4()) for _ in range(qtd_pedidos)],
    "data_pedido": [str(data_hoje)] * qtd_pedidos,
    "produto_id": np.random.choice(produtos["produto_id"], qtd_pedidos),
    "fornecedor_id": np.random.choice(fornecedores["fornecedor_id"], qtd_pedidos),
    "prazo_entrega_dias": np.random.randint(2, 15, qtd_pedidos),
    "quantidade_pedida": np.random.randint(50, 500, qtd_pedidos),
    "status_pedido": np.random.choice(
        ["Aberto", "Recebido", "Parcial", "Atrasado"],
        qtd_pedidos
    )
})

pedido["quantidade_recebida"] = np.where(
    pedido["status_pedido"] == "Recebido",
    pedido["quantidade_pedida"],
    np.where(
        pedido["status_pedido"] == "Parcial",
        np.round(pedido["quantidade_pedida"] * np.random.uniform(0.3, 0.8, qtd_pedidos)).astype(int),
        0
    )
)

pedido["data_prevista_entrega"] = pedido["prazo_entrega_dias"].apply(
    lambda x: str(data_hoje + timedelta(days=int(x)))
)

pedido = pedido[[
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

supabase.table("pedido_produtos").insert(
    pedido.to_dict(orient="records")
).execute()

# =============================
# RESUMO FINAL
# =============================
print("\n==============================")
print("📊 RESUMO DA CARGA")
print("==============================")
print(f"📅 Data: {data_hoje}")
print(f"🏬 Lojas atualizadas: {len(lojas)}")
print(f"🚚 Fornecedores atualizados: {len(fornecedores)}")
print(f"📦 Produtos atualizados: {len(produtos)}")
print(f"🛒 Vendas inseridas: {len(fato_vendas)}")
print(f"📦 Estoque inserido: {len(estoque)}")
print(f"⚠️ Quebras registradas: {len(quebra)}")
print(f"🚚 Pedidos gerados: {len(pedido)}")
print("==============================")
print("✅ PROCESSO FINALIZADO COM SUCESSO 🚀")
print("==============================\n")