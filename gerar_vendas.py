import os
import uuid
import argparse
from datetime import datetime, timedelta, date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client


# =====================================================
# GERADOR DE BASE SIMULADA PARA ANALISE, ML, LLM E REDES NEURAIS
# =====================================================
# Objetivo:
# - Gerar histórico desde 01/01/2025 até a data desejada.
# - Depois permitir carga diária incremental.
# - Manter continuidade de estoque entre os dias.
# - Gerar vendas, demanda real, demanda perdida, ruptura, baixa/quebra,
#   pedidos ao fornecedor, recebimento de pedidos e movimento de estoque.
#
# Tabelas principais:
# - lojas
# - fornecedores
# - produtos
# - fato_vendas
# - estoque_produtos
# - movimento_estoque
# - quebra_produtos
# - pedido_produtos
# - recebimento_pedidos
# - calendario
#
# Como usar:
# Carga histórica:
# python gerar_base_varejo_ml.py --modo historico --data-inicio 2025-01-01
#
# Carga diária:
# python gerar_base_varejo_ml.py --modo diario
# =====================================================


# =====================================================
# CONFIGURAÇÕES GERAIS
# =====================================================
SEED = 42

QTD_PRODUTOS = 200
QTD_LOJAS = 5
QTD_FORNECEDORES = 20

QTD_TENTATIVAS_COMPRA_DIA = 900
QTD_QUEBRAS_MAXIMA_DIA = 35

TAMANHO_LOTE = 500

ESTOQUE_INICIAL_MULTIPLICADOR_MIN = 8
ESTOQUE_INICIAL_MULTIPLICADOR_MAX = 22

# Quando estoque ficar menor ou igual ao estoque mínimo, gera pedido.
# Pedido tenta completar até o estoque máximo.
GERAR_PEDIDO_COM_RUPTURA = True

# Percentual máximo de baixa/quebra sobre o estoque disponível de um item sorteado.
PERCENTUAL_MAX_BAIXA = 0.08

# Chance de pedido ser recebido parcialmente.
CHANCE_RECEBIMENTO_PARCIAL = 0.20

# Chance de um fornecedor atrasar a entrega.
CHANCE_PEDIDO_ATRASADO = 0.15


# =====================================================
# CONEXÃO COM SUPABASE
# =====================================================
def conectar_supabase():
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "SUPABASE_URL e SUPABASE_KEY precisam estar configurados no arquivo .env"
        )

    return create_client(supabase_url, supabase_key)


# =====================================================
# FUNÇÕES DE BANCO
# =====================================================
def inserir_em_lotes(supabase, tabela, dataframe, tamanho_lote=TAMANHO_LOTE):
    if dataframe is None or len(dataframe) == 0:
        print(f"{tabela}: nenhum registro para inserir")
        return

    df = dataframe.copy()

    # Converte NaN para None para evitar erro no Supabase.
    df = df.replace({np.nan: None})

    registros = df.to_dict(orient="records")

    for i in range(0, len(registros), tamanho_lote):
        lote = registros[i:i + tamanho_lote]
        supabase.table(tabela).insert(lote).execute()

        print(
            f"{tabela}: lote {i // tamanho_lote + 1} "
            f"inserido com {len(lote)} registros"
        )


def upsert_em_lotes(supabase, tabela, dataframe, chave_conflito, tamanho_lote=TAMANHO_LOTE):
    if dataframe is None or len(dataframe) == 0:
        print(f"{tabela}: nenhum registro para upsert")
        return

    df = dataframe.copy()
    df = df.replace({np.nan: None})
    registros = df.to_dict(orient="records")

    for i in range(0, len(registros), tamanho_lote):
        lote = registros[i:i + tamanho_lote]
        supabase.table(tabela).upsert(
            lote,
            on_conflict=chave_conflito
        ).execute()

        print(
            f"{tabela}: lote {i // tamanho_lote + 1} "
            f"upsert com {len(lote)} registros"
        )


def buscar_tabela(supabase, tabela, colunas="*", limite=100000):
    resposta = supabase.table(tabela).select(colunas).limit(limite).execute()
    dados = resposta.data or []
    return pd.DataFrame(dados)


def buscar_ultimo_estoque(supabase):
    estoque = buscar_tabela(
        supabase,
        "estoque_produtos",
        "data_estoque,produto_id,loja_id,quantidade_estoque,estoque_minimo,estoque_maximo,custo_estoque,status_ruptura"
    )

    if len(estoque) == 0:
        return pd.DataFrame()

    estoque["data_estoque"] = pd.to_datetime(estoque["data_estoque"])

    idx = estoque.groupby(["produto_id", "loja_id"])["data_estoque"].idxmax()

    ultimo = estoque.loc[idx].copy()
    ultimo = ultimo.rename(columns={"quantidade_estoque": "estoque_inicial"})
    ultimo["data_estoque"] = ultimo["data_estoque"].dt.date.astype(str)

    return ultimo


def buscar_pedidos_abertos_ate_data(supabase, data_ref):
    pedidos = buscar_tabela(
        supabase,
        "pedido_produtos",
        "pedido_id,data_pedido,produto_id,loja_id,fornecedor_id,prazo_entrega_dias,quantidade_pedida,quantidade_recebida,data_prevista_entrega,status_pedido"
    )

    if len(pedidos) == 0:
        return pd.DataFrame()

    pedidos["data_prevista_entrega"] = pd.to_datetime(pedidos["data_prevista_entrega"]).dt.date

    pedidos_abertos = pedidos[
        (pedidos["status_pedido"].isin(["Aberto", "Atrasado"]))
        & (pedidos["data_prevista_entrega"] <= data_ref)
    ].copy()

    return pedidos_abertos


