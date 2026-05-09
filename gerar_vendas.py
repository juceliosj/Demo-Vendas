import os
import uuid
import pandas as pd
import numpy as np

from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

print("INICIANDO SCRIPT...")


# =====================================================
# FUNÇÃO PARA INSERIR DADOS EM LOTES NO SUPABASE
# =====================================================
def inserir_em_lotes(tabela, dataframe, tamanho_lote=500):
    registros = dataframe.to_dict(orient="records")

    for i in range(0, len(registros), tamanho_lote):
        lote = registros[i:i + tamanho_lote]

        supabase.table(tabela).insert(lote).execute()

        print(
            f"{tabela}: lote {i // tamanho_lote + 1} "
            f"inserido com {len(lote)} registros"
        )


# =====================================================
# CONEXÃO COM O SUPABASE
# =====================================================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

np.random.seed(42)

data_hoje = datetime.now().date()


# =====================================================
# MODO DE CARGA
# True  = gera histórico desde 01/01/2026 até hoje
# False = gera somente o dia atual
# =====================================================
MODO_CARGA_INICIAL = True

if MODO_CARGA_INICIAL:
    datas = pd.date_range(
        start="2026-01-01",
        end=data_hoje,
        freq="D"
    )
else:
    datas = pd.date_range(
        start=data_hoje,
        end=data_hoje,
        freq="D"
    )


# =====================================================
# CONFIGURAÇÕES
# =====================================================
qtd_produtos = 200
qtd_lojas = 5
qtd_fornecedores = 20

qtd_vendas_por_dia = 500
qtd_quebras_maxima = 30


# =====================================================
# LOJAS
# =====================================================
lojas = pd.DataFrame({
    "loja_id": range(1, qtd_lojas + 1),
    "loja_nome": [f"Loja_{i}" for i in range(1, qtd_lojas + 1)],
    "cidade": np.random.choice(
        ["Salvador", "Feira de Santana", "Camaçari", "Lauro de Freitas"],
        qtd_lojas
    ),
    "estado": ["BA"] * qtd_lojas,
    "tipo_loja": np.random.choice(
        ["Atacado", "Varejo", "Atacarejo"],
        qtd_lojas
    )
})

lojas["loja_id"] = lojas["loja_id"].astype(int)

supabase.table("lojas").upsert(
    lojas.to_dict(orient="records"),
    on_conflict="loja_id"
).execute()


# =====================================================
# FORNECEDORES
# =====================================================
fornecedores = pd.DataFrame({
    "fornecedor_id": range(1, qtd_fornecedores + 1),
    "fornecedor_nome": [
        f"Fornecedor_{i}" for i in range(1, qtd_fornecedores + 1)
    ],
    "categoria_fornecedor": np.random.choice(
        ["Alimentos", "Bebidas", "Higiene", "Limpeza"],
        qtd_fornecedores
    ),
    "prazo_medio_entrega_dias": np.random.randint(2, 15, qtd_fornecedores),
    "estado": np.random.choice(["BA", "SE", "PE", "SP"], qtd_fornecedores)
})

fornecedores["fornecedor_id"] = fornecedores["fornecedor_id"].astype(int)
fornecedores["prazo_medio_entrega_dias"] = fornecedores["prazo_medio_entrega_dias"].astype(int)

supabase.table("fornecedores").upsert(
    fornecedores.to_dict(orient="records"),
    on_conflict="fornecedor_id"
).execute()


# =====================================================
# PRODUTOS
# =====================================================
produtos = pd.DataFrame({
    "produto_id": range(1, qtd_produtos + 1),
    "produto_nome": [
        f"Produto_{i}" for i in range(1, qtd_produtos + 1)
    ],
    "categoria": np.random.choice(
        ["Alimentos", "Bebidas", "Higiene", "Limpeza"],
        qtd_produtos,
        p=[0.40, 0.25, 0.20, 0.15]
    ),
    "custo_unitario": np.round(
        np.random.uniform(1, 30, qtd_produtos),
        2
    ),
    "preco_base": np.round(
        np.random.uniform(5, 60, qtd_produtos),
        2
    )
})

produtos["produto_id"] = produtos["produto_id"].astype(int)
produtos["custo_unitario"] = produtos["custo_unitario"].astype(float)
produtos["preco_base"] = produtos["preco_base"].astype(float)


