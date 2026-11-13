import requests
from bs4 import BeautifulSoup
import re


def busca_cep(cep):
    # Getting data
    session = requests.session()
    data = {'relaxation': cep,
            'TipoCep': 'ALL',
            'semelhante': 'S',
            }
    r = session.post("http://www.buscacep.correios.com.br/sistemas/buscacep/resultadoBuscaCepEndereco.cfm", data, timeout=10)
    r.raise_for_status()

    content = r.content

    # Parsing
    soup = BeautifulSoup(content,"lxml")
    try:
        items = soup.find_all('table')[0].find_all('td')
    except:
        items=''
        return []

    # Parse list
    lista1=['', '', '', '']
    lista=[]
    grupo=len(items)-1
    gn=0
    if grupo > 3:
        for n in range(grupo):
            if gn == 0:
                lista1[gn] = re.sub(' - .*', '', items[n].string)
            else:
                lista1[gn] = items[n].string
            gn += 1

            if (gn > 3):
                gn = 0
                it={}
                it['logradouro'] = lista1[0]
                it['distrito_bairro'] = lista1[1]
                it['cidade'] = lista1[2]
                it['cep'] = lista1[3]
                lista.append(it)
    else:
        it = {}
        it['logradouro'] = re.sub(' - .*', '', items[0].string)
        it['distrito_bairro'] = items[1].string
        it['cidade'] = items[2].string
        it['cep'] = items[3].string
        lista.append(it)

    return lista
