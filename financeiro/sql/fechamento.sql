CREATE OR REPLACE FUNCTION public.fechamento(p1 date, p2 date, pc integer, us integer)
RETURNS text LANGUAGE plpgsql AS $function$
DECLARE
    empresa integer;
    dia date;
    anterior numeric;
    ultima_data date;
    entradas numeric;
    saidas numeric;
    pendente date;
BEGIN
    IF p1 IS NULL OR p2 IS NULL OR p2 < p1 OR p2 - p1 > 3660 THEN
        RAISE EXCEPTION 'Informe um período válido, de até 3661 dias';
    END IF;
    SELECT empresa_id INTO empresa FROM public.conta_conta WHERE id = pc FOR UPDATE;
    IF empresa IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.usuario_usuario_empresas
        WHERE usuario_id = us AND empresa_id = empresa
    ) THEN
        RAISE EXCEPTION 'Conta ou empresa não autorizada';
    END IF;
    IF EXISTS (SELECT 1 FROM public.conta_movimento WHERE conta_id = pc
               AND empresa_id IS NOT NULL AND empresa_id <> empresa)
       OR EXISTS (SELECT 1 FROM public.financeiro_fechamentocaixa WHERE conta_id = pc
                  AND empresa_id IS NOT NULL AND empresa_id <> empresa) THEN
        RAISE EXCEPTION 'Existem vínculos inconsistentes de empresa nesta conta';
    END IF;
    SELECT MIN(d::date) INTO pendente
    FROM generate_series(p1::timestamp, p2::timestamp, interval '1 day') d
    WHERE NOT EXISTS (SELECT 1 FROM public.financeiro_fechamentocaixa f
                      WHERE f.conta_id = pc AND f.data = d::date);
    IF pendente IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.financeiro_fechamentocaixa WHERE conta_id = pc AND data > pendente
    ) THEN
        RAISE EXCEPTION 'Reabra os fechamentos posteriores antes de inserir uma data anterior';
    END IF;
    FOR dia IN SELECT d::date FROM generate_series(p1::timestamp, p2::timestamp, interval '1 day') d
    LOOP
        IF EXISTS (SELECT 1 FROM public.financeiro_fechamentocaixa WHERE conta_id = pc AND data = dia) THEN
            CONTINUE;
        END IF;
        SELECT saldo, data INTO anterior, ultima_data FROM public.financeiro_fechamentocaixa
        WHERE conta_id = pc AND data < dia ORDER BY data DESC LIMIT 1;
        anterior := COALESCE(anterior, 0);
        -- Inclui os movimentos dos dias ainda sem fechamento, sem perder o saldo inicial.
        SELECT anterior + COALESCE(SUM(CASE tipo_movimento WHEN 'C' THEN valor
                                                          WHEN 'D' THEN -valor ELSE 0 END), 0)
        INTO anterior FROM public.conta_movimento
        WHERE conta_id = pc AND dt_movimento < dia
          AND (ultima_data IS NULL OR dt_movimento > ultima_data);
        SELECT COALESCE(SUM(valor) FILTER (WHERE tipo_movimento = 'C'), 0),
               COALESCE(SUM(valor) FILTER (WHERE tipo_movimento = 'D'), 0)
        INTO entradas, saidas FROM public.conta_movimento WHERE conta_id = pc AND dt_movimento = dia;
        INSERT INTO public.financeiro_fechamentocaixa
            (empresa_id, conta_id, data, hora, receitas, despesas, saldo_anterior, saldo, user_fechamento_id)
        VALUES (empresa, pc, dia, LOCALTIME, entradas, saidas, anterior, anterior + entradas - saidas, us);
    END LOOP;
    RETURN 'Terminado';
END;
$function$;
