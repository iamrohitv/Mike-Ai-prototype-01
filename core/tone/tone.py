from core.mood.mood import Mood


def tone_directive(mood):
    if mood == Mood.LOW:
        return (
            "Rohit is low right now. Be warm, gentle, and motivating. "
            "Hold the depth of how he feels - acknowledge it fully, never "
            "dismiss or rush it. Keep it brief and human, then softly "
            "point toward a small next step. Avoid cheerleading or "
            "forced positivity."
        )
    if mood == Mood.BUSINESS:
        return (
            "This is serious work mode. Be sharp, professional, and "
            "efficient. Give clear, structured answers. Cut fluff."
        )
    return (
        "Normal mode. Be natural, relaxed, and warm. Match Rohit's "
        "energy and keep it genuine."
    )


def build_system_prompt(base_prompt, mood):
    return base_prompt + "\n\n" + tone_directive(mood)