# =====================================================
# DEMANDA BASE DO PRODUTO
# Usada apenas na simulação Python
# =====================================================
produtos["demanda_base"] = np.select(
    [
        produtos["categoria"] == "Bebidas",
        produtos["categoria"] == "Alimentos",
        produtos["categoria"] == "Higiene",
        produtos["categoria"] == "Limpeza"
    ],
    [
        22.0,
        18.0,
        12.0,
        9.0
    ],
    default=10.0
)

produtos["produto_popular"] = np.random.choice(
    [0, 1],
    size=len(produtos),
    p=[0.75, 0.25]
)

produtos.loc[
    produtos["produto_popular"] == 1,
    "demanda_base"
] = produtos.loc[
    produtos["produto_popular"] == 1,
    "demanda_base"
] * 1.35


# Salva somente colunas existentes na tabela produtos
supabase.table("produtos").upsert(
    produtos[[
        "produto_id",
        "produto_nome",
        "categoria",
        "custo_unitario",
        "preco_base"
    ]].to_dict(orient="records"),
    on_conflict="produto_id"
).execute()


# =====================================================
# FERIADOS
# =====================================================
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


# =====================================================
# ESTOQUE BASE
# Estoque inicial por produto e loja
# =====================================================
estoque_base = []

for _, loja in lojas.iterrows():
    for _, produto in produtos.iterrows():

        estoque_minimo = int(produto["demanda_base"] * 2)
        estoque_maximo = int(produto["demanda_base"] * 12)

        quantidade_estoque = np.random.randint(
            estoque_minimo,
            estoque_maximo + 1
        )

        estoque_base.append({
            "produto_id": int(produto["produto_id"]),
            "loja_id": int(loja["loja_id"]),
            "estoque_inicial": int(quantidade_estoque),
            "estoque_minimo": int(estoque_minimo),
            "estoque_maximo": int(estoque_maximo),
            "custo_unitario": float(produto["custo_unitario"])
        })

estoque_base = pd.DataFrame(estoque_base)


# =====================================================
# GERAÇÃO DE VENDAS
# =====================================================
lista_vendas = []

