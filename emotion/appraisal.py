from .state import EmotionalState

APPRAISAL_RULES = [
    (["obrigado", "valeu", "grato", "gostei", "amei", "adorei"], 0.2, 0.1, "usuario agradeceu"),
    (["legal", "incrivel", "perfeito", "show", "otimo", "top", "massa"], 0.2, 0.15, "aprovacao positiva"),
    (["oi", "ola", "hey", "boa tarde", "boa noite", "bom dia"], 0.1, 0.1, "saudacao"),
    (["burra", "inutil", "idiota", "erro", "errou", "errada"], -0.3, 0.3, "critica negativa"),
    (["saudade", "falta", "precisei", "sozinha", "sozinho"], 0.1, -0.1, "expressao de carencia"),
    (["raiva", "odio", "tchau", "vai embora", "chata"], -0.15, 0.2, "tensao na conversa"),
    (["nao consigo", "dificil", "ajuda", "travei", "nao funciona"], -0.1, 0.1, "usuario em dificuldade"),
    (["consegui", "funcionou", "resolveu", "deu certo", "perfeito"], 0.25, 0.2, "conquista do usuario"),
    (["jogo", "projeto", "build", "godot", "rpg", "game", "designer"], 0.15, 0.1, "assunto preferido"),
    (["interessante", "curioso", "conta mais", "quero saber"], 0.1, 0.15, "curiosidade positiva"),
    (["triste", "cansado", "mal", "ruim", "pessimo"], -0.2, -0.1, "usuario com energia baixa"),
]

def appraise(message, state):
    msg_lower = message.lower()
    delta_v = 0.0
    delta_a = 0.0
    reasons = []
    for (keywords, dv, da, reason) in APPRAISAL_RULES:
        if any(k in msg_lower for k in keywords):
            delta_v += dv
            delta_a += da
            reasons.append(reason)
    delta_v = max(-0.4, min(0.4, delta_v))
    delta_a = max(-0.4, min(0.4, delta_a))
    reason_str = chr(59).join(reasons) if reasons else "evento neutro"
    return delta_v, delta_a, reason_str