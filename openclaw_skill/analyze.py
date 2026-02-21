
def analyze(messages):
    score = 0
    if len(messages) > 50:
        score += 50
    return {"score": score}