for data_ref in datas:

    dia_semana = data_ref.dayofweek
    mes = data_ref.month
    data_mes_dia = data_ref.strftime("%m-%d")

    peso_fim_semana = 1.60 if dia_semana in [5, 6] else 1.0
    peso_feriado = feriados_peso.get(data_mes_dia, 1.0)

    # Temperatura por época do ano
    if mes in [12, 1, 2]:
        temperatura = np.random.randint(30, 38)
    elif mes in [6, 7]:
        temperatura = np.random.randint(22, 28)
    else:
        temperatura = np.random.randint(26, 33)

    peso_clima = 1.10 if temperatura >= 32 else 1.0

    # Escolha de produtos por contexto
    peso_produto = np.ones(len(produtos))

    if mes in [12, 1, 2]:
        peso_produto = np.where(
            produtos["categoria"] == "Bebidas",
            12,
            1
        )

    elif mes == 6:
        peso_produto = np.where(
            produtos["categoria"].isin(["Alimentos", "Bebidas"]),
            8,
            1
        )

    elif mes == 11:
        peso_produto = np.where(
            produtos["categoria"].isin(["Higiene", "Limpeza"]),
            5,
            2
        )

    produtos_escolhidos = produtos.sample(
        qtd_vendas_por_dia,
        replace=True,
        weights=peso_produto
    )["produto_id"].values

    vendas_dia = pd.DataFrame({
        "venda_id": [
            str(uuid.uuid4()) for _ in range(qtd_vendas_por_dia)
        ],
        "data_venda": [str(data_ref.date())] * qtd_vendas_por_dia,
        "cliente_id": np.random.randint(1, 500, qtd_vendas_por_dia),
        "loja_id": np.random.choice(lojas["loja_id"], qtd_vendas_por_dia),
        "tipo_cliente": np.random.choice(
            ["Atacado", "Varejo"],
            qtd_vendas_por_dia,
            p=[0.35, 0.65]
        ),
        "produto_id": produtos_escolhidos,
        "desconto": np.round(
            np.random.uniform(0, 0.10, qtd_vendas_por_dia),
            2
        ),
        "dias_desde_ultima_compra": np.random.randint(
            1,
            60,
            qtd_vendas_por_dia
        ),
        "inadimplente": np.random.choice(
            [0, 1],
            qtd_vendas_por_dia,
            p=[0.90, 0.10]
        ),
        "temperatura": int(temperatura)
    })

    vendas_dia = vendas_dia.merge(
        produtos,
        on="produto_id",
        how="left"
    )

    # Quantidade extra por contexto
    vendas_dia["quantidade_extra"] = 0.0

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

    if mes in [12, 1, 2]:
        mask_bebidas = vendas_dia["categoria"] == "Bebidas"

        vendas_dia.loc[
            mask_bebidas,
            "quantidade_extra"
        ] += np.random.randint(
            5,
            12,
            mask_bebidas.sum()
        )

    if mes == 6:
        mask_sao_joao = vendas_dia["categoria"].isin(
            ["Alimentos", "Bebidas"]
        )

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

    # Pesos de comportamento
    vendas_dia["peso_loja"] = np.where(
        vendas_dia["loja_id"].isin([1, 2]),
        1.15,
        1.0
    )

    vendas_dia["peso_tipo_cliente"] = np.where(
        vendas_dia["tipo_cliente"] == "Atacado",
        1.40,
        1.0
    )

    vendas_dia["peso_promocao"] = np.where(
        vendas_dia["desconto"] >= 0.08,
        1.15,
        np.where(
            vendas_dia["desconto"] >= 0.04,
            1.08,
            1.0
        )
    )

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

    quantidade_base = vendas_dia["demanda_base"]

    ruido = np.random.normal(
        loc=1.0,
        scale=0.08,
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


# =====================================================
# UNE TODAS AS VENDAS DO PERÍODO
# =====================================================
vendas = pd.concat(lista_vendas, ignore_index=True)


# =====================================================
# VENDA RESPEITA ESTOQUE DISPONÍVEL
# =====================================================
demanda_por_produto_loja = vendas.groupby([
    "produto_id",
    "loja_id"
])["quantidade"].sum().reset_index()

demanda_por_produto_loja = demanda_por_produto_loja.rename(
    columns={"quantidade": "quantidade_demandada"}
)

demanda_por_produto_loja = demanda_por_produto_loja.merge(
    estoque_base[[
        "produto_id",
        "loja_id",
        "estoque_inicial"
    ]],
    on=["produto_id", "loja_id"],
    how="left"
)

demanda_por_produto_loja["fator_atendimento"] = np.where(
    demanda_por_produto_loja["quantidade_demandada"]
    > demanda_por_produto_loja["estoque_inicial"],
    demanda_por_produto_loja["estoque_inicial"]
    / demanda_por_produto_loja["quantidade_demandada"],
    1
)

vendas = vendas.merge(
    demanda_por_produto_loja[[
        "produto_id",
        "loja_id",
        "fator_atendimento"
    ]],
    on=["produto_id", "loja_id"],
    how="left"
)

vendas["fator_atendimento"] = vendas["fator_atendimento"].fillna(1)

vendas["quantidade"] = np.floor(
    vendas["quantidade"] * vendas["fator_atendimento"]
).astype(int)

vendas = vendas[vendas["quantidade"] > 0].copy()


# =====================================================
# CÁLCULOS FINAIS DE VENDA
# =====================================================
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


# =====================================================
# FATO_VENDAS
# =====================================================
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
]].copy()

# Garantir tipos corretos para o Supabase
colunas_int_vendas = [
    "cliente_id",
    "loja_id",
    "produto_id",
    "quantidade",
    "dias_desde_ultima_compra",
    "inadimplente",
    "temperatura",
    "churn"
]

for coluna in colunas_int_vendas:
    fato_vendas[coluna] = fato_vendas[coluna].astype(int)

colunas_float_vendas = [
    "desconto",
    "preco_unitario",
    "valor_total",
    "peso_categoria",
    "peso_sazonalidade",
    "peso_promocao",
    "peso_loja",
    "peso_ruptura",
    "peso_fornecedor"
]

for coluna in colunas_float_vendas:
    fato_vendas[coluna] = fato_vendas[coluna].astype(float)


