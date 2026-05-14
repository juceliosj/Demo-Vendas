# Base simulada de varejo para ML, LLM e Redes Neurais

## Objetivo

Este gerador cria uma base estável para vários testes sem precisar alterar o código toda hora.

Ele gera:

- Vendas
- Demanda real
- Demanda total
- Demanda perdida
- Ruptura
- Estoque diário
- Movimento de estoque
- Entrada de mercadoria
- Baixa/quebra de produto
- Pedido ao fornecedor
- Recebimento de pedido
- Calendário

## Ordem de uso

### 1. Execute o SQL no Supabase

Arquivo:

```text
schema_base_varejo_ml.sql
```

### 2. Carga histórica desde 01/01/2025

```bash
python gerar_base_varejo_ml.py --modo historico --data-inicio 2025-01-01
```

### 3. Carga diária nos próximos dias

```bash
python gerar_base_varejo_ml.py --modo diario
```

## Principais tabelas

### fato_vendas

Tabela para ML de previsão de venda e demanda.

Campos importantes:

- quantidade
- demanda_real
- demanda_total
- demanda_perdida
- percentual_atendimento
- flag_demanda_perdida
- status_ruptura_venda
- valor_total
- valor_demanda_total
- valor_demanda_perdida

### estoque_produtos

Foto diária do estoque por produto e loja.

Campos importantes:

- data_estoque
- produto_id
- loja_id
- quantidade_estoque
- estoque_minimo
- estoque_maximo
- status_ruptura

### movimento_estoque

Tabela para estudar movimentações.

Tipos:

- ENTRADA_PEDIDO
- SAIDA_VENDA
- BAIXA_QUEBRA

### pedido_produtos

Tabela para estudar projeção de pedidos e reposição.

Campos importantes:

- quantidade_pedida
- quantidade_recebida
- data_prevista_entrega
- status_pedido

### recebimento_pedidos

Tabela que gera entrada real no estoque quando o pedido chega.

## Alvos possíveis de ML

Previsão de venda realizada:

```python
y = df["demanda_real"]
```

Previsão de demanda total:

```python
y = df["demanda_total"]
```

Previsão de demanda perdida:

```python
y = df["demanda_perdida"]
```

Classificação de ruptura:

```python
y = df["status_ruptura_venda"]
```

Classificação de churn:

```python
y = df["churn"]
```

## Observação importante

No script antigo, o estoque era recriado aleatoriamente em cada execução.
Nesta nova versão, o estoque do dia seguinte parte do último estoque salvo, soma recebimentos, subtrai vendas e subtrai baixas.
