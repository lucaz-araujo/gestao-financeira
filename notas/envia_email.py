"""Compatibilidade com chamadas internas antigas; usa o EmailBackend configurado."""
from .mailing import send_note_email


class Email:
    def __init__(self, nota):
        self.nota = nota

    def Enviar(self):
        return send_note_email(self.nota)

    def EnviarNf(self):
        return send_note_email(self.nota, client_list=True)
