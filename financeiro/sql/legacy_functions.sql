CREATE OR REPLACE FUNCTION public.fechamento(p1 date, p2 date, pc integer, us integer) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE 
 rec_data  RECORD;
 cur_datas CURSOR FOR SELECT cast('2018-01-01' as date) + s.a AS dates FROM generate_series(1,730) AS s(a);
BEGIN
   -- Open the cursor
   OPEN cur_datas;
 
   LOOP
    -- fetch row into the film
      FETCH cur_datas INTO rec_data;
    -- exit when no more row to fetch
      EXIT WHEN NOT FOUND;
     -- build the output
     IF rec_data.dates > $2 THEN
        EXIT;
     END IF;
     
     EXECUTE FORMAT('insert into financeiro_fechamentocaixa (data,  hora,  receitas,  despesas,  saldo, saldo_anterior,  user_fechamento_id,  conta_id)
   select 
          tab1.dt_movimento,
          tab1.hora,
          sum(Case mov.tipo_movimento when ''C'' then mov.valor else 0 end) as receitas,
          sum(Case mov.tipo_movimento when ''D'' then mov.valor else 0 end) as despesas,
          (sum(Case mov.tipo_movimento when ''C'' then mov.valor else 0 end) + (select coalesce(sum(saldo),0) from financeiro_fechamentocaixa where conta_id = tab1.conta_id and data = (tab1.dt_movimento - interval ''1 day'') )) - sum(Case mov.tipo_movimento when ''D'' then mov.valor else 0 end) as saldo,
          (select coalesce(sum(saldo),0) from financeiro_fechamentocaixa where conta_id = tab1.conta_id and data = (tab1.dt_movimento - interval ''1 day'') ) saldo_anterior,
          tab1.user,
          tab1.conta_id
   from (
     select b.dates as dt_movimento, 
    ''17:00:00''::time as hora,
    %s as user,
    c.id as conta_id
    from (SELECT cast(''%I'' as date) + s.a AS dates FROM generate_series(1,730) AS s(a)) b
        left join conta_conta c on 1=1 
    where b.dates = ''%I''
        ) tab1 
        left join conta_movimento mov on tab1.dt_movimento = mov.dt_movimento and mov.conta_id = tab1.conta_id
        where tab1.conta_id = %L 
        and not exists (select 1 from financeiro_fechamentocaixa fd where fd.conta_id = tab1.conta_id and fd.data = tab1.dt_movimento)
                         
   group by 1,2,7,8',$4,$1,rec_data.dates,$3);

      
   END LOOP;
  
   -- Close the cursor
   CLOSE cur_datas;
 
   RETURN 'Terminado';
END; $_$;

CREATE OR REPLACE FUNCTION public.fn_analise(dt_inicial date, dt_final date) RETURNS TABLE(id bigint, tipo_movimento character varying, exercicio double precision, centrocusto character varying, tipodespesa character varying, janp numeric, fevp numeric, marp numeric, abrp numeric, maip numeric, junp numeric, julp numeric, agop numeric, setp numeric, outp numeric, novp numeric, dezp numeric, janr numeric, fevr numeric, marr numeric, abrr numeric, mair numeric, junr numeric, julr numeric, agor numeric, setr numeric, outr numeric, novr numeric, dezr numeric)
    LANGUAGE sql
    AS $_$

select 
   ROW_NUMBER() OVER (ORDER BY tabela.exercicio) as id,
   tabela.*

from (
 select DISTINCT 
    tab.tipo_movimento,
    tab.exercicio,
    tab.CentroCusto,
    tab.TipoDespesa,
   
    Sum( Case when (tab.competencia = 1 and tp = 'P') then tab.valor else 0 end) JanP,
    Sum( Case when (tab.competencia = 2 and tp = 'P') then tab.valor else 0 end) FevP,
    Sum( Case when (tab.competencia = 3 and tp = 'P') then tab.valor else 0 end) MarP,
    Sum( Case when (tab.competencia = 4 and tp = 'P') then tab.valor else 0 end) AbrP,
    Sum( Case when (tab.competencia = 5 and tp = 'P') then tab.valor else 0 end) MaiP,
    Sum( Case when (tab.competencia = 6 and tp = 'P') then tab.valor else 0 end) JunP,
    Sum( Case when (tab.competencia = 7 and tp = 'P') then tab.valor else 0 end) JulP,
    Sum( Case when (tab.competencia = 8 and tp = 'P') then tab.valor else 0 end) AgoP,
    Sum( Case when (tab.competencia = 9 and tp = 'P') then tab.valor else 0 end) SetP,
    Sum( Case when (tab.competencia = 10 and tp = 'P') then tab.valor else 0 end) OutP,
    Sum( Case when (tab.competencia = 11 and tp = 'P') then tab.valor else 0 end) NovP,
    Sum( Case when (tab.competencia = 12 and tp = 'P') then tab.valor else 0 end) DezP,

    Sum( Case when (tab.competencia = 1 and tp = 'R') then tab.valor else 0 end) JanR,
    Sum( Case when (tab.competencia = 2 and tp = 'R') then tab.valor else 0 end) FevR,
    Sum( Case when (tab.competencia = 3 and tp = 'R') then tab.valor else 0 end) MarR,
    Sum( Case when (tab.competencia = 4 and tp = 'R') then tab.valor else 0 end) AbrR,
    Sum( Case when (tab.competencia = 5 and tp = 'R') then tab.valor else 0 end) MaiR,
    Sum( Case when (tab.competencia = 6 and tp = 'R') then tab.valor else 0 end) JunR,
    Sum( Case when (tab.competencia = 7 and tp = 'R') then tab.valor else 0 end) JulR,
    Sum( Case when (tab.competencia = 8 and tp = 'R') then tab.valor else 0 end) AgoR,
    Sum( Case when (tab.competencia = 9 and tp = 'R') then tab.valor else 0 end) SetR,
    Sum( Case when (tab.competencia = 10 and tp = 'R') then tab.valor else 0 end) OutR,
    Sum( Case when (tab.competencia = 11 and tp = 'R') then tab.valor else 0 end) NovR,
    Sum( Case when (tab.competencia = 12 and tp = 'R') then tab.valor else 0 end) DezR
        
 from (

      select 'R' tp,
          a.tipo_movimento,
          extract('year' from a.dt_movimento) exercicio,
          extract('month' from a.dt_movimento) competencia,
          a.dt_movimento,
          c.conta,
   '111-RECEITA'::character Varying CentroCusto,
   '000-RECEITA'::character Varying TipoDespesa,
          a.valor
     from conta_movimento a
        join financeiro_recreceita r on r.id = a.receita_id    
        left join financeiro_docreceita b on b.id = r.receita_id
        left join (
       select con.id, concat(ban.nome,'-',con.numeroconta,'-',con.descricao) conta 
         from conta_conta con
         join conta_banco ban on ban.id = banco_id
                  ) c on c.id = a.conta_id
   where a.dt_movimento between $1 and $2   
     and a.tipo_movimento = 'C'
     
   union all
   
   select 'R' tp,
          a.tipo_movimento,
          extract('year' from a.dt_movimento) exercicio,
          extract('month' from a.dt_movimento) competencia,
          a.dt_movimento,
          c.conta,
   '111-RECEITA'::character Varying CentroCusto,
   '000-RECEITA'::character Varying TipoDespesa,
          a.valor
     from conta_movimento a
        left join (
       select con.id, concat(ban.nome,'-',con.numeroconta,'-',con.descricao) conta 
         from conta_conta con
         join conta_banco ban on ban.id = banco_id
                  ) c on c.id = a.conta_id
   where a.dt_movimento between $1 and $2   
     and a.receita_id is null
     and a.transferencia_id is null
     and a.tipo_movimento = 'C'

   union all
   
   select 'R' tp, a.tipo_movimento,
          extract('year' from a.dt_movimento) exercicio,
          extract('month' from a.dt_movimento) competencia,
          a.dt_movimento,
          e.conta,
   Case 
      when c.codigo is null then '999-SEM'
      else concat(c.codigo,'-',c.descricao) 
   end CentroCusto,
   Case
      when d.codigo is null then '999-SEM'
      else concat(d.codigo,'-',d.descricao) 
   End TipoDespesa,
          a.valor
     from conta_movimento a
        join financeiro_pagdespesa bb on bb.id = a.despesa_id
        left join financeiro_docdespesa b on b.id = bb.despesa_id
        left join contabil_centrocusto c on c.id = b.centro_custo_id
        left join contabil_tipodespesa d on d.id = b.tipo_despesa_id
        left join (
      select con.id, concat(ban.nome,'-',con.numeroconta,'-',con.descricao) conta 
        from conta_conta con
        join conta_banco ban on ban.id = banco_id
           ) e on e.id = a.conta_id
   where a.dt_movimento between $1 and $2  
     and a.tipo_movimento = 'D'

union all

     select 'P' tp,  'C'::character Varying tipo_movimento,
     extract('year' from a.dt_data_vencimento) exercicio,
     extract('month' from a.dt_data_vencimento) competencia,
     b.dt_vencimento as dt_movimento,
     null::character Varying conta,
     '111-RECEITA'::character Varying CentroCusto,
     '000-RECEITA'::character Varying TipoDespesa,
     b.valor
       from notas_nota A
            join financeiro_docreceita b on b.nota_id = a.id
     where 1=1
       and a.dt_data_vencimento between $1 and $2   
       
     union all 
    
     select 'P' tp, 'D'::character Varying tipo_movimento,
     extract('year' from b.dt_vencimento) exercicio,
     extract('month' from b.dt_vencimento) competencia,
     b.dt_vencimento as dt_movimento,
     null::character Varying conta,
     Case 
        when c.codigo is null then '999-SEM'
        else concat(c.codigo,'-',c.descricao) 
     end CentroCusto,
                          Case
                             when d.codigo is null then '999-SEM'
                             else concat(d.codigo,'-',d.descricao) 
                          End TipoDespesa,
     b.valor
       from financeiro_docdespesa b 
   left join contabil_centrocusto c on c.id = b.centro_custo_id
   left join contabil_tipodespesa d on d.id = b.tipo_despesa_id
     where b.dt_vencimento between $1 and $2  
       

    ) tab
 group by 1,2,3,4
 order by 1,2,3,4
) tabela
$_$;
DROP FUNCTION IF EXISTS public.fn_analise(date,date,integer);
