"""Tracks user's emotional state and provides adaptive context for LLM."""

from datetime import datetime


# Mood → Live2D expression mapping (model: mao_pro, exp_01~exp_08)
MOOD_EXPRESSIONS = {
    "happy":      "exp_02",   # 眯眼笑
    "excited":    "exp_04",   # 大眼+笑眼+星光特效
    "sad":        "exp_07",   # 大眼+抬眉+嘴角下垂
    "worried":    "exp_05",   # 眉角下压+嘴角下垂
    "angry":      "exp_08",   # 怒目+嘟嘴
    "tired":      "exp_03",   # 闭眼
    "bored":      "exp_03",   # 闭眼（同tired）
    "neutral":    "exp_01",   # 默认/全部归零
}

MOOD_ADAPTIVE_PROMPTS = {
    "happy":   "主人现在心情很好，请活泼回应，可以适当开玩笑～",
    "excited": "主人现在很兴奋，请一起开心，用热烈的语气～",
    "sad":     "主人现在情绪低落，请温柔安慰，给点鼓励和支持。",
    "worried": "主人现在有些焦虑，请安抚一下，给点信心。",
    "angry":   "主人现在有点生气，请不要抬杠，用软萌的方式降压。",
    "tired":   "主人现在很累，请温柔体贴，不要说太亢奋的话。",
    "bored":   "主人现在很无聊，请主动提议有趣的话题或活动～",
    "neutral": "请保持自然的聊天节奏。",
}


class MoodTracker:
    def __init__(self, max_history=10):
        self.history = []       # list of {mood, reason, timestamp}
        self.max_history = max_history
        self._current = "neutral"

    @property
    def current(self) -> str:
        return self._current

    def record(self, mood: str, reason: str = ""):
        mood = mood.strip().lower()
        if mood not in MOOD_ADAPTIVE_PROMPTS:
            mood = "neutral"

        self._current = mood
        self.history.append({
            "mood": mood,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        print(f"[Mood] 当前情绪: {mood}" + (f" (原因: {reason})" if reason else ""))

    def get_context(self) -> str:
        """Build an adaptive prompt snippet based on current and recent moods."""
        trend = self._trend()
        base = MOOD_ADAPTIVE_PROMPTS.get(self._current, MOOD_ADAPTIVE_PROMPTS["neutral"])

        if self._current != "neutral" and trend:
            return base + f" 注意：主人最近情绪趋势是{trend}。"

        return base

    def get_expression(self) -> str:
        return MOOD_EXPRESSIONS.get(self._current, "default")

    def _trend(self) -> str:
        if len(self.history) < 3:
            return ""

        recent = [e["mood"] for e in self.history[-3:]]
        positive = sum(1 for m in recent if m in ("happy", "excited"))
        negative = sum(1 for m in recent if m in ("sad", "worried", "angry", "tired"))

        if positive >= 2:
            return "持续开心"
        elif negative >= 2:
            return "持续低落"
        elif positive > negative:
            return "在好转"
        elif negative > positive:
            return "在变差"
        return ""
