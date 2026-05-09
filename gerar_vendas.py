import os
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from supabase import create_client
from dotenv import load_dotenv

print("INICIANDO SCRIPT...")

def inserir_em_lotes(tabela, dataframe, tamanho_lote=500):
    registros = dataframe.to_dict(orient="records")

    for i in range(0, len(registros), tamanho_lote):
        lote = registros[i:i + tamanho_lote]

        supabase.table(tabela).insert(lote).execute()

        print(f"{tabela}: lote {i // tamanho_lote + 1} inserido com {len(lote)} registros")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

np.random.seed()

data_hoje = datetime.now().date()

MODO_CARGA_INICIAL = True

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
qtd_vendas = 1000
qtd_estoque = 400
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

feriados_peso = {
    "01-01": 1.30,
    "02-16": 1.35,
    "02-17": 1.35,
    "04-03": 1.25,
    "05-10": 1.30,
    "06-24": 1.40,
    "08-09": 1.20,
    "11-27": 1.60,
    "12-24": 1.60,
    "12-25": 1.70,
    "12-31": 1.40
}

lista_vendas = []

for data_ref in datas:

    dia_semana = data_ref.dayofweek
    mes = data_ref.month
    data_mes_dia = data_ref.strftime("%m-%d")

    peso_fim_semana = 1.60 if dia_semana in [5, 6] else 1.0
    peso_feriado = feriados_peso.get(data_mes_dia, 1.0)

    if mes in [12, 1, 2]:
        temperatura = np.random.randint(30, 38)
    elif mes in [6, 7]:
        temperatura = np.random.randint(22, 28)
    else:
        temperatura = np.random.randint(26, 33)

    peso_clima = 1.10 if temperatura >= 32 else 1.0

    # =============================
    # ESCOLHA DE PRODUTOS POR CONTEXTO
    # =============================

    if mes in [12, 1, 2]:

        produtos_escolhidos = produtos.sample(
            qtd_vendas,
            replace=True,
            weights=np.where(
                produtos["categoria"] == "Bebidas",
                15,
                1
            )
        )["produto_id"].values

    elif mes == 6:

        produtos_escolhidos = produtos.sample(
            qtd_vendas,
            replace=True,
            weights=np.where(
                produtos["categoria"].isin(
                    ["Alimentos", "Bebidas"]
                ),
                10,
                1
            )
        )["produto_id"].values

    else:

        produtos_escolhidos = produtos.sample(
            qtd_vendas,
            replace=True
        )["produto_id"].values


    vendas_dia = pd.DataFrame({
        "venda_id": [str(uuid.uuid4()) for _ in range(qtd_vendas)],
        "data_venda": [str(data_ref.date())] * qtd_vendas,
        "cliente_id": np.random.randint(1, 500, qtd_vendas),
        "loja_id": np.random.choice(lojas["loja_id"], qtd_vendas),
        "tipo_cliente": np.random.choice(["Atacado", "Varejo"], qtd_vendas, p=[0.35, 0.65]),
        "produto_id": produtos_escolhidos,
        "desconto": np.round(np.random.uniform(0, 0.15, qtd_vendas), 2),
        "dias_desde_ultima_compra": np.random.randint(1, 60, qtd_vendas),
        "inadimplente": np.random.choice([0, 1], qtd_vendas, p=[0.90, 0.10]),
        "temperatura": temperatura
    })

    vendas_dia = vendas_dia.merge(
        produtos,
        on="produto_id",
        how="left"
    )

    # =============================
    # QUANTIDADE EXTRA POR CONTEXTO
    # =============================
    vendas_dia["quantidade_extra"] = 0

    # =============================
    # CALOR AUMENTA BEBIDAS
    # =============================
    if temperatura >= 32:

        mask_calor = vendas_dia["categoria"] == "Bebidas"

        vendas_dia.loc[
            mask_calor,
            "quantidade_extra"
        ] += np.random.randint(
            10,
            25,
            mask_calor.sum()
        )

    # VERÃO AUMENTA BEBIDAS    
    if mes in [12, 1, 2]:
        mask_bebidas = vendas_dia["categoria"] == "Bebidas"

        vendas_dia.loc[
            mask_bebidas,
            "quantidade_extra"
        ] = np.random.randint(
            5,
            12,
            mask_bebidas.sum()
        )

    if mes == 6:
        mask_sao_joao = vendas_dia["categoria"].isin(["Alimentos", "Bebidas"])

        vendas_dia.loc[
            mask_sao_joao,
            "quantidade_extra"
        ] += np.random.randint(
            4,
            10,
            mask_sao_joao.sum()
        )

    if mes == 11:
        vendas_dia["quantidade_extra"] += np.random.randint(
            3,
            8,
            len(vendas_dia)
        )

    if mes == 12:
        vendas_dia["quantidade_extra"] += np.random.randint(
            5,
            15,
            len(vendas_dia)
        )

    # =============================
    # LOJA PREMIUM VENDE MAIS
    # =============================
    vendas_dia["peso_loja"] = np.where(
        vendas_dia["loja_id"].isin([1, 2]),
        1.15,
        1.0
    )

    # =============================
    # ATACADO
    # =============================    
    vendas_dia["peso_tipo_cliente"] = np.where(
        vendas_dia["tipo_cliente"] == "Atacado",
        1.40,
        1.0
    )
    # =============================
    # PROMOÇÃO AUMENTA DEMANDA
    # =============================
    vendas_dia["peso_promocao"] = np.where(
        vendas_dia["desconto"] >= 0.20,
        1.20,
        np.where(
            vendas_dia["desconto"] >= 0.10,
            1.10,
            1.0
        )
    )

    # =============================
    # ATRASO FORNECEDOR
    # =============================
    vendas_dia["fornecedor_atrasado"] = np.random.choice(
        [0, 1],
        size=len(vendas_dia),
        p=[0.90, 0.10]
    )

    vendas_dia["peso_fornecedor"] = np.where(
        vendas_dia["fornecedor_atrasado"] == 1,
        0.90,
        1.0
    )

    # =============================
    # RUPTURA REDUZ VENDA
    # =============================
    vendas_dia["estoque_simulado"] = np.random.randint(
        0,
        300,
        len(vendas_dia)
    )

    vendas_dia["estoque_minimo_simulado"] = np.random.randint(
        20,
        80,
        len(vendas_dia)
    )

    vendas_dia["status_ruptura_simulado"] = np.where(
        vendas_dia["estoque_simulado"] <= vendas_dia["estoque_minimo_simulado"],
        1,
        0
    )

    vendas_dia["peso_ruptura"] = np.where(
        vendas_dia["status_ruptura_simulado"] == 1,
        0.70,
        1.0
    )

    # =============================
    # PESO POR CATEGORIA
    # =============================
    vendas_dia["peso_categoria"] = 1.0

    vendas_dia.loc[
        vendas_dia["categoria"] == "Bebidas",
        "peso_categoria"
    ] = 1.5

    vendas_dia.loc[
        vendas_dia["categoria"] == "Alimentos",
        "peso_categoria"
    ] = 1.3

    vendas_dia.loc[
        vendas_dia["categoria"] == "Higiene",
        "peso_categoria"
    ] = 1.1

    vendas_dia.loc[
        vendas_dia["categoria"] == "Limpeza",
        "peso_categoria"
    ] = 1.0

    # =============================
    # SAZONALIDADE
    # =============================
    vendas_dia["peso_sazonalidade"] = 1.0

    if mes in [1, 2, 12]:
        vendas_dia.loc[
            vendas_dia["categoria"] == "Bebidas",
            "peso_sazonalidade"
        ] = 1.20

    if mes == 6:
        vendas_dia.loc[
            vendas_dia["categoria"].isin(["Alimentos", "Bebidas"]),
            "peso_sazonalidade"
        ] = 1.30

    if mes == 11:
        vendas_dia["peso_sazonalidade"] = 1.50

    if mes == 12:
        vendas_dia["peso_sazonalidade"] = 1.60

    # =============================
    # PESO FINAL
    # =============================
    vendas_dia["peso_final"] = (
        peso_fim_semana
        * peso_feriado
        * peso_clima
        * vendas_dia["peso_categoria"]
        * vendas_dia["peso_sazonalidade"]
        * vendas_dia["peso_ruptura"]
        * vendas_dia["peso_promocao"]
        * vendas_dia["peso_loja"]
        * vendas_dia["peso_fornecedor"]
        * vendas_dia["peso_tipo_cliente"]
    )

    quantidade_base = np.random.randint(
        8,
        15,
        qtd_vendas
    )

    ruido = np.random.normal(
        loc=1.0,
        scale=0.10,
        size=len(vendas_dia)
    )

    vendas_dia["quantidade"] = np.round(
        (
            quantidade_base
            * vendas_dia["peso_final"]
            * ruido
        )
        + vendas_dia["quantidade_extra"]
    ).astype(int)

    vendas_dia["quantidade"] = vendas_dia["quantidade"].clip(lower=1)

    lista_vendas.append(vendas_dia)

vendas = pd.concat(lista_vendas, ignore_index=True)


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
    "temperatura",
    "peso_categoria",
    "peso_sazonalidade",
    "peso_promocao",
    "peso_loja",
    "peso_ruptura",
    "peso_fornecedor",
    "churn"
]]

inserir_em_lotes("fato_vendas", fato_vendas, tamanho_lote=500)

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

inserir_em_lotes("estoque_produtos", estoque, tamanho_lote=500)

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

inserir_em_lotes("quebra_produtos", quebra, tamanho_lote=500)

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

inserir_em_lotes("pedido_produtos", pedido, tamanho_lote=500)

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