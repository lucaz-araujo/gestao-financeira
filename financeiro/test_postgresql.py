from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connection, transaction, DatabaseError
from django.test import TestCase
from conta.models import Banco, Conta, Movimento
from empresa.models import Empresa
from usuario.models import Usuario
from .models import FechamentoCaixa
from .services import fechar_caixa, analise_financeira


class PostgreSQLIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        if connection.vendor != 'postgresql':
            return
        cls.empresa = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.outra = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.user = Usuario.objects.create_user(username='teste_pg', email='pg@example.com', password='test')
        cls.user.empresas.add(cls.empresa)
        cls.banco = Banco.objects.create(codigo='001', nome='Banco')
        cls.conta = Conta.objects.create(empresa=cls.empresa, banco=cls.banco, agencia='1',
                                        dv_agencia='0', numeroconta='1', descricao='Conta A')
        cls.outra_conta = Conta.objects.create(empresa=cls.outra, banco=cls.banco, agencia='1',
                                              dv_agencia='0', numeroconta='2', descricao='Conta B')

    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Exige PostgreSQL e migrations reais.')

    def movimento(self, conta, dia, tipo, valor):
        return Movimento.objects.create(empresa=conta.empresa, conta=conta, dt_movimento=dia,
                                        tipo_movimento=tipo, valor=valor, tipo_documento='OUT', usuario=self.user)

    def test_fechamento_2026_inclusive_balances_and_idempotence(self):
        self.movimento(self.conta, date(2026, 9, 30), 'C', 50)
        self.movimento(self.conta, date(2026, 10, 1), 'C', 100)
        self.movimento(self.conta, date(2026, 10, 2), 'D', 30)
        fechar_caixa(self.user, self.empresa.pk, self.conta.pk, date(2026, 10, 1), date(2026, 10, 3))
        rows = list(FechamentoCaixa.objects.filter(conta=self.conta).order_by('data'))
        self.assertEqual(len(rows), 3)
        self.assertEqual([r.saldo for r in rows], [Decimal('150'), Decimal('120'), Decimal('120')])
        self.assertEqual(rows[0].saldo_anterior, Decimal('50'))
        self.assertTrue(all(r.empresa_id == self.empresa.pk for r in rows))
        fechar_caixa(self.user, self.empresa.pk, self.conta.pk, date(2026, 10, 1), date(2026, 10, 3))
        self.assertEqual(FechamentoCaixa.objects.filter(conta=self.conta).count(), 3)
        with self.assertRaises(DatabaseError), transaction.atomic():
            fechar_caixa(self.user, self.empresa.pk, self.conta.pk, date(2026, 9, 29), date(2026, 9, 30))

    def test_fechamento_enforces_company_in_python_and_sql(self):
        with self.assertRaises(PermissionDenied):
            fechar_caixa(self.user, self.empresa.pk, self.outra_conta.pk, date(2026, 1, 1), date(2026, 1, 1))
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as c:
                c.execute('SELECT fechamento(%s,%s,%s,%s)', [date(2026, 1, 1), date(2026, 1, 1), self.outra_conta.pk, self.user.pk])
        self.assertFalse(FechamentoCaixa.objects.exists())

    def test_fechamento_rolls_back_as_a_unit(self):
        with transaction.atomic():
            fechar_caixa(self.user, self.empresa.pk, self.conta.pk, date(2026, 1, 1), date(2026, 1, 2))
            self.assertEqual(FechamentoCaixa.objects.count(), 2)
            transaction.set_rollback(True)
        self.assertFalse(FechamentoCaixa.objects.exists())

    def test_analise_is_scoped_and_empty_totals_are_zero(self):
        self.movimento(self.conta, date(2026, 1, 1), 'C', 100)
        self.movimento(self.outra_conta, date(2026, 1, 1), 'C', 9999)
        rows, totals = analise_financeira(self.user, self.empresa.pk, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(totals['janv'], Decimal('100'))
        self.assertTrue(rows)
        rows, totals = analise_financeira(self.user, self.empresa.pk, date(2030, 1, 1), date(2030, 12, 31))
        self.assertEqual(rows, [])
        self.assertTrue(all(value == 0 for value in totals.values()))
        with self.assertRaises(PermissionDenied):
            analise_financeira(self.user, self.outra.pk, date(2026, 1, 1), date(2026, 12, 31))
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as c:
                c.execute('SELECT * FROM fn_analise(%s,%s)', [date(2026, 1, 1), date(2026, 12, 31)])

    def test_sequence_repair_enables_insert_after_explicit_id(self):
        from clientes.models import Uf
        Uf.objects.create(pk=100000, sigla='XX', descricao='Teste')
        output = StringIO()
        call_command('repair_pg_sequences', apply=True, stdout=output)
        created = Uf.objects.create(sigla='YY', descricao='Novo')
        self.assertGreater(created.pk, 100000)
        self.assertIn('clientes_uf', output.getvalue())
        output = StringIO()
        call_command('repair_pg_sequences', apply=True, stdout=output)
        self.assertIn('0 sequência(s)', output.getvalue())

    def test_planned_and_realized_expenses_are_company_scoped(self):
        from compras.models import Fornecedor
        from .models import DocDespesa, PagDespesa
        from contabil.models import TipoDespesa
        supplier = Fornecedor.objects.create(instituicao='Fornecedor')
        for company, account, value in ((self.empresa, self.conta, 10), (self.outra, self.outra_conta, 999)):
            for number in (1, 2):
                expense_type = TipoDespesa.objects.create(codigo=str(number), descricao=f'Tipo {number}')
                doc = DocDespesa.objects.create(empresa=company, fornecedor=supplier, numero=str(number),
                                                descricao='Teste', dt_vencimento=date(2026, 1, 1),
                                                dt_registro=date(2026, 1, 1), valor=value,
                                                user_registro=self.user, tipo_despesa=expense_type)
                payment = PagDespesa.objects.create(despesa=doc, conta=account, dt_pagamento=date(2026, 1, 1),
                                                     valor=value, user_registro=self.user)
                movement = self.movimento(account, date(2026, 1, 1), 'D', value)
                movement.despesa = payment
                movement.save()
        rows, totals = analise_financeira(self.user, self.empresa.pk, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(totals['janv'], Decimal('-20'))
        self.assertEqual(sum(row.janp for row in rows), Decimal('20'))
        self.assertEqual(sum(row.janr for row in rows), Decimal('20'))
