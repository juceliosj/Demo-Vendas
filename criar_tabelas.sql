-- =============================
-- PRODUTOS (DIMENSÃO)
-- =============================
create table if not exists produtos (
  produto_id int primary key,
  produto_nome text,
  categoria text,
  custo_unitario numeric,
  preco_base numeric
);

-- =============================
-- VENDAS (FATO)
-- =============================
create table if not exists fato_vendas (
  venda_id uuid primary key,
  data_venda date,
  cliente_id int,
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
  loja_id int,
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
  loja_id int,
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
  fornecedor_id int,
  prazo_entrega_dias int,
  quantidade_pedida int,
  quantidade_recebida int,
  data_prevista_entrega date,
  status_pedido text
);

-- =============================
-- ATIVAR RLS
-- =============================
alter table produtos enable row level security;
alter table fato_vendas enable row level security;
alter table estoque_produtos enable row level security;
alter table quebra_produtos enable row level security;
alter table pedido_produtos enable row level security;

-- =============================
-- POLÍTICAS PRODUTOS (UPSERT)
-- =============================
create policy "produtos_select"
on produtos for select to anon using (true);

create policy "produtos_insert"
on produtos for insert to anon with check (true);

create policy "produtos_update"
on produtos for update to anon using (true) with check (true);

-- =============================
-- VENDAS
-- =============================
create policy "vendas_insert"
on fato_vendas for insert to anon with check (true);

create policy "vendas_select"
on fato_vendas for select to anon using (true);

-- =============================
-- ESTOQUE
-- =============================
create policy "estoque_insert"
on estoque_produtos for insert to anon with check (true);

create policy "estoque_select"
on estoque_produtos for select to anon using (true);

-- =============================
-- QUEBRA
-- =============================
create policy "quebra_insert"
on quebra_produtos for insert to anon with check (true);

create policy "quebra_select"
on quebra_produtos for select to anon using (true);

-- =============================
-- PEDIDOS
-- =============================
create policy "pedido_insert"
on pedido_produtos for insert to anon with check (true);

create policy "pedido_select"
on pedido_produtos for select to anon using (true);