inserir_em_lotes(
    "fato_vendas",
    fato_vendas,
    tamanho_lote=500
)


# =====================================================
# ESTOQUE APÓS VENDAS
# =====================================================
vendas_agrupadas = fato_vendas.groupby([
    "produto_id",
    "loja_id"
])["quantidade"].sum().reset_index()

vendas_agrupadas = vendas_agrupadas.rename(
    columns={"quantidade": "quantidade_vendida"}
)

estoque_mov = estoque_base.merge(
    vendas_agrupadas,
    on=["produto_id", "loja_id"],
    how="left"
)

estoque_mov["quantidade_vendida"] = (
    estoque_mov["quantidade_vendida"]
    .fillna(0)
)

estoque_mov["estoque_pos_venda"] = (
    estoque_mov["estoque_inicial"]
    - estoque_mov["quantidade_vendida"]
)

estoque_mov["estoque_pos_venda"] = (
    estoque_mov["estoque_pos_venda"]
    .clip(lower=0)
)


# =====================================================
# QUEBRA DE PRODUTOS
# =====================================================
produtos_com_estoque = estoque_mov[
    estoque_mov["estoque_pos_venda"] > 0
].copy()

qtd_quebras_real = min(
    qtd_quebras_maxima,
    len(produtos_com_estoque)
)

if qtd_quebras_real > 0:

    quebra_base = produtos_com_estoque.sample(
        qtd_quebras_real,
        replace=False
    )

    quebra = quebra_base[[
        "produto_id",
        "loja_id",
        "estoque_pos_venda",
        "custo_unitario"
    ]].copy()

    quebra["quebra_id"] = [
        str(uuid.uuid4()) for _ in range(len(quebra))
    ]

    quebra["data_quebra"] = str(data_hoje)

    quebra["quantidade_quebra"] = quebra["estoque_pos_venda"].apply(
        lambda x: np.random.randint(
            1,
            min(10, int(x)) + 1
        )
    )

    quebra["valor_quebra"] = np.round(
        quebra["quantidade_quebra"]
        * quebra["custo_unitario"],
        2
    )

    quebra["motivo_quebra"] = np.random.choice(
        [
            "Avaria",
            "Vencimento",
            "Perda operacional",
            "Produto danificado"
        ],
        len(quebra)
    )

    quebra = quebra[[
        "quebra_id",
        "data_quebra",
        "produto_id",
        "loja_id",
        "quantidade_quebra",
        "valor_quebra",
        "motivo_quebra"
    ]].copy()

else:

    quebra = pd.DataFrame(columns=[
        "quebra_id",
        "data_quebra",
        "produto_id",
        "loja_id",
        "quantidade_quebra",
        "valor_quebra",
        "motivo_quebra"
    ])

if len(quebra) > 0:

    colunas_int_quebra = [
        "produto_id",
        "loja_id",
        "quantidade_quebra"
    ]

    for coluna in colunas_int_quebra:
        quebra[coluna] = quebra[coluna].astype(int)

    quebra["valor_quebra"] = quebra["valor_quebra"].astype(float)

    inserir_em_lotes(
        "quebra_produtos",
        quebra,
        tamanho_lote=500
    )


# =====================================================
# ESTOQUE APÓS QUEBRA
# =====================================================
if len(quebra) > 0:

    quebra_agrupada = quebra.groupby([
        "produto_id",
        "loja_id"
    ])["quantidade_quebra"].sum().reset_index()

else:

    quebra_agrupada = pd.DataFrame(columns=[
        "produto_id",
        "loja_id",
        "quantidade_quebra"
    ])

estoque_mov = estoque_mov.merge(
    quebra_agrupada,
    on=["produto_id", "loja_id"],
    how="left"
)

estoque_mov["quantidade_quebra"] = (
    estoque_mov["quantidade_quebra"]
    .fillna(0)
)

estoque_mov["quantidade_estoque"] = (
    estoque_mov["estoque_pos_venda"]
    - estoque_mov["quantidade_quebra"]
)

estoque_mov["quantidade_estoque"] = (
    estoque_mov["quantidade_estoque"]
    .clip(lower=0)
)


