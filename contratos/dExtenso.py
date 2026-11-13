# -*- coding: utf-8 -*-

class Extenso:

    ext = [{1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez",
            11: "onze", 12: "doze", 13: "treze", 14: "quatorze", 15: "quinze",
            16: "dezesseis", 17: "dezessete", 18: "dezoito", 19: "dezenove"},
           {2: "vinte", 3: "trinta", 4: "quarenta", 5: "cinquenta", 6: "sessenta", 7: "setenta", 8: "oitenta",
            9: "noventa"},
           {1: "cento", 2: "duzentos", 3: "trezentos", 4: "quatrocentos", 5: "quinhentos", 6: "seissentos",
            7: "setessentos", 8: "oitocentos", 9: "novecentos"}]

    und = ['', ' mil', (' milhão', ' milhões'), (' bilhão', ' bilhões'), (' trilhão', ' trilhões')]


    def cent(self, s, grand):
        s = '0' * (3 - len(s)) + s
        if s == '000':
            return ''
        if s == '100':
            return 'cem'
        ret = ''
        dez = s[1] + s[2]
        if s[0] != '0':
            ret += self.ext[2][int(s[0])]
            if dez != '00':
                ret += ' e '
            else:
                return ret + (
                            type(self.und[grand]) == type(()) and (int(s) > 1 and self.und[grand][1] or self.und[grand][0]) or self.und[grand])
        if int(dez) < 20:
            ret += self.ext[0][int(dez)]
        else:
            if s[1] != '0':
                ret += self.ext[1][int(s[1])]
                if s[2] != '0':
                    ret += ' e ' + self.ext[0][int(s[2])]

        return ret + (type(self.und[grand]) == type(()) and (int(s) > 1 and self.und[grand][1] or self.und[grand][0]) or self.und[grand])


    def extenso(self ,valor):
        ret = []
        grand = 0
        reais, centavos = valor.split('.')
        if (int(centavos) == 0):
            ret.append('zero centavos')
        elif (int(centavos) == 1):
            ret.append('um centavo')
        else:
            ret.append(self.cent(centavos, 0) + ' centavos')
        if (int(reais) == 0):
            ret.append('zero reais')
            ret.reverse()
            return ' e '.join([r for r in ret if r])
        elif (int(reais) == 1):
            ret.append('um real')
            ret.reverse()
            return ' e '.join([r for r in ret if r])
        while reais:
            s = reais[-3:]
            reais = reais[:-3]
            if (grand == 0):
                ret.append(self.cent(s, grand) + ' reais')
            else:
                ret.append(self.cent(s, grand))
            grand += 1
        ret.reverse()
        return ' e '.join([r for r in ret if r])