# =====================================================
# DIMENSÕES
# =====================================================
def gerar_lojas(qtd_lojas):
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
            qtd_lojas,
            p=[0.25, 0.35, 0.40]
        )
    })

    lojas["loja_id"] = lojas["loja_id"].astype(int)
    return lojas


def gerar_fornecedores(qtd_fornecedores):
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
    return fornecedores


def gerar_produtos(qtd_produtos):
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

    produtos["demanda_base"] = np.select(
        [
            produtos["categoria"] == "Bebidas",
            produtos["categoria"] == "Alimentos",
            produtos["categoria"] == "Higiene",
            produtos["categoria"] == "Limpeza"
        ],
        [22.0, 18.0, 12.0, 9.0],
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

    produtos["margem_bruta_unitaria"] = (
        produtos["preco_base"] - produtos["custo_unitario"]
    ).round(2)

    return produtos


def gerar_calendario(datas):
    calendario = pd.DataFrame({"data": pd.to_datetime(datas)})
    calendario["data"] = calendario["data"].dt.date.astype(str)
    calendario["ano"] = pd.to_datetime(calendario["data"]).dt.year.astype(int)
    calendario["mes"] = pd.to_datetime(calendario["data"]).dt.month.astype(int)
    calendario["dia"] = pd.to_datetime(calendario["data"]).dt.day.astype(int)
    calendario["dia_semana"] = pd.to_datetime(calendario["data"]).dt.dayofweek.astype(int)
    calendario["nome_dia_semana"] = pd.to_datetime(calendario["data"]).dt.day_name()
    calendario["fim_semana"] = calendario["dia_semana"].isin([5, 6]).astype(int)

    feriados_peso = obter_feriados_peso()
    calendario["mes_dia"] = pd.to_datetime(calendario["data"]).dt.strftime("%m-%d")
    calendario["feriado"] = calendario["mes_dia"].isin(feriados_peso.keys()).astype(int)
    calendario["peso_feriado"] = calendario["mes_dia"].map(feriados_peso).fillna(1.0).astype(float)

    return calendario.drop(columns=["mes_dia"])


# =====================================================
# PARÂMETROS DE SIMULAÇÃO
# =====================================================
def obter_feriados_peso():
    return {
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


def temperatura_por_mes(mes):
    if mes in [12, 1, 2]:
        return int(np.random.randint(30, 38))

    if mes in [6, 7]:
        return int(np.random.randint(22, 28))

    return int(np.random.randint(26, 33))


def peso_produto_por_contexto(produtos, mes):
    peso_produto = np.ones(len(produtos))

    if mes in [12, 1, 2]:
        peso_produto = np.where(produtos["categoria"] == "Bebidas", 12, 1)

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

    return peso_produto


def preparar_dimensoes(supabase):
    lojas_existentes = buscar_tabela(supabase, "lojas")
    fornecedores_existentes = buscar_tabela(supabase, "fornecedores")
    produtos_existentes = buscar_tabela(supabase, "produtos")

    if len(lojas_existentes) == 0:
        lojas = gerar_lojas(QTD_LOJAS)
        upsert_em_lotes(supabase, "lojas", lojas, "loja_id")
    else:
        lojas = lojas_existentes.copy()

    if len(fornecedores_existentes) == 0:
        fornecedores = gerar_fornecedores(QTD_FORNECEDORES)
        upsert_em_lotes(supabase, "fornecedores", fornecedores, "fornecedor_id")
    else:
        fornecedores = fornecedores_existentes.copy()

    if len(produtos_existentes) == 0:
        produtos = gerar_produtos(QTD_PRODUTOS)

        produtos_supabase = produtos[[
            "produto_id",
            "produto_nome",
            "categoria",
            "custo_unitario",
            "preco_base"
        ]].copy()

        upsert_em_lotes(supabase, "produtos", produtos_supabase, "produto_id")
    else:
        produtos = produtos_existentes.copy()

        if "demanda_base" not in produtos.columns:
            produtos["demanda_base"] = np.select(
                [
                    produtos["categoria"] == "Bebidas",
                    produtos["categoria"] == "Alimentos",
                    produtos["categoria"] == "Higiene",
                    produtos["categoria"] == "Limpeza"
                ],
                [22.0, 18.0, 12.0, 9.0],
                default=10.0
            )

    lojas["loja_id"] = lojas["loja_id"].astype(int)
    fornecedores["fornecedor_id"] = fornecedores["fornecedor_id"].astype(int)
    fornecedores["prazo_medio_entrega_dias"] = fornecedores["prazo_medio_entrega_dias"].astype(int)

    produtos["produto_id"] = produtos["produto_id"].astype(int)
    produtos["custo_unitario"] = produtos["custo_unitario"].astype(float)
    produtos["preco_base"] = produtos["preco_base"].astype(float)
    produtos["demanda_base"] = produtos["demanda_base"].astype(float)

    return lojas, fornecedores, produtos


# =====================================================
# ESTOQUE
# =====================================================
def gerar_estoque_inicial(produtos, lojas):
    registros = []

    for _, loja in lojas.iterrows():
        for _, produto in produtos.iterrows():
            estoque_minimo = int(produto["demanda_base"] * 2)
            estoque_maximo = int(produto["demanda_base"] * 12)

            quantidade_estoque = np.random.randint(
                int(produto["demanda_base"] * ESTOQUE_INICIAL_MULTIPLICADOR_MIN),
                int(produto["demanda_base"] * ESTOQUE_INICIAL_MULTIPLICADOR_MAX) + 1
            )

            registros.append({
                "produto_id": int(produto["produto_id"]),
                "loja_id": int(loja["loja_id"]),
                "estoque_inicial": int(quantidade_estoque),
                "estoque_minimo": int(estoque_minimo),
                "estoque_maximo": int(estoque_maximo),
                "custo_unitario": float(produto["custo_unitario"])
            })

    return pd.DataFrame(registros)


def obter_estoque_base_do_dia(supabase, produtos, lojas):
    ultimo = buscar_ultimo_estoque(supabase)

    if len(ultimo) == 0:
        estoque_base = gerar_estoque_inicial(produtos, lojas)
        return estoque_base

    estoque_base = ultimo.merge(
        produtos[["produto_id", "custo_unitario", "demanda_base"]],
        on="produto_id",
        how="left"
    )

    if "estoque_minimo" not in estoque_base.columns or estoque_base["estoque_minimo"].isnull().any():
        estoque_base["estoque_minimo"] = (estoque_base["demanda_base"] * 2).astype(int)

    if "estoque_maximo" not in estoque_base.columns or estoque_base["estoque_maximo"].isnull().any():
        estoque_base["estoque_maximo"] = (estoque_base["demanda_base"] * 12).astype(int)

    estoque_base = estoque_base[[
        "produto_id",
        "loja_id",
        "estoque_inicial",
        "estoque_minimo",
        "estoque_maximo",
        "custo_unitario"
    ]].copy()

    estoque_base["estoque_inicial"] = estoque_base["estoque_inicial"].astype(int)
    estoque_base["estoque_minimo"] = estoque_base["estoque_minimo"].astype(int)
    estoque_base["estoque_maximo"] = estoque_base["estoque_maximo"].astype(int)
    estoque_base["custo_unitario"] = estoque_base["custo_unitario"].astype(float)

    return estoque_base


# =====================================================
# RECEBIMENTO DE PEDIDOS
# =====================================================
def gerar_recebimentos_do_dia(supabase, data_ref):
    pedidos_abertos = buscar_pedidos_abertos_ate_data(supabase, data_ref)

    if len(pedidos_abertos) == 0:
        return pd.DataFrame(), pd.DataFrame()

    recebimentos = []

    for _, pedido in pedidos_abertos.iterrows():
        quantidade_pedida = int(pedido["quantidade_pedida"])
        quantidade_ja_recebida = int(pedido.get("quantidade_recebida", 0) or 0)
        saldo_a_receber = max(quantidade_pedida - quantidade_ja_recebida, 0)

        if saldo_a_receber <= 0:
            continue

        recebimento_parcial = np.random.choice(
            [0, 1],
            p=[1 - CHANCE_RECEBIMENTO_PARCIAL, CHANCE_RECEBIMENTO_PARCIAL]
        )

        if recebimento_parcial == 1 and saldo_a_receber > 1:
            quantidade_recebida = int(np.random.randint(1, saldo_a_receber + 1))
        else:
            quantidade_recebida = saldo_a_receber

        recebimentos.append({
            "recebimento_id": str(uuid.uuid4()),
            "pedido_id": str(pedido["pedido_id"]),
            "data_recebimento": str(data_ref),
            "produto_id": int(pedido["produto_id"]),
            "loja_id": int(pedido["loja_id"]),
            "fornecedor_id": int(pedido["fornecedor_id"]),
            "quantidade_recebida": int(quantidade_recebida)
        })

    recebimentos_df = pd.DataFrame(recebimentos)

    if len(recebimentos_df) == 0:
        return pd.DataFrame(), pedidos_abertos

    return recebimentos_df, pedidos_abertos


def aplicar_recebimentos_no_estoque(estoque_base, recebimentos):
    estoque = estoque_base.copy()

    if recebimentos is None or len(recebimentos) == 0:
        estoque["entrada_estoque"] = 0
        return estoque

    receb_agrupado = recebimentos.groupby([
        "produto_id",
        "loja_id"
    ])["quantidade_recebida"].sum().reset_index()

    receb_agrupado = receb_agrupado.rename(
        columns={"quantidade_recebida": "entrada_estoque"}
    )

    estoque = estoque.merge(
        receb_agrupado,
        on=["produto_id", "loja_id"],
        how="left"
    )

    estoque["entrada_estoque"] = estoque["entrada_estoque"].fillna(0).astype(int)

    estoque["estoque_inicial"] = (
        estoque["estoque_inicial"] + estoque["entrada_estoque"]
    ).astype(int)

    return estoque


# =====================================================
# VENDAS E DEMANDA
# =====================================================
def gerar_tentativas_de_compra(data_ref, produtos, lojas):
    dia_semana = data_ref.weekday()
    mes = data_ref.month
    data_mes_dia = data_ref.strftime("%m-%d")

    feriados_peso = obter_feriados_peso()

    peso_fim_semana = 1.60 if dia_semana in [5, 6] else 1.0
    peso_feriado = feriados_peso.get(data_mes_dia, 1.0)

    temperatura = temperatura_por_mes(mes)
    peso_clima = 1.10 if temperatura >= 32 else 1.0

    peso_produto = peso_produto_por_contexto(produtos, mes)

    produtos_escolhidos = produtos.sample(
        QTD_TENTATIVAS_COMPRA_DIA,
        replace=True,
        weights=peso_produto
    )["produto_id"].values

    vendas_dia = pd.DataFrame({
        "venda_id": [
            str(uuid.uuid4()) for _ in range(QTD_TENTATIVAS_COMPRA_DIA)
        ],
        "data_venda": [str(data_ref)] * QTD_TENTATIVAS_COMPRA_DIA,
        "cliente_id": np.random.randint(1, 500, QTD_TENTATIVAS_COMPRA_DIA),
        "loja_id": np.random.choice(lojas["loja_id"], QTD_TENTATIVAS_COMPRA_DIA),
        "tipo_cliente": np.random.choice(
            ["Atacado", "Varejo"],
            QTD_TENTATIVAS_COMPRA_DIA,
            p=[0.35, 0.65]
        ),
        "produto_id": produtos_escolhidos,
        "desconto": np.round(
            np.random.uniform(0, 0.10, QTD_TENTATIVAS_COMPRA_DIA),
            2
        ),
        "dias_desde_ultima_compra": np.random.randint(
            1,
            60,
            QTD_TENTATIVAS_COMPRA_DIA
        ),
        "inadimplente": np.random.choice(
            [0, 1],
            QTD_TENTATIVAS_COMPRA_DIA,
            p=[0.90, 0.10]
        ),
        "temperatura": int(temperatura)
    })

    vendas_dia = vendas_dia.merge(produtos, on="produto_id", how="left")

    vendas_dia["quantidade_extra"] = 0.0

    if temperatura >= 32:
        mask_calor = vendas_dia["categoria"] == "Bebidas"
        vendas_dia.loc[mask_calor, "quantidade_extra"] += np.random.randint(
            10,
            25,
            mask_calor.sum()
        )

    if mes in [12, 1, 2]:
        mask_bebidas = vendas_dia["categoria"] == "Bebidas"
        vendas_dia.loc[mask_bebidas, "quantidade_extra"] += np.random.randint(
            5,
            12,
            mask_bebidas.sum()
        )

    if mes == 6:
        mask_sao_joao = vendas_dia["categoria"].isin(["Alimentos", "Bebidas"])
        vendas_dia.loc[mask_sao_joao, "quantidade_extra"] += np.random.randint(
            4,
            10,
            mask_sao_joao.sum()
        )

    if mes == 11:
        vendas_dia["quantidade_extra"] += np.random.randint(3, 8, len(vendas_dia))

    if mes == 12:
        vendas_dia["quantidade_extra"] += np.random.randint(5, 15, len(vendas_dia))

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
        np.where(vendas_dia["desconto"] >= 0.04, 1.08, 1.0)
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

    vendas_dia["peso_categoria"] = 1.0
    vendas_dia.loc[vendas_dia["categoria"] == "Bebidas", "peso_categoria"] = 1.5
    vendas_dia.loc[vendas_dia["categoria"] == "Alimentos", "peso_categoria"] = 1.3
    vendas_dia.loc[vendas_dia["categoria"] == "Higiene", "peso_categoria"] = 1.1

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

    vendas_dia["peso_final_demanda"] = (
        peso_fim_semana
        * peso_feriado
        * peso_clima
        * vendas_dia["peso_categoria"]
        * vendas_dia["peso_sazonalidade"]
        * vendas_dia["peso_promocao"]
        * vendas_dia["peso_loja"]
        * vendas_dia["peso_fornecedor"]
        * vendas_dia["peso_tipo_cliente"]
    )

    ruido = np.random.normal(loc=1.0, scale=0.08, size=len(vendas_dia))

    vendas_dia["demanda_total"] = np.round(
        (
            vendas_dia["demanda_base"]
            * vendas_dia["peso_final_demanda"]
            * ruido
        )
        + vendas_dia["quantidade_extra"]
    ).astype(int)

    vendas_dia["demanda_total"] = vendas_dia["demanda_total"].clip(lower=1)

    return vendas_dia


def aplicar_estoque_na_demanda(vendas_dia, estoque_base):
    estoque_disponivel = estoque_base[[
        "produto_id",
        "loja_id",
        "estoque_inicial",
        "estoque_minimo",
        "estoque_maximo"
    ]].copy()

    demanda_agrupada = vendas_dia.groupby([
        "produto_id",
        "loja_id"
    ])["demanda_total"].sum().reset_index()

    demanda_agrupada = demanda_agrupada.merge(
        estoque_disponivel,
        on=["produto_id", "loja_id"],
        how="left"
    )

    demanda_agrupada["estoque_inicial"] = demanda_agrupada["estoque_inicial"].fillna(0)

    demanda_agrupada["fator_atendimento"] = np.where(
        demanda_agrupada["demanda_total"] > demanda_agrupada["estoque_inicial"],
        demanda_agrupada["estoque_inicial"] / demanda_agrupada["demanda_total"],
        1
    )

    vendas = vendas_dia.merge(
        demanda_agrupada[[
            "produto_id",
            "loja_id",
            "estoque_inicial",
            "estoque_minimo",
            "estoque_maximo",
            "fator_atendimento"
        ]],
        on=["produto_id", "loja_id"],
        how="left"
    )

    vendas["fator_atendimento"] = vendas["fator_atendimento"].fillna(0)

    vendas["demanda_real"] = np.floor(
        vendas["demanda_total"] * vendas["fator_atendimento"]
    ).astype(int)

    vendas["demanda_perdida"] = (
        vendas["demanda_total"] - vendas["demanda_real"]
    ).clip(lower=0).astype(int)

    vendas["quantidade"] = vendas["demanda_real"]

    vendas["percentual_atendimento"] = np.where(
        vendas["demanda_total"] > 0,
        vendas["demanda_real"] / vendas["demanda_total"],
        0
    )

    vendas["flag_demanda_perdida"] = np.where(
        vendas["demanda_perdida"] > 0,
        1,
        0
    )

    vendas["status_ruptura_venda"] = np.where(
        vendas["percentual_atendimento"] < 1,
        1,
        0
    )

    vendas["preco_unitario"] = np.round(
        vendas["preco_base"] * (1 - vendas["desconto"]),
        2
    )

    vendas["valor_total"] = np.round(
        vendas["demanda_real"] * vendas["preco_unitario"],
        2
    )

    vendas["valor_demanda_total"] = np.round(
        vendas["demanda_total"] * vendas["preco_unitario"],
        2
    )

    vendas["valor_demanda_perdida"] = np.round(
        vendas["demanda_perdida"] * vendas["preco_unitario"],
        2
    )

    vendas["churn"] = np.where(
        (vendas["dias_desde_ultima_compra"] > 30)
        | (vendas["inadimplente"] == 1)
        | (vendas["flag_demanda_perdida"] == 1),
        1,
        0
    )

    # Mantém venda mesmo quando demanda_real = 0, pois isso é importante para estudar ruptura.
    vendas = vendas[
        (vendas["demanda_total"] > 0)
    ].copy()

    return vendas


def preparar_fato_vendas(vendas):
    fato_vendas = vendas[[
        "venda_id",
        "data_venda",
        "cliente_id",
        "loja_id",
        "tipo_cliente",
        "produto_id",
        "quantidade",
        "demanda_real",
        "demanda_total",
        "demanda_perdida",
        "percentual_atendimento",
        "flag_demanda_perdida",
        "status_ruptura_venda",
        "desconto",
        "preco_unitario",
        "valor_total",
        "valor_demanda_total",
        "valor_demanda_perdida",
        "dias_desde_ultima_compra",
        "inadimplente",
        "temperatura",
        "categoria",
        "peso_categoria",
        "peso_sazonalidade",
        "peso_promocao",
        "peso_loja",
        "peso_fornecedor",
        "peso_tipo_cliente",
        "churn"
    ]].copy()

    colunas_int = [
        "cliente_id",
        "loja_id",
        "produto_id",
        "quantidade",
        "demanda_real",
        "demanda_total",
        "demanda_perdida",
        "flag_demanda_perdida",
        "status_ruptura_venda",
        "dias_desde_ultima_compra",
        "inadimplente",
        "temperatura",
        "churn"
    ]

    for coluna in colunas_int:
        fato_vendas[coluna] = fato_vendas[coluna].astype(int)

    colunas_float = [
        "percentual_atendimento",
        "desconto",
        "preco_unitario",
        "valor_total",
        "valor_demanda_total",
        "valor_demanda_perdida",
        "peso_categoria",
        "peso_sazonalidade",
        "peso_promocao",
        "peso_loja",
        "peso_fornecedor",
        "peso_tipo_cliente"
    ]

    for coluna in colunas_float:
        fato_vendas[coluna] = fato_vendas[coluna].astype(float)

    return fato_vendas


# =====================================================
# ESTOQUE, BAIXAS E PEDIDOS
# =====================================================
def gerar_baixas_do_dia(data_ref, estoque_pos_venda):
    produtos_com_estoque = estoque_pos_venda[
        estoque_pos_venda["estoque_pos_venda"] > 0
    ].copy()

    qtd_baixas_real = min(QTD_QUEBRAS_MAXIMA_DIA, len(produtos_com_estoque))

    if qtd_baixas_real <= 0:
        return pd.DataFrame(columns=[
            "quebra_id",
            "data_quebra",
            "produto_id",
            "loja_id",
            "quantidade_quebra",
            "valor_quebra",
            "motivo_quebra"
        ])

    quebra_base = produtos_com_estoque.sample(
        qtd_baixas_real,
        replace=False
    )

    quebra = quebra_base[[
        "produto_id",
        "loja_id",
        "estoque_pos_venda",
        "custo_unitario"
    ]].copy()

    quebra["quebra_id"] = [str(uuid.uuid4()) for _ in range(len(quebra))]
    quebra["data_quebra"] = str(data_ref)

    def calcular_qtd_baixa(estoque):
        max_baixa = max(1, int(estoque * PERCENTUAL_MAX_BAIXA))
        return int(np.random.randint(1, min(max_baixa, int(estoque)) + 1))

    quebra["quantidade_quebra"] = quebra["estoque_pos_venda"].apply(calcular_qtd_baixa)

    quebra["valor_quebra"] = np.round(
        quebra["quantidade_quebra"] * quebra["custo_unitario"],
        2
    )

    quebra["motivo_quebra"] = np.random.choice(
        ["Avaria", "Vencimento", "Perda operacional", "Produto danificado"],
        len(quebra),
        p=[0.25, 0.30, 0.30, 0.15]
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

    quebra["produto_id"] = quebra["produto_id"].astype(int)
    quebra["loja_id"] = quebra["loja_id"].astype(int)
    quebra["quantidade_quebra"] = quebra["quantidade_quebra"].astype(int)
    quebra["valor_quebra"] = quebra["valor_quebra"].astype(float)

    return quebra


def calcular_estoque_final(data_ref, estoque_base, fato_vendas, quebra, recebimentos):
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

    estoque_mov["quantidade_vendida"] = estoque_mov["quantidade_vendida"].fillna(0).astype(int)

    estoque_mov["estoque_pos_venda"] = (
        estoque_mov["estoque_inicial"] - estoque_mov["quantidade_vendida"]
    ).clip(lower=0).astype(int)

    quebra_agrupada = quebra.groupby([
        "produto_id",
        "loja_id"
    ])["quantidade_quebra"].sum().reset_index() if len(quebra) > 0 else pd.DataFrame(columns=[
        "produto_id", "loja_id", "quantidade_quebra"
    ])

    estoque_mov = estoque_mov.merge(
        quebra_agrupada,
        on=["produto_id", "loja_id"],
        how="left"
    )

    estoque_mov["quantidade_quebra"] = estoque_mov["quantidade_quebra"].fillna(0).astype(int)

    estoque_mov["quantidade_estoque"] = (
        estoque_mov["estoque_pos_venda"] - estoque_mov["quantidade_quebra"]
    ).clip(lower=0).astype(int)

    estoque_mov["estoque_id"] = [str(uuid.uuid4()) for _ in range(len(estoque_mov))]
    estoque_mov["data_estoque"] = str(data_ref)

    estoque_mov["custo_estoque"] = np.round(
        estoque_mov["quantidade_estoque"] * estoque_mov["custo_unitario"],
        2
    )

    estoque_mov["status_ruptura"] = np.where(
        estoque_mov["quantidade_estoque"] <= estoque_mov["estoque_minimo"],
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

    estoque["produto_id"] = estoque["produto_id"].astype(int)
    estoque["loja_id"] = estoque["loja_id"].astype(int)
    estoque["quantidade_estoque"] = estoque["quantidade_estoque"].astype(int)
    estoque["estoque_minimo"] = estoque["estoque_minimo"].astype(int)
    estoque["estoque_maximo"] = estoque["estoque_maximo"].astype(int)
    estoque["status_ruptura"] = estoque["status_ruptura"].astype(int)
    estoque["custo_estoque"] = estoque["custo_estoque"].astype(float)

    return estoque, estoque_mov


def gerar_movimento_estoque(data_ref, estoque_mov, recebimentos):
    movimentos = []

    for _, linha in estoque_mov.iterrows():
        produto_id = int(linha["produto_id"])
        loja_id = int(linha["loja_id"])

        entrada = int(linha.get("entrada_estoque", 0) or 0)
        venda = int(linha.get("quantidade_vendida", 0) or 0)
        baixa = int(linha.get("quantidade_quebra", 0) or 0)

        if entrada > 0:
            movimentos.append({
                "movimento_id": str(uuid.uuid4()),
                "data_movimento": str(data_ref),
                "produto_id": produto_id,
                "loja_id": loja_id,
                "tipo_movimento": "ENTRADA_PEDIDO",
                "quantidade": entrada,
                "observacao": "Recebimento de pedido ao fornecedor"
            })

        if venda > 0:
            movimentos.append({
                "movimento_id": str(uuid.uuid4()),
                "data_movimento": str(data_ref),
                "produto_id": produto_id,
                "loja_id": loja_id,
                "tipo_movimento": "SAIDA_VENDA",
                "quantidade": venda,
                "observacao": "Venda de produto"
            })

        if baixa > 0:
            movimentos.append({
                "movimento_id": str(uuid.uuid4()),
                "data_movimento": str(data_ref),
                "produto_id": produto_id,
                "loja_id": loja_id,
                "tipo_movimento": "BAIXA_QUEBRA",
                "quantidade": baixa,
                "observacao": "Baixa por quebra, avaria, vencimento ou perda operacional"
            })

    return pd.DataFrame(movimentos)


def gerar_pedidos_do_dia(data_ref, estoque_mov, fornecedores):
    produtos_para_pedido = estoque_mov[
        estoque_mov["quantidade_estoque"] <= estoque_mov["estoque_minimo"]
    ].copy()

    if len(produtos_para_pedido) == 0:
        return pd.DataFrame(columns=[
            "pedido_id",
            "data_pedido",
            "produto_id",
            "loja_id",
            "fornecedor_id",
            "prazo_entrega_dias",
            "quantidade_pedida",
            "quantidade_recebida",
            "data_prevista_entrega",
            "status_pedido"
        ])

    fornecedor_categoria = fornecedores[[
        "fornecedor_id",
        "categoria_fornecedor",
        "prazo_medio_entrega_dias"
    ]].copy()

    pedidos = produtos_para_pedido.merge(
        fornecedor_categoria,
        left_on="categoria",
        right_on="categoria_fornecedor",
        how="left"
    ) if "categoria" in produtos_para_pedido.columns else produtos_para_pedido.copy()

    if "fornecedor_id" not in pedidos.columns or pedidos["fornecedor_id"].isnull().all():
        pedidos["fornecedor_id"] = np.random.choice(
            fornecedores["fornecedor_id"],
            len(pedidos)
        )
        pedidos["prazo_medio_entrega_dias"] = np.random.choice(
            fornecedores["prazo_medio_entrega_dias"],
            len(pedidos)
        )

    pedidos = pedidos.groupby(["produto_id", "loja_id"]).sample(
        n=1,
        replace=False,
        random_state=None
    ).reset_index(drop=True)

    pedidos["pedido_id"] = [str(uuid.uuid4()) for _ in range(len(pedidos))]
    pedidos["data_pedido"] = str(data_ref)

    pedidos["prazo_entrega_dias"] = pedidos["prazo_medio_entrega_dias"].fillna(
        np.random.randint(2, 15)
    ).astype(int)

    atraso = np.random.choice(
        [0, 1],
        size=len(pedidos),
        p=[1 - CHANCE_PEDIDO_ATRASADO, CHANCE_PEDIDO_ATRASADO]
    )

    pedidos["prazo_entrega_dias"] = pedidos["prazo_entrega_dias"] + np.where(
        atraso == 1,
        np.random.randint(1, 5, len(pedidos)),
        0
    )

    pedidos["quantidade_pedida"] = (
        pedidos["estoque_maximo"] - pedidos["quantidade_estoque"]
    ).clip(lower=1).astype(int)

    pedidos["quantidade_recebida"] = 0

    pedidos["data_prevista_entrega"] = pedidos["prazo_entrega_dias"].apply(
        lambda x: str(data_ref + timedelta(days=int(x)))
    )

    pedidos["status_pedido"] = np.where(atraso == 1, "Atrasado", "Aberto")

    pedidos = pedidos[[
        "pedido_id",
        "data_pedido",
        "produto_id",
        "loja_id",
        "fornecedor_id",
        "prazo_entrega_dias",
        "quantidade_pedida",
        "quantidade_recebida",
        "data_prevista_entrega",
        "status_pedido"
    ]].copy()

    pedidos["produto_id"] = pedidos["produto_id"].astype(int)
    pedidos["loja_id"] = pedidos["loja_id"].astype(int)
    pedidos["fornecedor_id"] = pedidos["fornecedor_id"].astype(int)
    pedidos["prazo_entrega_dias"] = pedidos["prazo_entrega_dias"].astype(int)
    pedidos["quantidade_pedida"] = pedidos["quantidade_pedida"].astype(int)
    pedidos["quantidade_recebida"] = pedidos["quantidade_recebida"].astype(int)

    return pedidos


def atualizar_status_pedidos_recebidos(supabase, recebimentos, pedidos_abertos):
    if len(recebimentos) == 0 or len(pedidos_abertos) == 0:
        return

    recebido_por_pedido = recebimentos.groupby("pedido_id")["quantidade_recebida"].sum().reset_index()

    pedidos_update = pedidos_abertos.merge(
        recebido_por_pedido,
        on="pedido_id",
        how="inner"
    )

    for _, pedido in pedidos_update.iterrows():
        qtd_pedida = int(pedido["quantidade_pedida"])
        qtd_recebida_anterior = int(pedido.get("quantidade_recebida_x", 0) or 0)
        qtd_recebida_agora = int(pedido["quantidade_recebida_y"])
        qtd_total_recebida = qtd_recebida_anterior + qtd_recebida_agora

        status = "Recebido" if qtd_total_recebida >= qtd_pedida else "Parcial"

        supabase.table("pedido_produtos").update({
            "quantidade_recebida": qtd_total_recebida,
            "status_pedido": status
        }).eq("pedido_id", str(pedido["pedido_id"])).execute()


# =====================================================
# PROCESSAMENTO DE UM DIA
# =====================================================
def processar_dia(supabase, data_ref, produtos, lojas, fornecedores):
    print(f"\n📅 Processando data: {data_ref}")

    estoque_base = obter_estoque_base_do_dia(supabase, produtos, lojas)

    recebimentos, pedidos_abertos = gerar_recebimentos_do_dia(supabase, data_ref)

    if len(recebimentos) > 0:
        inserir_em_lotes(supabase, "recebimento_pedidos", recebimentos)
        atualizar_status_pedidos_recebidos(supabase, recebimentos, pedidos_abertos)

    estoque_base = aplicar_recebimentos_no_estoque(estoque_base, recebimentos)

    vendas_dia = gerar_tentativas_de_compra(data_ref, produtos, lojas)
    vendas = aplicar_estoque_na_demanda(vendas_dia, estoque_base)
    fato_vendas = preparar_fato_vendas(vendas)

    inserir_em_lotes(supabase, "fato_vendas", fato_vendas)

    vendas_agrupadas = fato_vendas.groupby([
        "produto_id",
        "loja_id"
    ])["quantidade"].sum().reset_index().rename(
        columns={"quantidade": "quantidade_vendida"}
    )

    estoque_pos_venda = estoque_base.merge(
        vendas_agrupadas,
        on=["produto_id", "loja_id"],
        how="left"
    )

    estoque_pos_venda["quantidade_vendida"] = estoque_pos_venda["quantidade_vendida"].fillna(0).astype(int)

    estoque_pos_venda["estoque_pos_venda"] = (
        estoque_pos_venda["estoque_inicial"] - estoque_pos_venda["quantidade_vendida"]
    ).clip(lower=0).astype(int)

    quebra = gerar_baixas_do_dia(data_ref, estoque_pos_venda)

    if len(quebra) > 0:
        inserir_em_lotes(supabase, "quebra_produtos", quebra)

    estoque, estoque_mov = calcular_estoque_final(
        data_ref,
        estoque_base,
        fato_vendas,
        quebra,
        recebimentos
    )

    # Inclui categoria para escolher fornecedores por categoria ao gerar pedidos.
    estoque_mov = estoque_mov.merge(
        produtos[["produto_id", "categoria"]],
        on="produto_id",
        how="left"
    )

    inserir_em_lotes(supabase, "estoque_produtos", estoque)

    movimento = gerar_movimento_estoque(data_ref, estoque_mov, recebimentos)

    if len(movimento) > 0:
        inserir_em_lotes(supabase, "movimento_estoque", movimento)

    pedidos = gerar_pedidos_do_dia(data_ref, estoque_mov, fornecedores)

    if len(pedidos) > 0:
        inserir_em_lotes(supabase, "pedido_produtos", pedidos)

    resumo = {
        "data": str(data_ref),
        "vendas": len(fato_vendas),
        "demanda_total": int(fato_vendas["demanda_total"].sum()),
        "demanda_real": int(fato_vendas["demanda_real"].sum()),
        "demanda_perdida": int(fato_vendas["demanda_perdida"].sum()),
        "valor_vendido": float(fato_vendas["valor_total"].sum()),
        "valor_demanda_perdida": float(fato_vendas["valor_demanda_perdida"].sum()),
        "recebimentos": len(recebimentos),
        "baixas": len(quebra),
        "estoque": len(estoque),
        "rupturas": int(estoque["status_ruptura"].sum()),
        "pedidos": len(pedidos)
    }

    print("Resumo do dia:")
    print(resumo)

    return resumo


# =====================================================
# ARGUMENTOS
# =====================================================
def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--modo",
        choices=["historico", "diario"],
        default="diario",
        help="historico gera de uma data inicial até hoje; diario gera somente a data informada/hoje"
    )

    parser.add_argument(
        "--data-inicio",
        default="2025-01-01",
        help="Data inicial da carga histórica no formato YYYY-MM-DD"
    )

    parser.add_argument(
        "--data-fim",
        default=None,
        help="Data final no formato YYYY-MM-DD. Se vazio, usa hoje."
    )

    parser.add_argument(
        "--seed",
        default=SEED,
        type=int,
        help="Seed da simulação"
    )

    return parser.parse_args()


# =====================================================
# MAIN
# =====================================================
def main():
    args = parse_args()

    np.random.seed(args.seed)

    supabase = conectar_supabase()

    data_fim = (
        datetime.strptime(args.data_fim, "%Y-%m-%d").date()
        if args.data_fim
        else datetime.now().date()
    )

    if args.modo == "historico":
        data_inicio = datetime.strptime(args.data_inicio, "%Y-%m-%d").date()
    else:
        data_inicio = data_fim

    datas = pd.date_range(start=data_inicio, end=data_fim, freq="D")
    datas_date = [d.date() for d in datas]

    print("\n==============================")
    print("🚀 INICIANDO GERADOR DE DADOS")
    print("==============================")
    print(f"Modo: {args.modo}")
    print(f"Data início: {data_inicio}")
    print(f"Data fim: {data_fim}")
    print(f"Quantidade de dias: {len(datas_date)}")
    print("==============================\n")

    lojas, fornecedores, produtos = preparar_dimensoes(supabase)

    calendario = gerar_calendario(datas_date)
    upsert_em_lotes(supabase, "calendario", calendario, "data")

    resumo_geral = []

    for data_ref in datas_date:
        resumo_dia = processar_dia(
            supabase=supabase,
            data_ref=data_ref,
            produtos=produtos,
            lojas=lojas,
            fornecedores=fornecedores
        )

        resumo_geral.append(resumo_dia)

    resumo_df = pd.DataFrame(resumo_geral)

    print("\n==============================")
    print("📊 RESUMO FINAL DA CARGA")
    print("==============================")
    print(f"📅 Período: {data_inicio} até {data_fim}")
    print(f"🏬 Lojas: {len(lojas)}")
    print(f"🚚 Fornecedores: {len(fornecedores)}")
    print(f"📦 Produtos: {len(produtos)}")
    print(f"🛒 Linhas de venda: {int(resumo_df['vendas'].sum()) if len(resumo_df) else 0}")
    print(f"📈 Demanda total: {int(resumo_df['demanda_total'].sum()) if len(resumo_df) else 0}")
    print(f"✅ Demanda real: {int(resumo_df['demanda_real'].sum()) if len(resumo_df) else 0}")
    print(f"⚠️ Demanda perdida: {int(resumo_df['demanda_perdida'].sum()) if len(resumo_df) else 0}")
    print(f"💰 Valor vendido: {round(float(resumo_df['valor_vendido'].sum()), 2) if len(resumo_df) else 0}")
    print(f"💸 Valor demanda perdida: {round(float(resumo_df['valor_demanda_perdida'].sum()), 2) if len(resumo_df) else 0}")
    print(f"📦 Registros de estoque: {int(resumo_df['estoque'].sum()) if len(resumo_df) else 0}")
    print(f"⚠️ Baixas/quebras: {int(resumo_df['baixas'].sum()) if len(resumo_df) else 0}")
    print(f"🚚 Pedidos: {int(resumo_df['pedidos'].sum()) if len(resumo_df) else 0}")
    print("==============================")
    print("✅ PROCESSO FINALIZADO COM SUCESSO 🚀")
    print("==============================\n")


if __name__ == "__main__":
    main()