# =====================================================
# ESTOQUE_PRODUTOS
# =====================================================
estoque_mov["estoque_id"] = [
    str(uuid.uuid4()) for _ in range(len(estoque_mov))
]

estoque_mov["data_estoque"] = str(data_hoje)

estoque_mov["custo_estoque"] = np.round(
    estoque_mov["quantidade_estoque"]
    * estoque_mov["custo_unitario"],
    2
)

estoque_mov["status_ruptura"] = np.where(
    estoque_mov["quantidade_estoque"]
    <= estoque_mov["estoque_minimo"],
    1,
    0
)

estoque = estoque_mov[[
    "estoque_id",
    "data_estoque",
    "produto_id",
    "loja_id",
    "quantidade_estoque",
    "estoque_minimo",
    "estoque_maximo",
    "custo_estoque",
    "status_ruptura"
]].copy()

colunas_int_estoque = [
    "produto_id",
    "loja_id",
    "quantidade_estoque",
    "estoque_minimo",
    "estoque_maximo",
    "status_ruptura"
]

for coluna in colunas_int_estoque:
    estoque[coluna] = estoque[coluna].astype(int)

estoque["custo_estoque"] = estoque["custo_estoque"].astype(float)

inserir_em_lotes(
    "estoque_produtos",
    estoque,
    tamanho_lote=500
)


# =====================================================
# PEDIDOS AO FORNECEDOR
# =====================================================
produtos_para_pedido = estoque_mov[
    estoque_mov["quantidade_estoque"]
    <= estoque_mov["estoque_minimo"]
].copy()

if len(produtos_para_pedido) > 0:

    pedido = produtos_para_pedido.copy()

    pedido["pedido_id"] = [
        str(uuid.uuid4()) for _ in range(len(pedido))
    ]

    pedido["data_pedido"] = str(data_hoje)

    pedido["fornecedor_id"] = np.random.choice(
        fornecedores["fornecedor_id"],
        len(pedido)
    )

    pedido["prazo_entrega_dias"] = np.random.randint(
        2,
        15,
        len(pedido)
    )

    pedido["quantidade_pedida"] = (
        pedido["estoque_maximo"]
        - pedido["quantidade_estoque"]
    )

    pedido["quantidade_pedida"] = (
        pedido["quantidade_pedida"]
        .clip(lower=1)
    )

    pedido["quantidade_recebida"] = 0

    pedido["data_prevista_entrega"] = (
        pedido["prazo_entrega_dias"]
        .apply(lambda x: str(data_hoje + timedelta(days=int(x))))
    )

    pedido["status_pedido"] = np.random.choice(
        ["Aberto", "Atrasado"],
        len(pedido),
        p=[0.85, 0.15]
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
    ]].copy()

else:

    pedido = pd.DataFrame(columns=[
        "pedido_id",
        "data_pedido",
        "produto_id",
        "fornecedor_id",
        "prazo_entrega_dias",
        "quantidade_pedida",
        "quantidade_recebida",
        "data_prevista_entrega",
        "status_pedido"
    ])

if len(pedido) > 0:

    colunas_int_pedido = [
        "produto_id",
        "fornecedor_id",
        "prazo_entrega_dias",
        "quantidade_pedida",
        "quantidade_recebida"
    ]

    for coluna in colunas_int_pedido:
        pedido[coluna] = pedido[coluna].astype(int)

    inserir_em_lotes(
        "pedido_produtos",
        pedido,
        tamanho_lote=500
    )


# =====================================================
# RESUMO FINAL
# =====================================================
print("\n==============================")
print("📊 RESUMO DA CARGA")
print("==============================")
print(f"📅 Data: {data_hoje}")
print(f"🏬 Lojas atualizadas: {len(lojas)}")
print(f"🚚 Fornecedores atualizados: {len(fornecedores)}")
print(f"📦 Produtos atualizados: {len(produtos)}")
print(f"🛒 Vendas inseridas: {len(fato_vendas)}")
print(f"📦 Estoque gerado: {len(estoque)}")
print(f"⚠️ Quebras registradas: {len(quebra)}")
print(f"🚚 Pedidos gerados: {len(pedido)}")
print("==============================")
print("✅ PROCESSO FINALIZADO COM SUCESSO 🚀")
print("==============================\n")