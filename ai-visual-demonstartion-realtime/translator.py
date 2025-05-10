from googletrans import Translator

class TextTranslator:
    def __init__(self):
        self.translator = Translator()

    def translate(self, text, target_lang="es"):
        try:
            translated = self.translator.translate(text, dest=target_lang)
            return translated.text
        except Exception as e:
            return f"Translation error: {str(e)}"
