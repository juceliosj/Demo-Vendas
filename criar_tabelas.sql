-- =============================
-- DIMENSÕES
-- =============================

create table if not exists produtos (
  produto_id int primary key,
  produto_nome text,
  categoria text,
  custo_unitario numeric,
  preco_base numeric
);

create table if not exists lojas (
  loja_id int primary key,
  loja_nome text,
  cidade text,
  estado text,
  tipo_loja text
);

create table if not exists fornecedores (
  fornecedor_id int primary key,
  fornecedor_nome text,
  categoria_fornecedor text,
  prazo_medio_entrega_dias int,
  estado text
);

-- =============================
-- FATO VENDAS
-- =============================

create table if not exists fato_vendas (
  venda_id uuid primary key,
  data_venda date,
  cliente_id int,
  loja_id int references lojas(loja_id),
  tipo_cliente text,
  produto_id int references produtos(produto_id),
  quantidade int,
  desconto numeric,
  preco_unitario numeric,
  valor_total numeric,
  dias_desde_ultima_compra int,
  inadimplente int,
  churn int
);

-- =============================
-- ESTOQUE
-- =============================

create table if not exists estoque_produtos (
  estoque_id uuid primary key,
  data_estoque date,
  produto_id int references produtos(produto_id),
  loja_id int references lojas(loja_id),
  quantidade_estoque int,
  estoque_minimo int,
  estoque_maximo int,
  custo_estoque numeric,
  status_ruptura int
);

-- =============================
-- QUEBRA
-- =============================

create table if not exists quebra_produtos (
  quebra_id uuid primary key,
  data_quebra date,
  produto_id int references produtos(produto_id),
  loja_id int references lojas(loja_id),
  quantidade_quebra int,
  valor_quebra numeric,
  motivo_quebra text
);

-- =============================
-- PEDIDOS
-- =============================

create table if not exists pedido_produtos (
  pedido_id uuid primary key,
  data_pedido date,
  produto_id int references produtos(produto_id),
  fornecedor_id int references fornecedores(fornecedor_id),
  prazo_entrega_dias int,
  quantidade_pedida int,
  quantidade_recebida int,
  data_prevista_entrega date,
  status_pedido text
);

-- ATIVAR RLS
alter table produtos enable row level security;
alter table lojas enable row level security;
alter table fornecedores enable row level security;
alter table fato_vendas enable row level security;
alter table estoque_produtos enable row level security;
alter table quebra_produtos enable row level security;
alter table pedido_produtos enable row level security;

-- PRODUTOS
create policy "produtos_all" on produtos for all to anon using (true) with check (true);

-- LOJAS
create policy "lojas_all" on lojas for all to anon using (true) with check (true);

-- FORNECEDORES
create policy "fornecedores_all" on fornecedores for all to anon using (true) with check (true);

-- VENDAS
create policy "vendas_all" on fato_vendas for all to anon using (true) with check (true);

-- ESTOQUE
create policy "estoque_all" on estoque_produtos for all to anon using (true) with check (true);

-- QUEBRA
create policy "quebra_all" on quebra_produtos for all to anon using (true) with check (true);

-- PEDIDOS
create policy "pedido_all" on pedido_produtos for all to anon using (true) with check (true);