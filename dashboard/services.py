import calendar
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from clientes.models import Cliente, Parceiro
from contratos.models import Contrato
from financeiro.models import DocReceita, RecReceita
from notas.models import Nota
from .serializers import AlertaSerializer, ParceiroResumoSerializer


def competencia_atual(user):
    today = timezone.localdate()
    return {'mes': user.ultimo_mes if 1 <= user.ultimo_mes <= 12 else today.month,
            'ano': user.ultimo_ano if 1900 <= user.ultimo_ano <= 9999 else today.year}


def permissoes(user):
    return {
        'clientes': user.has_perm('clientes.view_cliente'),
        'notas': user.has_perm('notas.view_nota'),
        'receitas': user.has_perm('financeiro.view_docreceita'),
        'parceiros': user.has_perm('clientes.view_cliente') and user.has_perm('clientes.view_parceiro'),
        'alertas': user.has_perm('contratos.view_contrato'),
    }


def resumo(user, empresa, allowed, mes, ano, pagina_alertas):
    today = timezone.localdate()
    customers = Cliente.objects.filter(empresa_id=empresa)
    if user.uf_id:
        customers = customers.filter(uf_id=user.uf_id)
    contracts = Contrato.objects.filter(empresa_id=empresa, cliente__in=customers)
    notes = Nota.objects.filter(empresa_id=empresa, contrato__in=contracts)
    data = {'empresa': empresa, 'mes': mes, 'ano': ano, 'atualizado_em': timezone.now(), 'permissoes': allowed,
            'clientes': None, 'notas': None, 'receitas': None, 'parceiros': None, 'alertas': None}
    if allowed['clientes']:
        data['clientes'] = customers.aggregate(total=Count('pk'), ativos=Count('pk', filter=Q(ativo=True)))
    if allowed['notas']:
        annual = notes.filter(exercicio=ano)
        data['notas'] = annual.filter(competencia=mes).aggregate(
            total=Count('pk'), com_pagamento_registrado=Count('pk', filter=Q(dt_data_pagamento__isnull=False)),
            canceladas=Count('pk', filter=Q(cancelada_em__isnull=False)))
        grouped = {row['competencia']: row for row in annual.order_by().values('competencia').annotate(
            cadastradas=Count('pk'), com_pagamento_registrado=Count('pk', filter=Q(dt_data_pagamento__isnull=False)))}
        data['notas']['mensal'] = [grouped.get(month, {'competencia': month, 'cadastradas': 0, 'com_pagamento_registrado': 0}) for month in range(1, 13)]
    if allowed['receitas']:
        # Baixas reais são a fonte; o cache legado e o marcador da nota não
        # substituem recebimentos parciais ou seus estornos.
        totals = RecReceita.objects.filter(receita_id=OuterRef('pk')).order_by().values('receita_id').annotate(total=Sum('valor')).values('total')
        money = DecimalField(max_digits=20, decimal_places=2)
        zero = Value(Decimal('0.00'), output_field=money)
        docs = DocReceita.objects.filter(empresa_id=empresa, cliente__in=customers,
            dt_vencimento__range=(date(ano, mes, 1), date(ano, mes, calendar.monthrange(ano, mes)[1])))
        docs = docs.annotate(_recebido=Coalesce(Subquery(totals, output_field=money), zero),
                             pendente=Greatest(F('valor') - F('_recebido'), zero, output_field=money))
        values = docs.aggregate(documentos=Count('pk'), valor_total=Sum('valor'), recebido=Sum('_recebido'),
            saldo=Sum('pendente'), vencido=Sum('pendente', filter=Q(dt_vencimento__lt=today)),
            vencem_em_10_dias=Sum('pendente', filter=Q(dt_vencimento__range=(today, today + timedelta(days=10)))))
        data['receitas'] = {key: value if key == 'documentos' else format(value or Decimal('0.00'), '.2f') for key, value in values.items()}
    if allowed['parceiros']:
        partners = Parceiro.objects.filter(empresa_id=empresa)
        if user.uf_id:
            partners = partners.filter(uf_id=user.uf_id)
        linked = customers.filter(parceiro__in=partners)
        counts = linked.order_by().values('parceiro_id').annotate(total=Count('pk')).filter(parceiro_id=OuterRef('pk')).values('total')
        top = partners.annotate(clientes=Coalesce(Subquery(counts), 0)).filter(clientes__gt=0).order_by('-clientes', 'instituicao', 'pk')[:10]
        total = data['clientes']['total']
        data['parceiros'] = {'results': ParceiroResumoSerializer(top, many=True, context={'total_clientes': total}).data,
            'total_clientes': total, 'sem_parceiro_autorizado': total - linked.count()}
    if allowed['alertas']:
        alerts = contracts.filter(ativo=True, exercicio=ano,
            dt_data_final__range=(today - timedelta(days=30), today + timedelta(days=30))).order_by('dt_data_final', 'pk')
        offset = (pagina_alertas - 1) * 10
        data['alertas'] = {'count': alerts.count(), 'page': pagina_alertas, 'page_size': 10,
            'inicio': (today - timedelta(days=30)).isoformat(), 'fim': (today + timedelta(days=30)).isoformat(),
            'results': AlertaSerializer(alerts.select_related('cliente')[offset:offset + 10], many=True).data}
    return data
